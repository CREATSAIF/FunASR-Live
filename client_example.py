#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR Live 客户端示例
演示如何通过 API 调用语音识别服务
"""

import asyncio
import json
import sys
import time

import requests

# API 基础地址
API_BASE = "http://127.0.0.1:8765"
WS_URL = "ws://127.0.0.1:8765/ws"


def get_status():
    """获取服务状态"""
    response = requests.get(f"{API_BASE}/api/status")
    return response.json()


def get_result():
    """获取最新识别结果"""
    response = requests.get(f"{API_BASE}/api/result")
    return response.json()


def start_recording():
    """开始录音"""
    response = requests.post(f"{API_BASE}/api/control/start")
    return response.json()


def stop_recording():
    """停止录音并获取识别结果"""
    response = requests.post(f"{API_BASE}/api/control/stop")
    return response.json()


def cancel_recording():
    """取消录音"""
    response = requests.post(f"{API_BASE}/api/control/cancel")
    return response.json()


def recognize_file(file_path: str):
    """识别音频文件"""
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{API_BASE}/api/recognize",
            files={'file': f}
        )
    return response.json()


async def websocket_client():
    """WebSocket 客户端示例"""
    try:
        import websockets
    except ImportError:
        print("请安装 websockets: pip install websockets")
        return
    
    print(f"连接到 {WS_URL}...")
    
    async with websockets.connect(WS_URL) as ws:
        print("已连接！等待识别结果...")
        print("(在另一个终端中使用快捷键或 API 控制录音)")
        print("-" * 40)
        
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                
                if data["type"] == "connected":
                    print(f"[连接成功] 当前状态: 录音中={data['is_recording']}")
                    if data.get("latest_result"):
                        print(f"[最新结果] {data['latest_result']}")
                        
                elif data["type"] == "recording_started":
                    print("[状态] 🎤 开始录音...")
                    
                elif data["type"] == "recording_stopped":
                    print("[状态] ⏹️ 停止录音，正在识别...")
                    
                elif data["type"] == "recording_cancelled":
                    print("[状态] ❌ 录音已取消")
                    
                elif data["type"] == "result":
                    print(f"[识别结果] {data['text']}")
                    
                elif data["type"] == "status":
                    print(f"[状态] 录音中={data['is_recording']}")
                    
            except Exception as e:
                print(f"错误: {e}")
                break


async def websocket_control_demo():
    """WebSocket 控制示例"""
    try:
        import websockets
    except ImportError:
        print("请安装 websockets: pip install websockets")
        return
    
    async with websockets.connect(WS_URL) as ws:
        # 等待连接确认
        msg = await ws.recv()
        print(f"连接成功: {msg}")
        
        # 开始录音
        print("\n开始录音...")
        await ws.send(json.dumps({"action": "start"}))
        msg = await ws.recv()
        print(f"响应: {msg}")
        
        # 录音 3 秒
        print("录音中... (3秒)")
        await asyncio.sleep(3)
        
        # 停止录音
        print("\n停止录音...")
        await ws.send(json.dumps({"action": "stop"}))
        
        # 等待识别结果
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"响应: {msg}")
            
            if data["type"] == "result":
                print(f"\n✅ 识别结果: {data['text']}")
                break


def interactive_demo():
    """交互式演示"""
    print("=" * 50)
    print("FunASR Live 客户端演示")
    print("=" * 50)
    print()
    print("命令:")
    print("  s - 开始录音")
    print("  e - 停止录音并识别")
    print("  c - 取消录音")
    print("  r - 获取最新结果")
    print("  t - 获取状态")
    print("  q - 退出")
    print()
    
    while True:
        try:
            cmd = input("请输入命令: ").strip().lower()
            
            if cmd == 's':
                result = start_recording()
                print(f"结果: {result}")
                
            elif cmd == 'e':
                print("正在停止录音并识别...")
                result = stop_recording()
                if result.get("success") and result.get("text"):
                    print(f"✅ 识别结果: {result['text']}")
                else:
                    print(f"结果: {result}")
                    
            elif cmd == 'c':
                result = cancel_recording()
                print(f"结果: {result}")
                
            elif cmd == 'r':
                result = get_result()
                print(f"最新结果: {result.get('text', '(无)')}")
                
            elif cmd == 't':
                result = get_status()
                print(f"状态: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
            elif cmd == 'q':
                print("退出")
                break
                
            else:
                print("未知命令")
                
        except KeyboardInterrupt:
            print("\n退出")
            break
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到服务器，请确保 FunASR Live 正在运行")
        except Exception as e:
            print(f"错误: {e}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python client_example.py <命令>")
        print()
        print("命令:")
        print("  status     - 获取服务状态")
        print("  result     - 获取最新识别结果")
        print("  start      - 开始录音")
        print("  stop       - 停止录音并识别")
        print("  cancel     - 取消录音")
        print("  file <路径> - 识别音频文件")
        print("  ws         - WebSocket 监听模式")
        print("  ws-demo    - WebSocket 控制演示")
        print("  interactive - 交互式演示")
        return
    
    cmd = sys.argv[1]
    
    try:
        if cmd == "status":
            result = get_status()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif cmd == "result":
            result = get_result()
            print(f"识别结果: {result.get('text', '(无)')}")
            print(f"录音状态: {'录音中' if result.get('is_recording') else '空闲'}")
            
        elif cmd == "start":
            result = start_recording()
            print(result.get("message", result))
            
        elif cmd == "stop":
            result = stop_recording()
            if result.get("success") and result.get("text"):
                print(f"识别结果: {result['text']}")
            else:
                print(result.get("message", result))
                
        elif cmd == "cancel":
            result = cancel_recording()
            print(result.get("message", result))
            
        elif cmd == "file":
            if len(sys.argv) < 3:
                print("请指定音频文件路径")
                return
            result = recognize_file(sys.argv[2])
            if result.get("success"):
                print(f"识别结果: {result['text']}")
            else:
                print(f"错误: {result}")
                
        elif cmd == "ws":
            asyncio.run(websocket_client())
            
        elif cmd == "ws-demo":
            asyncio.run(websocket_control_demo())
            
        elif cmd == "interactive":
            interactive_demo()
            
        else:
            print(f"未知命令: {cmd}")
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        print("请确保 FunASR Live 正在运行: python funasr_live.py")


if __name__ == "__main__":
    main()
