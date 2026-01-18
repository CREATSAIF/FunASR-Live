#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR Live 设置界面 (PyQt5)
提供图形化配置界面，支持音频设备选择
"""

import os
import sys
import yaml
import sounddevice as sd
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton,
    QCheckBox, QTextEdit, QSpinBox, QRadioButton, QButtonGroup,
    QMessageBox, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


class AudioTestThread(QThread):
    """音频测试线程"""
    finished = pyqtSignal(float, float, str)  # avg_volume, max_volume, error
    
    def __init__(self, device_idx):
        super().__init__()
        self.device_idx = device_idx
        
    def run(self):
        try:
            duration = 2  # 秒
            sample_rate = 16000
            
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                device=self.device_idx,
                dtype='float32'
            )
            sd.wait()
            
            volume = np.abs(recording).mean()
            max_volume = np.abs(recording).max()
            
            self.finished.emit(volume, max_volume, "")
        except Exception as e:
            self.finished.emit(0, 0, str(e))


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FunASR Live 设置")
        self.setMinimumSize(550, 650)
        
        # 加载配置
        self.config = self.load_config()
        
        # 获取音频设备
        self.audio_devices = self.get_audio_devices()
        
        # 创建界面
        self.init_ui()
        
    def load_config(self) -> dict:
        """加载配置文件"""
        default_config = {
            'model_name': 'FunAudioLLM/Fun-ASR-Nano-2512',
            'model_hub': 'ms',
            'use_vad': True,
            'vad_model': 'fsmn-vad',
            'vad_max_segment_time': 30000,
            'device': 'auto',
            'dtype': 'fp16',
            'sample_rate': 16000,
            'channels': 1,
            'chunk_duration': 0.5,
            'hotkey_start_stop': 'ctrl+alt+r',
            'hotkey_cancel': 'escape',
            'output_mode': 'clipboard',
            'type_delay': 0.01,
            'language': '中文',
            'itn': True,
            'hotwords': [],
            'api_enabled': True,
            'api_host': '127.0.0.1',
            'api_port': 8765,
            'audio_device': None,
        }
        
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    loaded = yaml.safe_load(f) or {}
                    default_config.update(loaded)
                print(f"✓ 已加载配置: {CONFIG_PATH}")
            except Exception as e:
                print(f"⚠ 加载配置失败: {e}")
        
        return default_config
    
    def get_audio_devices(self) -> list:
        """获取音频输入设备列表"""
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
        except Exception as e:
            print(f"获取音频设备失败: {e}")
        return devices
    
    def init_ui(self):
        """初始化界面"""
        # 主窗口
        central = QWidget()
        self.setCentralWidget(central)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        
        # ========== 音频设备 ==========
        audio_group = QGroupBox("🎤 音频设备")
        audio_layout = QVBoxLayout()
        
        # 设备选择
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("输入设备:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.update_device_combo()
        device_row.addWidget(self.device_combo)
        device_row.addStretch()
        audio_layout.addLayout(device_row)
        
        # 按钮行
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新设备")
        refresh_btn.clicked.connect(self.refresh_devices)
        btn_row.addWidget(refresh_btn)
        
        test_btn = QPushButton("🎙️ 测试麦克风")
        test_btn.clicked.connect(self.test_microphone)
        btn_row.addWidget(test_btn)
        btn_row.addStretch()
        audio_layout.addLayout(btn_row)
        
        # 警告信息
        if not self.audio_devices:
            warn_label = QLabel("⚠️ 未检测到麦克风！请连接外部麦克风或 AirPods")
            warn_label.setStyleSheet("color: red; font-weight: bold;")
            audio_layout.addWidget(warn_label)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # ========== 快捷键 ==========
        hotkey_group = QGroupBox("⌨️ 快捷键")
        hotkey_layout = QVBoxLayout()
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("开始/停止录音:"))
        self.hotkey_start = QLineEdit(self.config.get('hotkey_start_stop', 'ctrl+alt+r'))
        self.hotkey_start.setMaximumWidth(150)
        row1.addWidget(self.hotkey_start)
        row1.addStretch()
        hotkey_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("取消录音:"))
        self.hotkey_cancel = QLineEdit(self.config.get('hotkey_cancel', 'escape'))
        self.hotkey_cancel.setMaximumWidth(150)
        row2.addWidget(self.hotkey_cancel)
        row2.addStretch()
        hotkey_layout.addLayout(row2)
        
        hint = QLabel("支持: ctrl, alt, shift, cmd, f1-f12, escape, space")
        hint.setStyleSheet("color: gray;")
        hotkey_layout.addWidget(hint)
        
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)
        
        # ========== 输出设置 ==========
        output_group = QGroupBox("📤 输出设置")
        output_layout = QVBoxLayout()
        
        self.output_mode_group = QButtonGroup()
        modes = [
            ('clipboard', '复制到剪贴板'),
            ('type', '模拟键盘输入'),
            ('both', '两者都执行'),
            ('none', '仅 API 输出'),
        ]
        
        current_mode = self.config.get('output_mode', 'clipboard')
        for value, text in modes:
            radio = QRadioButton(text)
            radio.setProperty('value', value)
            if value == current_mode:
                radio.setChecked(True)
            self.output_mode_group.addButton(radio)
            output_layout.addWidget(radio)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # ========== 识别设置 ==========
        recog_group = QGroupBox("🗣️ 识别设置")
        recog_layout = QVBoxLayout()
        
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("识别语言:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['中文', '英文', '日文'])
        self.lang_combo.setCurrentText(self.config.get('language', '中文'))
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        recog_layout.addLayout(lang_row)
        
        self.itn_check = QCheckBox("启用文本规整 (ITN)")
        self.itn_check.setChecked(self.config.get('itn', True))
        recog_layout.addWidget(self.itn_check)
        
        self.vad_check = QCheckBox("启用语音活动检测 (VAD)")
        self.vad_check.setChecked(self.config.get('use_vad', True))
        recog_layout.addWidget(self.vad_check)
        
        recog_layout.addWidget(QLabel("热词列表 (每行一个):"))
        self.hotwords_edit = QTextEdit()
        self.hotwords_edit.setMaximumHeight(80)
        hotwords = self.config.get('hotwords', [])
        if hotwords:
            self.hotwords_edit.setPlainText('\n'.join(hotwords))
        recog_layout.addWidget(self.hotwords_edit)
        
        recog_group.setLayout(recog_layout)
        layout.addWidget(recog_group)
        
        # ========== API 设置 ==========
        api_group = QGroupBox("🌐 API 设置")
        api_layout = QVBoxLayout()
        
        self.api_check = QCheckBox("启用 API 服务器")
        self.api_check.setChecked(self.config.get('api_enabled', True))
        api_layout.addWidget(self.api_check)
        
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(self.config.get('api_port', 8765))
        port_row.addWidget(self.port_spin)
        port_row.addStretch()
        api_layout.addLayout(port_row)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # ========== 按钮 ==========
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 保存配置")
        save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(save_btn)
        
        start_btn = QPushButton("🚀 保存并启动")
        start_btn.clicked.connect(self.save_and_start)
        start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_layout.addWidget(start_btn)
        
        quit_btn = QPushButton("❌ 退出")
        quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(quit_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(central)
        main_layout.addWidget(scroll)
    
    def update_device_combo(self):
        """更新设备下拉框"""
        self.device_combo.clear()
        
        if self.audio_devices:
            for d in self.audio_devices:
                self.device_combo.addItem(
                    f"[{d['index']}] {d['name']} ({d['channels']}ch)",
                    d['index']
                )
            
            # 选择之前保存的设备
            saved = self.config.get('audio_device')
            if saved is not None:
                for i, d in enumerate(self.audio_devices):
                    if d['index'] == saved:
                        self.device_combo.setCurrentIndex(i)
                        break
        else:
            self.device_combo.addItem("无可用输入设备", -1)
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.audio_devices = self.get_audio_devices()
        self.update_device_combo()
        QMessageBox.information(self, "刷新", f"找到 {len(self.audio_devices)} 个输入设备")
    
    def test_microphone(self):
        """测试麦克风"""
        device_idx = self.device_combo.currentData()
        if device_idx is None or device_idx < 0:
            QMessageBox.warning(self, "警告", "请先选择一个音频输入设备")
            return
        
        QMessageBox.information(self, "测试", "将录制 2 秒音频...\n请对着麦克风说话")
        
        self.test_thread = AudioTestThread(device_idx)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()
    
    def on_test_finished(self, avg_vol, max_vol, error):
        """测试完成回调"""
        if error:
            QMessageBox.critical(self, "测试失败", f"错误: {error}")
        elif max_vol > 0.01:
            QMessageBox.information(self, "测试成功",
                f"✓ 音频设备工作正常！\n\n"
                f"平均音量: {avg_vol:.4f}\n"
                f"最大音量: {max_vol:.4f}")
        else:
            QMessageBox.warning(self, "测试结果",
                f"⚠ 检测到音频，但音量很低\n\n"
                f"平均音量: {avg_vol:.4f}\n"
                f"最大音量: {max_vol:.4f}\n\n"
                f"请检查麦克风是否正常工作")
    
    def save_config(self):
        """保存配置"""
        try:
            # 收集配置
            self.config['hotkey_start_stop'] = self.hotkey_start.text()
            self.config['hotkey_cancel'] = self.hotkey_cancel.text()
            
            # 输出模式
            for btn in self.output_mode_group.buttons():
                if btn.isChecked():
                    self.config['output_mode'] = btn.property('value')
                    break
            
            self.config['language'] = self.lang_combo.currentText()
            self.config['itn'] = self.itn_check.isChecked()
            self.config['use_vad'] = self.vad_check.isChecked()
            
            # 热词
            hotwords_text = self.hotwords_edit.toPlainText().strip()
            if hotwords_text:
                self.config['hotwords'] = [w.strip() for w in hotwords_text.split('\n') if w.strip()]
            else:
                self.config['hotwords'] = []
            
            self.config['api_enabled'] = self.api_check.isChecked()
            self.config['api_port'] = self.port_spin.value()
            
            # 音频设备
            device_idx = self.device_combo.currentData()
            self.config['audio_device'] = device_idx if device_idx and device_idx >= 0 else None
            
            # 写入文件
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            QMessageBox.information(self, "成功", f"配置已保存到:\n{CONFIG_PATH}")
            print(f"✓ 配置已保存: {CONFIG_PATH}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{e}")
    
    def kill_existing_processes(self):
        """终止之前运行的进程"""
        import subprocess
        
        # 终止 funasr_live.py 进程
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'funasr_live.py'],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            subprocess.run(['kill', '-9', pid], check=True)
                            print(f"已终止进程 PID: {pid}")
                        except:
                            pass
        except:
            pass
        
        # 终止占用 API 端口的进程
        port = self.config.get('api_port', 8765)
        try:
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
                            print(f"已终止占用端口 {port} 的进程 PID: {pid}")
                        except:
                            pass
        except:
            pass
    
    def save_and_start(self):
        """保存并启动"""
        self.save_config()
        
        # 先终止之前的进程
        self.kill_existing_processes()
        
        # 等待端口释放
        import time
        time.sleep(0.5)
        
        self.close()
        
        # 启动主程序
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.Popen([
            sys.executable,
            os.path.join(script_dir, "funasr_live.py")
        ])


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置字体
    font = QFont()
    font.setPointSize(13)
    app.setFont(font)
    
    window = SettingsWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
