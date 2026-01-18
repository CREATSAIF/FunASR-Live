# FunASR Live - Mac MPS 实时语音识别工具

基于 [Fun-ASR-Nano-2512](https://modelscope.cn/models/FunAudioLLM/Fun-ASR-Nano-2512) 模型的 Mac 实时语音识别工具，支持 MPS (Metal Performance Shaders) 加速。

## ✨ 功能特性

- 🎤 **快捷键触发录音** - 自定义快捷键开始/停止录音
- 🚀 **MPS 加速** - 利用 Mac GPU 加速推理
- 📋 **多种输出方式** - 剪贴板复制 / 模拟键盘输入
- 🌐 **API 接口** - HTTP REST API + WebSocket 实时推送
- 🔧 **灵活配置** - YAML 配置文件，支持热词、多语言

## 📋 系统要求

- macOS 12.3+ (支持 MPS)
- Apple Silicon (M1/M2/M3) 或 Intel Mac
- Python 3.9+
- 麦克风访问权限
- 辅助功能权限 (如需模拟键盘输入)

## 🚀 快速开始

### 1. 安装依赖

```bash
cd Fun-ASR

# 使用现有虚拟环境
source funasrvenv/bin/activate

# 安装额外依赖
pip install -r requirements_live.txt
```

### 2. 生成配置文件

```bash
python funasr_live.py --init-config
```

### 3. 启动服务

```bash
# 方式一：直接运行
python funasr_live.py

# 方式二：使用启动脚本
chmod +x start_live.sh
./start_live.sh
```

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Alt+R` | 开始/停止录音 |
| `Escape` | 取消当前录音 |

> 💡 可在 `config.yaml` 中自定义快捷键

## 📝 配置说明

配置文件 `config.yaml` 主要选项：

```yaml
# 快捷键配置
hotkey_start_stop: "ctrl+alt+r"  # 开始/停止录音
hotkey_cancel: "escape"           # 取消录音

# 输出模式
output_mode: "clipboard"  # clipboard / type / both / none

# 识别语言
language: "中文"  # 中文、英文、日文

# 热词 (提高特定词汇识别率)
hotwords:
  - "人工智能"
  - "机器学习"

# API 配置
api_enabled: true
api_host: "127.0.0.1"
api_port: 8765
```

## 🌐 API 接口

### HTTP REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取服务状态 |
| `/api/result` | GET | 获取最新识别结果 |
| `/api/recognize` | POST | 上传音频文件识别 |
| `/api/control/start` | POST | 开始录音 |
| `/api/control/stop` | POST | 停止录音并识别 |
| `/api/control/cancel` | POST | 取消录音 |

### WebSocket

连接地址: `ws://127.0.0.1:8765/ws`

**服务端消息:**
```json
{"type": "result", "text": "识别结果", "timestamp": 1234567890.123}
{"type": "recording_started"}
{"type": "recording_stopped"}
{"type": "recording_cancelled"}
```

**客户端命令:**
```json
{"action": "start"}   // 开始录音
{"action": "stop"}    // 停止录音
{"action": "cancel"}  // 取消录音
{"action": "status"}  // 获取状态
```

### 使用示例

#### Python 客户端

```python
import requests

# 获取最新识别结果
response = requests.get("http://127.0.0.1:8765/api/result")
print(response.json())

# 控制录音
requests.post("http://127.0.0.1:8765/api/control/start")
# ... 录音中 ...
response = requests.post("http://127.0.0.1:8765/api/control/stop")
print(response.json()["text"])
```

#### WebSocket 客户端

```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect("ws://127.0.0.1:8765/ws") as ws:
        # 开始录音
        await ws.send(json.dumps({"action": "start"}))
        
        # 监听结果
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data["type"] == "result":
                print(f"识别结果: {data['text']}")

asyncio.run(listen())
```

#### curl 命令

```bash
# 获取状态
curl http://127.0.0.1:8765/api/status

# 获取最新结果
curl http://127.0.0.1:8765/api/result

# 开始录音
curl -X POST http://127.0.0.1:8765/api/control/start

# 停止录音
curl -X POST http://127.0.0.1:8765/api/control/stop

# 上传音频文件识别
curl -X POST -F "file=@audio.wav" http://127.0.0.1:8765/api/recognize
```

## 🔧 高级配置

### 自定义快捷键

支持的修饰键：
- `ctrl` / `control`
- `alt` / `option`
- `shift`
- `cmd` / `command`

支持的特殊键：
- `escape` / `esc`
- `space`
- `enter` / `return`
- `tab`
- `f1` - `f12`

示例：
```yaml
hotkey_start_stop: "cmd+shift+space"
hotkey_cancel: "cmd+escape"
```

### 输出模式

| 模式 | 说明 |
|------|------|
| `clipboard` | 复制到剪贴板 |
| `type` | 模拟键盘输入 (需要辅助功能权限) |
| `both` | 同时复制和输入 |
| `none` | 仅通过 API 获取 |

### 热词配置

热词可以提高特定词汇的识别准确率：

```yaml
hotwords:
  - "FunASR"
  - "ModelScope"
  - "语音识别"
```

## ⚠️ 权限设置

### 麦克风权限

首次运行时，系统会提示授予麦克风访问权限。

手动设置：`系统偏好设置` → `安全性与隐私` → `隐私` → `麦克风`

### 辅助功能权限 (模拟键盘输入)

如果使用 `type` 或 `both` 输出模式，需要授予辅助功能权限。

手动设置：`系统偏好设置` → `安全性与隐私` → `隐私` → `辅助功能`

## 🐛 常见问题

### Q: MPS 不可用怎么办？

确保：
1. macOS 版本 ≥ 12.3
2. PyTorch 版本 ≥ 2.0
3. 运行 `python -c "import torch; print(torch.backends.mps.is_available())"` 检查

### Q: 识别结果为空？

1. 检查麦克风权限
2. 检查音频输入设备是否正确
3. 尝试增加录音时长

### Q: 快捷键不响应？

1. 检查是否有其他程序占用该快捷键
2. 尝试更换快捷键组合
3. 确保终端/Python 有输入监控权限

### Q: 模拟输入不工作？

1. 授予辅助功能权限
2. 某些应用可能阻止模拟输入
3. 尝试使用 `clipboard` 模式

## 📄 文件结构

```
Fun-ASR/
├── funasr_live.py      # 主程序
├── api_server.py       # API 服务器
├── config.yaml         # 配置文件
├── model.py            # 模型定义
├── ctc.py              # CTC 解码器
├── requirements_live.txt  # 依赖列表
├── start_live.sh       # 启动脚本
└── LIVE_README.md      # 本文档
```

## 📚 参考资料

- [Fun-ASR-Nano-2512 模型](https://modelscope.cn/models/FunAudioLLM/Fun-ASR-Nano-2512)
- [FunASR GitHub](https://github.com/modelscope/FunASR)
- [PyTorch MPS 后端](https://developer.apple.com/metal/pytorch/)

## 📝 许可证

本项目遵循 MIT 许可证。
