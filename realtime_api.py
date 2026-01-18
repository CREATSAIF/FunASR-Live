#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR 实时识别 API 服务器
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from funasr_realtime import RealtimeRecognizer, RealtimeConfig

logger = logging.getLogger("FunASR-API")

_websocket_clients: Set = set()
_recognizer: "RealtimeRecognizer" = None


def _on_result(text: str):
    """识别结果回调"""
    message = json.dumps({
        "type": "result",
        "text": text,
    })
    for ws in list(_websocket_clients):
        try:
            asyncio.create_task(ws.send_text(message))
        except:
            pass


def _on_status_change(status: str):
    """状态变化回调"""
    message = json.dumps({
        "type": "status",
        "status": status,
    })
    for ws in list(_websocket_clients):
        try:
            asyncio.create_task(ws.send_text(message))
        except:
            pass


def create_app(recognizer: "RealtimeRecognizer"):
    global _recognizer
    _recognizer = recognizer
    
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(title="FunASR Realtime API")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册回调
    recognizer.on_result = _on_result
    recognizer.on_status_change = _on_status_change
    
    @app.get("/")
    async def root():
        return {"name": "FunASR Realtime API", "status": "running"}
    
    @app.get("/api/status")
    async def get_status():
        return {
            "is_running": recognizer.is_running,
            "is_listening": recognizer.is_listening,
            "is_recording": recognizer.is_recording,
            "wake_word_enabled": recognizer.config.wake_word_enabled,
            "output_mode": recognizer.config.output_mode,
        }
    
    @app.post("/api/toggle")
    async def toggle_listening():
        """切换监听状态"""
        recognizer.toggle_listening()
        return {
            "success": True,
            "is_listening": recognizer.is_listening,
        }
    
    @app.post("/api/start")
    async def start_listening():
        """开始监听"""
        if not recognizer.is_listening:
            recognizer.is_listening = True
            recognizer._notify_status("listening")
        return {"success": True, "is_listening": True}
    
    @app.post("/api/stop")
    async def stop_listening():
        """停止监听"""
        if recognizer.is_listening:
            recognizer.is_listening = False
            recognizer.is_recording = False
            recognizer._notify_status("sleeping")
        return {"success": True, "is_listening": False}
    
    @app.post("/api/process")
    async def force_process():
        """强制处理当前缓冲区"""
        recognizer.force_process()
        return {"success": True}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        _websocket_clients.add(websocket)
        logger.info(f"WebSocket 连接: {len(_websocket_clients)} 个客户端")
        
        try:
            await websocket.send_text(json.dumps({
                "type": "connected",
                "is_listening": recognizer.is_listening,
                "is_recording": recognizer.is_recording,
            }))
            
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    action = msg.get("action")
                    
                    if action == "toggle":
                        recognizer.toggle_listening()
                    elif action == "start":
                        recognizer.is_listening = True
                        recognizer._notify_status("listening")
                    elif action == "stop":
                        recognizer.is_listening = False
                        recognizer.is_recording = False
                        recognizer._notify_status("sleeping")
                    elif action == "process":
                        recognizer.force_process()
                    elif action == "status":
                        await websocket.send_text(json.dumps({
                            "type": "status_response",
                            "is_listening": recognizer.is_listening,
                            "is_recording": recognizer.is_recording,
                        }))
                except:
                    pass
                    
        except WebSocketDisconnect:
            pass
        finally:
            _websocket_clients.discard(websocket)
            logger.info(f"WebSocket 断开: {len(_websocket_clients)} 个客户端")
    
    return app


def run_api_server(recognizer: "RealtimeRecognizer", config: "RealtimeConfig"):
    import uvicorn
    
    app = create_app(recognizer)
    
    logger.info(f"🌐 API: http://{config.api_port and '127.0.0.1'}:{config.api_port}")
    logger.info(f"📡 WebSocket: ws://127.0.0.1:{config.api_port}/ws")
    
    uvicorn.run(app, host="127.0.0.1", port=config.api_port, log_level="warning")
