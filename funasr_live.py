#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR Live - Mac MPS 实时语音识别工具
支持快捷键触发录音、实时识别、剪贴板输出、键盘模拟输入
提供 WebSocket/HTTP API 供外部工具调用

作者: FunASR Live Tool
版本: 1.0.0
"""

import asyncio
import logging
import os
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

import numpy as np
import sounddevice as sd
import torch
import yaml
from pynput import keyboard

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FunASR-Live")


class OutputMode(Enum):
    """输出模式枚举"""
    CLIPBOARD = "clipboard"      # 复制到剪贴板
    TYPE = "type"                # 模拟键盘输入
    BOTH = "both"                # 两者都执行
    NONE = "none"                # 仅通过 API 输出


@dataclass
class Config:
    """配置类"""
    # 模型配置
    model_name: str = "FunAudioLLM/Fun-ASR-Nano-2512"
    model_hub: str = "ms"  # ms: ModelScope, hf: HuggingFace
    use_vad: bool = True
    vad_model: str = "fsmn-vad"
    vad_max_segment_time: int = 30000
    
    # 设备配置
    device: str = "auto"  # auto, mps, cuda, cpu
    dtype: str = "fp16"   # fp16, bf16, fp32
    
    # 音频配置
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration: float = 0.5  # 每个音频块的时长（秒）
    audio_device: Optional[int] = None  # 音频输入设备索引
    
    # 快捷键配置
    hotkey_start_stop: str = "ctrl+alt+r"  # 开始/停止录音
    hotkey_cancel: str = "escape"           # 取消当前录音
    
    # 输出配置
    output_mode: str = "clipboard"  # clipboard, type, both, none
    type_delay: float = 0.01        # 模拟输入时每个字符的延迟
    
    # 识别配置
    language: str = "中文"  # 中文、英文、日文
    itn: bool = True        # 是否进行文本规整（逆文本正则化）
    hotwords: List[str] = field(default_factory=list)  # 热词列表
    
    # API 配置
    api_enabled: bool = True
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """从 YAML 文件加载配置"""
        if not os.path.exists(path):
            logger.warning(f"配置文件不存在: {path}，使用默认配置")
            return cls()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            logger.info(f"已加载配置文件: {path}")
            # 只保留 Config 类有的属性
            valid_data = {k: v for k, v in data.items() if hasattr(cls, k)}
            return cls(**valid_data)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            return cls()
    
    def to_yaml(self, path: str):
        """保存配置到 YAML 文件"""
        data = {
            'model_name': self.model_name,
            'model_hub': self.model_hub,
            'use_vad': self.use_vad,
            'vad_model': self.vad_model,
            'vad_max_segment_time': self.vad_max_segment_time,
            'device': self.device,
            'dtype': self.dtype,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'chunk_duration': self.chunk_duration,
            'hotkey_start_stop': self.hotkey_start_stop,
            'hotkey_cancel': self.hotkey_cancel,
            'output_mode': self.output_mode,
            'type_delay': self.type_delay,
            'language': self.language,
            'itn': self.itn,
            'hotwords': self.hotwords,
            'api_enabled': self.api_enabled,
            'api_host': self.api_host,
            'api_port': self.api_port,
        }
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


class ASREngine:
    """语音识别引擎"""
    
    def __init__(self, config: Config):
        self.config = config
        self.model = None
        self.device = None
        self._initialized = False
        
    def initialize(self):
        """初始化模型"""
        if self._initialized:
            return
            
        logger.info("正在初始化 FunASR 模型...")
        
        # 确定设备
        if self.config.device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda:0"
            elif torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = self.config.device
            
        logger.info(f"使用设备: {self.device}")
        
        # 加载模型
        from funasr import AutoModel
        
        model_kwargs = {
            "model": self.config.model_name,
            "trust_remote_code": True,
            "remote_code": str(Path(__file__).parent / "model.py"),
            "device": self.device,
            "hub": self.config.model_hub,
        }
        
        # 添加 VAD 配置
        if self.config.use_vad:
            model_kwargs["vad_model"] = self.config.vad_model
            model_kwargs["vad_kwargs"] = {
                "max_single_segment_time": self.config.vad_max_segment_time
            }
        
        self.model = AutoModel(**model_kwargs)
        self._initialized = True
        logger.info("模型初始化完成！")
        
    def recognize(self, audio_data: np.ndarray) -> str:
        """
        识别音频数据
        
        Args:
            audio_data: numpy 数组，采样率应为 16000Hz
            
        Returns:
            识别结果文本
        """
        if not self._initialized:
            self.initialize()
            
        try:
            # 确保音频数据是正确的格式
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # 归一化
            if np.abs(audio_data).max() > 1.0:
                audio_data = audio_data / 32768.0
                
            # 转换为 tensor
            audio_tensor = torch.from_numpy(audio_data)
            
            # 执行识别
            result = self.model.generate(
                input=[audio_tensor],
                cache={},
                batch_size=1,
                hotwords=self.config.hotwords,
                language=self.config.language,
                itn=self.config.itn,
            )
            
            if result and len(result) > 0:
                text = result[0].get("text", "")
                return text.strip()
            return ""
            
        except Exception as e:
            logger.error(f"识别错误: {e}")
            return ""


class AudioRecorder:
    """音频录制器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.stream = None
        self._recorded_frames: List[np.ndarray] = []
        self._input_device = None
        self._init_audio_device()
        
    def _init_audio_device(self):
        """初始化音频设备"""
        # 首先检查配置文件中是否指定了设备
        if self.config.audio_device is not None:
            try:
                device_info = sd.query_devices(self.config.audio_device)
                if device_info['max_input_channels'] > 0:
                    self._input_device = self.config.audio_device
                    logger.info(f"🎙️ 使用配置的音频输入设备: [{self.config.audio_device}] {device_info['name']}")
                    return
                else:
                    logger.warning(f"配置的设备 [{self.config.audio_device}] 不是输入设备")
            except Exception as e:
                logger.warning(f"配置的音频设备无效: {e}")
        
        # 尝试获取默认输入设备
        try:
            default_input = sd.default.device[0]
            if default_input >= 0:
                device_info = sd.query_devices(default_input)
                self._input_device = default_input
                logger.info(f"🎙️ 使用默认音频输入设备: [{default_input}] {device_info['name']}")
                return
        except Exception as e:
            logger.warning(f"获取默认音频设备失败: {e}")
        
        # 尝试列出所有设备并选择第一个输入设备
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    self._input_device = i
                    logger.info(f"🎙️ 使用备选音频输入设备: [{i}] {dev['name']}")
                    return
        except Exception as e2:
            logger.error(f"无法找到可用的音频输入设备: {e2}")
        
        # 列出所有设备帮助用户诊断
        logger.error("❌ 没有找到可用的音频输入设备！")
        logger.info("可用的音频设备列表:")
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                input_ch = dev['max_input_channels']
                output_ch = dev['max_output_channels']
                logger.info(f"  [{i}] {dev['name']} - 输入: {input_ch}ch, 输出: {output_ch}ch")
        except:
            pass
        logger.info("请连接麦克风或使用 settings_gui.py 选择音频设备")
        
    def _audio_callback(self, indata, frames, time_info, status):
        """音频回调函数"""
        if status:
            logger.warning(f"音频状态: {status}")
        if self.is_recording:
            self._recorded_frames.append(indata.copy())
            self.audio_queue.put(indata.copy())
            
    def start_recording(self):
        """开始录音"""
        if self.is_recording:
            return
        
        if self._input_device is None:
            logger.error("❌ 没有可用的音频输入设备")
            return
            
        self._recorded_frames = []
        self.is_recording = True
        
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        try:
            self.stream = sd.InputStream(
                device=self._input_device,
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype='float32',
                callback=self._audio_callback,
                blocksize=int(self.config.sample_rate * self.config.chunk_duration)
            )
            self.stream.start()
            logger.info("🎤 开始录音...")
        except Exception as e:
            logger.error(f"❌ 启动录音失败: {e}")
            self.is_recording = False
        
    def stop_recording(self) -> np.ndarray:
        """停止录音并返回录制的音频数据"""
        if not self.is_recording:
            return np.array([])
            
        self.is_recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        logger.info("⏹️ 停止录音")
        
        if self._recorded_frames:
            audio_data = np.concatenate(self._recorded_frames, axis=0)
            return audio_data.flatten()
        return np.array([])
        
    def cancel_recording(self):
        """取消录音"""
        self.is_recording = False
        self._recorded_frames = []
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
                
        logger.info("❌ 录音已取消")


