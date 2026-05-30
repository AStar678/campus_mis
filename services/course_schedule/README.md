# Course Scheduling Service

选课与智能排课分服务，端口 `5004`。

## 认证方式

用户先在主服务登录获取 token。访问本服务接口时带上：

```http
Authorization: Bearer <token>
```

本服务会调用主服务 `GET /api/verify-token` 校验登录状态。

## 数据表

- `cs_courses`: 课程信息
- `cs_course_requests`: 学生选课申请
- `cs_time_slots`: 可排课时间段
- `cs_schedule_runs`: 智能排课任务记录
- `cs_schedule_results`: 排课结果

公共表 `classrooms`、`buildings`、`building_adjacency` 只读取，不修改。

## 接口

- `GET /api/course-schedule/courses`: 学生/管理员查看课程
- `POST /api/course-schedule/courses`: 管理员新增课程
- `POST /api/course-schedule/requests`: 学生提交选课申请
- `GET /api/course-schedule/my-requests`: 学生查看自己的申请
- `GET /api/course-schedule/requests`: 管理员查看全部申请
- `POST /api/course-schedule/agent/schedule`: 管理员触发智能排课
- `GET /api/course-schedule/results`: 查看排课结果
- `POST /api/course-schedule/results/publish`: 管理员发布排课结果

## 启动

```bash
python services/course_schedule/init_db.py
python services/course_schedule/app.py
```
