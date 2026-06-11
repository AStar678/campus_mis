FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY backend/app.py .
COPY frontend/ ./frontend/

# 环境变量：数据库连接本机
ENV DB_HOST=127.0.0.1
ENV DB_PORT=3306
ENV DB_USER=root
ENV DB_PASS=MySQL%402026
ENV FRONTEND_DIR=/app/frontend

EXPOSE 5001

CMD ["python", "app.py"]
