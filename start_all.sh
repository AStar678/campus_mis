#!/bin/bash
# ============================================================
# 校园教务管理MIS系统 - 一键启动脚本
# ============================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  校园教务管理MIS系统 - 启动中...${NC}"
echo -e "${GREEN}============================================${NC}"

# 检查 Python 虚拟环境
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${YELLOW}[INFO] 创建 Python 虚拟环境...${NC}"
    python3 -m venv "$PROJECT_DIR/venv"
fi

# 激活虚拟环境并安装依赖
source "$PROJECT_DIR/venv/bin/activate"

echo -e "${YELLOW}[INFO] 安装后端依赖...${NC}"
pip install -r "$PROJECT_DIR/gateway/requirements.txt" -q
pip install -r "$PROJECT_DIR/services/auth/requirements.txt" -q
pip install -r "$PROJECT_DIR/services/student/requirements.txt" -q

# 启动认证服务
echo -e "${GREEN}[START] 启动认证服务 (端口 5001)...${NC}"
cd "$PROJECT_DIR/services/auth"
python app.py &
AUTH_PID=$!
sleep 1

# 启动学生管理服务
echo -e "${GREEN}[START] 启动学生管理服务 (端口 5002)...${NC}"
cd "$PROJECT_DIR/services/student"
python app.py &
STUDENT_PID=$!
sleep 1

# 启动 API 网关
echo -e "${GREEN}[START] 启动 API 网关 (端口 5000)...${NC}"
cd "$PROJECT_DIR/gateway"
python app.py &
GATEWAY_PID=$!
sleep 1

# 启动前端开发服务器
echo -e "${GREEN}[START] 启动前端开发服务器 (端口 3000)...${NC}"
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  所有服务启动完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "  前端地址:   ${YELLOW}http://localhost:3000${NC}"
echo -e "  API网关:    ${YELLOW}http://localhost:5010${NC}"
echo -e "  认证服务:   ${YELLOW}http://localhost:5001${NC}"
echo -e "  学生服务:   ${YELLOW}http://localhost:5002${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"

# 捕获退出信号，关闭所有后台进程
cleanup() {
    echo ""
    echo -e "${RED}[STOP] 正在停止所有服务...${NC}"
    kill $AUTH_PID 2>/dev/null
    kill $STUDENT_PID 2>/dev/null
    kill $GATEWAY_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}所有服务已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 等待所有后台进程
wait
