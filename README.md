# 校园 MIS 系统

## 云端服务

- IP: `47.93.226.110`
- 服务端口: `5001`
- 项目路径: `/root/MIS2`
- 访问地址: `http://47.93.226.110:5001`

http://47.93.226.110:5001/

## 本地运行

```bash
# 主服务（端口 5001）
pip install -r main_service/backend/requirements.txt
python main_service/backend/app.py

# 课堂管理服务（端口 5003）
pip install -r classroom_teaching_service/requirements.txt
python classroom_teaching_service/app.py

# 选课排课服务（端口 5004）
python course_schedule_service/app.py

# 校园墙服务（端口 5005）
pip install -r campus_wall_service/backend/requirements.txt
python campus_wall_service/backend/app.py

# 信息查询服务（端口 5005）
pip install -r query_service/backend/requirements.txt
python query_service/backend/app.py
```

访问入口：http://127.0.0.1:5001

## 测试账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 学生 | 20240001 | 123456 |
| 教师 | 1001 | 123456 |
| 管理员 | admin | admin123 |
