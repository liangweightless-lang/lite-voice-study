#!/bin/bash

# Lite Voice Study 一键极速部署与启动脚本

# 终端彩色配置
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}     🎙️  Lite Voice Study 一键极速启动控制器         ${NC}"
echo -e "${BLUE}====================================================${NC}"

# 1. 秘钥安全校验
if [ ! -f "backend/.env" ]; then
    echo -e "${RED}[错误] 未发现 backend/.env 配置文件，请检查项目完整性。${NC}"
    exit 1
fi

if grep -q "your_dashscope_api_key_here" backend/.env; then
    echo -e "${YELLOW}[提示] 检测到 .env 中仍为默认占位符。${NC}"
    echo -e "${YELLOW}👉 请先使用编辑器打开 /Users/weightless/Documents/Project/lite-voice-study/backend/.env 并修改您的 DASHSCOPE_API_KEY，然后重新运行本脚本！${NC}"
    echo -e "${BLUE}====================================================${NC}"
    exit 0
fi

# 2. 调用 uv 部署环境
echo -e "\n${BLUE}[1/3] 正在使用 uv 极速初始化 Python 虚拟环境...${NC}"
~/.local/bin/uv venv --quiet
if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] uv 初始化虚拟环境失败，请确认 ~/.local/bin/uv 路径是否正确。${NC}"
    exit 1
fi
echo -e "${GREEN}✔ 虚拟环境创建完毕！${NC}"

echo -e "\n${BLUE}[2/3] 正在使用 uv 极速同步安装 Python 语音与模型依赖包...${NC}"
~/.local/bin/uv pip install -r backend/requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo -e "${RED}[错误] 依赖安装失败，请检查网络或配置。${NC}"
    exit 1
fi
echo -e "${GREEN}✔ 依赖包瞬间安装同步完成！${NC}"

# 3. 运行服务
echo -e "\n${BLUE}[3/3] 正在通过 uv 启动后台 WebSocket 语音对话引擎...${NC}"
echo -e "${GREEN}✔ 后端已经在 ws://localhost:9090 就绪。请在另一个终端使用 pnpm run dev 开启前端科技舱交互！${NC}"
echo -e "${BLUE}====================================================${NC}\n"

# 物理执行
~/.local/bin/uv run backend/main.py
