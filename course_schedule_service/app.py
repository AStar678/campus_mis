"""选课与智能排课分服务。

本服务负责维护 course_schedule_database 中的选课排课业务表。
公共教室、楼栋和楼栋距离数据从 main_database 只读获取；登录态统一委托主服务
/api/verify-token 校验，避免分服务重复实现认证逻辑。
"""

from datetime import datetime
from functools import wraps
from urllib.parse import quote_plus, unquote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import re

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import pymysql
import logging

logger = logging.getLogger(__name__)


app = Flask(__name__)
CORS(app)

# 数据库配置。
#
# 默认绑定：course_schedule_database，由本服务独立维护。
# main 绑定：main_database，只读访问主服务维护的校园公共数据。
DB_HOST = os.getenv("DB_HOST", "47.93.226.110")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_PASS_RAW = os.getenv("DB_PASS_RAW", unquote(DB_PASS))
DB_PASS_QUOTED = quote_plus(DB_PASS_RAW)
DB_NAME = os.getenv("COURSE_DB_NAME", "course_schedule_database")
MAIN_DB_NAME = os.getenv("MAIN_DB_NAME", "main_database")
MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://127.0.0.1:5001")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
app.config["SQLALCHEMY_BINDS"] = {
    "main": f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/{MAIN_DB_NAME}",
    "users": f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/users_database",
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# 主服务公共表映射，本服务只读使用，不修改表结构和公共数据。
class Classroom(db.Model):
    """教室基础信息，只读映射 main_database.classrooms。"""

    __bind_key__ = "main"
    __tablename__ = "classrooms"

    classroom_id = db.Column(db.String(4), primary_key=True)
    building = db.Column(db.String(50))


class Building(db.Model):
    """楼栋基础信息，只读映射 main_database.buildings。"""

    __bind_key__ = "main"
    __tablename__ = "buildings"

    building_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_name = db.Column(db.String(50), nullable=False)


class BuildingAdjacency(db.Model):
    """楼栋距离关系，只读映射 main_database.building_adjacency。"""

    __bind_key__ = "main"
    __tablename__ = "building_adjacency"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_a = db.Column(db.Integer, nullable=False)
    building_b = db.Column(db.Integer, nullable=False)
    distance = db.Column(db.Float, nullable=False)


class Teacher(db.Model):
    """教师基础信息，只读映射 users_database.teachers。"""

    __bind_key__ = "users"
    __tablename__ = "teachers"

    teacher_id = db.Column(db.String(4), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    college = db.Column(db.String(50))
    title = db.Column(db.String(20))
    name = db.Column(db.String(50), default="")


# 选课排课业务表，由本服务独立维护，统一使用 cs_ 表名前缀。
class Course(db.Model):
    """
    可选课程信息（排课系统专用），供学生提交申请、管理员参与排课。
    
    ⚠️ 跨库关系说明：
    - 本表（cs_courses）与 classroom_database.courses 维护两套独立的课程目录
    - cs_courses: 排课系统的「开课计划」，面向选课排课流程
    - classroom_database.courses: 教学管理的「课程主数据」，面向课堂教学
    - 两表职责不同，教师/学分等字段可能不同（如同名课程由不同教师任课）
    
    ⚠️ 数据流向：
    - 选课申请(cs_course_requests) → 排课结果(cs_schedule_results)
    - 发布排课结果 → 自动同步到 classroom_database.course_students
    - 同步规则：按 course_name ↔ courses.name 名称匹配
    
    ⚠️ 历史清理：
    - 本表 CS_CLS 开头的副本课程（20 行）已在 2026-06-16 清理
    - 数据真相源：classroom_teaching_service → classroom_database.courses
    - 本表仅用于排课流程，不复制 classroom 的课程数据
    """
    __tablename__ = "cs_courses"
    course_id = db.Column(db.String(20), primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(20))
    capacity = db.Column(db.Integer, nullable=False, default=40)
    credits = db.Column(db.Float, nullable=False, default=2.0)
    hours_per_week = db.Column(db.Integer, nullable=False, default=2)
    preferred_building = db.Column(db.String(50))
    allowed_majors = db.Column(db.String(200), nullable=False, default="all")
    allowed_grades = db.Column(db.String(100), nullable=False, default="all")
    prerequisite_note = db.Column(db.String(300), nullable=False, default="无")
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class CourseSection(db.Model):
    """课程教学班信息，同一门课程可由多个教师开设多个教学班。"""

    __tablename__ = "cs_course_sections"

    section_id = db.Column(db.String(30), primary_key=True)
    course_id = db.Column(db.String(20), db.ForeignKey("cs_courses.course_id"), nullable=False, index=True)
    section_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(20))
    capacity = db.Column(db.Integer, nullable=False, default=40)
    preferred_building = db.Column(db.String(50))
    required_room_type = db.Column(db.String(30), nullable=False, default="普通教室")
    unavailable_slot_ids = db.Column(db.String(200), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    course = db.relationship("Course", backref=db.backref("sections", lazy=True))


class CourseRequest(db.Model):
    """学生选课申请记录。"""

    __tablename__ = "cs_course_requests"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_cs_request_student_course"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(20), nullable=False, index=True)
    course_id = db.Column(db.String(20), db.ForeignKey("cs_courses.course_id"), nullable=False)
    section_id = db.Column(db.String(30), db.ForeignKey("cs_course_sections.section_id"))
    preference_level = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="submitted")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    course = db.relationship("Course")
    section = db.relationship("CourseSection")


class TimeSlot(db.Model):
    """可用于排课的候选时间段。"""

    __tablename__ = "cs_time_slots"

    slot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    label = db.Column(db.String(50))


class ScheduleRun(db.Model):
    """智能排课任务的一次执行记录。"""

    __tablename__ = "cs_schedule_runs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_by = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="completed")
    summary = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class ScheduleResult(db.Model):
    """智能排课生成的课程、教室和时间段分配结果。"""

    __tablename__ = "cs_schedule_results"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_id = db.Column(db.Integer, db.ForeignKey("cs_schedule_runs.id"), nullable=False)
    course_id = db.Column(db.String(20), db.ForeignKey("cs_courses.course_id"), nullable=False)
    section_id = db.Column(db.String(30), db.ForeignKey("cs_course_sections.section_id"))
    classroom_id = db.Column(db.String(4), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("cs_time_slots.slot_id"), nullable=False)
    enrolled_count = db.Column(db.Integer, nullable=False, default=0)
    score = db.Column(db.Float, nullable=False, default=0)
    reason = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    course = db.relationship("Course")
    section = db.relationship("CourseSection")
    slot = db.relationship("TimeSlot")


class SelectionBatch(db.Model):
    """选课批次配置，用于后端控制提交、撤销、排课和发布阶段。"""

    __tablename__ = "cs_selection_batches"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    term_name = db.Column(db.String(80), nullable=False, default="2025-2026-2")
    phase = db.Column(db.String(30), nullable=False, default="selecting")
    phase_label = db.Column(db.String(50), nullable=False, default="正式选课阶段")
    start_at = db.Column(db.DateTime)
    end_at = db.Column(db.DateTime)
    max_preferences = db.Column(db.Integer, nullable=False, default=3)
    min_credits = db.Column(db.Float, nullable=False, default=2.0)
    max_credits = db.Column(db.Float, nullable=False, default=8.0)
    notice = db.Column(db.String(300), nullable=False, default="排课结果以管理员发布为准。")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


def split_rule_values(value):
    """将逗号分隔的规则字段转换为集合，all 或空值表示不限制。"""

    if not value or str(value).strip().lower() == "all":
        return set()
    return {item.strip() for item in str(value).replace("，", ",").split(",") if item.strip()}


def parse_id_set(value):
    """解析逗号分隔的整数 ID 集合。"""

    if not value:
        return set()
    result = set()
    for item in str(value).replace("，", ",").split(","):
        item = item.strip()
        if item.isdigit():
            result.add(int(item))
    return result


def infer_classroom_type(classroom):
    """根据教室楼栋和编号推断演示用教室类型。"""

    text = f"{classroom.classroom_id or ''} {classroom.building or ''}"
    if "体育" in text:
        return "体育场馆"
    if "实验" in text:
        return "实验室"
    if "机房" in text or "计算机" in text:
        return "机房"
    return "普通教室"


def active_request_statuses():
    """当前仍计入选课方案的申请状态。"""

    return ["submitted", "scheduled", "waitlisted"]


def calculate_student_credits(student_id, replacing_course_id=None, additional_course=None):
    """计算学生当前有效意向学分，可排除待更新课程并追加新课程。"""

    query = CourseRequest.query.filter(
        CourseRequest.student_id == student_id,
        CourseRequest.status.in_(active_request_statuses()),
    )
    if replacing_course_id:
        query = query.filter(CourseRequest.course_id != replacing_course_id)
    total = 0.0
    for course_request in query.all():
        if course_request.course:
            total += float(course_request.course.credits or 0)
    if additional_course:
        total += float(additional_course.credits or 0)
    return total


def waitlist_info(course_request):
    """计算候补排名和候补总人数。"""

    if course_request.status != "waitlisted" or not course_request.section_id:
        return {"rank": None, "total": 0}
    ordered_requests = (
        CourseRequest.query.filter(
            CourseRequest.section_id == course_request.section_id,
            CourseRequest.status.in_(active_request_statuses()),
        )
        .order_by(CourseRequest.preference_level.asc(), CourseRequest.created_at.asc(), CourseRequest.id.asc())
        .all()
    )
    capacity = course_request.section.capacity if course_request.section else 0
    waitlisted_requests = ordered_requests[capacity:]
    ids = [item.id for item in waitlisted_requests]
    rank = ids.index(course_request.id) + 1 if course_request.id in ids else None
    return {"rank": rank, "total": len(waitlisted_requests)}


def get_student_profile(student_id):
    """构造演示用学生画像。

    真实系统应从学生信息表读取专业、年级和行政班；当前根据学号生成稳定演示数据。
    """

    year = str(student_id)[:4] if student_id else "2024"
    majors = ["软件工程", "计算机科学与技术", "数据科学与大数据技术", "人工智能"]
    index = int(str(student_id)[-1]) % len(majors) if str(student_id)[-1:].isdigit() else 0
    return {
        "student_id": student_id,
        "grade": year,
        "major": majors[index],
        "class_name": f"{year}级{majors[index]}{index + 1}班",
    }


def check_course_eligibility(course, student_id):
    """检查学生是否符合课程适用专业和年级规则。"""

    profile = get_student_profile(student_id)
    allowed_majors = split_rule_values(course.allowed_majors)
    allowed_grades = split_rule_values(course.allowed_grades)
    if allowed_majors and profile["major"] not in allowed_majors:
        return False, f"该课程仅限 {course.allowed_majors} 专业选择，当前专业为 {profile['major']}"
    if allowed_grades and profile["grade"] not in allowed_grades:
        return False, f"该课程仅限 {course.allowed_grades} 级学生选择，当前年级为 {profile['grade']}"
    return True, "符合培养方案范围"


def course_category(course):
    """判断课程类别，用于生成统一展示编号。"""

    code = str(course.course_id or "").upper()
    name = str(course.course_name or "")
    if code.startswith("PUB") or any(keyword in name for keyword in ("公共", "体育", "英语", "思政")):
        return "PUB"
    # 所有非公共课均视为选修课，不再区分必修（REQ）与选修（ELE）
    return "ELE"


def normalized_course_code(course):
    """生成统一教务展示编号，不改变数据库内部主键。"""

    digits = "".join(re.findall(r"\d+", str(course.course_id or "")))
    numeric_part = digits[-3:].zfill(3) if digits else "000"
    return f"{course_category(course)}{numeric_part}"


def parse_datetime_value(value):
    """解析前端传入的批次时间。"""

    if not value:
        return None
    if isinstance(value, datetime):
        return value
    normalized = str(value).replace("T", " ").strip()
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    raise ValueError("时间格式应为 YYYY-MM-DD HH:MM")


def get_active_batch():
    """获取当前生效批次，若不存在则创建默认批次。"""

    batch = SelectionBatch.query.filter_by(is_active=True).order_by(SelectionBatch.id.desc()).first()
    if batch:
        return batch
    batch = SelectionBatch(
        term_name="2025-2026 学年第二学期",
        phase="selecting",
        phase_label="正式选课阶段",
        start_at=datetime(2026, 6, 1, 9, 0),
        end_at=datetime(2026, 6, 20, 18, 0),
        max_preferences=3,
        min_credits=2,
        max_credits=8,
        notice="排课结果以管理员发布为准。",
        is_active=True,
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def serialize_batch(batch):
    """将选课批次转换为前端配置结构。"""

    now = datetime.now()
    phase_rules = {
        "preselect": {"submit": True, "cancel": True, "schedule": False, "publish": False},
        "selecting": {"submit": True, "cancel": True, "schedule": False, "publish": False},
        "scheduling": {"submit": False, "cancel": False, "schedule": True, "publish": False},
        "add_drop": {"submit": True, "cancel": True, "schedule": True, "publish": False},
        "final": {"submit": False, "cancel": False, "schedule": False, "publish": True},
        "closed": {"submit": False, "cancel": False, "schedule": False, "publish": False},
    }
    in_time_window = True
    if batch.start_at and now < batch.start_at:
        in_time_window = False
    if batch.end_at and now > batch.end_at:
        in_time_window = False
    rules = phase_rules.get(batch.phase, phase_rules["selecting"])
    return {
        "termName": batch.term_name,
        "phase": batch.phase,
        "phaseLabel": batch.phase_label,
        "startAt": batch.start_at.strftime("%Y-%m-%d %H:%M") if batch.start_at else "",
        "endAt": batch.end_at.strftime("%Y-%m-%d %H:%M") if batch.end_at else "",
        "maxPreferences": batch.max_preferences,
        "minCredits": batch.min_credits,
        "maxCredits": batch.max_credits,
        "notice": batch.notice,
        "inTimeWindow": in_time_window,
        "canSubmit": rules["submit"] and in_time_window,
        "canCancel": rules["cancel"] and in_time_window,
        "canSchedule": rules["schedule"],
        "canPublish": rules["publish"],
    }


def ensure_batch_action(action):
    """检查当前批次是否允许执行指定操作。"""

    batch_data = serialize_batch(get_active_batch())
    action_map = {
        "submit": "canSubmit",
        "cancel": "canCancel",
        "schedule": "canSchedule",
        "publish": "canPublish",
    }
    if not batch_data.get(action_map[action]):
        action_tips = {
            "submit": "请切换到预选/意向征集、正式选课或补退选阶段后再提交。",
            "cancel": "请切换到预选/意向征集、正式选课或补退选阶段后再撤销。",
            "schedule": "请在管理员端“批次设置”切换到排课处理阶段或补退选阶段后再生成排课方案。",
            "publish": "请在管理员端“批次设置”切换到最终确认阶段后再发布排课结果。",
        }
        return False, f"当前批次为 {batch_data['phaseLabel']}，暂不允许该操作。{action_tips.get(action, '')}"
    return True, ""


def serialize_section(section):
    """将教学班模型转换为前端接口返回结构。"""

    active_request_count = CourseRequest.query.filter(
        CourseRequest.section_id == section.section_id,
        CourseRequest.status.in_(["submitted", "scheduled", "waitlisted"]),
    ).count()
    status_label_map = {
        "open": "开放选课",
        "closed": "停止选课",
    }
    return {
        "section_id": section.section_id,
        "course_id": section.course_id,
        "course_code": normalized_course_code(section.course) if section.course else section.course_id,
        "section_name": section.section_name,
        "teacher_id": section.teacher_id,
        "capacity": section.capacity,
        "preferred_building": section.preferred_building,
        "required_room_type": section.required_room_type,
        "unavailable_slot_ids": section.unavailable_slot_ids,
        "unavailable_slot_id_list": sorted(parse_id_set(section.unavailable_slot_ids)),
        "status": section.status,
        "status_label": status_label_map.get(section.status, section.status),
        "active_request_count": active_request_count,
        "remaining_capacity": max(section.capacity - active_request_count, 0),
    }


def serialize_course(course):
    """将课程模型转换为前端接口返回结构。"""

    sections = CourseSection.query.filter_by(course_id=course.course_id).order_by(CourseSection.section_id).all()
    serialized_sections = [serialize_section(section) for section in sections]
    request_count = CourseRequest.query.filter(
        CourseRequest.course_id == course.course_id,
        CourseRequest.status != "cancelled",
    ).count()
    active_request_count = CourseRequest.query.filter(
        CourseRequest.course_id == course.course_id,
        CourseRequest.status.in_(["submitted", "scheduled", "waitlisted"]),
    ).count()
    status_label_map = {
        "open": "开放选课",
        "closed": "停止选课",
    }
    total_capacity = sum(item["capacity"] for item in serialized_sections) if serialized_sections else course.capacity
    total_remaining = sum(item["remaining_capacity"] for item in serialized_sections) if serialized_sections else max(course.capacity - active_request_count, 0)
    return {
        "course_id": course.course_id,
        "course_code": normalized_course_code(course),
        "course_name": course.course_name,
        "teacher_id": course.teacher_id,
        "capacity": total_capacity,
        "base_capacity": course.capacity,
        "credits": course.credits,
        "hours_per_week": course.hours_per_week,
        "preferred_building": course.preferred_building,
        "allowed_majors": course.allowed_majors,
        "allowed_grades": course.allowed_grades,
        "prerequisite_note": course.prerequisite_note,
        "status": course.status,
        "status_label": status_label_map.get(course.status, course.status),
        "request_count": request_count,
        "active_request_count": active_request_count,
        "remaining_capacity": total_remaining,
        "section_count": len(serialized_sections),
        "open_section_count": len([item for item in serialized_sections if item["status"] == "open"]),
        "sections": serialized_sections,
    }


def serialize_request(course_request):
    """将选课申请模型转换为前端接口返回结构。"""

    waitlist = waitlist_info(course_request)
    status_label_map = {
        "submitted": "已提交",
        "scheduled": "已排课",
        "waitlisted": "候补中",
        "cancelled": "已撤销",
    }
    return {
        "id": course_request.id,
        "student_id": course_request.student_id,
        "course_id": course_request.course_id,
        "course_code": normalized_course_code(course_request.course) if course_request.course else course_request.course_id,
        "course_name": course_request.course.course_name if course_request.course else None,
        "section_id": course_request.section_id,
        "section_name": course_request.section.section_name if course_request.section else None,
        "section_teacher_id": course_request.section.teacher_id if course_request.section else None,
        "preference_level": course_request.preference_level,
        "preference_label": f"第 {course_request.preference_level} 意向",
        "status": course_request.status,
        "status_label": status_label_map.get(course_request.status, course_request.status),
        "waitlist_rank": waitlist["rank"],
        "waitlist_total": waitlist["total"],
        "created_at": course_request.created_at.isoformat(),
    }


def serialize_slot(slot):
    """将时间段模型转换为前端接口返回结构。"""

    return {
        "slot_id": slot.slot_id,
        "weekday": slot.weekday,
        "start_time": slot.start_time,
        "end_time": slot.end_time,
        "label": slot.label,
    }


def serialize_classroom(classroom):
    """将教室模型转换为前端接口返回结构。"""

    return {
        "classroom_id": classroom.classroom_id,
        "building": classroom.building,
        "room_type": infer_classroom_type(classroom),
    }


def serialize_run(run):
    """将排课执行记录转换为前端接口返回结构。"""

    return {
        "id": run.id,
        "run_by": run.run_by,
        "status": run.status,
        "summary": run.summary,
        "created_at": run.created_at.isoformat(),
    }


def serialize_result(result):
    """将排课结果模型转换为前端接口返回结构。"""

    weekday = result.slot.weekday if result.slot else None
    weekday_label_map = {
        1: "周一",
        2: "周二",
        3: "周三",
        4: "周四",
        5: "周五",
        6: "周六",
        7: "周日",
    }
    return {
        "id": result.id,
        "run_id": result.run_id,
        "course_id": result.course_id,
        "course_code": normalized_course_code(result.course) if result.course else result.course_id,
        "course_name": result.course.course_name if result.course else None,
        "section_id": result.section_id,
        "section_name": result.section.section_name if result.section else None,
        "section_teacher_id": result.section.teacher_id if result.section else None,
        "classroom_id": result.classroom_id,
        "slot_id": result.slot_id,
        "weekday": weekday,
        "weekday_label": weekday_label_map.get(weekday, "-"),
        "start_time": result.slot.start_time if result.slot else None,
        "end_time": result.slot.end_time if result.slot else None,
        "enrolled_count": result.enrolled_count,
        "score": result.score,
        "reason": result.reason,
        "is_published": result.is_published,
        "created_at": result.created_at.isoformat(),
    }


def get_bearer_token():
    """从 Authorization 请求头读取 token，兼容测试场景下的 query 参数。"""

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    return request.args.get("token", "").strip()


def verify_token_with_main_service(token):
    """调用主服务校验 token，并返回当前登录用户信息。"""

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


def parse_positive_int(value, field_name, default=None):
    """解析请求中的正整数字段。"""

    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")
    if parsed <= 0:
        raise ValueError(f"{field_name} must be greater than 0")
    return parsed


def require_auth(*allowed_types):
    """校验主服务登录态，并按需限制访问角色。"""

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


def get_distance_between_buildings(building_name_a, building_name_b):
    """获取两栋楼之间的步行距离，缺失数据时返回默认惩罚距离。"""

    if not building_name_a or not building_name_b or building_name_a == building_name_b:
        return 0

    buildings = {b.building_name: b.building_id for b in Building.query.all()}
    building_a = buildings.get(building_name_a)
    building_b = buildings.get(building_name_b)
    if not building_a or not building_b:
        return 300

    adjacency = BuildingAdjacency.query.filter(
        ((BuildingAdjacency.building_a == building_a) & (BuildingAdjacency.building_b == building_b))
        | ((BuildingAdjacency.building_a == building_b) & (BuildingAdjacency.building_b == building_a))
    ).first()
    return adjacency.distance if adjacency else 300


def score_assignment(target, classroom, slot, request_count, used_pairs, used_teacher_slots, used_student_slots, student_ids):
    """为单个课程、教室、时间段候选组合计算排课评分。"""

    capacity_gap = target.capacity - request_count
    capacity_score = 40 if capacity_gap >= 0 else max(0, 40 + capacity_gap * 2)
    demand_score = min(request_count, target.capacity) * 1.5
    distance = get_distance_between_buildings(target.preferred_building, classroom.building)
    distance_penalty = distance / 20
    classroom_type = infer_classroom_type(classroom)
    room_type_penalty = 0 if target.required_room_type in ("", "普通教室", classroom_type) else 120
    unavailable_penalty = 120 if slot.slot_id in parse_id_set(target.unavailable_slot_ids) else 0
    classroom_conflict_penalty = 80 if (classroom.classroom_id, slot.slot_id) in used_pairs else 0
    teacher_conflict_penalty = 80 if target.teacher_id and (target.teacher_id, slot.slot_id) in used_teacher_slots else 0
    student_conflict_count = len(set(student_ids) & used_student_slots.get(slot.slot_id, set()))
    student_conflict_penalty = student_conflict_count * 12
    score = (
        capacity_score
        + demand_score
        - distance_penalty
        - room_type_penalty
        - unavailable_penalty
        - classroom_conflict_penalty
        - teacher_conflict_penalty
        - student_conflict_penalty
    )
    reason = (
        f"选课人数 {request_count}，教学班容量 {target.capacity}；"
        f"教学班偏好楼栋 {target.preferred_building or '未设置'}，"
        f"分配教室楼栋 {classroom.building}，教室类型 {classroom_type}；"
        f"类型惩罚 {room_type_penalty}，不可用时间惩罚 {unavailable_penalty}，"
        f"教师冲突惩罚 {teacher_conflict_penalty}，学生冲突 {student_conflict_count} 人。"
    )
    return score, reason


def run_schedule_agent(run_by):
    """使用规则版 Agent 生成排课结果。

    当前实现保持确定性和可解释性，综合评估课程需求、容量匹配、教室时间冲突和楼栋距离。
    后续接入真正的智能 Agent 时，可复用本函数的输入输出结构。
    """

    sections = (
        CourseSection.query.join(Course)
        .filter(Course.status == "open", CourseSection.status == "open")
        .order_by(CourseSection.course_id, CourseSection.section_id)
        .all()
    )
    classrooms = Classroom.query.all()
    slots = TimeSlot.query.all()
    if not sections or not classrooms or not slots:
        return None, "缺少教学班、教室或时间段数据，无法排课"

    ScheduleResult.query.delete()
    used_pairs = set()
    used_teacher_slots = set()
    used_student_slots = {}
    results = []

    run = ScheduleRun(run_by=run_by, status="running", summary="智能排课任务运行中")
    db.session.add(run)
    db.session.flush()

    for section in sections:
        requests_for_section = CourseRequest.query.filter(
            CourseRequest.section_id == section.section_id,
            CourseRequest.status.in_(["submitted", "scheduled", "waitlisted"]),
        ).order_by(CourseRequest.preference_level.asc(), CourseRequest.created_at.asc(), CourseRequest.id.asc()).all()
        request_count = len(requests_for_section)
        if not request_count:
            continue
        accepted_requests = requests_for_section[: section.capacity]
        waitlisted_requests = requests_for_section[section.capacity :]
        student_ids = [course_request.student_id for course_request in accepted_requests]
        best = None

        for classroom in classrooms:
            for slot in slots:
                score, reason = score_assignment(
                    section,
                    classroom,
                    slot,
                    request_count,
                    used_pairs,
                    used_teacher_slots,
                    used_student_slots,
                    student_ids,
                )
                if best is None or score > best["score"]:
                    best = {
                        "classroom": classroom,
                        "slot": slot,
                        "score": score,
                        "reason": reason,
                    }

        if not best:
            continue

        used_pairs.add((best["classroom"].classroom_id, best["slot"].slot_id))
        if section.teacher_id:
            used_teacher_slots.add((section.teacher_id, best["slot"].slot_id))
        used_student_slots.setdefault(best["slot"].slot_id, set()).update(student_ids)
        for course_request in accepted_requests:
            course_request.status = "scheduled"
        for course_request in waitlisted_requests:
            course_request.status = "waitlisted"

        result = ScheduleResult(
            run_id=run.id,
            course_id=section.course_id,
            section_id=section.section_id,
            classroom_id=best["classroom"].classroom_id,
            slot_id=best["slot"].slot_id,
            enrolled_count=min(request_count, section.capacity),
            score=round(best["score"], 2),
            reason=best["reason"],
        )
        db.session.add(result)
        results.append(result)

    run.status = "completed"
    run.summary = f"完成 {len(results)} 个教学班排课"
    db.session.commit()
    return run, None


@app.route("/", methods=["GET"])
def serve_course_schedule_page():
    """返回选课排课分服务前端页面。"""

    return send_from_directory(os.path.dirname(__file__), "index.html")


@app.route("/api/course-schedule/me", methods=["GET"])
def current_user_info():
    """查询当前 token 对应的用户信息。"""

    user = verify_token_with_main_service(get_bearer_token())
    if not user:
        return jsonify({"success": False, "message": "未登录或 token 无效"}), 401
    return jsonify({"success": True, "data": user})


@app.route("/api/course-schedule/health", methods=["GET"])
def health_check():
    """健康检查接口，用于服务发现和本地调试。"""

    return jsonify({"status": "ok", "service": "course-schedule-service", "port": 5004})


@app.route("/api/course-schedule/settings", methods=["GET"])
@require_auth("student", "admin", "teacher")
def get_selection_settings(_user):
    """查询当前选课批次设置。"""

    return jsonify({"success": True, "data": serialize_batch(get_active_batch())})


@app.route("/api/course-schedule/settings", methods=["PUT"])
@require_auth("admin")
def update_selection_settings(_user):
    """更新当前选课批次设置，仅管理员可访问。"""

    data = request.get_json() or {}
    batch = get_active_batch()
    try:
        start_at = parse_datetime_value(data.get("startAt", batch.start_at))
        end_at = parse_datetime_value(data.get("endAt", batch.end_at))
        max_preferences = parse_positive_int(data.get("maxPreferences"), "maxPreferences", batch.max_preferences)
        min_credits = float(data.get("minCredits", batch.min_credits))
        max_credits = float(data.get("maxCredits", batch.max_credits))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    if start_at and end_at and start_at >= end_at:
        return jsonify({"success": False, "message": "选课开始时间必须早于结束时间"}), 400
    if min_credits < 0 or max_credits <= 0 or min_credits > max_credits:
        return jsonify({"success": False, "message": "学分下限不能大于上限，且上限必须大于 0"}), 400

    phase = data.get("phase", batch.phase)
    phase_labels = {
        "preselect": "预选/意向征集",
        "selecting": "正式选课阶段",
        "scheduling": "排课处理阶段",
        "add_drop": "补退选阶段",
        "final": "管理员最终确认",
        "closed": "选课关闭",
    }
    if phase not in phase_labels:
        return jsonify({"success": False, "message": "未知选课阶段"}), 400

    batch.term_name = data.get("termName", batch.term_name)
    batch.phase = phase
    batch.phase_label = data.get("phaseLabel") or phase_labels[phase]
    batch.start_at = start_at
    batch.end_at = end_at
    batch.max_preferences = max_preferences
    batch.min_credits = min_credits
    batch.max_credits = max_credits
    batch.notice = data.get("notice", batch.notice)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_batch(batch)})


