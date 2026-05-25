"""认证服务 - 数据模型"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('student', 'teacher', 'admin'), nullable=False)
    ref_id = db.Column(db.String(50), default=None)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'ref_id': self.ref_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
