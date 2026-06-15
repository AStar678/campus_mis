"""综合信息查询服务。

支持学生、教师、管理员三端查询，并接入 DeepSeek Agent 智能问答。
- 学生：查询个人信息、成绩、课程表、选课记录
- 教师：查询所授课程、课程学生成绩、教学安排
- 管理员：查询所有信息，并可通过 Agent 修改数据库
端口：5002
"""

import json
import os
import re
from datetime import datetime
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, unquote
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

# ============ 应用初始化 ============

FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend")
)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# ============ 数据库配置 ============

DB_HOST = os.getenv("DB_HOST", "47.93.226.110")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "MySQL%402026")
DB_PASS_RAW = os.getenv("DB_PASS_RAW", unquote(DB_PASS))
DB_PASS_QUOTED = quote_plus(DB_PASS_RAW)

MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://127.0.0.1:5001")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-2615cf7b2c8a470bbc6cc487753ae3b1")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/main_database"
)
app.config["SQLALCHEMY_BINDS"] = {
    "users": f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/users_database",
    "course_schedule": f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/course_schedule_database",
    "classroom": f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/classroom_database",
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============ 数据模型 ============

class Student(db.Model):
    __bind_key__ = "users"
    __tablename__ = "students"
    student_id = db.Column(db.String(8), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    grade = db.Column(db.String(10))
    major = db.Column(db.String(50))


class Teacher(db.Model):
    __bind_key__ = "users"
    __tablename__ = "teachers"
    teacher_id = db.Column(db.String(4), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    college = db.Column(db.String(50))
    title = db.Column(db.String(20))


class Admin(db.Model):
    __bind_key__ = "users"
    __tablename__ = "admins"
    admin_id = db.Column(db.String(20), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(50))


# main_database 表
class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.String(4))
    target_grade = db.Column(db.String(10))
    target_major = db.Column(db.String(50))
    created_at = db.Column(db.DateTime)


class CourseEnrollment(db.Model):
    __tablename__ = "course_enrollments"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime)


class CourseGrade(db.Model):
    __tablename__ = "course_grades"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.String(255))
    updated_by = db.Column(db.String(4))
    updated_at = db.Column(db.DateTime)


# course_schedule_database 表
class CsScheduleResult(db.Model):
    __bind_key__ = "course_schedule"
    __tablename__ = "cs_schedule_results"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, nullable=False)
    course_id = db.Column(db.String(20), nullable=False)
    section_id = db.Column(db.String(30))
    classroom_id = db.Column(db.String(4), nullable=False)
    slot_id = db.Column(db.Integer, nullable=False)
    enrolled_count = db.Column(db.Integer)
    score = db.Column(db.Float)
    reason = db.Column(db.String(500))
    is_published = db.Column(db.Boolean)
    created_at = db.Column(db.DateTime)


class CsTimeSlot(db.Model):
    __bind_key__ = "course_schedule"
    __tablename__ = "cs_time_slots"
    slot_id = db.Column(db.Integer, primary_key=True)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    label = db.Column(db.String(50))


class CsCourse(db.Model):
    __bind_key__ = "course_schedule"
    __tablename__ = "cs_courses"
    course_id = db.Column(db.String(20), primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(4))
    capacity = db.Column(db.Integer)
    credits = db.Column(db.Float)
    hours_per_week = db.Column(db.Integer)
    preferred_building = db.Column(db.String(50))
    status = db.Column(db.String(20))


class CsCourseSection(db.Model):
    __bind_key__ = "course_schedule"
    __tablename__ = "cs_course_sections"
    section_id = db.Column(db.String(30), primary_key=True)
    course_id = db.Column(db.String(20), nullable=False)
    section_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(20))
    capacity = db.Column(db.Integer)
    preferred_building = db.Column(db.String(50))
    status = db.Column(db.String(20))