@app.route("/api/course-schedule/student-profile", methods=["GET"])
@require_auth("student")
def current_student_profile(user):
    """查询当前学生的演示培养方案画像。"""

    return jsonify({"success": True, "data": get_student_profile(user["user_id"])})


@app.route("/api/course-schedule/courses", methods=["GET"])
@require_auth("student", "admin", "teacher")
def list_courses(_user):
    """查询可选课程列表，学生和管理员可访问。"""

    courses = Course.query.order_by(Course.course_id).all()
    return jsonify({"success": True, "data": [serialize_course(course) for course in courses]})


@app.route("/api/course-schedule/courses", methods=["POST"])
@require_auth("admin")
def create_course(_user):
    """新增可选课程，仅管理员可访问。"""

    data = request.get_json() or {}
    required = ["course_id", "course_name"]
    if any(not data.get(field) for field in required):
        return jsonify({"success": False, "message": "course_id 和 course_name 必填"}), 400
    if db.session.get(Course, data["course_id"]):
        return jsonify({"success": False, "message": "课程编号已存在"}), 409

    try:
        capacity = parse_positive_int(data.get("capacity"), "capacity", 40)
        hours_per_week = parse_positive_int(data.get("hours_per_week"), "hours_per_week", 2)
        credits = float(data.get("credits", hours_per_week))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    if credits <= 0:
        return jsonify({"success": False, "message": "credits must be positive"}), 400

    course = Course(
        course_id=data["course_id"],
        course_name=data["course_name"],
        teacher_id=data.get("teacher_id"),
        capacity=capacity,
        credits=credits,
        hours_per_week=hours_per_week,
        preferred_building=data.get("preferred_building"),
        allowed_majors=data.get("allowed_majors") or "all",
        allowed_grades=data.get("allowed_grades") or "all",
        prerequisite_note=data.get("prerequisite_note") or "无",
        status=data.get("status", "open"),
    )
    db.session.add(course)
    default_section = CourseSection(
        section_id=f"{data['course_id']}-01",
        course_id=data["course_id"],
        section_name=f"{data['course_name']} 01班",
        teacher_id=data.get("teacher_id"),
        capacity=capacity,
        preferred_building=data.get("preferred_building"),
        required_room_type=data.get("required_room_type") or "普通教室",
        unavailable_slot_ids=data.get("unavailable_slot_ids") or "",
        status=data.get("status", "open"),
    )
    db.session.add(default_section)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_course(course)}), 201