class OutputHandler:
    """输出处理器"""
    
    def __init__(self, config: Config):
        self.config = config
        
    def output(self, text: str):
        """根据配置输出文本"""
        if not text:
            return
            
        mode = OutputMode(self.config.output_mode)
        
        if mode in (OutputMode.CLIPBOARD, OutputMode.BOTH):
            self._copy_to_clipboard(text)
            
        if mode in (OutputMode.TYPE, OutputMode.BOTH):
            self._type_text(text)
            
    def _copy_to_clipboard(self, text: str):
        """复制到剪贴板"""
        try:
            import subprocess
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                env={'LANG': 'en_US.UTF-8'}
            )
            process.communicate(text.encode('utf-8'))
            logger.info(f"📋 已复制到剪贴板: {text[:50]}...")
        except Exception as e:
            logger.error(f"复制到剪贴板失败: {e}")
            
    def _type_text(self, text: str):
        """模拟键盘输入（支持中文）"""
        try:
            import subprocess
            
            # 方法：先复制到剪贴板，然后模拟 Cmd+V 粘贴
            # 这是最可靠的中文输入方式
            
            # 1. 复制到剪贴板
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                env={'LANG': 'en_US.UTF-8'}
            )
            process.communicate(text.encode('utf-8'))
            
            # 2. 短暂延迟确保剪贴板更新
            time.sleep(0.05)
            
            # 3. 模拟 Cmd+V 粘贴
            script = '''
            tell application "System Events"
                keystroke "v" using command down
            end tell
            '''
            subprocess.run(['osascript', '-e', script], check=True)
            logger.info(f"⌨️ 已模拟输入: {text[:50]}...")
            
        except Exception as e:
            logger.error(f"模拟键盘输入失败: {e}")
            # 备用方案：尝试直接 keystroke（仅适用于英文）
            try:
                # 转义特殊字符
                escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
                script = f'''
                tell application "System Events"
                    keystroke "{escaped_text}"
                end tell
                '''
                subprocess.run(['osascript', '-e', script], check=True)
            except Exception as e2:
                logger.error(f"备用输入方式也失败: {e2}")