class CsCourseRequest(db.Model):
    __bind_key__ = "course_schedule"
    __tablename__ = "cs_course_requests"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(8), nullable=False)
    course_id = db.Column(db.String(20), nullable=False)
    section_id = db.Column(db.String(30))
    preference_level = db.Column(db.Integer)
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime)


# classroom_database 表
class ClassroomCourse(db.Model):
    __bind_key__ = "classroom"
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(4))
    description = db.Column(db.String(500))


class ClassroomCourseStudent(db.Model):
    __bind_key__ = "classroom"
    __tablename__ = "course_students"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    final_grade = db.Column(db.Float)


# ============ 认证工具 ============

def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    return request.args.get("token", "").strip()


def verify_token_with_main_service(token):
    if not token:
        return None
    req = Request(
        f"{MAIN_SERVICE_URL}/api/verify-token",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    if not data.get("valid"):
        return None
    return {"user_id": data.get("user_id"), "user_type": data.get("user_type")}


def require_auth(*allowed_types):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = verify_token_with_main_service(get_bearer_token())
            if not user:
                return jsonify({"success": False, "message": "未登录或 token 无效"}), 401
            if allowed_types and user["user_type"] not in allowed_types:
                return jsonify({"success": False, "message": "无权限访问该接口"}), 403
            return func(user, *args, **kwargs)
        return wrapper
    return decorator


# ============ 查询 API ============

@app.route("/api/query/me", methods=["GET"])
@require_auth("student", "teacher", "admin")
def get_my_info(user):
    """获取当前用户基本信息"""
    user_id = user["user_id"]
    user_type = user["user_type"]
    info = {"user_id": user_id, "user_type": user_type}

    if user_type == "student":
        s = db.session.get(Student, user_id)
        if s:
            info.update({"grade": s.grade, "major": s.major})
    elif user_type == "teacher":
        t = db.session.get(Teacher, user_id)
        if t:
            info.update({"college": t.college, "title": t.title})
    elif user_type == "admin":
        a = db.session.get(Admin, user_id)
        if a:
            info.update({"name": a.name})

    return jsonify({"success": True, "data": info})


@app.route("/api/query/student/grades", methods=["GET"])
@require_auth("student")
def get_student_grades(user):
    """学生查询自己的成绩"""
    student_id = user["user_id"]
    grades = CourseGrade.query.filter_by(student_id=student_id).all()
    result = []
    for g in grades:
        course = db.session.get(Course, g.course_id)
        result.append({
            "course_id": g.course_id,
            "course_code": course.code if course else None,
            "course_name": course.name if course else f"课程#{g.course_id}",
            "score": g.score,
            "comment": g.comment,
            "updated_at": g.updated_at.isoformat() if g.updated_at else None,
        })
    return jsonify({"success": True, "data": result})


@app.route("/api/query/student/courses", methods=["GET"])
@require_auth("student")
def get_student_courses(user):
    """学生查询自己选修的课程列表"""
    student_id = user["user_id"]
    enrollments = CourseEnrollment.query.filter_by(student_id=student_id).all()
    result = []
    for e in enrollments:
        course = db.session.get(Course, e.course_id)
        result.append({
            "course_id": e.course_id,
            "course_code": course.code if course else None,
            "course_name": course.name if course else f"课程#{e.course_id}",
            "teacher_id": course.teacher_id if course else None,
            "enrolled_at": e.created_at.isoformat() if e.created_at else None,
        })
    return jsonify({"success": True, "data": result})


@app.route("/api/query/student/schedule", methods=["GET"])
@require_auth("student")
def get_student_schedule(user):
    """学生查询自己的课程表（来自排课系统已发布结果）"""
    student_id = user["user_id"]
    # 查找学生已排课的选课申请
    scheduled_requests = CsCourseRequest.query.filter(
        CsCourseRequest.student_id == student_id,
        CsCourseRequest.status == "scheduled",
        CsCourseRequest.section_id.isnot(None),
    ).all()
    section_ids = [r.section_id for r in scheduled_requests]

    if not section_ids:
        return jsonify({"success": True, "data": []})

    results = CsScheduleResult.query.filter(
        CsScheduleResult.section_id.in_(section_ids),
        CsScheduleResult.is_published == True,
    ).all()

    schedule = []
    weekday_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
    for r in results:
        slot = db.session.get(CsTimeSlot, r.slot_id)
        cs_course = db.session.get(CsCourse, r.course_id)
        section = db.session.get(CsCourseSection, r.section_id)
        schedule.append({
            "course_name": cs_course.course_name if cs_course else r.course_id,
            "section_name": section.section_name if section else r.section_id,
            "teacher_id": section.teacher_id if section else None,
            "classroom_id": r.classroom_id,
            "weekday": slot.weekday if slot else None,
            "weekday_label": weekday_map.get(slot.weekday, "-") if slot else "-",
            "start_time": slot.start_time if slot else None,
            "end_time": slot.end_time if slot else None,
            "slot_label": slot.label if slot else None,
        })
    return jsonify({"success": True, "data": schedule})


@app.route("/api/query/teacher/courses", methods=["GET"])
@require_auth("teacher")
def get_teacher_courses(user):
    """教师查询自己教授的课程"""
    teacher_id = user["user_id"]
    # 从 main_database.courses
    courses = Course.query.filter_by(teacher_id=teacher_id).all()
    result = []
    for c in courses:
        enrollment_count = CourseEnrollment.query.filter_by(course_id=c.id).count()
        result.append({
            "course_id": c.id,
            "course_code": c.code,
            "course_name": c.name,
            "description": c.description,
            "target_grade": c.target_grade,
            "target_major": c.target_major,
            "enrollment_count": enrollment_count,
        })
    # 从 course_schedule_database 中的教学班
    cs_sections = CsCourseSection.query.filter_by(teacher_id=teacher_id).all()
    for s in cs_sections:
        cs_course = db.session.get(CsCourse, s.course_id)
        result.append({
            "course_id": s.course_id,
            "course_code": s.section_id,
            "course_name": cs_course.course_name if cs_course else s.section_name,
            "description": f"教学班: {s.section_name}",
            "target_grade": None,
            "target_major": None,
            "enrollment_count": s.capacity,
            "source": "course_schedule",
        })
    return jsonify({"success": True, "data": result})


@app.route("/api/query/teacher/grades", methods=["GET"])
@require_auth("teacher")
def get_teacher_course_grades(user):
    """教师查询自己课程的学生成绩"""
    teacher_id = user["user_id"]
    courses = Course.query.filter_by(teacher_id=teacher_id).all()
    course_ids = [c.id for c in courses]

    if not course_ids:
        return jsonify({"success": True, "data": []})

    grades = CourseGrade.query.filter(CourseGrade.course_id.in_(course_ids)).all()
    result = []
    for g in grades:
        course = db.session.get(Course, g.course_id)
        result.append({
            "course_id": g.course_id,
            "course_name": course.name if course else f"课程#{g.course_id}",
            "student_id": g.student_id,
            "score": g.score,
            "comment": g.comment,
            "updated_at": g.updated_at.isoformat() if g.updated_at else None,
        })
    return jsonify({"success": True, "data": result})


@app.route("/api/query/teacher/schedule", methods=["GET"])
@require_auth("teacher")
def get_teacher_schedule(user):
    """教师查询自己的教学安排（课程表）"""
    teacher_id = user["user_id"]
    sections = CsCourseSection.query.filter_by(teacher_id=teacher_id).all()
    section_ids = [s.section_id for s in sections]

    if not section_ids:
        return jsonify({"success": True, "data": []})

    results = CsScheduleResult.query.filter(
        CsScheduleResult.section_id.in_(section_ids)
    ).all()

    weekday_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
    schedule = []
    for r in results:
        slot = db.session.get(CsTimeSlot, r.slot_id)
        cs_course = db.session.get(CsCourse, r.course_id)
        section = db.session.get(CsCourseSection, r.section_id)
        schedule.append({
            "course_name": cs_course.course_name if cs_course else r.course_id,
            "section_name": section.section_name if section else r.section_id,
            "classroom_id": r.classroom_id,
            "weekday": slot.weekday if slot else None,
            "weekday_label": weekday_map.get(slot.weekday, "-") if slot else "-",
            "start_time": slot.start_time if slot else None,
            "end_time": slot.end_time if slot else None,
            "slot_label": slot.label if slot else None,
            "enrolled_count": r.enrolled_count,
            "is_published": r.is_published,
        })
    return jsonify({"success": True, "data": schedule})


@app.route("/api/query/admin/students", methods=["GET"])
@require_auth("admin")
def admin_list_students(user):
    """管理员查询所有学生信息"""
    students = Student.query.all()
    result = [{
        "student_id": s.student_id,
        "grade": s.grade,
        "major": s.major,
    } for s in students]
    return jsonify({"success": True, "data": result})


@app.route("/api/query/admin/teachers", methods=["GET"])
@require_auth("admin")
def admin_list_teachers(user):
    """管理员查询所有教师信息"""
    teachers = Teacher.query.all()
    result = [{
        "teacher_id": t.teacher_id,
        "college": t.college,
        "title": t.title,
    } for t in teachers]
    return jsonify({"success": True, "data": result})


@app.route("/api/query/admin/courses", methods=["GET"])
@require_auth("admin")
def admin_list_courses(user):
    """管理员查询所有课程信息"""
    courses = Course.query.all()
    result = [{
        "course_id": c.id,
        "code": c.code,
        "name": c.name,
        "teacher_id": c.teacher_id,
        "target_grade": c.target_grade,
        "target_major": c.target_major,
    } for c in courses]
    return jsonify({"success": True, "data": result})


@app.route("/api/query/admin/grades", methods=["GET"])
@require_auth("admin")
def admin_list_grades(user):
    """管理员查询所有成绩信息"""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    student_id = request.args.get("student_id", "")
    course_id = request.args.get("course_id", "", type=str)

    query = CourseGrade.query
    if student_id:
        query = query.filter_by(student_id=student_id)
    if course_id:
        query = query.filter_by(course_id=int(course_id))

    total = query.count()
    grades = query.order_by(CourseGrade.id.desc()).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for g in grades:
        course = db.session.get(Course, g.course_id)
        result.append({
            "id": g.id,
            "course_id": g.course_id,
            "course_name": course.name if course else f"课程#{g.course_id}",
            "student_id": g.student_id,
            "score": g.score,
            "comment": g.comment,
            "updated_by": g.updated_by,
            "updated_at": g.updated_at.isoformat() if g.updated_at else None,
        })
    return jsonify({"success": True, "data": result, "total": total, "page": page})


# ============ DeepSeek Agent ============

def get_db_schema_description(user_type):
    """根据角色返回可查询的数据库结构描述"""
    base_schema = """
可查询的数据库结构：

1. users_database.students (学生信息表)
   - student_id VARCHAR(8) 主键，学号
   - grade VARCHAR(10) 年级
   - major VARCHAR(50) 专业

2. users_database.teachers (教师信息表)
   - teacher_id VARCHAR(4) 主键，工号
   - college VARCHAR(50) 学院
   - title VARCHAR(20) 职称

3. main_database.courses (课程信息表)
   - id INT 主键
   - code VARCHAR(30) 课程编号
   - name VARCHAR(100) 课程名称
   - description TEXT 课程描述
   - teacher_id VARCHAR(4) 授课教师工号
   - target_grade VARCHAR(10) 目标年级
   - target_major VARCHAR(50) 目标专业

4. main_database.course_enrollments (选课记录表)
   - id INT 主键
   - course_id INT 课程ID
   - student_id VARCHAR(8) 学号
   - created_at DATETIME 选课时间

5. main_database.course_grades (成绩表)
   - id INT 主键
   - course_id INT 课程ID
   - student_id VARCHAR(8) 学号
   - score FLOAT 成绩分数
   - comment VARCHAR(255) 评语
   - updated_by VARCHAR(4) 更新者工号
   - updated_at DATETIME 更新时间

6. course_schedule_database.cs_courses (排课课程表)
   - course_id VARCHAR(20) 主键
   - course_name VARCHAR(100) 课程名
   - teacher_id VARCHAR(4) 教师工号
   - capacity INT 容量
   - credits FLOAT 学分
   - hours_per_week INT 每周学时
   - status VARCHAR(20) 状态

7. course_schedule_database.cs_course_sections (教学班表)
   - section_id VARCHAR(30) 主键
   - course_id VARCHAR(20) 所属课程
   - section_name VARCHAR(100) 教学班名
   - teacher_id VARCHAR(20) 教师
   - capacity INT 容量

8. course_schedule_database.cs_schedule_results (排课结果表)
   - id INT 主键
   - course_id VARCHAR(20)
   - section_id VARCHAR(30)
   - classroom_id VARCHAR(4) 教室
   - slot_id INT 时间段ID
   - enrolled_count INT 选课人数
   - is_published BOOLEAN 是否发布

9. course_schedule_database.cs_time_slots (时间段表)
   - slot_id INT 主键
   - weekday INT 星期几(1-7)
   - start_time VARCHAR(5) 开始时间
   - end_time VARCHAR(5) 结束时间
   - label VARCHAR(50) 时间段标签

10. course_schedule_database.cs_course_requests (选课申请表)
    - id INT 主键
    - student_id VARCHAR(8) 学号
    - course_id VARCHAR(20) 课程ID
    - section_id VARCHAR(30) 教学班ID
    - preference_level INT 意向级别
    - status VARCHAR(20) 状态(submitted/scheduled/waitlisted/cancelled)
"""
    return base_schema


def build_agent_system_prompt(user_type, user_id):
    """构建 Agent 的系统提示词"""
    schema = get_db_schema_description(user_type)

    permission_desc = ""
    if user_type == "student":
        permission_desc = f"""
你是一个校园教务查询助手，当前用户是学生，学号为 {user_id}。
权限限制：
- 只能查询该学生自己的信息（成绩、课程、选课记录等）
- 查询时必须加上 student_id = '{user_id}' 的过滤条件
- 禁止执行任何 INSERT、UPDATE、DELETE、DROP、ALTER 等修改操作
- 禁止查询其他学生的信息
- 可以查询课程的公共信息（课程名、教师等）
"""
    elif user_type == "teacher":
        permission_desc = f"""
你是一个校园教务查询助手，当前用户是教师，工号为 {user_id}。
权限限制：
- 可以查询自己教授课程的信息和学生成绩
- 查询课程时需要加上 teacher_id = '{user_id}' 的过滤条件
- 可以查询自己课程中学生的成绩
- 禁止执行任何 INSERT、UPDATE、DELETE、DROP、ALTER 等修改操作
- 禁止查询其他教师的课程成绩
- 可以查询课程的公共信息
"""
    elif user_type == "admin":
        permission_desc = f"""
你是一个校园教务管理助手，当前用户是管理员，账号为 {user_id}。
权限：
- 可以查询所有信息，不受限制
- 可以执行 INSERT、UPDATE 操作来修改数据
- 但禁止执行 DROP、TRUNCATE、ALTER 等危险的结构修改操作
- 修改操作需要谨慎，确保数据完整性
"""

    return f"""{permission_desc}

{schema}

请根据用户的自然语言问题，生成合适的 SQL 查询语句并返回结果。

输出规则：
1. 如果需要执行SQL，请在回复中包含 ```sql 代码块
2. 对查询结果进行简明易懂的中文总结
3. 如果用户的请求超出权限范围，请礼貌拒绝并说明原因
4. 生成的SQL必须是安全的，不能包含危险操作
5. 如果不确定用户的意图，请询问澄清
"""


def execute_safe_sql(sql, user_type):
    """安全执行 SQL 语句"""
    sql_upper = sql.strip().upper()

    # 检查危险操作
    dangerous_keywords = ["DROP", "TRUNCATE", "ALTER", "CREATE DATABASE"]
    for kw in dangerous_keywords:
        if kw in sql_upper:
            return None, f"禁止执行危险操作: {kw}"

    # 非管理员禁止修改操作
    modify_keywords = ["INSERT", "UPDATE", "DELETE"]
    if user_type != "admin":
        for kw in modify_keywords:
            if sql_upper.startswith(kw):
                return None, "当前角色无权执行修改操作"

    try:
        import pymysql
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS_RAW,
            charset="utf8mb4",
        )
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(sql)

        if sql_upper.startswith("SELECT") or sql_upper.startswith("SHOW"):
            rows = cursor.fetchall()
            # 将 datetime 对象转为字符串
            for row in rows:
                for key, val in row.items():
                    if isinstance(val, datetime):
                        row[key] = val.isoformat()
            conn.close()
            return rows, None
        else:
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return {"affected_rows": affected}, None
    except Exception as e:
        return None, str(e)


