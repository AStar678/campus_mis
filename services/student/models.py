"""学生管理服务 - 数据模型"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Student(db.Model):
    """学生模型"""
    __tablename__ = 'students'

    student_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.Enum('男', '女'), default='男')
    college = db.Column(db.String(100))
    major = db.Column(db.String(100))
    class_name = db.Column(db.String(100))
    gpa = db.Column(db.Numeric(3, 2), default=0.00)
    enrollment_year = db.Column(db.Integer)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'student_id': self.student_id,
            'name': self.name,
            'gender': self.gender,
            'college': self.college,
            'major': self.major,
            'class_name': self.class_name,
            'gpa': float(self.gpa) if self.gpa else 0.00,
            'enrollment_year': self.enrollment_year,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
