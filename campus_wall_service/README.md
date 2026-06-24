# 校园墙服务

`campus_wall_service` 是校园 MIS 中独立拆出的校园墙微服务，默认运行在 `5005` 端口。服务本身不负责登录，用户从主服务大厅进入校园墙时携带 token，校园墙后端会调用主服务 `/api/verify-token` 完成身份校验。

## 模块结构

```text
campus_wall_service/
├── backend/
│   ├── app.py              # Flask API 服务入口，端口 5005
│   ├── init_db.py          # 初始化数据库，并对旧表做兼容迁移
│   ├── requirements.txt    # 校园墙服务独立依赖
│   └── schema.sql          # campus_wall_database 表结构
├── frontend/
│   └── index.html          # Vue 3 CDN 单页前端
└── uploads/                # 上传图片保存目录，已在 .gitignore 中忽略
```

## 当前功能

- 学生端
  - 发布校园动态。
  - 浏览校园动态，首页每页 10 条。
  - 按关键词、作者类型筛选帖子。
  - 点击帖子查看详情。
  - 发布和更新帖子时支持上传照片。
  - 个人主页查看本人帖子，并可编辑或删除正常状态帖子。

- 教师端
  - 与学生端一致：发布、浏览、筛选、查看详情、上传照片、个人主页管理本人帖子。

- 管理端
  - 分页查看全部帖子，首页每页 10 条。
  - 查看正常和已删除帖子。
  - 按关键词、作者类型、帖子状态、风险等级筛选。
  - 删除违规帖子并填写删除原因。
  - 查看舆情趋势统计。
  - 查看重大舆情告警，告警每页 3 条，按风险级别优先展示。
  - 标记告警为已处理。

## 数据库说明

校园墙使用独立数据库：

```text
campus_wall_database
```

包含三张业务表：

| 表名 | 说明 |
| --- | --- |
| `wall_posts` | 校园墙帖子，包含作者、内容、状态、风险等级、图片路径、删除信息 |
| `wall_alerts` | 舆情告警，包含告警类型、级别、关键词、处理状态 |
| `wall_moderation_logs` | 管理员删除违规帖的操作日志 |

帖子删除采用软删除：

- `status = active`：正常。
- `status = deleted`：已删除。
- 删除后保留帖子内容、删除人、删除时间和删除原因，便于审计和趋势统计。

风险等级采用后端枚举值：

- `normal`：前端显示为 `无风险`。
- `high`：前端显示为 `高风险`。

## 图片上传

帖子图片不会直接存入数据库。

当前实现是：

1. 图片文件保存到本地目录 `campus_wall_service/uploads/`。
2. 数据库 `wall_posts.image_paths` 字段保存图片相对路径 JSON。
3. 前端通过 `/uploads/<path>` 访问图片。

限制：

- 每条帖子最多上传 `3` 张图片。
- 单张图片默认最大 `5MB`。
- 支持格式：`jpg`、`jpeg`、`png`、`gif`、`webp`。

## 智能分析和告警

当前没有接入真实外部 AI，采用可演示、可解释的规则版分析。

### 高风险关键词告警

学生或教师发布、更新帖子时，后端会扫描标题和内容。命中高风险关键词后：

- 帖子风险等级设为 `high`。
- 写入一条 `critical` 告警。
- 管理端显示为重大告警。

当前高风险关键词包括：

```text
打架、霸凌、欺凌、自杀、跳楼、诈骗、火灾、爆炸、食物中毒、泄露、谣言、暴力、失踪、群体事件
```

### 趋势波动告警

如果近 24 小时内同一个关注关键词出现次数达到阈值，会生成趋势告警：

- 告警类型：`trend_spike`
- 告警级别：`warning`
- 默认阈值：`TREND_ALERT_THRESHOLD=3`

### 告警展示优先级

管理端“重大舆情告警”按以下顺序展示：

1. `critical` 重大告警优先。
2. `warning` 关注告警其次。
3. 同一风险级别内按创建时间倒序。

告警列表每页显示 3 条。

## 本地运行

建议先启动主服务，再启动校园墙服务。

### 1. 安装依赖

```powershell
pip install -r campus_wall_service\backend\requirements.txt
```

### 2. 初始化或迁移数据库

```powershell
python campus_wall_service\backend\init_db.py
```

`init_db.py` 会执行 `schema.sql`，并对旧版本表结构做兼容迁移。

### 3. 启动校园墙服务

```powershell
python campus_wall_service\backend\app.py
```

服务地址：

```text
http://127.0.0.1:5005
```

健康检查：

```text
http://127.0.0.1:5005/api/wall/health
```

从主服务进入时，主服务会跳转到：