def call_deepseek_api(messages):
    """调用 DeepSeek API"""
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2000,
    }).encode("utf-8")

    req = Request(
        DEEPSEEK_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, f"调用 DeepSeek API 失败: {str(e)}"


def extract_sql_from_response(response_text):
    """从 AI 响应中提取 SQL 语句"""
    # 尝试匹配 ```sql ... ``` 代码块
    pattern = r"```sql\s*(.*?)\s*```"
    matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
    if matches:
        return [m.strip() for m in matches if m.strip()]
    return []


@app.route("/api/query/agent", methods=["POST"])
@require_auth("student", "teacher", "admin")
def agent_query(user):
    """Agent 智能查询接口"""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"success": False, "message": "请输入查询问题"}), 400

    user_id = user["user_id"]
    user_type = user["user_type"]

    system_prompt = build_agent_system_prompt(user_type, user_id)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    # 第一轮调用: 生成 SQL
    ai_response, error = call_deepseek_api(messages)
    if error:
        return jsonify({"success": False, "message": error}), 500

    # 提取 SQL 并执行
    sql_statements = extract_sql_from_response(ai_response)
    query_results = []

    if sql_statements:
        for sql in sql_statements:
            result, sql_error = execute_safe_sql(sql, user_type)
            if sql_error:
                query_results.append({"sql": sql, "error": sql_error})
            else:
                query_results.append({"sql": sql, "data": result})

        # 第二轮调用: 让 AI 解读结果
        result_text = json.dumps(query_results, ensure_ascii=False, default=str)
        messages.append({"role": "assistant", "content": ai_response})
        messages.append({
            "role": "user",
            "content": f"以下是SQL执行结果，请用简明中文总结回答用户的问题:\n{result_text}",
        })

        summary, error2 = call_deepseek_api(messages)
        if error2:
            summary = ai_response  # 如果第二轮失败，直接使用第一轮结果

        return jsonify({
            "success": True,
            "data": {
                "answer": summary,
                "sql_executed": sql_statements,
                "raw_results": query_results,
            },
        })
    else:
        # 没有 SQL，AI 直接回答
        return jsonify({
            "success": True,
            "data": {
                "answer": ai_response,
                "sql_executed": [],
                "raw_results": [],
            },
        })


# ============ 页面路由 ============

@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/query/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "query-service", "port": 5002})


# ============ 启动 ============

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
