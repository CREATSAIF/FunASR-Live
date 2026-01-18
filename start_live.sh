#!/bin/bash
# FunASR Live 启动脚本
# Mac MPS 实时语音识别工具

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   FunASR Live - Mac 实时语音识别工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python 版本
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"
        return 0
    else
        echo -e "${RED}✗ 未找到 Python3，请先安装 Python 3.9+${NC}"
        return 1
    fi
}

# 检查虚拟环境
check_venv() {
    if [ -d "funasrvenv" ]; then
        echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
        return 0
    else
        echo -e "${YELLOW}! 虚拟环境不存在，正在创建...${NC}"
        python3 -m venv funasrvenv
        echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
        return 0
    fi
}

# 激活虚拟环境
activate_venv() {
    source funasrvenv/bin/activate
    echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
}

# 检查依赖
check_dependencies() {
    echo -e "${BLUE}检查依赖...${NC}"
    
    # 检查核心依赖
    MISSING_DEPS=()
    
    python3 -c "import torch" 2>/dev/null || MISSING_DEPS+=("torch")
    python3 -c "import funasr" 2>/dev/null || MISSING_DEPS+=("funasr")
    python3 -c "import sounddevice" 2>/dev/null || MISSING_DEPS+=("sounddevice")
    python3 -c "import pynput" 2>/dev/null || MISSING_DEPS+=("pynput")
    python3 -c "import fastapi" 2>/dev/null || MISSING_DEPS+=("fastapi")
    python3 -c "import uvicorn" 2>/dev/null || MISSING_DEPS+=("uvicorn")
    python3 -c "import yaml" 2>/dev/null || MISSING_DEPS+=("pyyaml")
    
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        echo -e "${YELLOW}! 缺少依赖: ${MISSING_DEPS[*]}${NC}"
        echo -e "${YELLOW}正在安装依赖...${NC}"
        pip install -r requirements_live.txt
        echo -e "${GREEN}✓ 依赖安装完成${NC}"
    else
        echo -e "${GREEN}✓ 所有依赖已安装${NC}"
    fi
}

# 检查 MPS 支持
check_mps() {
    MPS_AVAILABLE=$(python3 -c "import torch; print(torch.backends.mps.is_available())" 2>/dev/null || echo "False")
    if [ "$MPS_AVAILABLE" = "True" ]; then
        echo -e "${GREEN}✓ MPS (Metal Performance Shaders) 可用${NC}"
    else
        echo -e "${YELLOW}! MPS 不可用，将使用 CPU 模式${NC}"
    fi
}

# 检查麦克风权限
check_microphone() {
    echo -e "${BLUE}检查麦克风权限...${NC}"
    # 尝试列出音频设备
    python3 -c "import sounddevice as sd; sd.query_devices()" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 麦克风权限正常${NC}"
    else
        echo -e "${YELLOW}! 请在系统偏好设置中授予终端麦克风访问权限${NC}"
    fi
}

# 生成默认配置
generate_config() {
    if [ ! -f "config.yaml" ]; then
        echo -e "${YELLOW}! 配置文件不存在，正在生成默认配置...${NC}"
        python3 funasr_live.py --init-config
        echo -e "${GREEN}✓ 默认配置已生成: config.yaml${NC}"
    else
        echo -e "${GREEN}✓ 配置文件已存在${NC}"
    fi
}

# 显示使用说明
show_usage() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}启动成功！使用说明:${NC}"
    echo ""
    echo -e "  ${YELLOW}快捷键:${NC}"
    echo -e "    Ctrl+Alt+R  - 开始/停止录音"
    echo -e "    Escape      - 取消当前录音"
    echo ""
    echo -e "  ${YELLOW}API 接口:${NC}"
    echo -e "    HTTP:      http://127.0.0.1:8765"
    echo -e "    WebSocket: ws://127.0.0.1:8765/ws"
    echo ""
    echo -e "  ${YELLOW}配置文件:${NC} config.yaml"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 主函数
main() {
    check_python || exit 1
    check_venv
    activate_venv
    check_dependencies
    check_mps
    check_microphone
    generate_config
    show_usage
    
    # 启动服务
    echo -e "${GREEN}正在启动 FunASR Live...${NC}"
    echo ""
    python3 funasr_live.py "$@"
}

# 处理命令行参数
case "$1" in
    --help|-h)
        echo "用法: $0 [选项]"
        echo ""
        echo "选项:"
        echo "  --help, -h       显示帮助信息"
        echo "  --init-config    生成默认配置文件"
        echo "  --no-api         禁用 API 服务器"
        echo "  -c, --config     指定配置文件路径"
        echo ""
        exit 0
        ;;
    --install)
        check_python || exit 1
        check_venv
        activate_venv
        echo -e "${YELLOW}正在安装依赖...${NC}"
        pip install -r requirements_live.txt
        echo -e "${GREEN}✓ 安装完成${NC}"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
