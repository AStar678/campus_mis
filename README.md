# 校园 MIS 系统

本项目采用“主服务 + 业务微服务”的结构。主服务负责统一登录、Token 签发与校验、服务大厅；业务模块作为独立服务运行。

## 项目结构

```text
campus_mis/
├── main_service/              # 主服务，端口 5001
│   ├── backend/
│   ├── frontend/
│   └── README.md
├── campus_wall_service/       # 校园墙微服务，端口 5005
│   ├── backend/
│   ├── frontend/
│   ├── uploads/               # 上传图片目录，已忽略提交
│   └── README.md
└── docs/
    └── architecture.md        # 全局架构说明
```

## 服务说明

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 主服务 | `5001` | 登录、Token 校验、学生/教师/管理员服务大厅 |
| 校园墙服务 | `5005` | 校园动态、图片上传、个人主页、违规删除、舆情趋势和告警 |

## 校园墙功能

- 学生/教师：发布帖子、上传照片、分页浏览、查看详情、个人主页管理本人帖子。
- 管理员：分页查看全部帖子、删除违规帖、填写删除原因。
- 舆情分析：规则版关键词识别，帖子风险显示为 `无风险 / 高风险`。
- 重大舆情告警：每页 3 条，按风险级别优先展示，可标记已处理。

## 本地启动

先安装主服务依赖并启动主服务：

```powershell
pip install -r main_service\backend\requirements.txt
python main_service\backend\app.py
```

再安装校园墙依赖、初始化数据库并启动校园墙服务：

```powershell
pip install -r campus_wall_service\backend\requirements.txt
python campus_wall_service\backend\init_db.py
python campus_wall_service\backend\app.py
```

访问入口：

```text
http://127.0.0.1:5001
```

登录后从服务大厅点击“校园墙”，会跳转到：

```text
http://127.0.0.1:5005/?token=<token>
```

## 数据库

当前默认连接云端 MySQL：

```text
47.93.226.110:3306
```

主要数据库：

| 数据库 | 说明 |
| --- | --- |
| `main_database` | 主服务业务数据 |
| `users_database` | 登录用户数据 |
| `campus_wall_database` | 校园墙帖子、告警和操作日志 |

详细配置可查看各模块 `backend/app.py` 和 `backend/init_db.py` 中的环境变量。

## 测试账号

```text
学生：20240001 / 123456
学生：20240002 / 123456
教师：1001 / 123456
管理员：admin / admin123
```

## 更多文档

- 主服务说明：`main_service/README.md`
- 校园墙说明：`campus_wall_service/README.md`
- 架构说明：`docs/architecture.md`
