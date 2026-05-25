"""认证服务配置"""
import os


class Config:
    """基础配置"""
    # MySQL 数据库连接
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:Aoxiang050916!@localhost:3306/campus_mis?charset=utf8mb4'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'campus-mis-secret-key-2024')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))

    # 服务配置
    SERVICE_NAME = 'auth-service'
    SERVICE_PORT = int(os.environ.get('AUTH_SERVICE_PORT', 5001))
