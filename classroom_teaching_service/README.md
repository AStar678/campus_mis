# 课堂教学子服务

独立微服务模块，不修改主服务代码。覆盖学生端、教师端、管理端，并提供 DDL 管理、DeepSeek AI 阅卷和教学统计 Agent 能力。

## 功能范围

- 教师端：查看自己负责几门课、总学分、已发布作业、待复核提交；发布作业/公告，AI 按小题批改，教师批准后自动更新学生成绩。
- 学生端：查看课程名称、上课时间、地点、老师、学分、授课语言、必修/选修、授课方式；支持按关键词、必修/选修、语言、授课方式筛选；提交作业并查看成绩。
- 管理端：课程新增、删除、修改，分配授课教师，维护学分、地点、语言、类型、授课方式等字段。
- AI Agent：基于数据库统计课程平均分、不及格人数、提交情况等，调用 DeepSeek 生成自然语言分析。

## 启动

```bash
cd classroom_teaching_service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

默认访问：`http://127.0.0.1:5003`

演示账号：

- 学生：`20240001` / `123456`
- 教师：`1001` / `123456`
- 管理员：`admin` / `admin123`

## DeepSeek 配置

请在 `.env` 或系统环境变量中设置：

```bash
DEEPSEEK_API_KEY=你的密钥
```

不要把真实密钥提交到仓库。服务启动时会自动读取 `classroom_teaching_service/.env`，如果未配置 DeepSeek 密钥，则使用本地规则给出可复核初评。

PDF 文本解析依赖 `PyMuPDF`。如果环境没有安装，也不影响发布作业和文本答案 AI 批改；安装 `requirements.txt` 后可自动解析上传的 PDF。

## 主服务跳转

本模块不改主服务。主服务中的“课堂教学”卡片后续只需跳转到：

```text
http://课堂教学服务IP:5003
```

如需共用主服务登录态，可在跳转时追加 `?token=...&role=student`，本服务已预留本地登录和独立演示账号。