@app.route("/api/course-schedule/courses/<course_id>", methods=["PUT"])
@require_auth("admin")
def update_course(_user, course_id):
    """更新可选课程信息，仅管理员可访问。"""

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    data = request.get_json() or {}
    try:
        capacity = parse_positive_int(data.get("capacity"), "capacity", course.capacity)
        hours_per_week = parse_positive_int(
            data.get("hours_per_week"),
            "hours_per_week",
            course.hours_per_week,
        )
        credits = float(data.get("credits", course.credits))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    if credits <= 0:
        return jsonify({"success": False, "message": "credits must be positive"}), 400

    course.course_name = data.get("course_name", course.course_name)
    course.teacher_id = data.get("teacher_id", course.teacher_id)
    course.capacity = capacity
    course.credits = credits
    course.hours_per_week = hours_per_week
    course.preferred_building = data.get("preferred_building", course.preferred_building)
    course.allowed_majors = data.get("allowed_majors", course.allowed_majors) or "all"
    course.allowed_grades = data.get("allowed_grades", course.allowed_grades) or "all"
    course.prerequisite_note = data.get("prerequisite_note", course.prerequisite_note) or "无"
    course.status = data.get("status", course.status)

    sections = (
        CourseSection.query.filter_by(course_id=course_id)
        .order_by(CourseSection.section_id.asc())
        .all()
    )
    if not sections:
        db.session.add(
            CourseSection(
                section_id=f"{course.course_id}-01",
                course_id=course.course_id,
                section_name=f"{course.course_name} 01班",
                teacher_id=course.teacher_id,
                capacity=course.capacity,
                preferred_building=course.preferred_building,
                required_room_type=data.get("required_room_type") or "普通教室",
                unavailable_slot_ids=data.get("unavailable_slot_ids") or "",
                status=course.status,
            )
        )
    elif len(sections) == 1:
        sections[0].section_name = f"{course.course_name} 01班"
        sections[0].teacher_id = course.teacher_id
        sections[0].capacity = course.capacity
        sections[0].preferred_building = course.preferred_building
        sections[0].required_room_type = data.get("required_room_type", sections[0].required_room_type) or "普通教室"
        sections[0].unavailable_slot_ids = data.get("unavailable_slot_ids", sections[0].unavailable_slot_ids) or ""
        sections[0].status = course.status

    db.session.commit()
    return jsonify({"success": True, "data": serialize_course(course)})


