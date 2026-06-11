# 主服务部署与重启教程

## 服务器信息

- IP: `47.93.226.110`
- 服务端口: `5001`
- 项目路径: `/root/MIS2`
- 访问地址: `http://47.93.226.110:5001`

## 重启主服务

SSH 登录服务器后执行：

```bash
# 1. 停止旧进程
pkill -f 'python3 app.py'

# 2. 启动服务
cd /root/MIS2/backend
DB_HOST=127.0.0.1 FRONTEND_DIR=/root/MIS2/frontend nohup python3 app.py > /root/MIS2/app.log 2>&1 &

# 3. 验证是否启动成功
sleep 2 && curl -s http://127.0.0.1:5001/api/health
```

返回 `{"status":"ok",...}` 即表示启动成功。

## 更新代码后重启

在本地修改代码后，执行以下步骤：

```bash
# 1. 本地打包
cd /Users/aoxiang/Desktop/校园MIS/MIS2
tar czf /tmp/mis2.tar.gz Dockerfile .dockerignore backend/app.py backend/requirements.txt frontend/index.html

# 2. 上传到服务器
scp /tmp/mis2.tar.gz root@47.93.226.110:/root/mis2.tar.gz

# 3. SSH 登录服务器
ssh root@47.93.226.110

# 4. 解压并重启
cd /root
rm -rf MIS2 && mkdir MIS2 && tar xzf mis2.tar.gz -C MIS2
pkill -f 'python3 app.py'
cd /root/MIS2/backend
DB_HOST=127.0.0.1 FRONTEND_DIR=/root/MIS2/frontend nohup python3 app.py > /root/MIS2/app.log 2>&1 &
```

## 查看日志

```bash
tail -f /root/MIS2/app.log
```

## 检查服务状态

```bash
# 查看进程
ps aux | grep app.py

# 健康检查
curl http://127.0.0.1:5001/api/health
```
