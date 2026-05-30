from datetime import datetime
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
CORS(app)

DB_HOST = os.getenv("DB_HOST", "47.93.226.110")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "main_database")
MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://127.0.0.1:5001")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Public tables owned by the main service. This service reads them only.
class Classroom(db.Model):
    __tablename__ = "classrooms"

    classroom_id = db.Column(db.String(4), primary_key=True)
    building = db.Column(db.String(50))


class Building(db.Model):
    __tablename__ = "buildings"

    building_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_name = db.Column(db.String(50), nullable=False)


class BuildingAdjacency(db.Model):
    __tablename__ = "building_adjacency"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_a = db.Column(db.Integer, nullable=False)
    building_b = db.Column(db.Integer, nullable=False)
    distance = db.Column(db.Float, nullable=False)


# Course scheduling tables owned by this service.
class Course(db.Model):
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
    __tablename__ = "cs_course_requests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(20), nullable=False, index=True)
    course_id = db.Column(db.String(20), db.ForeignKey("cs_courses.course_id"), nullable=False)
    preference_level = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="submitted")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    course = db.relationship("Course")


class TimeSlot(db.Model):
    __tablename__ = "cs_time_slots"

    slot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    label = db.Column(db.String(50))


class ScheduleRun(db.Model):
    __tablename__ = "cs_schedule_runs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_by = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="completed")
    summary = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


class ScheduleResult(db.Model):
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
    request_count = CourseRequest.query.filter_by(course_id=course.course_id).count()
    return {
        "course_id": course.course_id,
        "course_name": course.course_name,
        "teacher_id": course.teacher_id,
        "capacity": course.capacity,
        "hours_per_week": course.hours_per_week,
        "preferred_building": course.preferred_building,
        "status": course.status,
        "request_count": request_count,
    }


def serialize_request(course_request):
    return {
        "id": course_request.id,
        "student_id": course_request.student_id,
        "course_id": course_request.course_id,
        "course_name": course_request.course.course_name if course_request.course else None,
        "preference_level": course_request.preference_level,
        "status": course_request.status,
        "created_at": course_request.created_at.isoformat(),
    }


def serialize_result(result):
    return {
        "id": result.id,
        "run_id": result.run_id,
        "course_id": result.course_id,
        "course_name": result.course.course_name if result.course else None,
        "classroom_id": result.classroom_id,
        "slot_id": result.slot_id,
        "weekday": result.slot.weekday if result.slot else None,
        "start_time": result.slot.start_time if result.slot else None,
        "end_time": result.slot.end_time if result.slot else None,
        "enrolled_count": result.enrolled_count,
        "score": result.score,
        "reason": result.reason,
        "is_published": result.is_published,
        "created_at": result.created_at.isoformat(),
    }


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


def get_distance_between_buildings(building_name_a, building_name_b):
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
        requests_for_course = CourseRequest.query.filter_by(course_id=course.course_id).all()
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


@app.route("/api/course-schedule/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "course-schedule-service", "port": 5004})


@app.route("/api/course-schedule/courses", methods=["GET"])
@require_auth("student", "admin")
def list_courses(_user):
    courses = Course.query.order_by(Course.course_id).all()
    return jsonify({"success": True, "data": [serialize_course(course) for course in courses]})


@app.route("/api/course-schedule/courses", methods=["POST"])
@require_auth("admin")
def create_course(_user):
    data = request.get_json() or {}
    required = ["course_id", "course_name"]
    if any(not data.get(field) for field in required):
        return jsonify({"success": False, "message": "course_id 和 course_name 必填"}), 400
    if db.session.get(Course, data["course_id"]):
        return jsonify({"success": False, "message": "课程编号已存在"}), 409

    course = Course(
        course_id=data["course_id"],
        course_name=data["course_name"],
        teacher_id=data.get("teacher_id"),
        capacity=int(data.get("capacity", 40)),
        hours_per_week=int(data.get("hours_per_week", 2)),
        preferred_building=data.get("preferred_building"),
        status=data.get("status", "open"),
    )
    db.session.add(course)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_course(course)}), 201


@app.route("/api/course-schedule/requests", methods=["POST"])
@require_auth("student")
def submit_course_request(user):
    data = request.get_json() or {}
    course_id = data.get("course_id")
    if not course_id:
        return jsonify({"success": False, "message": "course_id 必填"}), 400
    if not db.session.get(Course, course_id):
        return jsonify({"success": False, "message": "课程不存在"}), 404

    existing = CourseRequest.query.filter_by(
        student_id=user["user_id"],
        course_id=course_id,
    ).first()
    if existing:
        existing.preference_level = int(data.get("preference_level", existing.preference_level))
        existing.status = "submitted"
        db.session.commit()
        return jsonify({"success": True, "data": serialize_request(existing)})

    course_request = CourseRequest(
        student_id=user["user_id"],
        course_id=course_id,
        preference_level=int(data.get("preference_level", 1)),
    )
    db.session.add(course_request)
    db.session.commit()
    return jsonify({"success": True, "data": serialize_request(course_request)}), 201


@app.route("/api/course-schedule/my-requests", methods=["GET"])
@require_auth("student")
def list_my_requests(user):
    requests_for_student = CourseRequest.query.filter_by(student_id=user["user_id"]).all()
    return jsonify({
        "success": True,
        "data": [serialize_request(course_request) for course_request in requests_for_student],
    })


@app.route("/api/course-schedule/requests", methods=["GET"])
@require_auth("admin")
def list_all_requests(_user):
    course_id = request.args.get("course_id")
    query = CourseRequest.query
    if course_id:
        query = query.filter_by(course_id=course_id)
    requests_for_courses = query.order_by(CourseRequest.created_at.desc()).all()
    return jsonify({
        "success": True,
        "data": [serialize_request(course_request) for course_request in requests_for_courses],
    })


@app.route("/api/course-schedule/agent/schedule", methods=["POST"])
@require_auth("admin")
def schedule_courses(user):
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
    query = ScheduleResult.query
    if user["user_type"] == "student":
        requested_course_ids = [
            item.course_id
            for item in CourseRequest.query.filter_by(student_id=user["user_id"]).all()
        ]
        query = query.filter(ScheduleResult.course_id.in_(requested_course_ids))
        query = query.filter_by(is_published=True)

    results = query.order_by(ScheduleResult.course_id).all()
    return jsonify({"success": True, "data": [serialize_result(result) for result in results]})


@app.route("/api/course-schedule/results/publish", methods=["POST"])
@require_auth("admin")
def publish_results(_user):
    updated = ScheduleResult.query.update({"is_published": True})
    db.session.commit()
    return jsonify({"success": True, "message": f"已发布 {updated} 条排课结果"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True)