@app.route("/api/course-schedule/courses/<course_id>/sections", methods=["POST"])
@require_auth("admin")
def create_course_section(_user, course_id):
    """新增课程教学班，仅管理员可访问。"""

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    data = request.get_json() or {}
    try:
        capacity = parse_positive_int(data.get("capacity"), "capacity", course.capacity)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    section_count = CourseSection.query.filter_by(course_id=course_id).count()
    section_id = data.get("section_id") or f"{course_id}-{section_count + 1:02d}"
    if db.session.get(CourseSection, section_id):
        return jsonify({"success": False, "message": "教学班编号已存在"}), 409

    # 自动生成教学班名称，自动使用课程的教师
    auto_name = data.get("section_name") or f"{course.course_name} {section_count + 1:02d}班"
    auto_teacher = data.get("teacher_id") or course.teacher_id

    section = CourseSection(
        section_id=section_id,
        course_id=course_id,
        section_name=auto_name,
        teacher_id=auto_teacher,
        capacity=capacity,
        preferred_building=data.get("preferred_building") or course.preferred_building,
        required_room_type=data.get("required_room_type") or "普通教室",
        unavailable_slot_ids=data.get("unavailable_slot_ids") or "",
        status=data.get("status", "open"),
    )
    db.session.add(section)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_section(section)}), 201


