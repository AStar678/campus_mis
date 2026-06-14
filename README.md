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
├── services/
│   └── course_schedule/       # 选课与智能排课微服务，端口 5004
│       ├── backend/
│       ├── frontend/
│       └── README.md
└── docs/
    └── architecture.md        # 全局架构说明
```

## 服务说明

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 主服务 | `5001` | 登录、Token 校验、学生/教师/管理员服务大厅 |
| 校园墙服务 | `5005` | 校园动态、图片上传、个人主页、违规删除、舆情趋势和告警 |
| 选课与排课服务 | `5004` | 学生选课意向、智能排课、需求分析、教师与管理员工作台 |

## 校园墙功能

- 学生/教师：发布帖子、上传照片、分页浏览、查看详情、个人主页管理本人帖子。
- 管理员：分页查看全部帖子、删除违规帖、填写删除原因。
- 舆情分析：规则版关键词识别，帖子风险显示为 `无风险 / 高风险`。
- 重大舆情告警：每页 3 条，按风险级别优先展示，可标记已处理。

## 选课与排课功能

### 学生端
- **选课意向提交**：浏览可选课程、提交最多3个意向、学分上下限推荐提示
- **选课体检**：校验学分范围、意向数量、专业年级匹配提示
- **个人课表**：查看排课结果（表格与周课表两个视图）、新增并排课候补

### 教师端
- **教学班管理**：查看负责教学班信息、维护不可用时间段
- **学生报名**：查看每个教学班的学生名单（按意向优先级排序）、支持CSV导出
- **排课结果**：查看本人教学班的最终排课方案（教室、时间、学生人数）

### 管理员端
- **课程供给管理**：新增/编辑/删除课程信息和教学班
- **学生意向分析**：实时统计课程热度、超容量预警、课程均衡度
- **智能排课执行**：触发Agent规则版排课（考虑容量、热度、楼栋距离、时间冲突等）、人工调整结果、发布到学生端
- **选课批次配置**：管理选课阶段（预选→正式→排课→补退→确认→关闭）、时间窗口、学分限制、公告

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

启动选课与排课微服务：

```powershell
pip install -r services\course_schedule\requirements.txt
python services\course_schedule\init_db.py
python services\course_schedule\app.py
```

访问入口：

```text
http://127.0.0.1:5001
```

登录后从服务大厅点击“校园墙”，会跳转到：

```text
http://127.0.0.1:5005/?token=<token>
```
登录后从服务大厅点击"选课系统"，会跳转到：

```text
http://127.0.0.1:5004/?token=<token>
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
| `course_schedule_database` | 选课申请、课程供给、排课结果、批次配置 |

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
- 选课排课说明：`services/course_schedule/README.md`
- 架构说明：`docs/architecture.md`
