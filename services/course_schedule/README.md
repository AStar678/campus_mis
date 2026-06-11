# 选课与智能排课分服务

本服务负责“选课与智能排课系统”，作为独立分服务运行，默认端口为 `5004`。

当前项目主服务已迁移到 `main_service/` 目录。实际使用时，需要同时启动：

- 主服务：`main_service/backend/app.py`，端口 `5001`
- 选课排课分服务：`services/course_schedule/app.py`，端口 `5004`

## 一、运行方式

在项目根目录执行：

```powershell
cd D:\数据库系统实训\MIS\campus_mis
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 1. 启动主服务

打开第一个终端：

```powershell
python main_service\backend\app.py
```

主服务访问地址：

```text
http://127.0.0.1:5001
```

### 2. 初始化并启动选课排课分服务

打开第二个终端，同样进入项目根目录并激活虚拟环境后执行：

```powershell
python services\course_schedule\init_db.py
python services\course_schedule\app.py
```

分服务地址：

```text
http://127.0.0.1:5004
```

注意：`5004` 现在同时提供分服务页面和接口。从主服务大厅点击“选课系统”后，会跳转到 `http://127.0.0.1:5004/?token=...`。

可通过健康检查确认服务是否启动成功：

```text
http://127.0.0.1:5004/api/course-schedule/health
```

## 二、登录与入口

浏览器打开主服务：

```text
http://127.0.0.1:5001
```

学生登录后，在服务大厅点击：

```text
选课系统
```

管理员登录后，在服务大厅点击：

```text
选课管理
```

主服务会跳转到 `5004` 分服务，并携带登录 token。

常用测试账号：

```text
学生：20240001 / 123456
学生：20240002 / 123456
管理员：admin / admin123
```

说明：

- 学生端：查看可选课程、提交选课申请、撤销申请、查看本人申请、查看已发布排课结果。
- 管理端：新增/删除课程、新增时间段、查看全部申请、触发智能排课、发布排课结果。
- 教师端：当前不参与选课排课模块。

## 三、认证方式

用户先在主服务登录，获取主服务返回的 token。

访问本服务接口时，需要携带：

```http
Authorization: Bearer <token>
```

本服务不单独实现登录逻辑，而是调用主服务校验 token：

```http
GET http://127.0.0.1:5001/api/verify-token
```

校验成功后，根据 `user_type` 控制接口权限。

## 四、数据库说明

本服务使用独立业务库：

```text
course_schedule_database
```

业务表统一使用 `cs_` 前缀：

- `cs_courses`：课程信息
- `cs_course_requests`：学生选课申请
- `cs_time_slots`：可排课时间段
- `cs_schedule_runs`：智能排课任务记录
- `cs_schedule_results`：排课结果

公共数据仍从主服务数据库只读获取：

```text
main_database
```

只读取以下公共表，不修改其结构：

- `classrooms`
- `buildings`
- `building_adjacency`

建表 SQL 见：

```text
services/course_schedule/schema.sql
```

## 五、学生端接口

- `GET /api/course-schedule/courses`：查看可选课程
- `GET /api/course-schedule/time-slots`：查看可排课时间段
- `POST /api/course-schedule/requests`：提交或更新选课申请
- `DELETE /api/course-schedule/requests/<request_id>`：撤销自己的选课申请
- `GET /api/course-schedule/my-requests`：查看自己的选课申请
- `GET /api/course-schedule/results`：查看已发布的个人排课结果

## 六、管理端接口

- `POST /api/course-schedule/courses`：新增课程
- `PUT /api/course-schedule/courses/<course_id>`：修改课程
- `DELETE /api/course-schedule/courses/<course_id>`：删除课程
- `POST /api/course-schedule/time-slots`：新增时间段
- `GET /api/course-schedule/requests`：查看全部选课申请
- `GET /api/course-schedule/schedule-runs`：查看智能排课运行记录
- `POST /api/course-schedule/agent/schedule`：触发智能排课
- `GET /api/course-schedule/results`：查看排课结果
- `POST /api/course-schedule/results/publish`：发布排课结果

## 七、智能排课策略

当前版本先实现规则版 Agent，便于演示和后续替换为真正的 MCP/AI Agent。

评分因素包括：

- 学生选课人数
- 课程容量
- 教室与课程偏好楼栋的距离
- 同一教室同一时间段冲突惩罚
- 每门课生成一条可解释的推荐原因

后续接入 MCP 框架时，可复用当前接口：

```text
POST /api/course-schedule/agent/schedule
```

推荐改造方向：

```text
收集排课上下文 -> 调用 MCP/AI Agent -> 保存排课结果 -> 管理员审核发布
```

## 八、课程分类与选课意向规则

当前版本不修改数据库表结构，课程分类由前端根据课程编号和课程名称推断：

- `PUB` 开头，或课程名包含“公共、体育、英语、思政”：公共课。
- `REQ` 开头，或课程名包含“必修、基础”：必修课。
- 其他课程：专业选修课。

学生端会提示：

- 必修课属于培养方案保障课程，不参与学生意向排序。
- 专业选修课和公共课可提交第一、第二、第三意向。
- 同一学生的第一、第二、第三意向各只能对应 1 门有效课程。
- 建议不要超过当前设置的最大意向数量。
- 超容量课程会提示增加备选课程。

管理端可以从“学生画像”和“需求分析”查看哪些学生缺少第一意向、哪些课程需求过热、哪些课程需要扩容或加开平行班。

说明：真实教务系统里，更完整的模型通常是“一门课程下有多个教学班/教师/时间段，学生对不同教学班填报志愿”。当前数据库暂未设计教学班表，因此本版本先把 `preference_level` 解释为选修课和公共课的选课意向优先级，避免把专业必修课误做成抢课志愿。

## 九、常见问题

### 1. 应该从哪里进入选课系统？

推荐从主服务进入：

```text
http://127.0.0.1:5001
```

登录后点击“选课系统”，主服务会自动跳转到 `5004` 并携带 token。

### 2. 学生端看不到课程怎么办？

检查：

- 是否启动了主服务 `5001`
- 是否启动了分服务 `5004`
- 是否执行过 `init_db.py`
- 管理端是否已经创建课程

### 3. 点击选课系统没反应怎么办？

确认 `services/course_schedule/app.py` 正在运行，并检查浏览器地址是否跳转到：

```text
http://127.0.0.1:5004?token=...
```