@app.route("/api/course-schedule/sections/<section_id>", methods=["PUT"])
@require_auth("admin")
def update_course_section(_user, section_id):
    """更新课程教学班，仅管理员可访问。"""

    section = db.session.get(CourseSection, section_id)
    if not section:
        return jsonify({"success": False, "message": "教学班不存在"}), 404

    data = request.get_json() or {}
    try:
        capacity = parse_positive_int(data.get("capacity"), "capacity", section.capacity)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    section.section_name = data.get("section_name", section.section_name)
    section.teacher_id = data.get("teacher_id", section.teacher_id)
    section.capacity = capacity
    section.preferred_building = data.get("preferred_building", section.preferred_building)
    section.required_room_type = data.get("required_room_type", section.required_room_type) or "普通教室"
    section.unavailable_slot_ids = data.get("unavailable_slot_ids", section.unavailable_slot_ids) or ""
    section.status = data.get("status", section.status)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_section(section)})


@app.route("/api/course-schedule/sections/<section_id>", methods=["DELETE"])
@require_auth("admin")
def delete_course_section(_user, section_id):
    """删除未被使用的课程教学班，仅管理员可访问。"""

    section = db.session.get(CourseSection, section_id)
    if not section:
        return jsonify({"success": False, "message": "教学班不存在"}), 404

    has_requests = CourseRequest.query.filter_by(section_id=section_id).first()
    has_results = ScheduleResult.query.filter_by(section_id=section_id).first()
    if has_requests or has_results:
        return jsonify({"success": False, "message": "教学班已有选课申请或排课结果，请改为停止选课"}), 400

    db.session.delete(section)
    db.session.commit()
    return jsonify({"success": True, "message": "教学班已删除"})


@app.route("/api/course-schedule/courses/<course_id>", methods=["DELETE"])
@require_auth("admin")
def delete_course(_user, course_id):
    """删除课程及本服务内关联排课数据，仅管理员可访问。"""

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    ScheduleResult.query.filter_by(course_id=course_id).delete()
    CourseRequest.query.filter_by(course_id=course_id).delete()
    CourseSection.query.filter_by(course_id=course_id).delete()
    db.session.delete(course)
    db.session.commit()
    return jsonify({"success": True, "message": "课程已删除"})


@app.route("/api/course-schedule/time-slots", methods=["GET"])
@require_auth("student", "admin", "teacher")
def list_time_slots(_user):
    """查询候选排课时间段。"""

    slots = TimeSlot.query.order_by(TimeSlot.weekday, TimeSlot.start_time).all()
    return jsonify({"success": True, "data": [serialize_slot(slot) for slot in slots]})


@app.route("/api/course-schedule/classrooms", methods=["GET"])
@require_auth("admin")
def list_classrooms(_user):
    """查询可用于排课的教室列表，仅管理员可访问。"""

    classrooms = Classroom.query.order_by(Classroom.classroom_id).all()
    return jsonify({"success": True, "data": [serialize_classroom(classroom) for classroom in classrooms]})


@app.route("/api/course-schedule/teachers", methods=["GET"])
@require_auth("admin")
def list_teachers(_user):
    """查询教师列表，仅管理员可访问。"""

    teachers = Teacher.query.order_by(Teacher.teacher_id).all()
    return jsonify({"success": True, "data": [{
        "teacher_id": t.teacher_id,
        "name": t.name or t.teacher_id,
        "college": t.college or "",
        "title": t.title or "",
    } for t in teachers]})


@app.route("/api/course-schedule/buildings", methods=["GET"])
@require_auth("admin")
def list_buildings(_user):
    """查询楼栋列表，仅管理员可访问。"""

    buildings = Building.query.order_by(Building.building_id).all()
    return jsonify({"success": True, "data": [{
        "id": b.building_id,
        "name": b.building_name,
    } for b in buildings]})


@app.route("/api/course-schedule/time-slots", methods=["POST"])
@require_auth("admin")
def create_time_slot(_user):
    """新增候选排课时间段，仅管理员可访问。"""

    data = request.get_json() or {}
    required = ["weekday", "start_time", "end_time"]
    if any(not data.get(field) for field in required):
        return jsonify({"success": False, "message": "weekday、start_time 和 end_time 必填"}), 400

    try:
        weekday = parse_positive_int(data.get("weekday"), "weekday")
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    if weekday > 7:
        return jsonify({"success": False, "message": "weekday must be between 1 and 7"}), 400

    slot = TimeSlot(
        weekday=weekday,
        start_time=data["start_time"],
        end_time=data["end_time"],
        label=data.get("label"),
    )
    db.session.add(slot)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_slot(slot)}), 201


@app.route("/api/course-schedule/requests", methods=["POST"])
@require_auth("student")
def submit_course_request(user):
    """提交或更新当前学生的选课申请。"""

    allowed, message = ensure_batch_action("submit")
    if not allowed:
        return jsonify({"success": False, "message": message}), 400

    data = request.get_json() or {}
    course_id = data.get("course_id")
    if not course_id:
        return jsonify({"success": False, "message": "course_id 必填"}), 400
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404
    if course.status != "open":
        return jsonify({"success": False, "message": "当前课程未开放选课"}), 400
    eligible, eligibility_message = check_course_eligibility(course, user["user_id"])
    if not eligible:
        return jsonify({"success": False, "message": eligibility_message}), 400

    section_id = data.get("section_id")
    if not section_id:
        return jsonify({"success": False, "message": "请选择具体教学班"}), 400
    section = db.session.get(CourseSection, section_id)
    if not section or section.course_id != course_id:
        return jsonify({"success": False, "message": "教学班不存在或不属于当前课程"}), 404
    if section.status != "open":
        return jsonify({"success": False, "message": "当前教学班未开放选课"}), 400

    try:
        preference_level = int(data.get("preference_level", 1))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "意向级别必须是数字"}), 400
    if preference_level not in (1, 2, 3):
        return jsonify({"success": False, "message": "意向级别只能是 1、2 或 3"}), 400

    batch = get_active_batch()
    planned_credits = calculate_student_credits(
        user["user_id"],
        replacing_course_id=course_id,
        additional_course=course,
    )
    if planned_credits > float(batch.max_credits):
        return jsonify({
            "success": False,
            "message": f"提交后意向学分为 {planned_credits:g}，超过本批次上限 {batch.max_credits:g} 学分",
        }), 400

    existing = CourseRequest.query.filter_by(
        student_id=user["user_id"],
        course_id=course_id,
    ).first()
    preference_conflict = CourseRequest.query.filter(
        CourseRequest.student_id == user["user_id"],
        CourseRequest.preference_level == preference_level,
        CourseRequest.status.in_(["submitted", "scheduled", "waitlisted"]),
        CourseRequest.course_id != course_id,
    ).first()
    if preference_conflict:
        conflict_name = preference_conflict.section.section_name if preference_conflict.section else (
            preference_conflict.course.course_name if preference_conflict.course else preference_conflict.course_id
        )
        return jsonify({
            "success": False,
            "message": f"{conflict_name} 已经是第 {preference_level} 意向，请先调整或撤销原意向",
        }), 400

    if existing:
        if existing.status == "scheduled":
            return jsonify({"success": False, "message": "已排课的申请不能修改意向"}), 400
        existing.section_id = section_id
        existing.preference_level = preference_level
        existing.status = "submitted"
        db.session.commit()
        return jsonify({"success": True, "data": serialize_request(existing)})

    course_request = CourseRequest(
        student_id=user["user_id"],
        course_id=course_id,
        section_id=section_id,
        preference_level=preference_level,
    )
    db.session.add(course_request)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_request(course_request)}), 201


