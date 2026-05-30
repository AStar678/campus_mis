# 选课与智能排课分服务

本服务负责“选课 & 智能排课系统”，作为独立分服务运行，默认端口 `5004`。

## 认证方式

用户先在主服务登录，拿到主服务返回的 token。访问本服务接口时，在请求头携带：

```http
Authorization: Bearer <token>
```

本服务不会自己登录，会调用主服务：

```http
GET http://127.0.0.1:5001/api/verify-token
```

验证成功后，根据 `user_type` 控制权限。

## 数据库

本服务使用独立业务库：

```text
course_schedule_database
```

业务表统一使用 `cs_` 前缀：

- `cs_courses`: 课程信息
- `cs_course_requests`: 学生选课申请
- `cs_time_slots`: 可排课时间段
- `cs_schedule_runs`: 智能排课任务记录
- `cs_schedule_results`: 排课结果

公共数据仍从主服务数据库只读：

```text
main_database
```

只读取这些公共表，不修改结构：

- `classrooms`
- `buildings`
- `building_adjacency`

建表 SQL 见 `schema.sql`。

## 学生端接口

- `GET /api/course-schedule/courses`: 查看可选课程
- `GET /api/course-schedule/time-slots`: 查看可排课时间段
- `POST /api/course-schedule/requests`: 提交或更新选课申请
- `DELETE /api/course-schedule/requests/<request_id>`: 撤销自己的选课申请
- `GET /api/course-schedule/my-requests`: 查看自己的选课申请
- `GET /api/course-schedule/results`: 查看已发布的个人排课结果

## 管理端接口

- `POST /api/course-schedule/courses`: 新增课程
- `PUT /api/course-schedule/courses/<course_id>`: 修改课程
- `DELETE /api/course-schedule/courses/<course_id>`: 删除课程
- `POST /api/course-schedule/time-slots`: 新增时间段
- `GET /api/course-schedule/requests`: 查看全部选课申请
- `GET /api/course-schedule/schedule-runs`: 查看智能排课运行记录
- `POST /api/course-schedule/agent/schedule`: 触发智能排课
- `GET /api/course-schedule/results`: 查看排课结果
- `POST /api/course-schedule/results/publish`: 发布排课结果

## 智能排课策略

当前版本先实现规则版 Agent，便于演示和后续替换为真实 AI Agent。评分因素包括：

- 学生选课人数和课程容量
- 教室与课程偏好楼栋的距离
- 同一教室同一时间段冲突惩罚
- 每门课生成一条可解释的推荐原因

## 启动

```bash
python services/course_schedule/init_db.py
python services/course_schedule/app.py
```

可通过环境变量覆盖数据库配置：

```bash
COURSE_DB_NAME=course_schedule_database
MAIN_DB_NAME=main_database
MAIN_SERVICE_URL=http://127.0.0.1:5001
```
