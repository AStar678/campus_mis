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

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy


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


# 选课排课业务表，由本服务独立维护，统一使用 cs_ 表名前缀。
class Course(db.Model):
    """可选课程信息，供学生提交申请、管理员参与排课。"""

    __tablename__ = "cs_courses"

    course_id = db.Column(db.String(20), primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.String(20))
    capacity = db.Column(db.Integer, nullable=False, default=40)
    hours_per_week = db.Column(db.Integer, nullable=False, default=2)
    preferred_building = db.Column(db.String(50))
    status = db.Column(db.String(20), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class CourseRequest(db.Model):
    """学生选课申请记录。"""

    __tablename__ = "cs_course_requests"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", name="uq_cs_request_student_course"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(20), nullable=False, index=True)
    course_id = db.Column(db.String(20), db.ForeignKey("cs_courses.course_id"), nullable=False)
    preference_level = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="submitted")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    course = db.relationship("Course")


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
    classroom_id = db.Column(db.String(4), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("cs_time_slots.slot_id"), nullable=False)
    enrolled_count = db.Column(db.Integer, nullable=False, default=0)
    score = db.Column(db.Float, nullable=False, default=0)
    reason = db.Column(db.String(500))
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    course = db.relationship("Course")
    slot = db.relationship("TimeSlot")


def serialize_course(course):
    """将课程模型转换为前端接口返回结构。"""

    request_count = CourseRequest.query.filter_by(course_id=course.course_id).count()
    active_request_count = CourseRequest.query.filter(
        CourseRequest.course_id == course.course_id,
        CourseRequest.status.in_(["submitted", "scheduled"]),
    ).count()
    status_label_map = {
        "open": "开放选课",
        "closed": "停止选课",
    }
    return {
        "course_id": course.course_id,
        "course_name": course.course_name,
        "teacher_id": course.teacher_id,
        "capacity": course.capacity,
        "hours_per_week": course.hours_per_week,
        "preferred_building": course.preferred_building,
        "status": course.status,
        "status_label": status_label_map.get(course.status, course.status),
        "request_count": request_count,
        "active_request_count": active_request_count,
        "remaining_capacity": max(course.capacity - active_request_count, 0),
    }


def serialize_request(course_request):
    """将选课申请模型转换为前端接口返回结构。"""

    status_label_map = {
        "submitted": "已提交",
        "scheduled": "已排课",
        "cancelled": "已撤销",
    }
    return {
        "id": course_request.id,
        "student_id": course_request.student_id,
        "course_id": course_request.course_id,
        "course_name": course_request.course.course_name if course_request.course else None,
        "preference_level": course_request.preference_level,
        "preference_label": f"第 {course_request.preference_level} 意向",
        "status": course_request.status,
        "status_label": status_label_map.get(course_request.status, course_request.status),
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
        "course_name": result.course.course_name if result.course else None,
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


def score_assignment(course, classroom, slot, request_count, used_pairs):
    """为单个课程、教室、时间段候选组合计算排课评分。"""

    capacity_gap = course.capacity - request_count
    capacity_score = 40 if capacity_gap >= 0 else max(0, 40 + capacity_gap * 2)
    demand_score = min(request_count, course.capacity) * 1.5
    distance = get_distance_between_buildings(course.preferred_building, classroom.building)
    distance_penalty = distance / 20
    conflict_penalty = 60 if (classroom.classroom_id, slot.slot_id) in used_pairs else 0
    score = capacity_score + demand_score - distance_penalty - conflict_penalty
    reason = (
        f"选课人数 {request_count}，教室容量参考 {course.capacity}；"
        f"课程偏好楼栋 {course.preferred_building or '未设置'}，"
        f"分配教室楼栋 {classroom.building}，距离惩罚 {round(distance_penalty, 1)}。"
    )
    return score, reason


def run_schedule_agent(run_by):
    """使用规则版 Agent 生成排课结果。

    当前实现保持确定性和可解释性，综合评估课程需求、容量匹配、教室时间冲突和楼栋距离。
    后续接入真正的智能 Agent 时，可复用本函数的输入输出结构。
    """

    courses = Course.query.filter_by(status="open").all()
    classrooms = Classroom.query.all()
    slots = TimeSlot.query.all()
    if not courses or not classrooms or not slots:
        return None, "缺少课程、教室或时间段数据，无法排课"

    ScheduleResult.query.delete()
    used_pairs = set()
    results = []

    run = ScheduleRun(run_by=run_by, status="running", summary="智能排课任务运行中")
    db.session.add(run)
    db.session.flush()

    for course in courses:
        requests_for_course = CourseRequest.query.filter(
            CourseRequest.course_id == course.course_id,
            CourseRequest.status.in_(["submitted", "scheduled"]),
        ).all()
        request_count = len(requests_for_course)
        best = None

        for classroom in classrooms:
            for slot in slots:
                score, reason = score_assignment(course, classroom, slot, request_count, used_pairs)
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
        for course_request in requests_for_course[: course.capacity]:
            course_request.status = "scheduled"

        result = ScheduleResult(
            run_id=run.id,
            course_id=course.course_id,
            classroom_id=best["classroom"].classroom_id,
            slot_id=best["slot"].slot_id,
            enrolled_count=min(request_count, course.capacity),
            score=round(best["score"], 2),
            reason=best["reason"],
        )
        db.session.add(result)
        results.append(result)

    run.status = "completed"
    run.summary = f"完成 {len(results)} 门课程排课"
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


@app.route("/api/course-schedule/courses", methods=["GET"])
@require_auth("student", "admin")
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
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    course = Course(
        course_id=data["course_id"],
        course_name=data["course_name"],
        teacher_id=data.get("teacher_id"),
        capacity=capacity,
        hours_per_week=hours_per_week,
        preferred_building=data.get("preferred_building"),
        status=data.get("status", "open"),
    )
    db.session.add(course)
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
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    course.course_name = data.get("course_name", course.course_name)
    course.teacher_id = data.get("teacher_id", course.teacher_id)
    course.capacity = capacity
    course.hours_per_week = hours_per_week
    course.preferred_building = data.get("preferred_building", course.preferred_building)
    course.status = data.get("status", course.status)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_course(course)})


