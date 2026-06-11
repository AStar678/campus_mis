"""
数据库初始化脚本：建库建表 + 插入测试数据
使用方法：python init_db.py
"""
import pymysql
from app import app, db, Student, Teacher, Admin, Classroom, Building, BuildingAdjacency, SubService
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_database():
    """删除旧库并重新创建"""
    conn = pymysql.connect(host='localhost', user='root', password='Aoxiang050916!', charset='utf8mb4')
    cursor = conn.cursor()
    cursor.execute("DROP DATABASE IF EXISTS campus_mis")
    cursor.execute("CREATE DATABASE campus_mis DEFAULT CHARACTER SET utf8mb4")
    conn.close()
    print("数据库 campus_mis 重建成功")

def init_tables():
    """创建所有表（先删除旧表）"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("所有表创建成功（已重建）")

def insert_test_data():
    """插入测试数据"""
    with app.app_context():
        # 检查是否已有数据
        if Student.query.first():
            print("数据库已有数据，跳过插入")
            return

        # 测试学生
        students = [
            Student(student_id='20240001', password=hash_password('123456'), grade='2024', major='计算机科学'),
            Student(student_id='20240002', password=hash_password('123456'), grade='2024', major='软件工程'),
        ]

        # 测试教师
        teachers = [
            Teacher(teacher_id='1001', password=hash_password('123456'), college='计算机学院', title='教授'),
            Teacher(teacher_id='1002', password=hash_password('123456'), college='计算机学院', title='副教授'),
        ]

        # 测试管理员
        admins = [
            Admin(admin_id='admin', password=hash_password('admin123'), name='系统管理员'),
        ]

        # 测试教室
        classrooms = [
            Classroom(classroom_id='A101', building='1号楼'),
            Classroom(classroom_id='A201', building='1号楼'),
            Classroom(classroom_id='B101', building='2号楼'),
        ]

        # 校园建筑
        buildings = [
            Building(building_name='1号楼'),
            Building(building_name='2号楼'),
            Building(building_name='图书馆'),
            Building(building_name='食堂'),
            Building(building_name='体育馆'),
        ]
        db.session.add_all(buildings)
        db.session.flush()  # 获取自增 ID

        # 建筑间距离（邻接表）
        adjacency = [
            BuildingAdjacency(building_a=1, building_b=2, distance=200.0),
            BuildingAdjacency(building_a=1, building_b=3, distance=350.0),
            BuildingAdjacency(building_a=2, building_b=3, distance=250.0),
            BuildingAdjacency(building_a=1, building_b=4, distance=400.0),
            BuildingAdjacency(building_a=2, building_b=4, distance=300.0),
            BuildingAdjacency(building_a=3, building_b=4, distance=150.0),
            BuildingAdjacency(building_a=4, building_b=5, distance=200.0),
            BuildingAdjacency(building_a=3, building_b=5, distance=500.0),
        ]

        # 分服务注册信息（端口管理）
        services = [
            SubService(service_name='教务服务', service_ip='127.0.0.1', service_port=5002, description='课程管理、成绩管理、学分计算'),
            SubService(service_name='课堂服务', service_ip='127.0.0.1', service_port=5003, description='作业发布、课堂公告、AI批改'),
            SubService(service_name='选课排课服务', service_ip='127.0.0.1', service_port=5004, description='学生选课、智能排课'),
            SubService(service_name='校园墙服务', service_ip='127.0.0.1', service_port=5005, description='校园社交、动态发布'),
        ]

        db.session.add_all(students + teachers + admins + classrooms + adjacency + services)
        db.session.commit()
        print("测试数据插入成功")
        print("=" * 40)
        print("测试账号：")
        print("  学生: 20240001 / 123456")
        print("  学生: 20240002 / 123456")
        print("  教师: 1001 / 123456")
        print("  教师: 1002 / 123456")
        print("  管理员: admin / admin123")
        print("=" * 40)

if __name__ == '__main__':
    create_database()
    init_tables()
    insert_test_data()
