#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR 实时连续语音识别
支持关键词唤醒、连续识别、实时输出

功能：
1. 关键词唤醒模式 - 说出唤醒词后开始识别
2. 连续识别模式 - 持续监听并实时输出
3. 静音检测 - 自动在说话停顿时输出结果
4. 实时输入 - 边说边输入到当前应用
"""

import logging
import os
import queue
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Callable

import numpy as np
import sounddevice as sd
import torch
import yaml

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FunASR-Realtime")


@dataclass
class RealtimeConfig:
    """实时识别配置"""
    # 模型配置
    model_name: str = "FunAudioLLM/Fun-ASR-Nano-2512"
    model_hub: str = "ms"
    
    # 音频配置
    sample_rate: int = 16000
    channels: int = 1
    audio_device: Optional[int] = None
    
    # 唤醒词配置
    wake_word_enabled: bool = True
    wake_words: List[str] = field(default_factory=lambda: ["小助手", "开始听写", "语音输入"])
    sleep_words: List[str] = field(default_factory=lambda: ["停止听写", "结束输入", "休息一下"])
    
    # 快捷键配置
    hotkey_toggle: str = "ctrl+alt+r"  # 切换监听状态
    hotkey_force: str = "ctrl+alt+f"   # 强制输出当前内容
    
    # 识别配置
    language: str = "中文"
    hotwords: List[str] = field(default_factory=list)
    
    # 静音检测配置
    silence_threshold: float = 0.01  # 静音阈值
    silence_duration: float = 0.8    # 静音持续时间（秒）触发输出
    max_record_duration: float = 30  # 最大录音时长（秒）
    min_record_duration: float = 0.5 # 最小录音时长（秒）
    
    # 输出配置
    output_mode: str = "clipboard"  # clipboard, type, both
    auto_punctuation: bool = True   # 自动添加标点
    
    # API 配置
    api_enabled: bool = True
    api_port: int = 8765
    
    @classmethod
    def from_yaml(cls, path: str) -> "RealtimeConfig":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return cls()
    
    def to_yaml(self, path: str):
        data = {
            'model_name': self.model_name,
            'model_hub': self.model_hub,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'audio_device': self.audio_device,
            'wake_word_enabled': self.wake_word_enabled,
            'wake_words': self.wake_words,
            'sleep_words': self.sleep_words,
            'hotkey_toggle': self.hotkey_toggle,
            'hotkey_force': self.hotkey_force,
            'language': self.language,
            'hotwords': self.hotwords,
            'silence_threshold': self.silence_threshold,
            'silence_duration': self.silence_duration,
            'max_record_duration': self.max_record_duration,
            'min_record_duration': self.min_record_duration,
            'output_mode': self.output_mode,
            'auto_punctuation': self.auto_punctuation,
            'api_enabled': self.api_enabled,
            'api_port': self.api_port,
        }
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


class HotkeyManager:
    """快捷键管理器"""
    
    def __init__(self):
        self.listener = None
        self.callbacks = {}
        self._current_keys = set()
        self._enabled = True
        
    def _parse_hotkey(self, hotkey_str: str) -> set:
        """解析快捷键字符串"""
        from pynput import keyboard
        
        keys = set()
        parts = hotkey_str.lower().split('+')
        
        key_map = {
            'ctrl': keyboard.Key.ctrl,
            'control': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt,
            'option': keyboard.Key.alt,
            'shift': keyboard.Key.shift,
            'cmd': keyboard.Key.cmd,
            'command': keyboard.Key.cmd,
            'escape': keyboard.Key.esc,
            'esc': keyboard.Key.esc,
            'space': keyboard.Key.space,
            'enter': keyboard.Key.enter,
            'f1': keyboard.Key.f1, 'f2': keyboard.Key.f2,
            'f3': keyboard.Key.f3, 'f4': keyboard.Key.f4,
            'f5': keyboard.Key.f5, 'f6': keyboard.Key.f6,
            'f7': keyboard.Key.f7, 'f8': keyboard.Key.f8,
            'f9': keyboard.Key.f9, 'f10': keyboard.Key.f10,
            'f11': keyboard.Key.f11, 'f12': keyboard.Key.f12,
        }
        
        for part in parts:
            part = part.strip()
            if part in key_map:
                keys.add(key_map[part])
            elif len(part) == 1:
                keys.add(keyboard.KeyCode.from_char(part))
        
        return keys
    
    def register(self, hotkey: str, callback):
        """注册快捷键"""
        self.callbacks[hotkey] = {
            'keys': self._parse_hotkey(hotkey),
            'callback': callback
        }
    
    def _on_press(self, key):
        if not self._enabled:
            return
        self._current_keys.add(key)
        
        for hotkey, data in self.callbacks.items():
            if data['keys'].issubset(self._current_keys):
                try:
                    data['callback']()
                except Exception as e:
                    logger.error(f"快捷键回调错误: {e}")
    
    def _on_release(self, key):
        try:
            self._current_keys.discard(key)
        except:
            pass
    
    def start(self):
        """启动监听"""
        from pynput import keyboard
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        logger.info("⌨️ 快捷键监听已启动")
    
    def stop(self):
        """停止监听"""
        if self.listener:
            self.listener.stop()
            self.listener = None


class ASREngine:
    """语音识别引擎"""
    
    def __init__(self, config: RealtimeConfig):
        self.config = config
        self.model = None
        self.device = None
        self._initialized = False
        
    def initialize(self):
        if self._initialized:
            return
            
        logger.info("正在初始化 FunASR 模型...")
        
        # 确定设备
        if torch.cuda.is_available():
            self.device = "cuda:0"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"
            
        logger.info(f"使用设备: {self.device}")
        
        from funasr import AutoModel
        
        self.model = AutoModel(
            model=self.config.model_name,
            trust_remote_code=True,
            remote_code=str(Path(__file__).parent / "model.py"),
            device=self.device,
            hub=self.config.model_hub,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            disable_update=True,
        )
        
        self._initialized = True
        logger.info("模型初始化完成！")
        
    def recognize(self, audio_data: np.ndarray) -> str:
        if not self._initialized:
            self.initialize()
            
        try:
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            if np.abs(audio_data).max() > 1.0:
                audio_data = audio_data / 32768.0
                
            audio_tensor = torch.from_numpy(audio_data)
            
            result = self.model.generate(
                input=[audio_tensor],
                cache={},
                batch_size=1,
                hotwords=self.config.hotwords,
                language=self.config.language,
                itn=True,
            )
            
            if result and len(result) > 0:
                text = result[0].get("text", "")
                return text.strip()
            return ""
            
        except Exception as e:
            logger.error(f"识别错误: {e}")
            return ""


class RealtimeRecognizer:
    """实时连续语音识别器"""
    
    def __init__(self, config: RealtimeConfig):
        self.config = config
        self.asr_engine = ASREngine(config)
        self.hotkey_manager = HotkeyManager()
        
        # 状态
        self.is_running = False
        self.is_listening = False  # 是否在监听（唤醒后）
        self.is_recording = False  # 是否在录音（检测到语音）
        
        # 音频缓冲
        self.audio_buffer = deque(maxlen=int(config.sample_rate * config.max_record_duration))
        self.current_segment = []  # 当前语音段
        
        # 静音检测
        self.silence_frames = 0
        self.voice_frames = 0
        
        # 回调
        self.on_result: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None
        
        # 输出回调 - 用于在主线程中执行输出操作
        # 这是为了解决 macOS 上 TSMGetInputSourceProperty 必须在主线程调用的问题
        self.on_output: Optional[Callable[[str], None]] = None
        
        # 线程
        self._stream = None
        self._process_thread = None
        self._stop_event = threading.Event()
        
        # 待输出队列 - 用于跨线程传递输出文本
        self._output_queue = queue.Queue()
        
        # 输入设备
        self._input_device = self._get_input_device()
        
        # 注册快捷键
        self._setup_hotkeys()
    
    def _setup_hotkeys(self):
        """设置快捷键"""
        # 切换监听状态
        self.hotkey_manager.register(
            self.config.hotkey_toggle,
            self._on_hotkey_toggle
        )
        # 强制输出当前内容
        self.hotkey_manager.register(
            self.config.hotkey_force,
            self._on_hotkey_force
        )
    
    def _on_hotkey_toggle(self):
        """快捷键：切换监听状态"""
        self.toggle_listening()
    
    def _on_hotkey_force(self):
        """快捷键：强制输出当前内容"""
        if self.is_listening and self.current_segment:
            logger.info("⚡ 强制输出当前内容")
            self.force_process()
        
    def _get_input_device(self) -> Optional[int]:
        """获取输入设备"""
        if self.config.audio_device is not None:
            try:
                info = sd.query_devices(self.config.audio_device)
                if info['max_input_channels'] > 0:
                    logger.info(f"使用音频设备: [{self.config.audio_device}] {info['name']}")
                    return self.config.audio_device
            except:
                pass
        
        # 查找可用的输入设备
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    logger.info(f"使用音频设备: [{i}] {dev['name']}")
                    return i
        except:
            pass
        
        logger.error("未找到可用的音频输入设备！")
        return None
    
    def _audio_callback(self, indata, frames, time_info, status):
        """音频回调"""
        if status:
            logger.warning(f"音频状态: {status}")
        
        audio = indata.flatten()
        volume = np.abs(audio).mean()
        
        # 添加到缓冲区
        self.audio_buffer.extend(audio)
        
        # 如果启用唤醒词且未激活，只监听唤醒词
        if self.config.wake_word_enabled and not self.is_listening:
            # 检测是否有语音（用于唤醒词检测）
            if volume > self.config.silence_threshold:
                self.current_segment.extend(audio)
                self.voice_frames += 1
                self.silence_frames = 0
            else:
                self.silence_frames += 1
                if self.silence_frames > int(self.config.silence_duration * self.config.sample_rate / len(audio)):
                    if len(self.current_segment) > self.config.sample_rate * self.config.min_record_duration:
                        # 检查唤醒词
                        self._check_wake_word()
                    self.current_segment = []
                    self.voice_frames = 0
            return
        
        # 正在监听状态
        if self.is_listening:
            if volume > self.config.silence_threshold:
                # 检测到语音
                if not self.is_recording:
                    self.is_recording = True
                    self._notify_status("recording")
                    logger.info("🎤 检测到语音，开始录音...")
                
                self.current_segment.extend(audio)
                self.voice_frames += 1
                self.silence_frames = 0
            else:
                # 静音
                self.silence_frames += 1
                
                if self.is_recording:
                    self.current_segment.extend(audio)  # 继续录制静音部分
                    
                    # 检查是否静音足够长
                    silence_samples = int(self.config.silence_duration * self.config.sample_rate / len(audio))
                    if self.silence_frames > silence_samples:
                        # 静音足够长，处理当前段
                        if len(self.current_segment) > self.config.sample_rate * self.config.min_record_duration:
                            self._process_segment()
                        self.current_segment = []
                        self.voice_frames = 0
                        self.is_recording = False
                        self._notify_status("listening")
    
    def _check_wake_word(self):
        """检查唤醒词"""
        if not self.current_segment:
            return
        
        audio_data = np.array(self.current_segment, dtype=np.float32)
        text = self.asr_engine.recognize(audio_data)
        
        if text:
            logger.info(f"检测到语音: {text}")
            
            # 检查是否包含唤醒词
            for wake_word in self.config.wake_words:
                if wake_word in text:
                    logger.info(f"🔔 唤醒词触发: {wake_word}")
                    self.is_listening = True
                    self._notify_status("listening")
                    return
    
    def _process_segment(self):
        """处理语音段"""
        if not self.current_segment:
            return
        
        audio_data = np.array(self.current_segment, dtype=np.float32)
        
        # 在后台线程中识别
        def recognize():
            text = self.asr_engine.recognize(audio_data)
            
            if text:
                # 检查是否是休眠词
                for sleep_word in self.config.sleep_words:
                    if sleep_word in text:
                        logger.info(f"💤 休眠词触发: {sleep_word}")
                        self.is_listening = False
                        self._notify_status("sleeping")
                        return
                
                logger.info(f"✅ 识别结果: {text}")
                self._output_text(text)
                
                if self.on_result:
                    self.on_result(text)
            else:
                logger.info("⚠️ 未识别到有效内容")
        
        threading.Thread(target=recognize, daemon=True).start()
    
    def _output_text(self, text: str):
        """输出文本 - 将文本放入队列，由主线程处理"""
        if not text:
            return
        
        # 如果设置了输出回调（GUI 模式），使用回调
        if self.on_output:
            self.on_output(text)
            return
        
        # 否则放入队列，由 process_pending_outputs 处理
        self._output_queue.put(text)
    
    def process_pending_outputs(self):
        """处理待输出队列 - 必须在主线程中调用"""
        while not self._output_queue.empty():
            try:
                text = self._output_queue.get_nowait()
                self._do_output(text)
            except queue.Empty:
                break
    
    def _do_output(self, text: str):
        """实际执行输出操作 - 必须在主线程中调用"""
        if not text:
            return
        
        mode = self.config.output_mode
        
        if mode in ("clipboard", "both"):
            self._copy_to_clipboard(text)
        
        if mode in ("type", "both"):
            self._type_text(text)
    
    def _copy_to_clipboard(self, text: str):
        """复制到剪贴板"""
        try:
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                env={'LANG': 'en_US.UTF-8'}
            )
            process.communicate(text.encode('utf-8'))
            logger.info(f"📋 已复制: {text[:30]}...")
        except Exception as e:
            logger.error(f"复制失败: {e}")
    
    def _type_text(self, text: str):
        """模拟输入"""
        try:
            # 先复制到剪贴板
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                env={'LANG': 'en_US.UTF-8'}
            )
            process.communicate(text.encode('utf-8'))
            
            time.sleep(0.05)
            
            # 模拟 Cmd+V
            script = '''
            tell application "System Events"
                keystroke "v" using command down
            end tell
            '''
            subprocess.run(['osascript', '-e', script], check=True, 
                         capture_output=True, timeout=5)
            logger.info(f"⌨️ 已输入: {text[:30]}...")
        except Exception as e:
            logger.error(f"输入失败: {e}")
    
    def _notify_status(self, status: str):
        """通知状态变化"""
        status_map = {
            "sleeping": "💤 休眠中（等待唤醒词）",
            "listening": "👂 监听中（等待语音）",
            "recording": "🎤 录音中...",
        }
        logger.info(status_map.get(status, status))
        
        if self.on_status_change:
            self.on_status_change(status)
    
    def start(self, enable_hotkeys: bool = True):
        """启动实时识别"""
        if self.is_running:
            return
        
        if self._input_device is None:
            logger.error("无法启动：没有可用的音频输入设备")
            return
        
        logger.info("=" * 50)
        logger.info("🚀 FunASR 实时识别启动")
        logger.info("=" * 50)
        
        # 初始化模型
        self.asr_engine.initialize()
        
        self.is_running = True
        self._stop_event.clear()
        
        # 启动快捷键监听（如果启用）
        if enable_hotkeys and self.config.hotkey_toggle and self.config.hotkey_force:
            self.hotkey_manager.start()
            logger.info(f"快捷键: [{self.config.hotkey_toggle}] 切换监听, [{self.config.hotkey_force}] 强制输出")
        else:
            logger.info("快捷键已禁用")
        
        # 初始状态
        if self.config.wake_word_enabled:
            self.is_listening = False
            self._notify_status("sleeping")
            logger.info(f"唤醒词: {', '.join(self.config.wake_words)}")
            logger.info(f"休眠词: {', '.join(self.config.sleep_words)}")
        else:
            self.is_listening = True
            self._notify_status("listening")
        
        logger.info(f"输出模式: {self.config.output_mode}")
        logger.info("=" * 50)
        
        # 启动音频流
        self._stream = sd.InputStream(
            device=self._input_device,
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype='float32',
            callback=self._audio_callback,
            blocksize=int(self.config.sample_rate * 0.1)  # 100ms 块
        )
        self._stream.start()
    
    def start_without_hotkeys(self):
        """启动实时识别（不启动快捷键监听）- 用于 GUI 模式"""
        self.start(enable_hotkeys=False)
    
    def stop(self):
        """停止实时识别"""
        if not self.is_running:
            return
        
        logger.info("正在停止...")
        
        self.is_running = False
        self.is_listening = False
        self.is_recording = False
        self._stop_event.set()
        
        # 停止快捷键监听
        self.hotkey_manager.stop()
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        logger.info("已停止")
    
    def toggle_listening(self):
        """切换监听状态"""
        if self.is_listening:
            self.is_listening = False
            self.is_recording = False
            self._notify_status("sleeping")
        else:
            self.is_listening = True
            self._notify_status("listening")
    
    def force_process(self):
        """强制处理当前缓冲区"""
        if self.current_segment:
            self._process_segment()
            self.current_segment = []
            self.is_recording = False


def kill_existing_processes(port: int):
    """终止已存在的进程"""
    try:
        # 终止 funasr 相关进程
        subprocess.run(['pkill', '-f', 'funasr_realtime.py'], capture_output=True)
        subprocess.run(['pkill', '-f', 'funasr_live.py'], capture_output=True)
        
        # 终止占用端口的进程
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        if result.stdout.strip():
            for pid in result.stdout.strip().split('\n'):
                if pid:
                    subprocess.run(['kill', '-9', pid], capture_output=True)
        
        time.sleep(0.5)
    except:
        pass


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='FunASR 实时连续语音识别')
    parser.add_argument('-c', '--config', default='config_realtime.yaml', help='配置文件')
    parser.add_argument('--init-config', action='store_true', help='生成默认配置')
    parser.add_argument('--no-wake', action='store_true', help='禁用唤醒词（直接开始监听）')
    parser.add_argument('--no-api', action='store_true', help='禁用 API')
    
    args = parser.parse_args()
    
    config_path = Path(__file__).parent / args.config
    
    if args.init_config:
        config = RealtimeConfig()
        config.to_yaml(str(config_path))
        logger.info(f"已生成配置文件: {config_path}")
        return
    
    # 加载配置
    if config_path.exists():
        config = RealtimeConfig.from_yaml(str(config_path))
        logger.info(f"已加载配置: {config_path}")
    else:
        config = RealtimeConfig()
        config.to_yaml(str(config_path))
        logger.info(f"已生成默认配置: {config_path}")
    
    if args.no_wake:
        config.wake_word_enabled = False
    
    # 终止已存在的进程
    kill_existing_processes(config.api_port)
    
    # 创建识别器
    recognizer = RealtimeRecognizer(config)
    
    # 启动 API 服务器（如果启用）
    if config.api_enabled and not args.no_api:
        from realtime_api import run_api_server
        api_thread = threading.Thread(
            target=run_api_server,
            args=(recognizer, config),
            daemon=True
        )
        api_thread.start()
    
    # 启动识别
    recognizer.start()
    
    try:
        logger.info("\n按 Ctrl+C 退出\n")
        while recognizer.is_running:
            # 在主线程中处理待输出队列
            recognizer.process_pending_outputs()
            time.sleep(0.05)
    except KeyboardInterrupt:
        logger.info("\n收到退出信号...")
    finally:
        recognizer.stop()


if __name__ == "__main__":
    main()