@app.route("/api/course-schedule/requests/<int:request_id>", methods=["DELETE"])
@require_auth("student")
def cancel_course_request(user, request_id):
    """撤销当前学生尚未完成排课的选课申请。"""

    allowed, message = ensure_batch_action("cancel")
    if not allowed:
        return jsonify({"success": False, "message": message}), 400

    course_request = db.session.get(CourseRequest, request_id)
    if not course_request or course_request.student_id != user["user_id"]:
        return jsonify({"success": False, "message": "选课申请不存在"}), 404
    if course_request.status == "scheduled":
        return jsonify({"success": False, "message": "已排课的申请不能撤销"}), 400

    course_request.status = "cancelled"
    db.session.commit()
    return jsonify({"success": True, "data": serialize_request(course_request)})


@app.route("/api/course-schedule/my-requests", methods=["GET"])
@require_auth("student")
def list_my_requests(user):
    """查询当前学生提交的选课申请。"""

    requests_for_student = CourseRequest.query.filter_by(student_id=user["user_id"]).all()
    return jsonify({
        "success": True,
        "data": [serialize_request(course_request) for course_request in requests_for_student],
    })


@app.route("/api/course-schedule/requests", methods=["GET"])
@require_auth("admin")
def list_all_requests(_user):
    """查询全部选课申请，可按课程编号过滤，仅管理员可访问。"""

    course_id = request.args.get("course_id")
    query = CourseRequest.query
    if course_id:
        query = query.filter_by(course_id=course_id)
    requests_for_courses = query.order_by(CourseRequest.created_at.desc()).all()
    return jsonify({
        "success": True,
        "data": [serialize_request(course_request) for course_request in requests_for_courses],
    })


@app.route("/api/course-schedule/teacher/sections", methods=["GET"])
@require_auth("teacher")
def list_teacher_sections(user):
    """查询当前教师负责的教学班。"""

    sections = (
        CourseSection.query.filter_by(teacher_id=user["user_id"])
        .order_by(CourseSection.course_id, CourseSection.section_id)
        .all()
    )
    return jsonify({"success": True, "data": [serialize_section(section) for section in sections]})


@app.route("/api/course-schedule/teacher/requests", methods=["GET"])
@require_auth("teacher")
def list_teacher_requests(user):
    """查询当前教师教学班下的学生选课申请。"""

    section_ids = [
        row[0]
        for row in db.session.query(CourseSection.section_id)
        .filter(CourseSection.teacher_id == user["user_id"])
        .all()
    ]
    if not section_ids:
        return jsonify({"success": True, "data": []})
    requests_for_teacher = (
        CourseRequest.query.filter(CourseRequest.section_id.in_(section_ids))
        .order_by(CourseRequest.section_id, CourseRequest.preference_level, CourseRequest.created_at)
        .all()
    )
    return jsonify({"success": True, "data": [serialize_request(course_request) for course_request in requests_for_teacher]})


@app.route("/api/course-schedule/teacher/sections/<section_id>/availability", methods=["PUT"])
@require_auth("teacher")
def update_teacher_section_availability(user, section_id):
    """教师维护自己教学班的不可用时间段。"""

    section = db.session.get(CourseSection, section_id)
    if not section or section.teacher_id != user["user_id"]:
        return jsonify({"success": False, "message": "教学班不存在或不属于当前教师"}), 404

    data = request.get_json() or {}
    section.unavailable_slot_ids = data.get("unavailable_slot_ids", section.unavailable_slot_ids) or ""
    db.session.commit()
    return jsonify({"success": True, "data": serialize_section(section)})


@app.route("/api/course-schedule/schedule-runs", methods=["GET"])
@require_auth("admin")
def list_schedule_runs(_user):
    """查询智能排课执行记录，仅管理员可访问。"""

    runs = ScheduleRun.query.order_by(ScheduleRun.created_at.desc()).all()
    return jsonify({"success": True, "data": [serialize_run(run) for run in runs]})


@app.route("/api/course-schedule/agent/schedule", methods=["POST"])
@require_auth("admin")
def schedule_courses(user):
    """触发规则版智能排课，仅管理员可访问。"""

    allowed, message = ensure_batch_action("schedule")
    if not allowed:
        return jsonify({"success": False, "message": message}), 400

    run, error = run_schedule_agent(user["user_id"])
    if error:
        return jsonify({"success": False, "message": error}), 400
    results = ScheduleResult.query.filter_by(run_id=run.id).all()
    return jsonify({
        "success": True,
        "data": {
            "run_id": run.id,
            "summary": run.summary,
            "results": [serialize_result(result) for result in results],
        },
    })


@app.route("/api/course-schedule/results", methods=["GET"])
@require_auth("student", "admin", "teacher")
def list_results(user):
    """查询排课结果。

    管理员可查看全部生成结果；学生只能查看自己已申请课程中已发布的排课结果。
    """

    query = ScheduleResult.query
    if user["user_type"] == "student":
        requested_section_ids = [
            item.section_id
            for item in CourseRequest.query.filter(
                CourseRequest.student_id == user["user_id"],
                CourseRequest.status == "scheduled",
                CourseRequest.section_id.isnot(None),
            ).all()
        ]
        query = query.filter(ScheduleResult.section_id.in_(requested_section_ids))
        query = query.filter_by(is_published=True)
    elif user["user_type"] == "teacher":
        teacher_section_ids = [
            row[0]
            for row in db.session.query(CourseSection.section_id)
            .filter(CourseSection.teacher_id == user["user_id"])
            .all()
        ]
        query = query.filter(ScheduleResult.section_id.in_(teacher_section_ids))

    results = query.order_by(ScheduleResult.course_id, ScheduleResult.section_id).all()
    return jsonify({"success": True, "data": [serialize_result(result) for result in results]})


@app.route("/api/course-schedule/results/<int:result_id>", methods=["PUT"])
@require_auth("admin")
def update_schedule_result(_user, result_id):
    """人工调整单条排课结果的教室和时间。"""

    result = db.session.get(ScheduleResult, result_id)
    if not result:
        return jsonify({"success": False, "message": "排课结果不存在"}), 404

    data = request.get_json() or {}
    classroom_id = data.get("classroom_id")
    slot_id = data.get("slot_id")
    if not classroom_id or not slot_id:
        return jsonify({"success": False, "message": "classroom_id 和 slot_id 必填"}), 400

    classroom = db.session.get(Classroom, classroom_id)
    slot = db.session.get(TimeSlot, slot_id)
    if not classroom:
        return jsonify({"success": False, "message": "教室不存在"}), 404
    if not slot:
        return jsonify({"success": False, "message": "时间段不存在"}), 404

    result.classroom_id = classroom_id
    result.slot_id = slot.slot_id
    result.is_published = False
    result.score = 0
    result.reason = (
        f"管理员人工调整：教室 {classroom_id}，"
        f"时间 {slot.label or ''} {slot.start_time}-{slot.end_time}。"
        "请在发布前重新检查教室、教师和学生时间冲突。"
    )
    db.session.commit()
    return jsonify({"success": True, "data": serialize_result(result)})


