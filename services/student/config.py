"""学生管理服务配置"""
import os


class Config:
    """基础配置"""
    # MySQL 数据库连接
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:Aoxiang050916!@localhost:3306/campus_mis?charset=utf8mb4'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT 密钥 (需要与 auth service 保持一致，用于验证token)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'campus-mis-secret-key-2024')

    # 服务配置
    SERVICE_NAME = 'student-service'
    SERVICE_PORT = int(os.environ.get('STUDENT_SERVICE_PORT', 5002))
