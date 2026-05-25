# 校园教务管理 MIS 系统

基于 Flask 微服务架构的学校教务管理系统，采用前后端分离设计（Vue 3 + Flask），支持管理员端和学生端双角色登录。

## 系统架构

```
浏览器 (Vue 3, localhost:3000)
    │
    │  Vite Proxy
    ▼
API Gateway (Flask, localhost:5010)
    │
    ├──→ Auth Service    (Flask, localhost:5001)  认证服务
    ├──→ Student Service (Flask, localhost:5002)  学生管理服务
    └──→ [未来服务...]    (Flask, localhost:500x)  可扩展
```

- **API 网关**：统一入口，负责路由转发、JWT Token 校验、用户信息透传
- **认证服务**：用户登录、Token 签发与验证
- **学生管理服务**：学生信息 CRUD，支持角色权限控制
- **Vue 前端**：管理员端 / 学生端双角色界面

## 项目结构

```
campus_mis/
├── gateway/                     # API 网关服务 (端口 5010)
│   ├── app.py                   # 网关主应用（路由转发 + Token校验）
│   ├── config.py                # 网关配置（服务注册表、路由映射）
│   └── requirements.txt
│
├── services/
│   ├── auth/                    # 认证服务 (端口 5001)
│   │   ├── app.py              # 登录、Token签发/验证
│   │   ├── config.py           # 数据库和JWT配置
│   │   ├── models.py           # User 模型
│   │   └── requirements.txt
│   │
│   └── student/                 # 学生管理服务 (端口 5002)
│       ├── app.py              # 学生 CRUD + 权限控制
│       ├── config.py           # 数据库配置
│       ├── models.py           # Student 模型
│       └── requirements.txt
│
├── frontend/                    # Vue 3 前端
│   ├── src/
│   │   ├── views/
│   │   │   ├── Login.vue       # 登录页（角色分流）
│   │   │   ├── AdminDashboard.vue    # 管理员仪表盘
│   │   │   ├── StudentManage.vue     # 学生管理（管理员）
│   │   │   └── StudentDashboard.vue  # 学生仪表盘
│   │   ├── router/index.js     # 路由配置 + 角色守卫
│   │   ├── api/index.js        # API 封装 + 拦截器
│   │   ├── App.vue
│   │   └── main.js
│   ├── vite.config.js          # Vite 配置（代理到网关）
│   └── package.json
│
├── database/
│   └── init.sql                # 数据库初始化脚本（建表 + 测试数据）
│
├── requirements.txt            # 全局 Python 依赖
├── start_all.sh                # 一键启动脚本
└── README.md
```

## 环境要求

- Python 3.9+
- Node.js 18+
- MySQL 8.0+

## 快速启动

### 1. 初始化数据库

```bash
# 使用你的 MySQL 用户名和密码执行初始化脚本
mysql -u root -p < database/init.sql
```

### 2. 配置数据库连接

修改以下文件中的数据库连接字符串（默认用户名 root）：

- `services/auth/config.py`
- `services/student/config.py`

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://用户名:密码@localhost:3306/campus_mis?charset=utf8mb4'
```

### 3. 安装依赖并启动

**方式一：一键启动**

```bash
chmod +x start_all.sh
./start_all.sh
```

**方式二：手动分别启动**

```bash
# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 启动认证服务
cd services/auth && python app.py &

# 启动学生管理服务
cd services/student && python app.py &

# 启动 API 网关
cd gateway && python app.py &

# 启动前端
cd frontend
npm install
npm run dev
```

### 4. 访问系统

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:3000 |
| API 网关 | http://localhost:5010 |
| 认证服务 | http://localhost:5001 |
| 学生服务 | http://localhost:5002 |

### 5. 测试账号

| 角色 | 用户名 | 密码 | 登录后页面 |
|------|--------|------|-----------|
| 管理员 | admin | admin123 | 管理员仪表盘 |
| 学生 | 2024001 | 123456 | 学生仪表盘（只能看自己） |
| 学生 | 2024002 | 123456 | 学生仪表盘 |
| 学生 | 2024003 | 123456 | 学生仪表盘 |

## API 接口说明

### 认证服务 (/api/auth)

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/auth/login | 用户登录 | 否 |
| GET | /api/auth/verify | 验证 Token | 是 |
| GET | /api/auth/profile | 获取当前用户信息 | 是 |

### 学生管理服务 (/api/students)

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /api/students | 学生列表（分页/搜索） | 仅管理员 |
| GET | /api/students/:id | 获取学生信息 | 管理员或学生本人 |
| POST | /api/students | 新增学生 | 仅管理员 |
| PUT | /api/students/:id | 修改学生信息 | 仅管理员 |
| DELETE | /api/students/:id | 删除学生 | 仅管理员 |

## 如何扩展新的微服务

本系统采用敏捷开发模式，支持快速扩展新功能模块。以新增「课程服务」为例：

### Step 1：创建服务目录

```bash
mkdir -p services/course
```

### Step 2：编写服务代码

```python
# services/course/config.py
class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:密码@localhost:3306/campus_mis?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'campus-mis-secret-key-2024'  # 与其他服务保持一致
    SERVICE_NAME = 'course-service'
    SERVICE_PORT = 5003

# services/course/app.py
from flask import Flask, request, jsonify
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/api/courses', methods=['GET'])
def get_courses():
    # 你的业务逻辑
    pass

@app.route('/api/courses/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': Config.SERVICE_NAME})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=True)
```

### Step 3：在网关注册路由

修改 `gateway/config.py`：

```python
SERVICES = {
    'auth': 'http://localhost:5001',
    'student': 'http://localhost:5002',
    'course': 'http://localhost:5003',  # 新增
}

ROUTE_MAP = {
    '/api/auth': 'auth',
    '/api/students': 'student',
    '/api/courses': 'course',  # 新增
}

PUBLIC_ROUTES = [
    '/api/auth/login',
    '/api/auth/health',
    '/api/students/health',
    '/api/courses/health',  # 新增
]
```

### Step 4：前端对接

在 `frontend/src/api/index.js` 中添加 API 封装：

```javascript
export const courseApi = {
  getList(params) {
    return api.get('/courses', { params })
  },
  // ...
}
```

创建对应的 Vue 页面，并在 `router/index.js` 中注册路由。

### Step 5：启动新服务

```bash
cd services/course && python app.py
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Vue 3 + Vite |
| UI 组件库 | Element Plus |
| HTTP 客户端 | Axios |
| 后端框架 | Flask |
| ORM | Flask-SQLAlchemy |
| 数据库 | MySQL 8.0 |
| 认证方案 | JWT (PyJWT) |
| 密码加密 | bcrypt |
| 服务通信 | HTTP REST (通过 API 网关转发) |

## 设计要点

1. **无状态认证**：使用 JWT Token，各微服务无需共享 Session
2. **网关统一鉴权**：网关校验 Token 后将用户信息通过 X-User-* 请求头传递给下游服务
3. **角色权限控制**：后端接口级别的权限验证（学生只能访问自己的数据）
4. **数据库共享**：当前阶段各服务共享同一 MySQL 数据库，后续可按服务拆分
5. **敏捷扩展**：新增微服务只需 3 步——创建服务、网关注册、前端对接
