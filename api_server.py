#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR Live API 服务器
提供 HTTP REST API 和 WebSocket 接口供外部工具调用

API 端点:
- GET  /api/status          - 获取服务状态
- GET  /api/result          - 获取最新识别结果
- POST /api/recognize       - 上传音频文件进行识别
- POST /api/control/start   - 开始录音
- POST /api/control/stop    - 停止录音并识别
- POST /api/control/cancel  - 取消录音
- WS   /ws                  - WebSocket 实时推送识别结果
"""

import asyncio
import base64
import json
import logging
import os
import tempfile
import threading
from typing import TYPE_CHECKING, Set

import numpy as np

if TYPE_CHECKING:
    from funasr_live import FunASRLive, Config

logger = logging.getLogger("FunASR-API")

# 全局变量存储 WebSocket 连接
_websocket_clients: Set = set()
_app_instance: "FunASRLive" = None


def _notify_websocket_clients(text: str):
    """通知所有 WebSocket 客户端"""
    if not _websocket_clients:
        return
        
    message = json.dumps({
        "type": "result",
        "text": text,
        "timestamp": __import__('time').time()
    })
    
    # 在事件循环中发送消息
    for ws in list(_websocket_clients):
        try:
            asyncio.create_task(ws.send_text(message))
        except Exception as e:
            logger.error(f"WebSocket 发送失败: {e}")


def create_app(funasr_live: "FunASRLive"):
    """创建 FastAPI 应用"""
    global _app_instance
    _app_instance = funasr_live
    
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    
    app = FastAPI(
        title="FunASR Live API",
        description="Mac MPS 实时语音识别服务 API",
        version="1.0.0"
    )
    
    # 添加 CORS 支持
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册结果回调
    funasr_live.register_result_callback(_notify_websocket_clients)
    
    @app.get("/")
    async def root():
        """根路径"""
        return {
            "name": "FunASR Live API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "status": "/api/status",
                "result": "/api/result",
                "recognize": "/api/recognize",
                "control": {
                    "start": "/api/control/start",
                    "stop": "/api/control/stop",
                    "cancel": "/api/control/cancel"
                },
                "websocket": "/ws"
            }
        }
    
    @app.get("/api/status")
    async def get_status():
        """获取服务状态"""
        return {
            "status": "running",
            "is_recording": funasr_live.recorder.is_recording,
            "device": funasr_live.asr_engine.device,
            "config": {
                "language": funasr_live.config.language,
                "output_mode": funasr_live.config.output_mode,
                "hotkey_start_stop": funasr_live.config.hotkey_start_stop,
                "hotkey_cancel": funasr_live.config.hotkey_cancel,
            },
            "websocket_clients": len(_websocket_clients)
        }
    
    @app.get("/api/result")
    async def get_result():
        """获取最新识别结果"""
        return {
            "text": funasr_live.get_latest_result(),
            "is_recording": funasr_live.recorder.is_recording
        }
    
    @app.post("/api/recognize")
    async def recognize_audio(
        file: UploadFile = File(None),
        audio_base64: str = None
    ):
        """
        上传音频文件进行识别
        
        支持两种方式:
        1. 上传音频文件 (multipart/form-data)
        2. 发送 base64 编码的音频数据 (application/json)
        """
        try:
            audio_data = None
            
            if file:
                # 从上传的文件读取
                content = await file.read()
                
                # 保存到临时文件
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                try:
                    # 使用 soundfile 或 librosa 读取音频
                    import soundfile as sf
                    audio_data, sr = sf.read(tmp_path)
                    
                    # 如果采样率不是 16000，需要重采样
                    if sr != 16000:
                        import librosa
                        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
                finally:
                    os.unlink(tmp_path)
                    
            elif audio_base64:
                # 从 base64 解码
                audio_bytes = base64.b64decode(audio_base64)
                audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
            else:
                raise HTTPException(status_code=400, detail="请提供音频文件或 base64 编码的音频数据")
            
            # 执行识别
            text = funasr_live.asr_engine.recognize(audio_data)
            
            return {
                "success": True,
                "text": text
            }
            
        except Exception as e:
            logger.error(f"识别错误: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/control/start")
    async def control_start():
        """开始录音"""
        if funasr_live.recorder.is_recording:
            return {"success": False, "message": "已经在录音中"}
            
        funasr_live.recorder.start_recording()
        
        # 通知 WebSocket 客户端
        message = json.dumps({"type": "recording_started"})
        for ws in list(_websocket_clients):
            try:
                await ws.send_text(message)
            except:
                pass
                
        return {"success": True, "message": "开始录音"}
    
    @app.post("/api/control/stop")
    async def control_stop():
        """停止录音并识别"""
        if not funasr_live.recorder.is_recording:
            return {"success": False, "message": "当前没有在录音"}
            
        audio_data = funasr_live.recorder.stop_recording()
        
        # 通知 WebSocket 客户端
        message = json.dumps({"type": "recording_stopped"})
        for ws in list(_websocket_clients):
            try:
                await ws.send_text(message)
            except:
                pass
        
        if len(audio_data) > 0:
            # 执行识别
            text = funasr_live.asr_engine.recognize(audio_data)
            
            if text:
                # 输出结果
                funasr_live.output_handler.output(text)
                
                # 更新最新结果
                with funasr_live._result_lock:
                    funasr_live._latest_result = text
                    
                # 通知回调
                _notify_websocket_clients(text)
                
                return {"success": True, "text": text}
            else:
                return {"success": True, "text": "", "message": "未识别到有效内容"}
        else:
            return {"success": False, "message": "没有录制到音频数据"}
    
    @app.post("/api/control/cancel")
    async def control_cancel():
        """取消录音"""
        if not funasr_live.recorder.is_recording:
            return {"success": False, "message": "当前没有在录音"}
            
        funasr_live.recorder.cancel_recording()
        
        # 通知 WebSocket 客户端
        message = json.dumps({"type": "recording_cancelled"})
        for ws in list(_websocket_clients):
            try:
                await ws.send_text(message)
            except:
                pass
                
        return {"success": True, "message": "录音已取消"}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """
        WebSocket 端点
        
        客户端可以通过 WebSocket 实时接收识别结果
        
        消息格式:
        - 服务端发送:
          - {"type": "result", "text": "识别结果", "timestamp": 1234567890.123}
          - {"type": "recording_started"}
          - {"type": "recording_stopped"}
          - {"type": "recording_cancelled"}
          - {"type": "status", "is_recording": true/false}
        
        - 客户端可发送:
          - {"action": "start"}   - 开始录音
          - {"action": "stop"}    - 停止录音
          - {"action": "cancel"}  - 取消录音
          - {"action": "status"}  - 获取状态
        """
        await websocket.accept()
        _websocket_clients.add(websocket)
        logger.info(f"WebSocket 客户端连接，当前连接数: {len(_websocket_clients)}")
        
        try:
            # 发送初始状态
            await websocket.send_text(json.dumps({
                "type": "connected",
                "is_recording": funasr_live.recorder.is_recording,
                "latest_result": funasr_live.get_latest_result()
            }))
            
            while True:
                # 接收客户端消息
                data = await websocket.receive_text()
                
                try:
                    msg = json.loads(data)
                    action = msg.get("action")
                    
                    if action == "start":
                        if not funasr_live.recorder.is_recording:
                            funasr_live.recorder.start_recording()
                            await websocket.send_text(json.dumps({"type": "recording_started"}))
                            
                    elif action == "stop":
                        if funasr_live.recorder.is_recording:
                            audio_data = funasr_live.recorder.stop_recording()
                            await websocket.send_text(json.dumps({"type": "recording_stopped"}))
                            
                            if len(audio_data) > 0:
                                # 在后台线程中执行识别
                                def recognize():
                                    text = funasr_live.asr_engine.recognize(audio_data)
                                    if text:
                                        funasr_live.output_handler.output(text)
                                        with funasr_live._result_lock:
                                            funasr_live._latest_result = text
                                        _notify_websocket_clients(text)
                                        
                                threading.Thread(target=recognize).start()
                                
                    elif action == "cancel":
                        if funasr_live.recorder.is_recording:
                            funasr_live.recorder.cancel_recording()
                            await websocket.send_text(json.dumps({"type": "recording_cancelled"}))
                            
                    elif action == "status":
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "is_recording": funasr_live.recorder.is_recording,
                            "latest_result": funasr_live.get_latest_result()
                        }))
                        
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "无效的 JSON 格式"
                    }))
                    
        except WebSocketDisconnect:
            pass
        finally:
            _websocket_clients.discard(websocket)
            logger.info(f"WebSocket 客户端断开，当前连接数: {len(_websocket_clients)}")
    
    return app


def run_api_server(funasr_live: "FunASRLive", config: "Config"):
    """运行 API 服务器"""
    import uvicorn
    
    app = create_app(funasr_live)
    
    logger.info(f"🌐 API 服务器启动: http://{config.api_host}:{config.api_port}")
    logger.info(f"📡 WebSocket 地址: ws://{config.api_host}:{config.api_port}/ws")
    
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        log_level="warning"
    )


# 独立运行测试
if __name__ == "__main__":
    print("API 服务器模块 - 请通过 funasr_live.py 启动")