```text
http://<host>:5005/?token=<token>
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_HOST` | `127.0.0.1` | MySQL 地址 |
| `DB_PORT` | `3306` | MySQL 端口 |
| `DB_USER` | `root` | MySQL 用户名 |
| `DB_PASS` | 空 | URL 编码后的 MySQL 密码，通过环境变量配置 |
| `DB_PASS_RAW` | 从 `DB_PASS` 解码 | 原始 MySQL 密码，优先用于连接数据库 |
| `WALL_DB_NAME` | `campus_wall_database` | 校园墙数据库名 |
| `MAIN_SERVICE_URL` | `http://127.0.0.1:5001` | 主服务地址 |
| `VERIFY_TOKEN_URL` | `${MAIN_SERVICE_URL}/api/verify-token` | token 校验接口 |
| `FRONTEND_DIR` | `campus_wall_service/frontend` | 前端页面目录 |
| `UPLOAD_DIR` | `campus_wall_service/uploads` | 图片上传保存目录 |
| `TREND_ALERT_THRESHOLD` | `3` | 24 小时内关键词趋势告警阈值 |
| `MAX_IMAGES_PER_POST` | `3` | 每条帖子最多上传图片数 |
| `MAX_IMAGE_SIZE` | `5242880` | 单张图片最大字节数，默认 5MB |
| `FLASK_DEBUG` | 空 | 设置为 `1` 时开启 Flask debug |

## API 概览

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/` | 学生/教师/管理员 | 返回校园墙前端页面 |
| `GET` | `/uploads/<path>` | 学生/教师/管理员 | 访问已上传图片 |
| `GET` | `/api/wall/health` | 无 | 健康检查 |
| `GET` | `/api/wall/me` | 学生/教师/管理员 | 查询当前用户 |
| `GET` | `/api/wall/posts` | 学生/教师/管理员 | 分页浏览帖子 |
| `GET` | `/api/wall/posts/<id>` | 学生/教师/管理员 | 查看帖子详情 |
| `POST` | `/api/wall/posts` | 学生/教师 | 发布帖子，支持 `multipart/form-data` 上传照片 |
| `PUT` | `/api/wall/posts/<id>` | 学生/教师 | 更新本人发布的正常状态帖子 |
| `DELETE` | `/api/wall/posts/<id>` | 学生/教师/管理员 | 学生/教师删除本人帖子；管理员删除违规帖子 |
| `GET` | `/api/wall/analysis/trends` | 管理员 | 查看舆情趋势 |
| `GET` | `/api/wall/analysis/alerts` | 管理员 | 分页查看舆情告警，按风险级别优先排序 |
| `POST` | `/api/wall/analysis/alerts/<id>/handle` | 管理员 | 标记告警已处理 |

## 常用接口参数

### `GET /api/wall/posts`

| 参数 | 说明 |
| --- | --- |
| `page` | 页码，默认 `1` |
| `page_size` | 每页数量，默认 `10`，最大 `50` |
| `keyword` | 搜索标题或内容 |
| `author_type` | 作者类型：`student`、`teacher` |
| `status` | 帖子状态：`active`、`deleted` |
| `risk_level` | 风险等级：`normal`、`high` |
| `mine` | 学生/教师查看本人帖子时传 `true` |
| `include_deleted` | 管理员查看已删除帖子时传 `true` |

返回结构：

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 0,
    "total_pages": 1,
    "has_prev": false,
    "has_next": false
  }
}
```

### `GET /api/wall/analysis/alerts`

| 参数 | 说明 |
| --- | --- |
| `page` | 页码，默认 `1` |
| `page_size` | 每页数量，默认 `3`，最大 `50` |
| `status` | 告警状态：`pending`、`handled` |
| `alert_level` | 告警级别：`critical`、`warning` |

返回结构：

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 3,
    "total": 0,
    "total_pages": 1,
    "has_prev": false,
    "has_next": false
  }
}
```

## 权限规则

| 操作 | 学生 | 教师 | 管理员 |
| --- | --- | --- | --- |
| 浏览正常帖子 | 支持 | 支持 | 支持 |
| 发布帖子 | 支持 | 支持 | 不支持 |
| 查看本人主页 | 支持 | 支持 | 不支持 |
| 编辑本人帖子 | 支持 | 支持 | 不支持 |
| 删除本人帖子 | 支持 | 支持 | 不支持 |
| 查看全部帖子和已删除帖子 | 不支持 | 不支持 | 支持 |
| 删除违规帖子 | 不支持 | 不支持 | 支持 |
| 查看趋势和告警 | 不支持 | 不支持 | 支持 |
| 处理告警 | 不支持 | 不支持 | 支持 |

## 验证建议

```powershell
python -c "import ast, pathlib; ast.parse(pathlib.Path('campus_wall_service/backend/app.py').read_text(encoding='utf-8')); print('backend syntax ok')"
python -c "import ast, pathlib; ast.parse(pathlib.Path('campus_wall_service/backend/init_db.py').read_text(encoding='utf-8')); print('init_db syntax ok')"
```

功能验证：

- 学生或教师发布普通帖子，首页能分页展示。
- 学生或教师上传图片后，详情页能看到图片。
- 学生或教师进入“我的主页”，能查看、编辑、删除本人帖子。
- 管理员能分页查看帖子，并删除违规帖。
- 发布包含 `诈骗`、`火灾`、`霸凌` 等关键词的帖子后，管理端能看到重大舆情告警。
- 告警列表每页 3 条，重大告警优先展示。