@app.route("/api/course-schedule/results/publish", methods=["POST"])
@require_auth("admin")
def publish_results(_user):
    """
    发布排课结果，发布后学生端可查看。
    
    ⚠️ 跨库同步说明：
    发布排课结果后，需要将 scheduled 状态的选课申请同步到
    classroom_database.course_students（课堂教学管理的教学班学生表）。
    
    同步规则：
    - 仅同步 status='scheduled' 的选课申请
    - 按课程名称匹配 cs_courses.course_name ↔ classroom_database.courses.name
    - 课程时间/地点按 课程名+学期 匹配，不存在则 INSERT，存在则 UPDATE
    - 学生同步带上 semester 字段，不同学期数据独立
    
    数据流向：
    cs_course_requests (选课申请) → cs_schedule_results (排课结果)
      ↓ 发布后
    classroom.course_students (教学班学生) ← 课堂教学管理
    """

    allowed, message = ensure_batch_action("publish")
    if not allowed:
        return jsonify({"success": False, "message": message}), 400

    updated = ScheduleResult.query.update({"is_published": True})
    db.session.commit()
    
    # 获取当前活跃批次的学期标识
    active_batch = get_active_batch()
    semester = active_batch.term_name if active_batch else "2025-2026-2"
    
    # 先同步课程时间/地点到 classroom_database.courses（课程名+学期）
    course_sync_count = _sync_course_time_location_to_classroom(semester)
    
    # 再同步选课学生到 classroom_database.course_students（带学期）
    sync_count = _sync_scheduled_students_to_classroom(semester)
    
    return jsonify({
        "success": True,
        "message": f"已发布 {updated} 条排课结果",
        "synced_students": sync_count,
        "synced_courses": course_sync_count
    })


def _sync_scheduled_students_to_classroom(semester):
    """
    将 scheduled 状态的选课学生同步到 classroom_database.course_students。
    
    同步逻辑：
    1. 查询所有 status='scheduled' 的选课申请
    2. 按课程名称 + 学期匹配 classroom_database.courses
    3. 将匹配成功的学生插入 classroom_database.course_students（带 semester）
    
    返回：成功同步的学生数量
    
    ⚠️ 跨库同步限制：
    - course_schedule_database 和 classroom_database 维护独立的课程目录
    - 只有名称+学期完全匹配的课程才能自动同步
    - 名称不匹配的课程需要管理员手动处理
    """
    import pymysql
    
    # 获取数据库密码
    _DB_PASS = os.getenv("DB_PASS", "")
    _DB_PASS_RAW = unquote(_DB_PASS)
    
    sync_count = 0
    
    try:
        # 查询 scheduled 选课
        scheduled = db.session.execute(
            db.text("""
                SELECT r.student_id, r.course_id, c.course_name
                FROM cs_course_requests r
                JOIN cs_courses c ON r.course_id = c.course_id
                WHERE r.status = 'scheduled'
            """)
        ).fetchall()
        
        if not scheduled:
            return 0
        
        # 连接 classroom_database
        cl_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=_DB_PASS_RAW,
            database="classroom_database", charset="utf8mb4"
        )
        cl_cur = cl_conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取 classroom.courses 的 (name, semester)→id 映射
        cl_cur.execute("SELECT id, name, semester FROM courses")
        cl_courses = {}  # key: (name, semester) → id
        for r in cl_cur.fetchall():
            cl_courses[(r['name'], r['semester'])] = r['id']
        
        # 本次同步已处理集合（防止同一批次内重复插入）
        synced_in_batch = set()
        
        # 同步
        for row in scheduled:
            course_name = row[2]  # course_name
            student_id = row[0]   # student_id
            
            course_key = (course_name, semester)
            if course_key in cl_courses:
                cl_course_id = cl_courses[course_key]
                entry_key = (student_id, cl_course_id, semester)
                if entry_key not in synced_in_batch:
                    cl_cur.execute(
                        "INSERT INTO course_students (course_id, student_id, semester, final_grade) VALUES (%s, %s, %s, NULL)",
                        (cl_course_id, student_id, semester)
                    )
                    synced_in_batch.add(entry_key)
                    sync_count += 1
            else:
                logger.warning(
                    f"跨库同步跳过: 课程「{course_name}」(学期={semester}) 不在 classroom_database.courses 中，"
                    f"学生={student_id} 需手动处理"
                )
        
        cl_conn.commit()
        cl_cur.close()
        cl_conn.close()
        
        if sync_count > 0:
            logger.info(f"跨库同步完成: {sync_count} 名学生已同步到 classroom_database.course_students (学期={semester})")
        
    except Exception as e:
        logger.error(f"跨库同步失败: {e}")
        import traceback
        traceback.print_exc()
    
    return sync_count


