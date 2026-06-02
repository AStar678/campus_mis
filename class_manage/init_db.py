import pymysql
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# ============ 数据库基础配置 ============
DB_HOST = os.environ.get('DB_HOST', '47.93.226.110')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', 'MySQL%402026') # 对密码中的@进行URL编码

app = Flask(__name__)
# 配置连接到专属的课堂教学服务数据库 classroom_database
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/classroom_database'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============ 课堂教学系统 - 数据模型 ============

class Course(db.Model):
    """
    课程主表
    存储管理端创建的课程元数据，并关联授课教师
    """
    __tablename__ = 'courses'
    # 添加表级注释
    __table_args__ = {'comment': '课程信息主表，存储课程基本元数据'}
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='课程自增唯一标识ID')
    name = db.Column(db.String(100), nullable=False, comment='课程名称(如: 深度学习基础)')
    teacher_id = db.Column(db.String(20), nullable=False, comment='授课教师工号(跨库关联users_database中的teachers表)')
    description = db.Column(db.String(500), comment='课程详细描述或教学大纲')


class CourseStudent(db.Model):
    """
    课程-学生关系表（选课/排课映射）
    实现课程与学生的多对多关联
    """
    __tablename__ = 'course_students'
    __table_args__ = {'comment': '学生选课关系表，维护学生与课程的修读映射'}
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='关系表自增ID')
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, comment='关联的课程ID')
    student_id = db.Column(db.String(20), nullable=False, comment='学生学号(跨库关联users_database中的students表)')


class Announcement(db.Model):
    """
    课堂公告表
    教师发布的课堂通知，属于某一门特定课程
    """
    __tablename__ = 'announcements'
    __table_args__ = {'comment': '课堂公告表，存储教师发布的课程通知'}
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='公告自增ID')
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, comment='所属课程ID')
    title = db.Column(db.String(100), nullable=False, comment='公告标题')
    content = db.Column(db.Text, comment='公告正文内容')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='公告发布时间')


class Homework(db.Model):
    """
    作业及DDL发布表
    核心DDL管理系统的基础数据源
    """
    __tablename__ = 'homeworks'
    __table_args__ = {'comment': '作业发布表，包含作业要求及截止时间(DDL)'}
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='作业自增ID')
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False, comment='所属课程ID')
    title = db.Column(db.String(100), nullable=False, comment='作业题目')
    description = db.Column(db.Text, comment='作业具体要求与描述')
    deadline = db.Column(db.DateTime, nullable=False, comment='截止提交时间(核心DDL时间戳)')


class Submission(db.Model):
    """
    学生作业提交及批改流水表
    承载学生在线提交内容、AI预评分结果以及教师最终审核成绩
    """
    __tablename__ = 'submissions'
    __table_args__ = {'comment': '学生作业提交记录与成绩流水表(包含AI批改与教师最终成绩)'}
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='提交流水自增ID')
    homework_id = db.Column(db.Integer, db.ForeignKey('homeworks.id'), nullable=False, comment='关联的作业ID')
    student_id = db.Column(db.String(20), nullable=False, comment='提交作业的学生学号')
    content = db.Column(db.Text, nullable=False, comment='学生提交的文本内容、解答或代码片段')
    submit_time = db.Column(db.DateTime, default=datetime.now, comment='学生实际提交时间')
    ai_score = db.Column(db.Float, comment='AI大模型给出的预判分数(0-100)')
    ai_comment = db.Column(db.Text, comment='AI自动生成的诊断性评语')
    final_score = db.Column(db.Float, comment='教师查阅或调整后的最终录入成绩')


# ============ 数据库环境自动初始化逻辑 ============

def init_database_environment():
    """
    连接云端MySQL服务器，确保目标物理库存在，随后创建带有完整结构注释的表
    """
    # 1. 建立裸连接（不指定具体数据库），用于执行创建库操作
    print(f"正在连接云端数据库服务器: {DB_HOST}...")
    conn = pymysql.connect(
        host=DB_HOST, 
        port=DB_PORT, 
        user=DB_USER, 
        password='MySQL@2026', # 此处传入原始未编码的密码
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # 创建独立的子服务物理库
    cursor.execute("CREATE DATABASE IF NOT EXISTS classroom_database DEFAULT CHARACTER SET utf8mb4")
    conn.close()
    print("-> 物理库 classroom_database 校验/创建成功")

    # 2. 进入 Flask 上下文，利用 SQLAlchemy 映射建立带有 COMMENT 注释的表结构
    with app.app_context():
        # 如果需要彻底重建表，可取消下行的注释：
        # db.drop_all()
        db.create_all()
        print("-> 课堂教学服务相关表结构（包含表/字段级注释）已成功同步至云端")

        # 3. 构造基础测试数据（仅在空库时注入）
        if not Course.query.first():
            print("正在注入初始测试数据...")
            
            # 创建演示课程
            demo_course = Course(
                name='人工智能导论与实践', 
                teacher_id='1001', # 关联主库中已有的教师工号
                description='本课程探讨基础机器学习算法与深度学习序列建模。'
            )
            db.session.add(demo_course)
            db.session.flush() # 提前获取自增出的 course.id
            
            # 为该课程绑定测试学生
            db.session.add(CourseStudent(course_id=demo_course.id, student_id='20240001'))
            
            # 发布初始公告
            db.session.add(Announcement(course_id=demo_course.id, title='开课通知', content='请同学们准时登录系统查看后续作业的DDL。'))
            
            # 发布一项带有明确 DDL 的作业
            future_ddl = datetime(2026, 6, 30, 23, 59, 59)
            db.session.add(Homework(
                course_id=demo_course.id,
                title='Lab 1: 神经网络基础组件实现',
                description='请在线提交单层感知机的前向传播核心代码。',
                deadline=future_ddl
            ))
            
            db.session.commit()
            print("-> 初始测试数据及DDL任务注入完成！")

if __name__ == '__main__':
    init_database_environment()