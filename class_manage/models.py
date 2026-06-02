from extensions import db
from datetime import datetime

class Course(db.Model):
    __tablename__ = 'courses'
    __table_args__ = {'comment': '课程信息主表'}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(500))

class CourseStudent(db.Model):
    __tablename__ = 'course_students'
    __table_args__ = {'comment': '学生选课关系表及期末总评成绩'}
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.String(20), nullable=False)
    final_grade = db.Column(db.Float, comment='期末总评成绩(由教师录入)') # 新增的期末成绩字段

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Homework(db.Model):
    __tablename__ = 'homeworks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=False)

class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    homework_id = db.Column(db.Integer, db.ForeignKey('homeworks.id'), nullable=False)
    student_id = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    submit_time = db.Column(db.DateTime, default=datetime.now)
    ai_score = db.Column(db.Float)
    ai_comment = db.Column(db.Text)
    final_score = db.Column(db.Float)