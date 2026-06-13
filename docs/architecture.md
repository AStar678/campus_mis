# 系统架构

## 总体结构

校园 MIS 系统采用“主服务 + 微服务”的结构：

- 主服务暴露 `5001` 端口，负责统一登录、Token 签发、Token 校验和服务大厅。
- 每个业务模块作为独立微服务运行在单独端口。
- 用户先登录主服务，再从服务大厅进入业务服务。
- 微服务收到 Token 后，调用主服务 `/api/verify-token` 校验登录态和角色。

```text
浏览器
  ├── 主服务 5001：登录、服务大厅、Token 校验
  └── 校园墙服务 5005：动态发布、帖子浏览、舆情分析、告警处理

校园墙服务 5005
  └── 调用主服务 5001 /api/verify-token 校验 Token
```

## 当前服务

| 服务 | 端口 | 目录 | 数据库 |
| --- | --- | --- | --- |
| 主服务 | `5001` | `main_service/` | `main_database`、`users_database` |
| 校园墙服务 | `5005` | `campus_wall_service/` | `campus_wall_database` |

## 认证流程

1. 用户访问主服务 `5001` 并登录。
2. 主服务校验账号密码，生成 JWT Token，并记录到 `active_sessions`。
3. 用户从服务大厅点击业务模块。
4. 主服务前端打开业务服务地址，并在 URL 中附带 `token`。
5. 业务服务前端读取 `token`，后续请求使用 `Authorization: Bearer <token>`。
6. 业务服务调用主服务 `/api/verify-token` 确认 Token 是否有效。
7. 业务服务根据 `user_type` 控制学生、教师、管理员权限。

## 数据边界

主服务维护公共身份和基础资源：

- `students`
- `teachers`
- `admins`
- `active_sessions`
- `classrooms`
- `buildings`
- `building_adjacency`
- `sub_services`

校园墙服务维护自己的业务数据：

- `wall_posts`
- `wall_alerts`
- `wall_moderation_logs`

业务服务不直接修改主服务用户表，只通过主服务校验身份。

## 端口约定

| 端口 | 用途 |
| --- | --- |
| `5001` | 主服务 |
| `5002` | 教务/成绩服务预留 |
| `5003` | 课堂互动服务预留 |
| `5004` | 选课排课服务预留 |
| `5005` | 校园墙服务 |
