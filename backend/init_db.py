"""
Database initialization script.

Usage:
    python init_db.py

The script creates tables for all configured SQLAlchemy binds and inserts a
small demo dataset for the classroom teaching system.
"""
from app import (
    app,
    db,
    Admin,
    Assignment,
    Building,
    BuildingAdjacency,
    Classroom,
    ClassroomAnnouncement,
    Course,
    CourseEnrollment,
    Student,
    SubService,
    Teacher,
    hash_password,
)


def init_tables():
    with app.app_context():
        db.create_all(bind_key=None)
        db.create_all(bind_key='users')
        print("Tables are ready.")


def insert_test_data():
    with app.app_context():
        if not Student.query.filter_by(student_id='20240001').first():
            db.session.add_all([
                Student(student_id='20240001', password=hash_password('123456'), grade='2024', major='计算机科学'),
                Student(student_id='20240002', password=hash_password('123456'), grade='2024', major='软件工程'),
                Student(student_id='20230001', password=hash_password('123456'), grade='2023', major='软件工程'),
            ])

        if not Teacher.query.filter_by(teacher_id='1001').first():
            db.session.add_all([
                Teacher(teacher_id='1001', password=hash_password('123456'), college='计算机学院', title='教授'),
                Teacher(teacher_id='1002', password=hash_password('123456'), college='计算机学院', title='副教授'),
            ])

        if not Admin.query.filter_by(admin_id='admin').first():
            db.session.add(Admin(admin_id='admin', password=hash_password('admin123'), name='系统管理员'))

        if not Classroom.query.filter_by(classroom_id='A101').first():
            db.session.add_all([
                Classroom(classroom_id='A101', building='1号楼'),
                Classroom(classroom_id='A201', building='1号楼'),
                Classroom(classroom_id='B101', building='2号楼'),
            ])

        if not Building.query.first():
            db.session.add_all([
                Building(building_name='1号楼'),
                Building(building_name='2号楼'),
                Building(building_name='图书馆'),
                Building(building_name='食堂'),
                Building(building_name='体育馆'),
            ])
            db.session.flush()
            db.session.add_all([
                BuildingAdjacency(building_a=1, building_b=2, distance=200.0),
                BuildingAdjacency(building_a=1, building_b=3, distance=350.0),
                BuildingAdjacency(building_a=2, building_b=3, distance=250.0),
                BuildingAdjacency(building_a=1, building_b=4, distance=400.0),
                BuildingAdjacency(building_a=2, building_b=4, distance=300.0),
                BuildingAdjacency(building_a=3, building_b=4, distance=150.0),
                BuildingAdjacency(building_a=4, building_b=5, distance=200.0),
                BuildingAdjacency(building_a=3, building_b=5, distance=500.0),
            ])

        if not SubService.query.filter_by(service_port=5003).first():
            db.session.add_all([
                SubService(service_name='教务服务', service_ip='127.0.0.1', service_port=5002, description='课程管理、成绩管理、学分计算'),
                SubService(service_name='课堂教学服务', service_ip='127.0.0.1', service_port=5003, description='作业发布、课堂公告、AI批改'),
                SubService(service_name='选课排课服务', service_ip='127.0.0.1', service_port=5004, description='学生选课、智能排课'),
                SubService(service_name='校园墙服务', service_ip='127.0.0.1', service_port=5005, description='校园社交、动态发布'),
            ])

        db.session.commit()

        if not Course.query.filter_by(code='CS101').first():
            course = Course(
                code='CS101',
                name='数据库系统',
                description='关系模型、SQL、事务与索引基础。',
                teacher_id='1001',
                target_grade='2024',
                target_major='软件工程'
            )
            db.session.add(course)
            db.session.flush()
            db.session.add_all([
                CourseEnrollment(course_id=course.id, student_id='20240002'),
                ClassroomAnnouncement(
                    course_id=course.id,
                    title='第一次课准备',
                    content='请提前安装数据库客户端，并阅读第一章教材。',
                    created_by='1001'
                ),
                Assignment(
                    course_id=course.id,
                    title='SQL查询练习',
                    content='完成三道多表查询题，提交SQL语句和执行结果说明。',
                    created_by='1001'
                ),
            ])
            db.session.commit()

        print("Demo data is ready.")
        print("Student: 20240001 / 123456")
        print("Student: 20240002 / 123456")
        print("Teacher: 1001 / 123456")
        print("Admin: admin / admin123")


if __name__ == '__main__':
    init_tables()
    insert_test_data()