@app.route("/api/course-schedule/courses/<course_id>", methods=["DELETE"])
@require_auth("admin")
def delete_course(_user, course_id):
    """删除课程及本服务内关联排课数据，仅管理员可访问。"""

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    CourseRequest.query.filter_by(course_id=course_id).delete()
    ScheduleResult.query.filter_by(course_id=course_id).delete()
    db.session.delete(course)
    db.session.commit()
    return jsonify({"success": True, "message": "课程已删除"})


@app.route("/api/course-schedule/time-slots", methods=["GET"])
@require_auth("student", "admin")
def list_time_slots(_user):
    """查询候选排课时间段。"""

    slots = TimeSlot.query.order_by(TimeSlot.weekday, TimeSlot.start_time).all()
    return jsonify({"success": True, "data": [serialize_slot(slot) for slot in slots]})


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

    data = request.get_json() or {}
    course_id = data.get("course_id")
    if not course_id:
        return jsonify({"success": False, "message": "course_id 必填"}), 400
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404
    if course.status != "open":
        return jsonify({"success": False, "message": "当前课程未开放选课"}), 400
    try:
        preference_level = int(data.get("preference_level", 1))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "意向级别必须是数字"}), 400
    if preference_level not in (1, 2, 3):
        return jsonify({"success": False, "message": "意向级别只能是 1、2 或 3"}), 400

    existing = CourseRequest.query.filter_by(
        student_id=user["user_id"],
        course_id=course_id,
    ).first()
    preference_conflict = CourseRequest.query.filter(
        CourseRequest.student_id == user["user_id"],
        CourseRequest.preference_level == preference_level,
        CourseRequest.status.in_(["submitted", "scheduled"]),
        CourseRequest.course_id != course_id,
    ).first()
    if preference_conflict:
        conflict_name = preference_conflict.course.course_name if preference_conflict.course else preference_conflict.course_id
        return jsonify({
            "success": False,
            "message": f"{conflict_name} 已经是第 {preference_level} 意向，请先调整或撤销原意向",
        }), 400

    if existing:
        if existing.status == "scheduled":
            return jsonify({"success": False, "message": "已排课的申请不能修改意向"}), 400
        existing.preference_level = preference_level
        existing.status = "submitted"
        db.session.commit()
        return jsonify({"success": True, "data": serialize_request(existing)})

    course_request = CourseRequest(
        student_id=user["user_id"],
        course_id=course_id,
        preference_level=preference_level,
    )
    db.session.add(course_request)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_request(course_request)}), 201


@app.route("/api/course-schedule/requests/<int:request_id>", methods=["DELETE"])
@require_auth("student")
def cancel_course_request(user, request_id):
    """撤销当前学生尚未完成排课的选课申请。"""

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
@require_auth("student", "admin")
def list_results(user):
    """查询排课结果。

    管理员可查看全部生成结果；学生只能查看自己已申请课程中已发布的排课结果。
    """

    query = ScheduleResult.query
    if user["user_type"] == "student":
        requested_course_ids = [
            item.course_id
            for item in CourseRequest.query.filter(
                CourseRequest.student_id == user["user_id"],
                CourseRequest.status.in_(["submitted", "scheduled"]),
            ).all()
        ]
        query = query.filter(ScheduleResult.course_id.in_(requested_course_ids))
        query = query.filter_by(is_published=True)

    results = query.order_by(ScheduleResult.course_id).all()
    return jsonify({"success": True, "data": [serialize_result(result) for result in results]})


@app.route("/api/course-schedule/results/publish", methods=["POST"])
@require_auth("admin")
def publish_results(_user):
    """发布排课结果，发布后学生端可查看。"""

    updated = ScheduleResult.query.update({"is_published": True})
    db.session.commit()
    return jsonify({"success": True, "message": f"已发布 {updated} 条排课结果"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)

