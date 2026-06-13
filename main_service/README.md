# 主服务

主服务是校园 MIS 的统一入口，默认运行在 `5001` 端口。它负责用户登录、Token 签发、Token 校验和服务大厅跳转。

## 目录结构

```text
main_service/
├── backend/
│   ├── app.py              # Flask 主服务入口
│   ├── init_db.py          # 主服务数据库初始化脚本
│   ├── requirements.txt    # 主服务依赖
│   └── schema.sql          # 主服务数据库结构
├── frontend/
│   └── index.html          # 登录页和服务大厅
├── Dockerfile              # 主服务容器配置
├── deploy.exp              # 服务器部署辅助脚本
└── README.md               # 当前文档
```

## 职责

- 学生、教师、管理员登录。
- 生成 JWT Token，并记录当前登录会话。
- 提供 `/api/verify-token` 给微服务校验登录态。
- 提供服务大厅，按角色展示可进入的微服务。
- 维护基础信息：学生、教师、管理员、教室、楼栋、服务注册。

## 本地运行

安装依赖：

```powershell
pip install -r main_service\backend\requirements.txt
```

启动主服务：

```powershell
python main_service\backend\app.py
```

访问地址：

```text
http://127.0.0.1:5001
```

健康检查：

```text
http://127.0.0.1:5001/api/health
```

## 微服务跳转

登录成功后，前端会把主服务 Token 作为查询参数传给微服务：

```text
http://<host>:<service_port>/?token=<token>
```

当前主服务大厅包含：

- 学生端：选课系统、成绩查询、课堂互动、校园墙。
- 教师端：课程管理、成绩管理、课堂管理、校园墙。
- 管理端：用户管理、教室管理、服务管理、数据统计、校园墙。

## 对外接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/login` | 登录并签发 Token |
| `POST` | `/api/logout` | 登出并清理会话 |
| `GET` | `/api/verify-token` | 给微服务校验 Token |
| `GET` | `/api/user-info` | 查询当前用户信息 |
| `GET` | `/api/services` | 查询服务注册列表 |
| `GET` | `/api/buildings` | 查询楼栋信息 |
| `GET` | `/api/campus-map` | 查询校园地图数据 |
| `GET` | `/api/classrooms` | 查询教室信息 |
| `GET` | `/api/health` | 健康检查 |

## 服务器部署提示

服务器上建议分别启动主服务和各微服务。主服务启动示例：

```bash
cd /root/MIS2
DB_HOST=127.0.0.1 FRONTEND_DIR=/root/MIS2/main_service/frontend \
nohup python3 main_service/backend/app.py > /root/MIS2/main_service.log 2>&1 &
```

验证：

```bash
curl http://127.0.0.1:5001/api/health
```
