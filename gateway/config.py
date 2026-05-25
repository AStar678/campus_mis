"""API网关配置"""
import os


class Config:
    """网关配置"""
    # JWT 密钥 (与 auth service 一致)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'campus-mis-secret-key-2024')

    # 网关端口
    GATEWAY_PORT = int(os.environ.get('GATEWAY_PORT', 5010))

    # 微服务注册表 (服务名 -> 服务地址)
    SERVICES = {
        'auth': os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001'),
        'student': os.environ.get('STUDENT_SERVICE_URL', 'http://localhost:5002'),
        # 未来新增服务只需在这里添加
        # 'course': os.environ.get('COURSE_SERVICE_URL', 'http://localhost:5003'),
        # 'grade': os.environ.get('GRADE_SERVICE_URL', 'http://localhost:5004'),
    }

    # 路由映射 (URL前缀 -> 服务名)
    ROUTE_MAP = {
        '/api/auth': 'auth',
        '/api/students': 'student',
        # 未来新增路由
        # '/api/courses': 'course',
        # '/api/grades': 'grade',
    }

    # 不需要认证的路由
    PUBLIC_ROUTES = [
        '/api/auth/login',
        '/api/auth/health',
        '/api/students/health',
    ]
