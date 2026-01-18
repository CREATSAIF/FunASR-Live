#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR 实时识别 GUI 控制面板
提供图形化界面来配置和控制实时语音识别
"""

import os
import sys
import subprocess
import threading
import time
import yaml
import numpy as np
import sounddevice as sd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton,
    QCheckBox, QTextEdit, QSpinBox, QRadioButton, QButtonGroup,
    QMessageBox, QScrollArea, QFrame, QSlider, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont

# 配置文件路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config_realtime.yaml")


class SignalBridge(QObject):
    """信号桥接器，用于跨线程通信"""
    status_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    level_signal = pyqtSignal(float)
    output_signal = pyqtSignal(str)  # 输出信号 - 用于在主线程中执行输出


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FunASR 实时语音识别")
        self.setMinimumSize(600, 700)
        
        # 信号桥接器
        self.signals = SignalBridge()
        self.signals.status_signal.connect(self.on_status_changed)
        self.signals.result_signal.connect(self.on_result_received)
        self.signals.error_signal.connect(self.on_error)
        self.signals.level_signal.connect(self.update_level)
        self.signals.output_signal.connect(self.do_output_in_main_thread)
        
        # 加载配置
        self.config = self.load_config()
        
        # 获取音频设备
        self.audio_devices = self.get_audio_devices()
        
        # 状态
        self.is_running = False
        self.recognizer = None
        self.recognizer_thread = None
        self.level_thread = None
        self.level_running = False
        
        # 创建界面
        self.init_ui()
        
        # 启动音频电平监测
        self.start_level_monitor()
    
    def load_config(self) -> dict:
        """加载配置"""
        default_config = {
            'model_name': 'FunAudioLLM/Fun-ASR-Nano-2512',
            'model_hub': 'ms',
            'sample_rate': 16000,
            'channels': 1,
            'audio_device': None,
            'wake_word_enabled': False,
            'wake_words': ['小助手', '开始听写', '语音输入'],
            'sleep_words': ['停止听写', '结束输入', '休息一下'],
            'hotkey_toggle': 'ctrl+alt+r',
            'hotkey_force': 'ctrl+alt+f',
            'language': '中文',
            'hotwords': [],
            'silence_threshold': 0.01,
            'silence_duration': 0.8,
            'max_record_duration': 30,
            'min_record_duration': 0.5,
            'output_mode': 'clipboard',
            'auto_punctuation': True,
            'api_enabled': True,
            'api_port': 8765,
        }
        
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    loaded = yaml.safe_load(f) or {}
                    default_config.update(loaded)
            except:
                pass
        
        return default_config
    
    def save_config(self) -> bool:
        """保存配置"""
        try:
            # 收集配置
            device_data = self.device_combo.currentData()
            self.config['audio_device'] = device_data if device_data and device_data >= 0 else None
            self.config['hotkey_toggle'] = self.hotkey_toggle.text()
            self.config['hotkey_force'] = self.hotkey_force.text()
            self.config['wake_word_enabled'] = self.wake_enabled.isChecked()
            self.config['silence_duration'] = self.silence_slider.value() / 10.0
            self.config['silence_threshold'] = self.threshold_slider.value() / 1000.0
            
            # 输出模式
            for btn in self.output_mode_group.buttons():
                if btn.isChecked():
                    self.config['output_mode'] = btn.property('value')
                    break
            
            self.config['language'] = self.lang_combo.currentText()
            
            # 热词
            hotwords_text = self.hotwords_edit.toPlainText().strip()
            self.config['hotwords'] = [w.strip() for w in hotwords_text.split('\n') if w.strip()] if hotwords_text else []
            
            # 唤醒词
            wake_text = self.wake_words_edit.toPlainText().strip()
            self.config['wake_words'] = [w.strip() for w in wake_text.split('\n') if w.strip()] if wake_text else ['小助手']
            
            # 休眠词
            sleep_text = self.sleep_words_edit.toPlainText().strip()
            self.config['sleep_words'] = [w.strip() for w in sleep_text.split('\n') if w.strip()] if sleep_text else ['停止听写']
            
            self.config['api_enabled'] = self.api_enabled.isChecked()
            self.config['api_port'] = self.api_port.value()
            
            # 写入文件
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)
            
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败:\n{e}")
            return False
    
    def get_audio_devices(self) -> list:
        """获取音频输入设备"""
        devices = []
        try:
            all_devices = sd.query_devices()
            for i, dev in enumerate(all_devices):
                if dev['max_input_channels'] > 0:
                    devices.append({
                        'index': i,
                        'name': dev['name'],
                        'channels': dev['max_input_channels'],
                    })
        except:
            pass
        return devices
    
    def init_ui(self):
        """初始化界面"""
        central = QWidget()
        self.setCentralWidget(central)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        
        # ========== 状态面板 ==========
        status_group = QGroupBox("📊 状态")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("⏹️ 未启动")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        # 音频电平
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("音量:"))
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(15)
        level_row.addWidget(self.level_bar)
        status_layout.addLayout(level_row)
        
        # 识别结果
        status_layout.addWidget(QLabel("识别结果:"))
        self.result_text = QTextEdit()
        self.result_text.setMaximumHeight(100)
        self.result_text.setReadOnly(True)
        status_layout.addWidget(self.result_text)
        
        # 控制按钮
        btn_row = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ 启动")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.start_btn.clicked.connect(self.toggle_service)
        btn_row.addWidget(self.start_btn)
        
        self.toggle_btn = QPushButton("⏸️ 暂停")
        self.toggle_btn.setEnabled(False)
        self.toggle_btn.clicked.connect(self.toggle_listening)
        btn_row.addWidget(self.toggle_btn)
        
        self.force_btn = QPushButton("⚡ 立即输出")
        self.force_btn.setEnabled(False)
        self.force_btn.clicked.connect(self.force_process)
        btn_row.addWidget(self.force_btn)
        
        status_layout.addLayout(btn_row)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # ========== 音频设备 ==========
        audio_group = QGroupBox("🎤 音频设备")
        audio_layout = QVBoxLayout()
        
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("输入:"))
        self.device_combo = QComboBox()
        self.update_device_combo()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        device_row.addWidget(self.device_combo, 1)
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(35)
        refresh_btn.clicked.connect(self.refresh_devices)
        device_row.addWidget(refresh_btn)
        audio_layout.addLayout(device_row)
        
        # 静音阈值
        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("静音阈值:"))
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setRange(5, 50)
        self.threshold_slider.setValue(int(self.config.get('silence_threshold', 0.01) * 1000))
        threshold_row.addWidget(self.threshold_slider)
        self.threshold_label = QLabel(f"{self.threshold_slider.value() / 1000:.3f}")
        self.threshold_label.setFixedWidth(45)
        self.threshold_slider.valueChanged.connect(lambda v: self.threshold_label.setText(f"{v / 1000:.3f}"))
        threshold_row.addWidget(self.threshold_label)
        audio_layout.addLayout(threshold_row)
        
        # 静音时长
        silence_row = QHBoxLayout()
        silence_row.addWidget(QLabel("静音时长:"))
        self.silence_slider = QSlider(Qt.Horizontal)
        self.silence_slider.setRange(3, 20)
        self.silence_slider.setValue(int(self.config.get('silence_duration', 0.8) * 10))
        silence_row.addWidget(self.silence_slider)
        self.silence_label = QLabel(f"{self.silence_slider.value() / 10:.1f}s")
        self.silence_label.setFixedWidth(35)
        self.silence_slider.valueChanged.connect(lambda v: self.silence_label.setText(f"{v / 10:.1f}s"))
        silence_row.addWidget(self.silence_label)
        audio_layout.addLayout(silence_row)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # ========== 快捷键 ==========
        hotkey_group = QGroupBox("⌨️ 快捷键")
        hotkey_layout = QHBoxLayout()
        
        hotkey_layout.addWidget(QLabel("切换:"))
        self.hotkey_toggle = QLineEdit(self.config.get('hotkey_toggle', 'ctrl+alt+r'))
        self.hotkey_toggle.setFixedWidth(100)
        hotkey_layout.addWidget(self.hotkey_toggle)
        
        hotkey_layout.addWidget(QLabel("输出:"))
        self.hotkey_force = QLineEdit(self.config.get('hotkey_force', 'ctrl+alt+f'))
        self.hotkey_force.setFixedWidth(100)
        hotkey_layout.addWidget(self.hotkey_force)
        
        hotkey_layout.addStretch()
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)
        
        # ========== 输出设置 ==========
        output_group = QGroupBox("📤 输出模式")
        output_layout = QHBoxLayout()
        
        self.output_mode_group = QButtonGroup()
        modes = [('clipboard', '剪贴板'), ('type', '模拟输入'), ('both', '两者')]
        
        current_mode = self.config.get('output_mode', 'clipboard')
        for value, text in modes:
            radio = QRadioButton(text)
            radio.setProperty('value', value)
            if value == current_mode:
                radio.setChecked(True)
            self.output_mode_group.addButton(radio)
            output_layout.addWidget(radio)
        
        output_layout.addStretch()
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # ========== 识别设置 ==========
        recog_group = QGroupBox("🗣️ 识别")
        recog_layout = QVBoxLayout()
        
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("语言:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['中文', '英文', '日文'])
        self.lang_combo.setCurrentText(self.config.get('language', '中文'))
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        recog_layout.addLayout(lang_row)
        
        recog_layout.addWidget(QLabel("热词 (每行一个):"))
        self.hotwords_edit = QTextEdit()
        self.hotwords_edit.setMaximumHeight(50)
        hotwords = self.config.get('hotwords', [])
        if hotwords:
            self.hotwords_edit.setPlainText('\n'.join(hotwords))
        recog_layout.addWidget(self.hotwords_edit)
        
        recog_group.setLayout(recog_layout)
        layout.addWidget(recog_group)
        
        # ========== 唤醒词 ==========
        wake_group = QGroupBox("🔔 唤醒词")
        wake_layout = QVBoxLayout()
        
        self.wake_enabled = QCheckBox("启用唤醒词模式")
        self.wake_enabled.setChecked(self.config.get('wake_word_enabled', False))
        wake_layout.addWidget(self.wake_enabled)
        
        words_row = QHBoxLayout()
        
        wake_col = QVBoxLayout()
        wake_col.addWidget(QLabel("唤醒词:"))
        self.wake_words_edit = QTextEdit()
        self.wake_words_edit.setMaximumHeight(50)
        wake_words = self.config.get('wake_words', [])
        self.wake_words_edit.setPlainText('\n'.join(wake_words) if wake_words else '小助手')
        wake_col.addWidget(self.wake_words_edit)
        words_row.addLayout(wake_col)
        
        sleep_col = QVBoxLayout()
        sleep_col.addWidget(QLabel("休眠词:"))
        self.sleep_words_edit = QTextEdit()
        self.sleep_words_edit.setMaximumHeight(50)
        sleep_words = self.config.get('sleep_words', [])
        self.sleep_words_edit.setPlainText('\n'.join(sleep_words) if sleep_words else '停止听写')
        sleep_col.addWidget(self.sleep_words_edit)
        words_row.addLayout(sleep_col)
        
        wake_layout.addLayout(words_row)
        wake_group.setLayout(wake_layout)
        layout.addWidget(wake_group)
        
        # ========== API ==========
        api_group = QGroupBox("🌐 API")
        api_layout = QHBoxLayout()
        
        self.api_enabled = QCheckBox("启用")
        self.api_enabled.setChecked(self.config.get('api_enabled', True))
        api_layout.addWidget(self.api_enabled)
        
        api_layout.addWidget(QLabel("端口:"))
        self.api_port = QSpinBox()
        self.api_port.setRange(1024, 65535)
        self.api_port.setValue(self.config.get('api_port', 8765))
        api_layout.addWidget(self.api_port)
        
        api_layout.addStretch()
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # ========== 底部按钮 ==========
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self.on_save_clicked)
        btn_layout.addWidget(save_btn)
        
        btn_layout.addStretch()
        
        quit_btn = QPushButton("❌ 退出")
        quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(quit_btn)
        
        layout.addLayout(btn_layout)
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(scroll)
    
    def update_device_combo(self):
        """更新设备下拉框"""
        self.device_combo.clear()
        
        if self.audio_devices:
            for d in self.audio_devices:
                self.device_combo.addItem(f"[{d['index']}] {d['name']}", d['index'])
            
            saved = self.config.get('audio_device')
            if saved is not None:
                for i, d in enumerate(self.audio_devices):
                    if d['index'] == saved:
                        self.device_combo.setCurrentIndex(i)
                        break
        else:
            self.device_combo.addItem("无可用设备", -1)
    
    def refresh_devices(self):
        """刷新设备"""
        self.audio_devices = self.get_audio_devices()
        self.update_device_combo()
        self.restart_level_monitor()
    
    def on_device_changed(self):
        """设备改变"""
        self.restart_level_monitor()
    
    def start_level_monitor(self):
        """启动音频电平监测"""
        device_idx = self.device_combo.currentData()
        if device_idx is None or device_idx < 0:
            return
        
        self.level_running = True
        
        def monitor():
            try:
                def callback(indata, frames, time_info, status):
                    if self.level_running:
                        level = np.abs(indata).mean()
                        self.signals.level_signal.emit(level)
                
                with sd.InputStream(
                    device=device_idx,
                    samplerate=16000,
                    channels=1,
                    callback=callback,
                    blocksize=1600
                ):
                    while self.level_running:
                        time.sleep(0.05)
            except Exception as e:
                print(f"音频监测错误: {e}")
        
        self.level_thread = threading.Thread(target=monitor, daemon=True)
        self.level_thread.start()
    
    def stop_level_monitor(self):
        """停止音频电平监测"""
        self.level_running = False
        if self.level_thread:
            self.level_thread.join(timeout=1)
            self.level_thread = None
    
    def restart_level_monitor(self):
        """重启音频电平监测"""
        self.stop_level_monitor()
        time.sleep(0.2)
        self.start_level_monitor()
    
    def update_level(self, level):
        """更新音频电平"""
        value = min(100, int(level * 1000))
        self.level_bar.setValue(value)
    
    def on_save_clicked(self):
        """保存按钮点击"""
        if self.save_config():
            QMessageBox.information(self, "成功", "配置已保存")
    
    def toggle_service(self):
        """切换服务"""
        if self.is_running:
            self.stop_service()
        else:
            self.start_service()
    
    def start_service(self):
        """启动服务"""
        if not self.save_config():
            return
        
        # 终止已存在的进程
        self.kill_existing()
        
        self.status_label.setText("⏳ 启动中...")
        self.start_btn.setEnabled(False)
        QApplication.processEvents()
        
        # 在后台线程启动识别器
        def run_recognizer():
            try:
                from funasr_realtime import RealtimeRecognizer, RealtimeConfig
                
                config = RealtimeConfig.from_yaml(CONFIG_PATH)
                
                # GUI 模式下禁用快捷键（避免 pynput 与 PyQt5 冲突）
                config.hotkey_toggle = ""
                config.hotkey_force = ""
                
                self.recognizer = RealtimeRecognizer(config)
                
                # 禁用快捷键管理器
                self.recognizer.hotkey_manager._enabled = False
                
                # 设置回调 - 使用线程安全的方式
                def on_result(text):
                    # 使用 QMetaObject.invokeMethod 确保在主线程执行
                    self.signals.result_signal.emit(text)
                
                def on_status(status):
                    self.signals.status_signal.emit(status)
                
                # 设置输出回调 - 通过信号在主线程中执行输出
                def on_output(text):
                    self.signals.output_signal.emit(text)
                
                self.recognizer.on_result = on_result
                self.recognizer.on_status_change = on_status
                self.recognizer.on_output = on_output  # 关键：设置输出回调
                
                # 启动（不启动快捷键监听）
                self.recognizer.start_without_hotkeys()
                
                # 通知启动完成
                self.signals.status_signal.emit("started")
                
                # 等待停止
                while self.is_running and self.recognizer.is_running:
                    time.sleep(0.1)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.signals.error_signal.emit(str(e))
            finally:
                if self.recognizer:
                    self.recognizer.stop()
                    self.recognizer = None
        
        self.is_running = True
        self.recognizer_thread = threading.Thread(target=run_recognizer, daemon=True)
        self.recognizer_thread.start()
        
        # 延迟更新 UI
        QTimer.singleShot(3000, self.on_service_started)
    
    def on_service_started(self):
        """服务启动后"""
        if not self.is_running:
            return
        
        self.start_btn.setText("⏹️ 停止")
        self.start_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 8px;")
        self.start_btn.setEnabled(True)
        self.toggle_btn.setEnabled(True)
        self.force_btn.setEnabled(True)
    
    def stop_service(self):
        """停止服务"""
        self.is_running = False
        
        if self.recognizer:
            self.recognizer.stop()
        
        if self.recognizer_thread:
            self.recognizer_thread.join(timeout=3)
            self.recognizer_thread = None
        
        self.recognizer = None
        
        self.status_label.setText("⏹️ 已停止")
        self.start_btn.setText("▶️ 启动")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.toggle_btn.setEnabled(False)
        self.force_btn.setEnabled(False)
    
    def toggle_listening(self):
        """切换监听"""
        if self.recognizer:
            self.recognizer.toggle_listening()
    
    def force_process(self):
        """强制输出"""
        if self.recognizer:
            self.recognizer.force_process()
    
    def on_status_changed(self, status):
        """状态变化"""
        status_map = {
            "started": "✅ 已启动",
            "sleeping": "💤 休眠中",
            "listening": "👂 监听中",
            "recording": "🎤 录音中",
        }
        self.status_label.setText(status_map.get(status, status))
        
        if status == "listening":
            self.toggle_btn.setText("⏸️ 暂停")
        elif status == "sleeping":
            self.toggle_btn.setText("▶️ 继续")
    
    def on_result_received(self, text):
        """收到识别结果"""
        self.result_text.append(f"• {text}")
        # 滚动到底部
        scrollbar = self.result_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_error(self, error):
        """错误"""
        QMessageBox.critical(self, "错误", f"识别错误:\n{error}")
        self.stop_service()
    
    def do_output_in_main_thread(self, text: str):
        """在主线程中执行输出操作 - 解决 macOS TSMGetInputSourceProperty 线程问题"""
        if not text:
            return
        
        mode = self.config.get('output_mode', 'clipboard')
        
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
        except Exception as e:
            print(f"复制失败: {e}")
    
    def _type_text(self, text: str):
        """模拟输入 - 必须在主线程中调用"""
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
        except Exception as e:
            print(f"输入失败: {e}")
    
    def kill_existing(self):
        """终止已存在的进程"""
        try:
            subprocess.run(['pkill', '-f', 'funasr_realtime.py'], capture_output=True)
            subprocess.run(['pkill', '-f', 'funasr_live.py'], capture_output=True)
            
            port = self.config.get('api_port', 8765)
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.stdout.strip():
                for pid in result.stdout.strip().split('\n'):
                    if pid:
                        subprocess.run(['kill', '-9', pid], capture_output=True)
            
            time.sleep(0.3)
        except:
            pass
    
    def closeEvent(self, event):
        """关闭"""
        if self.is_running:
            reply = QMessageBox.question(
                self, '确认',
                '服务正在运行，确定退出？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        
        self.stop_service()
        self.stop_level_monitor()
        event.accept()


def main():
    # 终止已存在的进程
    try:
        subprocess.run(['pkill', '-f', 'funasr_realtime.py'], capture_output=True)
    except:
        pass
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font = QFont()
    font.setPointSize(13)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
