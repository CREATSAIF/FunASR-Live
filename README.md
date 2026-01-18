# FunASR Live - 实时语音识别工具

[![Build and Release](https://github.com/CREATSAIF/FunASR-Live/actions/workflows/build-release.yml/badge.svg)](https://github.com/CREATSAIF/FunASR-Live/actions/workflows/build-release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

基于阿里巴巴 [FunASR](https://github.com/modelscope/FunASR) 的实时语音识别工具，支持快捷键触发、连续识别、剪贴板输出和模拟键盘输入。

## ✨ 功能特性

- 🎤 **实时语音识别** - 基于 Fun-ASR-Nano-2512 模型，支持中文、英文、日文
- ⌨️ **快捷键触发** - 自定义快捷键开始/停止录音
- 📋 **剪贴板输出** - 识别结果自动复制到剪贴板
- 🖥️ **模拟输入** - 直接将识别结果输入到当前应用
- 🔔 **唤醒词支持** - 语音唤醒，解放双手
- 🌐 **API 接口** - 提供 HTTP REST 和 WebSocket API
- 🖼️ **图形界面** - 简洁易用的 GUI 控制面板

## 📥 下载安装

### 预编译版本

从 [Releases](https://github.com/CREATSAIF/FunASR-Live/releases) 页面下载对应平台的预编译版本：

| 平台 | 文件 |
|------|------|
| Windows (x64) | `FunASR-Live-Windows-x64.zip` |
| macOS (Intel) | `FunASR-Live-macOS-Intel.zip` |
| macOS (Apple Silicon) | `FunASR-Live-macOS-AppleSilicon.zip` |
| Linux (x64) | `FunASR-Live-Linux-x64.tar.gz` |

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/CREATSAIF/FunASR-Live.git
cd FunASR-Live

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements_live.txt
```

## 🚀 快速开始

### GUI 模式（推荐）

```bash
python realtime_gui.py
```

或运行预编译的 `FunASR-GUI` 可执行文件。

### 命令行模式

```bash
# 快捷键触发模式
python funasr_live.py

# 实时连续识别模式
python funasr_realtime.py
```

## ⚙️ 配置说明

### config.yaml (快捷键模式)

```yaml
model:
  name: "FunAudioLLM/Fun-ASR-Nano-2512"
  hub: "ms"

audio:
  sample_rate: 16000
  channels: 1
  audio_device: null  # null 表示使用默认设备

hotkey:
  start_stop: "ctrl+alt+space"

output:
  mode: "both"  # clipboard, type, both
```

### config_realtime.yaml (实时模式)

```yaml
model_name: "FunAudioLLM/Fun-ASR-Nano-2512"
model_hub: "ms"

# 唤醒词设置
wake_word_enabled: false
wake_words:
  - "小助手"
  - "开始听写"
sleep_words:
  - "停止听写"
  - "休息一下"

# 静音检测
silence_threshold: 0.01
silence_duration: 0.8

# 输出模式
output_mode: "clipboard"  # clipboard, type, both

# API 设置
api_enabled: true
api_port: 8765
```

## 🔑 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Alt+Space` | 开始/停止录音 (快捷键模式) |
| `Ctrl+Alt+R` | 切换监听状态 (实时模式) |
| `Ctrl+Alt+F` | 强制输出当前内容 (实时模式) |

## 🌐 API 接口

### HTTP REST API

```bash
# 获取状态
curl http://localhost:8765/status

# 获取最新识别结果
curl http://localhost:8765/result
```

### WebSocket API

```javascript
const ws = new WebSocket('ws://localhost:8765/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('识别结果:', data.text);
};
```

## 🔧 系统要求

### 硬件要求
- CPU: 支持 AVX2 指令集
- 内存: 4GB+ RAM
- 麦克风: 任意音频输入设备

### 软件要求
- Python 3.9+
- macOS 10.15+ / Windows 10+ / Ubuntu 20.04+

### macOS 权限设置
1. **麦克风权限**: 系统偏好设置 → 安全性与隐私 → 隐私 → 麦克风
2. **辅助功能权限**: 系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能

## 📁 项目结构

```
FunASR-Live/
├── funasr_live.py        # 快捷键触发模式主程序
├── funasr_realtime.py    # 实时连续识别主程序
├── realtime_gui.py       # GUI 控制面板
├── settings_gui.py       # 设置界面
├── api_server.py         # API 服务器
├── realtime_api.py       # 实时模式 API
├── model.py              # 模型定义
├── config.yaml           # 快捷键模式配置
├── config_realtime.yaml  # 实时模式配置
├── requirements_live.txt # 依赖列表
└── README.md             # 说明文档
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

## 🙏 致谢

- [FunASR](https://github.com/modelscope/FunASR) - 阿里巴巴达摩院语音识别框架
- [ModelScope](https://modelscope.cn/) - 模型托管平台
