#!/bin/bash

# 重启所有校园MIS服务脚本

set -e

REMOTE_DIR="/campus_mis"

echo "=========================================="
echo "重启校园MIS系统服务"
echo "=========================================="

cd ${REMOTE_DIR}

# 停止旧的服务进程
echo "停止旧的服务进程..."
pkill -f "python3.*app.py" || true
sleep 2

# 创建日志目录
mkdir -p logs

# 启动主服务 (端口 5001)
echo "启动主服务 (端口 5001)..."
cd main_service/backend
nohup python3 app.py > ../../logs/main_service.log 2>&1 &
echo $! > ../../logs/main_service.pid
cd ../..

# 启动选课排课服务 (端口 5004)
echo "启动选课排课服务 (端口 5004)..."
cd course_schedule_service
nohup python3 app.py > ../logs/course_schedule_service.log 2>&1 &
echo $! > ../logs/course_schedule_service.pid
cd ..

# 启动校园墙服务 (端口 5005)
echo "启动校园墙服务 (端口 5005)..."
cd campus_wall_service/backend
nohup python3 app.py > ../../logs/campus_wall_service.log 2>&1 &
echo $! > ../../logs/campus_wall_service.pid
cd ../..

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "服务状态:"
for port in 5001 5004 5005; do
    if curl -s http://localhost:$port/api/health > /dev/null 2>&1; then
        echo "✓ 端口 $port 服务运行正常"
    else
        echo "✗ 端口 $port 服务启动失败"
    fi
done

echo ""
echo "=========================================="
echo "服务重启完成"
echo "=========================================="