def _sync_courses_to_classroom(semester):
    """
    将排课端的课程（cs_courses）同步到课堂管理端（classroom_database.courses）。
    
    同步规则：
    - 读取 cs_courses 中所有课程
    - 按 课程名称+学期 匹配 classroom_database.courses
    - 不存在则 INSERT（自动生成 CLS 编号），已存在则跳过（保留课堂端已有数据）
    - 字段映射：course_name→name, teacher_id→teacher_id, credits→credits
    """
    import pymysql
    _DB_PASS = os.getenv("DB_PASS", "")
    _DB_PASS_RAW = unquote(_DB_PASS)
    
    inserted = 0
    skipped = 0
    
    try:
        # 读取所有排课端课程
        cs_courses = db.session.execute(
            db.text("""
                SELECT c.course_id, c.course_name, c.teacher_id, c.credits,
                       COALESCE(s.teacher_id, c.teacher_id) AS section_teacher_id
                FROM cs_courses c
                LEFT JOIN cs_course_sections s ON c.course_id = s.course_id
                WHERE c.status = 'open'
            """)
        ).fetchall()
        
        if not cs_courses:
            return 0, 0
        
        # 去重（同一课程可能有多个 section）
        seen = {}
        for row in cs_courses:
            course_name = row[1]
            if course_name not in seen:
                seen[course_name] = {
                    "course_name": course_name,
                    "teacher_id": row[4] or row[2] or "",  # section teacher 优先
                    "credits": float(row[3]) if row[3] else 2.0,
                }
        
        cl_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=_DB_PASS_RAW,
            database="classroom_database", charset="utf8mb4"
        )
        cl_cur = cl_conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取已有课程的 (name, semester)→id 映射 + 最大 code 编号
        cl_cur.execute("SELECT id, name, semester, code FROM courses")
        existing = {}
        max_code_num = 0
        for r in cl_cur.fetchall():
            existing[(r['name'], r['semester'])] = r
            code = r.get('code') or ''
            if code.startswith('CLS'):
                try:
                    num = int(code[3:])
                    if num > max_code_num:
                        max_code_num = num
                except ValueError:
                    pass
        
        for name, info in seen.items():
            key = (name, semester)
            if key in existing:
                skipped += 1
                continue
            
            # 生成新课编号
            max_code_num += 1
            new_code = f"CLS{max_code_num:03d}"
            
            cl_cur.execute(
                """INSERT INTO courses 
                   (semester, name, teacher_id, code, credits, language, course_type, 
                    teaching_method, target_grade, target_major, description, class_time, location)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (semester, name, info['teacher_id'], new_code, info['credits'],
                 '中文', '选修', '线下', '', '', '', '', '')
            )
            inserted += 1
        
        cl_conn.commit()
        cl_cur.close()
        cl_conn.close()
        
        logger.info(f"课程同步完成 (学期={semester}): {inserted} 门新课, {skipped} 门已存在")
        return inserted, skipped
        
    except Exception as e:
        logger.error(f"同步课程到课堂失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0


def _sync_course_time_location_to_classroom(semester):
    """
    将排课结果中的时间和教室信息同步到 classroom_database.courses。
    
    同步规则：
    - 查询已发布的 cs_schedule_results，关联 cs_time_slots 和 cs_courses
    - 按 课程名称+学期 匹配 classroom_database.courses
    - 如果课程名+学期不存在则 INSERT 新课程，存在则 UPDATE 时间和地点
    - class_time 格式：{slot_label} {start_time}-{end_time}（如"周一 1-2节 08:00-09:40"）
    """
    try:
        results = db.session.execute(
            db.text("""
                SELECT c.course_name, r.classroom_id, s.label, s.start_time, s.end_time
                FROM cs_schedule_results r
                JOIN cs_courses c ON r.course_id = c.course_id
                JOIN cs_time_slots s ON r.slot_id = s.slot_id
                WHERE r.is_published = 1
            """)
        ).fetchall()
        
        if not results:
            return 0
        
        _DB_PASS = os.getenv("DB_PASS", "")
        _DB_PASS_RAW = unquote(_DB_PASS)
        
        cl_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=_DB_PASS_RAW,
            database="classroom_database", charset="utf8mb4"
        )
        cl_cur = cl_conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取现有课程的 (name, semester)→id 映射
        cl_cur.execute("SELECT id, name, semester FROM courses")
        existing_courses = {(r['name'], r['semester']): r['id'] for r in cl_cur.fetchall()}
        
        inserted = 0
        updated = 0
        for row in results:
            course_name = row[0]
            classroom_id = row[1]
            slot_label = row[2] or ""
            start_time = row[3] or ""
            end_time = row[4] or ""
            class_time = f"{slot_label} {start_time}-{end_time}".strip()
            
            course_key = (course_name, semester)
            if course_key in existing_courses:
                # 同一学期内 UPDATE
                cl_cur.execute(
                    "UPDATE courses SET class_time = %s, location = %s WHERE id = %s",
                    (class_time, classroom_id, existing_courses[course_key])
                )
                updated += cl_cur.rowcount
            else:
                # 新学期新课程：INSERT
                cl_cur.execute(
                    "INSERT INTO courses (name, semester, class_time, location) VALUES (%s, %s, %s, %s)",
                    (course_name, semester, class_time, classroom_id)
                )
                new_id = cl_cur.lastrowid
                existing_courses[course_key] = new_id
                inserted += 1
        
        cl_conn.commit()
        cl_cur.close()
        cl_conn.close()
        
        if inserted > 0 or updated > 0:
            logger.info(f"课程时间/地点同步完成: {inserted} 门新课已插入, {updated} 门课程已更新 (学期={semester})")
        return inserted + updated
        
    except Exception as e:
        logger.error(f"同步课程时间/地点失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


@app.route("/api/course-schedule/sync-to-classroom", methods=["POST"])
@require_auth("admin")
def sync_to_classroom(_user):
    """
    学期结束：将排课结果完整同步到课堂管理系统，并清空排课数据。

    完整流程：
    1. 导出 classroom_database 旧数据到备份文件
    2. 导出 course_schedule_database 当前数据到备份文件
    3. 清空 classroom_database.course_students
    4. 从已发布排课结果重建 course_students（按课程名匹配）
    5. 清空 course_schedule_database 操作数据

    返回：各步骤执行结果
    """
    import pymysql
    from datetime import datetime as dt
    from decimal import Decimal

    _DB_PASS = os.getenv("DB_PASS", "")
    _DB_PASS_RAW = unquote(_DB_PASS)
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups", timestamp)
    os.makedirs(backup_dir, exist_ok=True)

    def _serialize(val):
        if isinstance(val, dt):
            return val.isoformat()
        if isinstance(val, Decimal):
            return float(val)
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        return val

    report = {"backup_dir": backup_dir, "steps": []}

    # ── 1. 导出 classroom_database ──
    try:
        cl_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=_DB_PASS_RAW,
            database="classroom_database", charset="utf8mb4"
        )
        cl_cur = cl_conn.cursor(pymysql.cursors.DictCursor)

        for table in ["courses", "course_students"]:
            cl_cur.execute(f"SELECT * FROM {table}")
            rows = cl_cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    row[k] = _serialize(v)
            path = os.path.join(backup_dir, f"classroom_{table}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            report["steps"].append(f"导出 classroom.{table}: {len(rows)} 行")

        cl_cur.close()
        cl_conn.close()
    except Exception as e:
        report["steps"].append(f"❌ 导出 classroom 失败: {e}")
        return jsonify({"success": False, "message": f"备份课堂数据失败: {e}", "report": report}), 500

    # ── 2. 导出 course_schedule_database ──
    try:
        sch_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=_DB_PASS_RAW,
            database="course_schedule_database", charset="utf8mb4"
        )
        sch_cur = sch_conn.cursor(pymysql.cursors.DictCursor)

        for table in ["cs_course_requests", "cs_schedule_results", "cs_schedule_runs", "cs_courses", "cs_course_sections"]:
            sch_cur.execute(f"SELECT * FROM {table}")
            rows = sch_cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    row[k] = _serialize(v)
            path = os.path.join(backup_dir, f"schedule_{table}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            report["steps"].append(f"导出 schedule.{table}: {len(rows)} 行")

        sch_cur.close()
        sch_conn.close()
    except Exception as e:
        report["steps"].append(f"❌ 导出排课数据失败: {e}")
        return jsonify({"success": False, "message": f"备份排课数据失败: {e}", "report": report}), 500

    # 获取当前活跃批次的学期标识
    active_batch = get_active_batch()
    semester = active_batch.term_name if active_batch else "2025-2026-2"

    # ── 3. 清空 classroom_database 当前学期数据 ──
    try:
        cl_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=_DB_PASS_RAW,
            database="classroom_database", charset="utf8mb4"
        )
        cl_cur = cl_conn.cursor()
        cl_cur.execute("SET FOREIGN_KEY_CHECKS=0")
        cl_cur.execute("DELETE FROM course_students WHERE semester = %s", (semester,))
        cl_cur.execute("SET FOREIGN_KEY_CHECKS=1")
        cl_conn.commit()
        report["steps"].append(f"清空 classroom.course_students (学期={semester}): {cl_cur.rowcount} 行")
        cl_cur.close()
        cl_conn.close()
    except Exception as e:
        report["steps"].append(f"❌ 清空课堂学生表失败: {e}")
        return jsonify({"success": False, "message": f"清空课堂数据失败: {e}", "report": report}), 500

    # ── 3.5 同步排课端课程到课堂管理端（课程名+学期不存在则 INSERT）──
    try:
        course_inserted, course_skipped = _sync_courses_to_classroom(semester)
        report["steps"].append(f"同步课程到 classroom (学期={semester}): 新增 {course_inserted} 门, 跳过 {course_skipped} 门（已存在）")
    except Exception as e:
        report["steps"].append(f"❌ 同步课程失败: {e}")

    # ── 4. 从排课结果重建 course_students ──
    synced = 0
    skipped = 0
    try:
        scheduled = db.session.execute(
            db.text("""
                SELECT r.student_id, r.course_id, c.course_name
                FROM cs_course_requests r
                JOIN cs_courses c ON r.course_id = c.course_id
                WHERE r.status = 'scheduled'
            """)
        ).fetchall()

        cl_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=_DB_PASS_RAW,
            database="classroom_database", charset="utf8mb4"
        )
        cl_cur = cl_conn.cursor(pymysql.cursors.DictCursor)
        cl_cur.execute("SELECT id, name, semester FROM courses")
        cl_courses = {}  # key: (name, semester) → id
        for r in cl_cur.fetchall():
            cl_courses[(r['name'], r['semester'])] = r['id']
        synced_in_batch = set()

        for row in scheduled:
            course_name = row[2]
            student_id = row[0]
            course_key = (course_name, semester)
            if course_key in cl_courses:
                cl_course_id = cl_courses[course_key]
                entry_key = (student_id, cl_course_id, semester)
                if entry_key not in synced_in_batch:
                    cl_cur.execute(
                        "INSERT INTO course_students (course_id, student_id, semester, final_grade) VALUES (%s, %s, %s, NULL)",
                        (cl_course_id, student_id, semester)
                    )
                    synced_in_batch.add(entry_key)
                    synced += 1
            else:
                skipped += 1

        cl_conn.commit()
        cl_cur.close()
        cl_conn.close()
        report["steps"].append(f"同步学生到 classroom (学期={semester}): {synced} 人, 跳过 {skipped} 人（课程名不匹配）")

        # ── 4.5 同步课程时间/地点到 classroom_database.courses ──
        time_updated = _sync_course_time_location_to_classroom(semester)
        report["steps"].append(f"更新课程时间/地点 (学期={semester}): {time_updated} 门课程")

    except Exception as e:
        report["steps"].append(f"❌ 同步学生失败: {e}")
        return jsonify({"success": False, "message": f"同步学生数据失败: {e}", "report": report}), 500

    # ── 5. 清空 course_schedule_database 操作数据 ──
    try:
        sch_conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT, user=DB_USER, password=_DB_PASS_RAW,
            database="course_schedule_database", charset="utf8mb4"
        )
        sch_cur = sch_conn.cursor()
        sch_cur.execute("SET FOREIGN_KEY_CHECKS=0")
        sch_cur.execute("DELETE FROM cs_schedule_results")
        sch_cur.execute("DELETE FROM cs_course_requests")
        sch_cur.execute("DELETE FROM cs_schedule_runs")
        sch_cur.execute("SET FOREIGN_KEY_CHECKS=1")
        sch_conn.commit()
        report["steps"].append(f"清空排课数据库操作表完成")
        sch_cur.close()
        sch_conn.close()
    except Exception as e:
        report["steps"].append(f"❌ 清空排课数据失败: {e}")
        return jsonify({"success": False, "message": f"清空排课数据失败: {e}", "report": report}), 500

    report["steps"].append(f"✅ 全部完成：备份至 {backup_dir}，同步 {synced} 名学生，跳过 {skipped} 人")
    return jsonify({"success": True, "message": "学期同步完成", "report": report})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)