class HotkeyManager:
    """快捷键管理器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.listener = None
        self.callbacks: Dict[str, Callable] = {}
        self._current_keys = set()
        
    def _parse_hotkey(self, hotkey_str: str) -> set:
        """解析快捷键字符串"""
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
            'return': keyboard.Key.enter,
            'tab': keyboard.Key.tab,
            'f1': keyboard.Key.f1,
            'f2': keyboard.Key.f2,
            'f3': keyboard.Key.f3,
            'f4': keyboard.Key.f4,
            'f5': keyboard.Key.f5,
            'f6': keyboard.Key.f6,
            'f7': keyboard.Key.f7,
            'f8': keyboard.Key.f8,
            'f9': keyboard.Key.f9,
            'f10': keyboard.Key.f10,
            'f11': keyboard.Key.f11,
            'f12': keyboard.Key.f12,
        }
        
        for part in parts:
            part = part.strip()
            if part in key_map:
                keys.add(key_map[part])
            elif len(part) == 1:
                keys.add(keyboard.KeyCode.from_char(part))
                
        return keys
        
    def register(self, hotkey: str, callback: Callable):
        """注册快捷键回调"""
        self.callbacks[hotkey] = {
            'keys': self._parse_hotkey(hotkey),
            'callback': callback
        }
        
    def _on_press(self, key):
        """按键按下事件"""
        self._current_keys.add(key)
        
        for hotkey, data in self.callbacks.items():
            if data['keys'].issubset(self._current_keys):
                try:
                    data['callback']()
                except Exception as e:
                    logger.error(f"快捷键回调错误: {e}")
                    
    def _on_release(self, key):
        """按键释放事件"""
        try:
            self._current_keys.discard(key)
        except:
            pass
            
    def start(self):
        """启动快捷键监听"""
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        logger.info("⌨️ 快捷键监听已启动")
        
    def stop(self):
        """停止快捷键监听"""
        if self.listener:
            self.listener.stop()
            self.listener = None


class FunASRLive:
    """FunASR Live 主类"""
    
    def __init__(self, config_path: str = None):
        # 确定配置文件路径
        if config_path is None:
            # 默认使用脚本所在目录的 config.yaml
            script_dir = Path(__file__).parent
            config_path = str(script_dir / "config.yaml")
        
        # 加载配置
        if os.path.exists(config_path):
            self.config = Config.from_yaml(config_path)
        else:
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
            self.config = Config()
        
        # 打印关键配置
        logger.info(f"📋 配置: 输出模式={self.config.output_mode}, 语言={self.config.language}, 音频设备={self.config.audio_device}")
            
        # 初始化组件
        self.asr_engine = ASREngine(self.config)
        self.recorder = AudioRecorder(self.config)
        self.output_handler = OutputHandler(self.config)
        self.hotkey_manager = HotkeyManager(self.config)
        
        # 状态
        self._is_running = False
        self._latest_result = ""
        self._result_lock = threading.Lock()
        self._result_callbacks: List[Callable[[str], None]] = []
        
        # API 服务器
        self._api_server = None
        
    def _on_hotkey_start_stop(self):
        """开始/停止录音快捷键回调"""
        if self.recorder.is_recording:
            # 停止录音并识别
            audio_data = self.recorder.stop_recording()
            if len(audio_data) > 0:
                self._process_audio(audio_data)
        else:
            # 开始录音
            self.recorder.start_recording()
            
    def _on_hotkey_cancel(self):
        """取消录音快捷键回调"""
        if self.recorder.is_recording:
            self.recorder.cancel_recording()
            
    def _process_audio(self, audio_data: np.ndarray):
        """处理音频数据"""
        logger.info("🔄 正在识别...")
        
        # 在新线程中执行识别，避免阻塞
        def recognize_thread():
            text = self.asr_engine.recognize(audio_data)
            if text:
                logger.info(f"✅ 识别结果: {text}")
                
                # 更新最新结果
                with self._result_lock:
                    self._latest_result = text
                    
                # 输出结果
                self.output_handler.output(text)
                
                # 通知回调
                for callback in self._result_callbacks:
                    try:
                        callback(text)
                    except Exception as e:
                        logger.error(f"回调错误: {e}")
            else:
                logger.warning("⚠️ 未识别到有效内容")
                
        thread = threading.Thread(target=recognize_thread)
        thread.start()
        
    def get_latest_result(self) -> str:
        """获取最新识别结果"""
        with self._result_lock:
            return self._latest_result
            
    def register_result_callback(self, callback: Callable[[str], None]):
        """注册结果回调函数"""
        self._result_callbacks.append(callback)
        
    def unregister_result_callback(self, callback: Callable[[str], None]):
        """取消注册结果回调函数"""
        if callback in self._result_callbacks:
            self._result_callbacks.remove(callback)
            
    def start(self):
        """启动服务"""
        if self._is_running:
            return
            
        logger.info("=" * 50)
        logger.info("🚀 FunASR Live 启动中...")
        logger.info("=" * 50)
        
        # 初始化 ASR 引擎
        self.asr_engine.initialize()
        
        # 注册快捷键
        self.hotkey_manager.register(
            self.config.hotkey_start_stop,
            self._on_hotkey_start_stop
        )
        self.hotkey_manager.register(
            self.config.hotkey_cancel,
            self._on_hotkey_cancel
        )
        self.hotkey_manager.start()
        
        self._is_running = True
        
        logger.info("")
        logger.info("📌 使用说明:")
        logger.info(f"   - 按 [{self.config.hotkey_start_stop}] 开始/停止录音")
        logger.info(f"   - 按 [{self.config.hotkey_cancel}] 取消当前录音")
        logger.info(f"   - 输出模式: {self.config.output_mode}")
        if self.config.api_enabled:
            logger.info(f"   - API 地址: http://{self.config.api_host}:{self.config.api_port}")
        logger.info("")
        logger.info("按 Ctrl+C 退出程序")
        logger.info("=" * 50)
        
    def stop(self):
        """停止服务"""
        if not self._is_running:
            return
            
        logger.info("正在停止服务...")
        
        self.hotkey_manager.stop()
        
        if self.recorder.is_recording:
            self.recorder.cancel_recording()
            
        self._is_running = False
        logger.info("服务已停止")
        
    def run_forever(self):
        """运行主循环"""
        self.start()
        
        try:
            # 如果启用 API，启动 API 服务器
            if self.config.api_enabled:
                from api_server import run_api_server
                run_api_server(self, self.config)
            else:
                # 否则只是等待
                while self._is_running:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("\n收到退出信号...")
        finally:
            self.stop()


def kill_existing_process(port: int) -> bool:
    """终止占用指定端口的进程"""
    import subprocess
    
    try:
        # 查找占用端口的进程
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        logger.info(f"已终止占用端口 {port} 的进程 (PID: {pid})")
                    except:
                        pass
            return True
    except Exception as e:
        logger.warning(f"检查端口占用失败: {e}")
    
    return False


def kill_existing_funasr_processes():
    """终止之前运行的 FunASR Live 进程"""
    import subprocess
    
    try:
        # 查找 funasr_live.py 进程
        result = subprocess.run(
            ['pgrep', '-f', 'funasr_live.py'],
            capture_output=True,
            text=True
        )
        
        current_pid = str(os.getpid())
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid and pid != current_pid:
                    try:
                        subprocess.run(['kill', '-9', pid], check=True)
                        logger.info(f"已终止之前的 FunASR Live 进程 (PID: {pid})")
                    except:
                        pass
    except Exception as e:
        logger.warning(f"检查进程失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FunASR Live - Mac 实时语音识别工具')
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='配置文件路径 (默认: config.yaml)'
    )
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='生成默认配置文件'
    )
    parser.add_argument(
        '--no-api',
        action='store_true',
        help='禁用 API 服务器'
    )
    parser.add_argument(
        '--no-kill',
        action='store_true',
        help='不终止之前的进程'
    )
    
    args = parser.parse_args()
    
    # 生成默认配置文件
    if args.init_config:
        config = Config()
        config.to_yaml(args.config)
        logger.info(f"已生成默认配置文件: {args.config}")
        return
    
    # 终止之前的进程
    if not args.no_kill:
        logger.info("检查并终止之前的进程...")
        kill_existing_funasr_processes()
        
        # 加载配置获取端口号
        script_dir = Path(__file__).parent
        config_path = args.config
        if not os.path.isabs(config_path):
            config_path = str(script_dir / config_path)
        
        if os.path.exists(config_path):
            temp_config = Config.from_yaml(config_path)
            if temp_config.api_enabled:
                kill_existing_process(temp_config.api_port)
        else:
            # 默认端口
            kill_existing_process(8765)
        
        # 等待端口释放
        time.sleep(0.5)
        
    # 加载配置
    config_path = args.config if os.path.exists(args.config) else None
    
    # 创建并运行服务
    app = FunASRLive(config_path)
    
    if args.no_api:
        app.config.api_enabled = False
        
    app.run_forever()


if __name__ == "__main__":
    main()
