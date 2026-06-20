from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import jwt
import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus as _qp
from urllib.request import Request, urlopen
from werkzeug.utils import secure_filename

try:
    import fitz
except ImportError:
    fitz = None


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", BASE_DIR / "frontend"))

# ─── Cloud MySQL Configuration ───────────────────────────────────────────────

DB_HOST = os.environ.get("DB_HOST", "47.93.226.110")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "")

_PASS_ENC = _qp(DB_PASS)
CLASSROOM_DB_URI = f"mysql+pymysql://{DB_USER}:{_PASS_ENC}@{DB_HOST}:{DB_PORT}/classroom_database?charset=utf8mb4"
USERS_DB_URI = f"mysql+pymysql://{DB_USER}:{_PASS_ENC}@{DB_HOST}:{DB_PORT}/users_database?charset=utf8mb4"
COURSE_SCHEDULE_DB_URI = f"mysql+pymysql://{DB_USER}:{_PASS_ENC}@{DB_HOST}:{DB_PORT}/course_schedule_database?charset=utf8mb4"
MAIN_DB_URI = f"mysql+pymysql://{DB_USER}:{_PASS_ENC}@{DB_HOST}:{DB_PORT}/main_database?charset=utf8mb4"

MAIN_SERVICE_URL = os.environ.get("MAIN_SERVICE_URL", "http://127.0.0.1:5001")

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "classroom-teaching-dev-secret-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = CLASSROOM_DB_URI
app.config["SQLALCHEMY_BINDS"] = {
    "users": USERS_DB_URI,
    "course_schedule": COURSE_SCHEDULE_DB_URI,
    "main": MAIN_DB_URI,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
db = SQLAlchemy(app)
app.json.ensure_ascii = False


@app.after_request
def add_utf8_and_no_cache_headers(response):
    if response.mimetype in {"text/html", "application/json", "text/plain"}:
        response.headers["Content-Type"] = f"{response.mimetype}; charset=utf-8"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# Models — mapped to cloud MySQL tables
# ═══════════════════════════════════════════════════════════════════════════════

class Student(db.Model):
    """
    学生信息（只读访问）
    
    ⚠️ 只读！禁止 INSERT/UPDATE/DELETE
    数据真相源：main_service → users_database
    用途：查询学生姓名、年级、专业等信息
    """
    __bind_key__ = "users"
    __tablename__ = "students"
    student_id = db.Column(db.String(8), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    grade = db.Column(db.String(10), default="")
    major = db.Column(db.String(50), default="")
    name = db.Column(db.String(50), default="")


class Teacher(db.Model):
    """
    教师信息（只读访问）
    
    ⚠️ 只读！禁止 INSERT/UPDATE/DELETE
    数据真相源：main_service → users_database
    用途：查询教师姓名、学院、职称等信息
    """
    __bind_key__ = "users"
    __tablename__ = "teachers"
    teacher_id = db.Column(db.String(4), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    college = db.Column(db.String(50), default="")
    title = db.Column(db.String(20), default="")
    name = db.Column(db.String(50), default="")


class Admin(db.Model):
    """
    管理员信息（只读访问）
    
    ⚠️ 只读！禁止 INSERT/UPDATE/DELETE
    数据真相源：main_service → users_database
    """
    __bind_key__ = "users"
    __tablename__ = "admins"
    admin_id = db.Column(db.String(20), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(50), default="")


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    code = db.Column(db.String(32), default="")
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), default="")
    teacher_id = db.Column(db.String(4), nullable=False)
    class_time = db.Column(db.String(120), default="")
    location = db.Column(db.String(120), default="")
    credits = db.Column(db.Float, default=2.0)
    language = db.Column(db.String(20), default="中文")
    course_type = db.Column(db.String(20), default="必修")
    teaching_method = db.Column(db.String(40), default="线下")
    target_grade = db.Column(db.String(16), default="")
    target_major = db.Column(db.String(64), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)


class CourseStudent(db.Model):
    """
    当前教学班学生（真相源）
    
    ✅ 可读写：教师录入成绩、管理选课学生
    数据真相源：classroom_database.course_students
    用途：课堂教学管理的核心数据
    数据流向：
      - 来源：course_schedule_database.cs_course_requests（排课成功后发布时自动同步）
        ⚠️ 同步触发时机：管理员在排课系统执行「发布排课结果」操作时
        ⚠️ 同步方式：按课程名称匹配（cs_courses.course_name ↔ courses.name）
        ⚠️ 限制：仅名称完全匹配的课程可自动同步，不匹配需手动处理
      - 去向：main_database.course_enrollments（学期结束归档）
    """
    __tablename__ = "course_students"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    final_grade = db.Column(db.Float, default=None)


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, default="")
    created_by = db.Column(db.String(32), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)


class Homework(db.Model):
    """Maps to cloud 'homeworks' table (equivalent to Assignment in old code)."""
    __tablename__ = "homeworks"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    deadline = db.Column(db.DateTime)
    answer_pdf = db.Column(db.String(255), default="")
    answer_text = db.Column(db.Text, default="")
    total_score = db.Column(db.Float, default=100)
    created_by = db.Column(db.String(32), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)


class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    homework_id = db.Column(db.Integer, db.ForeignKey("homeworks.id"), nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    content = db.Column(db.Text, default="")
    submit_time = db.Column(db.DateTime, default=datetime.now)
    ai_score = db.Column(db.Float)
    ai_comment = db.Column(db.Text, default="")
    final_score = db.Column(db.Float)
    pdf_path = db.Column(db.String(255), default="")
    extracted_text = db.Column(db.Text, default="")
    ai_detail = db.Column(db.Text, default="[]")
    ai_feedback = db.Column(db.Text, default="")
    teacher_score = db.Column(db.Float)
    teacher_feedback = db.Column(db.Text, default="")
    review_status = db.Column(db.String(20), default="待复核")


class Grade(db.Model):
    __tablename__ = "grades"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    source_type = db.Column(db.String(32), default="course")
    source_id = db.Column(db.Integer)
    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.String(255), default="")
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class DdlItem(db.Model):
    __tablename__ = "ddl_items"
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(20), nullable=False, default="2025-2026-2")
    course_id = db.Column(db.Integer)
    owner_id = db.Column(db.String(32), nullable=False)
    owner_role = db.Column(db.String(16), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    due_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending")


# ── 跨库只读模型 ──

class CsTimeSlot(db.Model):
    """排课时间槽（只读，来源 course_schedule_database）"""
    __bind_key__ = "course_schedule"
    __tablename__ = "cs_time_slots"
    slot_id = db.Column(db.Integer, primary_key=True)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    label = db.Column(db.String(50))


class Classroom(db.Model):
    """教室（只读，来源 main_database）"""
    __bind_key__ = "main"
    __tablename__ = "classrooms"
    classroom_id = db.Column(db.String(4), primary_key=True)
    building = db.Column(db.String(50))


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def token_for(user_id: str, user_type: str) -> str:
    payload = {
        "user_id": user_id,
        "user_type": user_type,
        "exp": datetime.utcnow() + timedelta(hours=12),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def get_user_info(user_id: str, user_type: str) -> dict | None:
    """Fetch user info from users_database based on user_type."""
    if user_type == "student":
        s = Student.query.filter_by(student_id=user_id).first()
        if s:
            return {"user_id": s.student_id, "user_type": "student", "name": s.name or s.student_id, "grade": s.grade or "", "major": s.major or "", "college": ""}
    elif user_type == "teacher":
        t = Teacher.query.filter_by(teacher_id=user_id).first()
        if t:
            return {"user_id": t.teacher_id, "user_type": "teacher", "name": t.name or t.teacher_id, "grade": "", "major": "", "college": t.college or ""}
    elif user_type == "admin":
        a = Admin.query.filter_by(admin_id=user_id).first()
        if a:
            return {"user_id": a.admin_id, "user_type": "admin", "name": a.name or a.admin_id, "grade": "", "major": "", "college": ""}
    return None


def current_user():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    # 每次请求都向主服务实时验证 token（不缓存登录状态）
    verified = verify_token_with_main_service(token)
    if not verified:
        return None
    user_id = verified["user_id"]
    user_type = verified["user_type"]
    info = get_user_info(user_id, user_type)
    if info:
        return type("UserCtx", (), info)()
    return None


def require_roles(*user_types):
    user = current_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录"}), 401)
    if user_types and user.user_type not in user_types:
        return None, (jsonify({"success": False, "message": "无权访问该功能"}), 403)
    return user, None


def parse_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    raise ValueError("时间格式无效")


def dt(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def extract_pdf_text(path: Path) -> str:
    if fitz is None:
        return ""
    with fitz.open(path) as doc:
        return "\n".join(page.get_text("text") for page in doc)[:20000]


def save_pdf(file_storage, prefix: str, required: bool = True) -> tuple[str, str]:
    if not file_storage or not file_storage.filename:
        if required:
            raise ValueError("请上传 PDF 文件")
        return "", ""
    if not file_storage.filename.lower().endswith(".pdf"):
        raise ValueError("只支持 PDF 文件")
    filename = secure_filename(file_storage.filename)
    stored = f"{prefix}_{uuid.uuid4().hex}_{filename}"
    path = UPLOAD_DIR / stored
    file_storage.save(path)
    return stored, extract_pdf_text(path)


def course_dict(course: Course):
    teacher = Teacher.query.filter_by(teacher_id=course.teacher_id).first()
    return {
        "id": course.id,
        "code": course.code or "",
        "name": course.name,
        "description": course.description or "",
        "teacher_id": course.teacher_id or "",
        "teacher_name": (teacher.name if teacher and teacher.name else course.teacher_id) if course.teacher_id else "未分配",
        "class_time": course.class_time or "",
        "location": course.location or "",
        "credits": course.credits or 0,
        "language": course.language or "中文",
        "course_type": course.course_type or "必修",
        "teaching_method": course.teaching_method or "线下",
        "target_grade": course.target_grade or "",
        "target_major": course.target_major or "",
    }


def submission_dict(sub: Submission):
    student = Student.query.filter_by(student_id=sub.student_id).first()
    student_name = (student.name if student and student.name else sub.student_id)
    return {
        "id": sub.id,
        "assignment_id": sub.homework_id,
        "student_id": sub.student_id,
        "student_name": student_name,
        "submitted_at": dt(sub.submit_time),
        "content": sub.content or "",
        "extracted_text": sub.extracted_text or "",
        "ai_score": round(sub.ai_score) if sub.ai_score is not None else None,
        "ai_detail": json.loads(sub.ai_detail or "[]"),
        "ai_feedback": sub.ai_feedback or "",
        "ai_engine": ai_runtime_status()["engine_label"],
        "teacher_score": round(sub.teacher_score) if sub.teacher_score is not None else None,
        "teacher_feedback": sub.teacher_feedback or "",
        "review_status": sub.review_status or "待复核",
    }


def assignment_dict(item: Homework, student_id: str | None = None):
    course = db.session.get(Course, item.course_id)
    sub = None
    submission_count = Submission.query.filter_by(homework_id=item.id).count()
    pending_count = Submission.query.filter_by(homework_id=item.id, review_status="待复核").count()
    if student_id:
        sub = Submission.query.filter_by(homework_id=item.id, student_id=student_id).first()
    return {
        "id": item.id,
        "course_id": item.course_id,
        "course_name": course.name if course else "",
        "title": item.title,
        "requirement": item.description or "",
        "due_at": dt(item.deadline),
        "total_score": item.total_score,
        "has_answer_pdf": bool(item.answer_pdf),
        "has_answer_text": bool(item.answer_text),
        "created_at": dt(item.created_at),
        "submission_count": submission_count,
        "pending_count": pending_count,
        "submission": submission_dict(sub) if sub else None,
    }


def grade_dict(grade: Grade):
    course = db.session.get(Course, grade.course_id)
    teacher = Teacher.query.filter_by(teacher_id=course.teacher_id).first() if course and course.teacher_id else None
    # Look up assignment title if source_id references a homework
    assignment_title = ""
    if grade.source_id:
        hw = db.session.get(Homework, grade.source_id)
        if hw:
            assignment_title = hw.title
    return {
        "id": grade.id,
        "course_id": grade.course_id,
        "course_code": course.code if course else "",
        "course_name": course.name if course else "",
        "credits": course.credits if course else 0,
        "teacher_name": (teacher.name if teacher and teacher.name else "-"),
        "semester": "2025-2026-1",
        "student_id": grade.student_id,
        "source_type": grade.source_type,
        "source_id": grade.source_id,
        "assignment_title": assignment_title,
        "score": round(grade.score) if grade.score is not None else None,
        "comment": grade.comment or "",
        "updated_at": dt(grade.updated_at),
    }


def student_course_ids(user) -> set:
    """获取学生已选课程的 ID 集合，仅基于 course_students 表中的实际选课记录。"""
    return {row.course_id for row in CourseStudent.query.filter_by(student_id=user.user_id)}


def apply_course_filters(query):
    keyword = (request.args.get("keyword") or "").strip()
    course_type = (request.args.get("course_type") or "").strip()
    language = (request.args.get("language") or "").strip()
    teaching_method = (request.args.get("teaching_method") or "").strip()
    min_credits = request.args.get("min_credits")
    max_credits = request.args.get("max_credits")
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(db.or_(Course.name.like(like), Course.code.like(like), Course.location.like(like)))
    if course_type:
        query = query.filter(Course.course_type == course_type)
    if language:
        query = query.filter(Course.language == language)
    if teaching_method:
        query = query.filter(Course.teaching_method == teaching_method)
    if min_credits:
        query = query.filter(Course.credits >= float(min_credits))
    if max_credits:
        query = query.filter(Course.credits <= float(max_credits))
    return query


def deepseek_chat(messages):
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    res = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.2},
        timeout=60,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def ai_runtime_status():
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    configured = bool(api_key)
    return {
        "provider": "DeepSeek" if configured else "本地规则",
        "model": model if configured else "rule-based-fallback",
        "configured": configured,
        "engine_label": f"DeepSeek / {model}" if configured else "本地规则初评",
        "pdf_parser": "PyMuPDF 已启用" if fitz is not None else "PyMuPDF 未安装，PDF 会保留但无法自动抽取文本",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 学期管理工具
# ═══════════════════════════════════════════════════════════════════════════════

_CACHED_SEMESTER = None
_CACHED_SEMESTER_TS = 0


def get_current_semester():
    """获取当前活跃学期，从 course_schedule_database.cs_selection_batches 读取。
    
    缓存 60 秒避免每次请求都跨库查询。
    兜底值：'2025-2026-2'
    """
    global _CACHED_SEMESTER, _CACHED_SEMESTER_TS
    now = datetime.now().timestamp()
    if _CACHED_SEMESTER and (now - _CACHED_SEMESTER_TS) < 60:
        return _CACHED_SEMESTER

    fallback = "2025-2026-2"
    try:
        import pymysql as _pm
        _conn = _pm.connect(
            host=DB_HOST, port=int(DB_PORT), user=DB_USER,
            password=DB_PASS, database="course_schedule_database", charset="utf8mb4"
        )
        _cur = _conn.cursor()
        _cur.execute(
            "SELECT term_name FROM cs_selection_batches WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        )
        _row = _cur.fetchone()
        _conn.close()
        if _row:
            _CACHED_SEMESTER = _row[0]
        else:
            _CACHED_SEMESTER = fallback
    except Exception:
        _CACHED_SEMESTER = fallback

    _CACHED_SEMESTER_TS = now
    return _CACHED_SEMESTER


def get_request_semester():
    """从请求参数 ?semester= 获取学期，默认返回当前学期。"""
    req_sem = (request.args.get("semester") or "").strip()
    return req_sem if req_sem else get_current_semester()


def check_semester_writable():
    """校验请求学期是否为当前学期，非当前学期禁止写操作。
    
    返回 (is_writable: bool, message: str)
    """
    req_sem = get_request_semester()
    current = get_current_semester()
    if req_sem != current:
        return False, f"历史学期（{req_sem}）数据只读，当前学期为 {current}"
    return True, ""


def require_writable_semester():
    """装饰器/函数：校验当前请求学期是否可写，不可写返回 403。
    
    用法：
        ok, err = require_writable_semester()
        if not ok:
            return err
    """
    ok, msg = check_semester_writable()
    if not ok:
        return False, (jsonify({"success": False, "message": msg}), 403)
    return True, None


def parse_ai_json(content: str):
    cleaned = content.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def fallback_grade(student_text: str, answer_text: str, total_score: float):
    student_len = len((student_text or "").strip())
    answer_len = max(len((answer_text or "").strip()), 120)
    ratio = min(1.0, student_len / answer_len)
    score = round(max(total_score * 0.55, total_score * ratio), 1)
    return {
        "score": score,
        "items": [
            {"question": "完成度", "score": round(score * 0.4, 1), "max_score": round(total_score * 0.4, 1), "comment": "根据提交内容完整度估算"},
            {"question": "关键步骤", "score": round(score * 0.35, 1), "max_score": round(total_score * 0.35, 1), "comment": "建议教师重点复核推理过程"},
            {"question": "表达规范", "score": round(score * 0.25, 1), "max_score": round(total_score * 0.25, 1), "comment": "根据格式和表达完整性估算"},
        ],
        "feedback": "未配置 DeepSeek 或 PDF 未能解析文本，已使用本地规则给出可复核初评。",
    }


def ai_grade(homework: Homework, submission: Submission):
    prompt = f"""
你是高校课程作业阅卷助手。请依据标准答案和学生答案评分，必须只返回 JSON：
{{"score": 数字, "items": [{{"question":"小题名","score":数字,"max_score":数字,"comment":"扣分或给分理由"}}], "feedback":"总评"}}

要求：
1. 总分不能超过 {homework.total_score}
2. 尽量按题号或知识点拆分小题明细
3. 如果文本不足，需要明确提示教师复核

作业要求：
{homework.description}

标准答案：
{(homework.answer_text or '')[:12000]}

学生答案：
{(submission.extracted_text or submission.content or '')[:12000]}
"""
    try:
        content = deepseek_chat([
            {"role": "system", "content": "你是严谨的教学阅卷 Agent，只返回可解析 JSON。"},
            {"role": "user", "content": prompt},
        ])
        data = parse_ai_json(content) if content else fallback_grade(submission.extracted_text or submission.content, homework.answer_text, homework.total_score)
    except Exception as exc:
        data = fallback_grade(submission.extracted_text or submission.content, homework.answer_text, homework.total_score)
        data["feedback"] += f" AI 服务暂不可用：{exc}"
    submission.ai_score = round(min(float(data.get("score", 0)), float(homework.total_score)))
    submission.ai_detail = json.dumps(data.get("items", []), ensure_ascii=False)
    submission.ai_feedback = data.get("feedback", "")
    submission.review_status = "待复核"
    return submission


def upsert_grade(course_id: int, student_id: str, source_type: str, source_id: int | None, score: float, comment: str, semester: str = None):
    # 分数范围校验，保留整数
    if semester is None:
        semester = get_current_semester()
    score = round(max(0.0, min(100.0, float(score))))
    grade = Grade.query.filter_by(
        course_id=course_id,
        student_id=student_id,
        source_type=source_type,
        source_id=source_id,
        semester=semester,
    ).first()
    if not grade:
        grade = Grade(course_id=course_id, student_id=student_id, source_type=source_type, source_id=source_id, score=score, semester=semester)
        db.session.add(grade)
    grade.score = score
    grade.comment = comment
    grade.updated_at = datetime.now()
    return grade


# ═══════════════════════════════════════════════════════════════════════════════
# API Routes
# ═══════════════════════════════════════════════════════════════════════════════


def verify_token_with_main_service(token):
    """调用主服务 /api/verify-token 校验 token，返回 {user_id, user_type} 或 None"""
    if not token:
        return None
    req = Request(
        f"{MAIN_SERVICE_URL}/api/verify-token",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    if not data.get("valid"):
        return None
    return {"user_id": data.get("user_id"), "user_type": data.get("user_type")}


@app.route("/api/sso-login", methods=["POST"])
def sso_login():
    """主服务单点登录：验证主服务 token 并返回用户信息（不再签发本地 JWT，每次请求实时验证）"""
    data = request.get_json() or {}
    main_token = data.get("token", "").strip()
    if not main_token:
        return jsonify({"success": False, "message": "缺少 token"}), 400

    verified = verify_token_with_main_service(main_token)
    if not verified:
        return jsonify({"success": False, "message": "主服务 token 无效或已过期"}), 401

    user_id = verified["user_id"]
    user_type = verified["user_type"]
    info = get_user_info(user_id, user_type)
    if not info:
        return jsonify({"success": False, "message": "用户信息不存在"}), 404

    # 直接返回主服务 token，不再签发本地 JWT
    return jsonify({"success": True, "token": main_token, "user": info})


@app.route("/api/me")
def me():
    user, error = require_roles("student", "teacher", "admin")
    if error:
        return error
    return jsonify({"success": True, "data": get_user_info(user.user_id, user.user_type)})


@app.route("/api/teachers")
def teachers():
    user, error = require_roles("admin")
    if error:
        return error
    data = [{"user_id": t.teacher_id, "role": "teacher", "name": t.name or t.teacher_id, "college": t.college or "", "title": t.title or ""} for t in Teacher.query.order_by(Teacher.teacher_id)]
    return jsonify({"success": True, "data": data})


@app.route("/api/students")
def students():
    user, error = require_roles("teacher", "admin")
    if error:
        return error
    if user.user_type == "teacher":
        # 教师只能看到自己课程中的学生
        semester = get_request_semester()
        teacher_course_ids = [c.id for c in Course.query.filter_by(teacher_id=user.user_id, semester=semester).all()]
        if not teacher_course_ids:
            return jsonify({"success": True, "data": []})
        student_ids = list(set(
            cs.student_id for cs in CourseStudent.query.filter(
                CourseStudent.course_id.in_(teacher_course_ids),
                CourseStudent.semester == semester
            ).all()
        ))
        data = [{"user_id": s.student_id, "role": "student", "name": s.name or s.student_id, "grade": s.grade or "", "major": s.major or ""}
                for s in Student.query.filter(Student.student_id.in_(student_ids)).order_by(Student.student_id)]
    else:
        data = [{"user_id": s.student_id, "role": "student", "name": s.name or s.student_id, "grade": s.grade or "", "major": s.major or ""} for s in Student.query.order_by(Student.student_id)]
    return jsonify({"success": True, "data": data})


@app.route("/api/time-slots")
def time_slots():
    """获取排课时间槽列表（来源 course_schedule_database.cs_time_slots）"""
    user, error = require_roles("admin")
    if error:
        return error
    data = [{"slot_id": s.slot_id, "weekday": s.weekday, "start_time": s.start_time, "end_time": s.end_time, "label": s.label or f"周{s.weekday} {s.start_time}-{s.end_time}"} for s in CsTimeSlot.query.order_by(CsTimeSlot.weekday, CsTimeSlot.start_time)]
    return jsonify({"success": True, "data": data})


@app.route("/api/classrooms")
def classrooms():
    """获取教室列表（来源 main_database.classrooms）"""
    user, error = require_roles("admin")
    if error:
        return error
    data = [{"classroom_id": c.classroom_id, "building": c.building or ""} for c in Classroom.query.order_by(Classroom.building, Classroom.classroom_id)]
    return jsonify({"success": True, "data": data})


@app.route("/api/courses", methods=["GET", "POST"])
def courses():
    user, error = require_roles("student", "teacher", "admin")
    if error:
        return error

    semester = get_request_semester()

    if request.method == "POST":
        ok, err = require_writable_semester()
        if not ok:
            return err
        if user.user_type != "admin":
            return jsonify({"success": False, "message": "仅管理员可新增课程"}), 403
        data = request.get_json() or {}
        course = Course()
        course.semester = semester
        update_course(course, data)
        if not course.code or not course.name or not course.teacher_id:
            return jsonify({"success": False, "message": "课程编号、名称、授课教师为必填项"}), 400
        # 检查课程号唯一（同学期内）
        if Course.query.filter_by(code=course.code, semester=semester).first():
            return jsonify({"success": False, "message": f"课程编号 {course.code} 在当前学期已存在，请使用其他编号"}), 409
        db.session.add(course)
        db.session.commit()
        return jsonify({"success": True, "data": course_dict(course)})

    query = Course.query.filter_by(semester=semester)
    if user.user_type == "teacher":
        query = query.filter_by(teacher_id=user.user_id)
    elif user.user_type == "student":
        ids = student_course_ids(user)
        query = query.filter(Course.id.in_(ids)) if ids else query.filter(db.literal(False))
    query = apply_course_filters(query)
    rows = query.order_by(Course.course_type.desc(), Course.created_at.desc()).all()
    return jsonify({"success": True, "data": [course_dict(c) for c in rows]})


def update_course(course: Course, data: dict):
    fields = [
        "code", "name", "description", "teacher_id", "class_time",
        "location", "language", "course_type", "teaching_method",
        "target_grade", "target_major",
    ]
    for key in fields:
        if key in data:
            setattr(course, key, str(data.get(key) or "").strip())
    if "credits" in data:
        course.credits = float(data.get("credits") or 0)


@app.route("/api/courses/<int:course_id>", methods=["PUT", "DELETE"])
def course_detail(course_id):
    user, error = require_roles("admin")
    if error:
        return error

    ok, err = require_writable_semester()
    if not ok:
        return err

    semester = get_request_semester()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404
    if request.method == "DELETE":
        db.session.delete(course)
        db.session.commit()
        return jsonify({"success": True})
    data = request.get_json() or {}
    # 修改时的课程号去重检查（同学期内）
    new_code = str(data.get("code", "") or "").strip()
    if new_code and new_code != course.code:
        if Course.query.filter_by(code=new_code, semester=semester).first():
            return jsonify({"success": False, "message": f"课程编号 {new_code} 已存在"}), 409
    update_course(course, data)
    db.session.commit()
    return jsonify({"success": True, "data": course_dict(course)})


@app.route("/api/teacher/dashboard")
def teacher_dashboard():
    user, error = require_roles("teacher")
    if error:
        return error
    semester = get_request_semester()
    tcourses = Course.query.filter_by(teacher_id=user.user_id, semester=semester).all()
    course_ids = [course.id for course in tcourses]
    assignments = Homework.query.filter(Homework.course_id.in_(course_ids), Homework.semester == semester).all() if course_ids else []
    assignment_ids = [item.id for item in assignments]
    submissions = Submission.query.filter(Submission.homework_id.in_(assignment_ids), Submission.semester == semester).all() if assignment_ids else []
    pending = [item for item in submissions if item.review_status == "待复核"]
    return jsonify({
        "success": True,
        "data": {
            "course_count": len(tcourses),
            "credits": sum(course.credits or 0 for course in tcourses),
            "assignment_count": len(assignments),
            "submission_count": len(submissions),
            "pending_count": len(pending),
            "courses": [course_dict(course) for course in tcourses],
            "recent_assignments": [assignment_dict(item) for item in sorted(assignments, key=lambda x: x.created_at or datetime.min, reverse=True)[:6]],
        },
    })


@app.route("/api/courses/<int:course_id>/announcements", methods=["GET", "POST"])
def announcements(course_id):
    user, error = require_roles("student", "teacher")
    if error:
        return error

    semester = get_request_semester()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    if request.method == "POST":
        ok, err = require_writable_semester()
        if not ok:
            return err
        if user.user_type != "teacher" or course.teacher_id != user.user_id:
            return jsonify({"success": False, "message": "只能发布自己课程的公告"}), 403
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        if not title or not content:
            return jsonify({"success": False, "message": "公告标题和内容必填"}), 400
        item = Announcement(course_id=course_id, title=title, content=content, created_by=user.user_id, semester=semester)
        db.session.add(item)
        db.session.commit()

    rows = Announcement.query.filter_by(course_id=course_id, semester=semester).order_by(Announcement.created_at.desc()).all()
    data = [{"id": a.id, "title": a.title, "content": a.content or "", "created_by": a.created_by or "", "created_at": dt(a.created_at)} for a in rows]
    return jsonify({"success": True, "data": data})


@app.route("/api/courses/<int:course_id>/assignments", methods=["GET", "POST"])
def assignments(course_id):
    user, error = require_roles("student", "teacher")
    if error:
        return error

    semester = get_request_semester()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    if request.method == "POST":
        ok, err = require_writable_semester()
        if not ok:
            return err
        if user.user_type != "teacher" or course.teacher_id != user.user_id:
            return jsonify({"success": False, "message": "只能给自己课程发布作业"}), 403
        title = request.form.get("title", "").strip()
        if not title:
            return jsonify({"success": False, "message": "作业标题必填"}), 400
        try:
            answer_name, answer_pdf_text = save_pdf(request.files.get("answer_pdf"), "answer", required=False)
            due_at = parse_dt(request.form.get("due_at"))
            total_score = float(request.form.get("total_score") or 100)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400
        answer_text = (request.form.get("answer_text") or "").strip()
        item = Homework(
            course_id=course_id,
            title=title,
            description=request.form.get("requirement", "").strip(),
            deadline=due_at,
            answer_pdf=answer_name,
            answer_text=answer_text or answer_pdf_text,
            total_score=total_score,
            created_by=user.user_id,
            semester=semester,
        )
        db.session.add(item)
        if item.deadline:
            db.session.add(DdlItem(course_id=course_id, owner_id=user.user_id, owner_role="teacher", title=f"{course.name}：{item.title}", due_at=item.deadline, semester=semester))
        db.session.commit()

    rows = Homework.query.filter_by(course_id=course_id, semester=semester).order_by(Homework.created_at.desc()).all()
    return jsonify({"success": True, "data": [assignment_dict(a, user.user_id if user.user_type == "student" else None) for a in rows]})


@app.route("/api/assignments/<int:assignment_id>/submit", methods=["POST"])
def submit_assignment(assignment_id):
    user, error = require_roles("student")
    if error:
        return error

    ok, err = require_writable_semester()
    if not ok:
        return err

    semester = get_request_semester()
    homework = db.session.get(Homework, assignment_id)
    if not homework:
        return jsonify({"success": False, "message": "作业不存在"}), 404
    try:
        pdf_name, pdf_text = save_pdf(request.files.get("pdf"), "submission", required=False)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    typed_answer = (request.form.get("answer_text") or "").strip()
    if not pdf_name and not typed_answer:
        return jsonify({"success": False, "message": "请上传 PDF 或填写答案文本"}), 400
    sub = Submission.query.filter_by(homework_id=assignment_id, student_id=user.user_id, semester=semester).first()
    if not sub:
        sub = Submission(homework_id=assignment_id, student_id=user.user_id, content="", semester=semester)
        db.session.add(sub)
    sub.pdf_path = pdf_name or sub.pdf_path
    sub.extracted_text = typed_answer or pdf_text
    sub.content = typed_answer or pdf_text or sub.content
    sub.submit_time = datetime.now()
    ai_grade(homework, sub)
    upsert_grade(homework.course_id, user.user_id, "assignment", homework.id, sub.ai_score or 0, "AI 初评自动录入，等待教师复核")
    db.session.commit()
    return jsonify({"success": True, "data": submission_dict(sub)})


@app.route("/api/assignments/<int:assignment_id>/submissions")
def submissions_list(assignment_id):
    user, error = require_roles("teacher")
    if error:
        return error

    semester = get_request_semester()
    homework = db.session.get(Homework, assignment_id)
    course = db.session.get(Course, homework.course_id) if homework else None
    if not homework or course.teacher_id != user.user_id:
        return jsonify({"success": False, "message": "无权查看提交"}), 403
    rows = Submission.query.filter_by(homework_id=assignment_id, semester=semester).order_by(Submission.submit_time.desc()).all()
    return jsonify({"success": True, "data": [submission_dict(s) for s in rows]})


@app.route("/api/submissions/<int:submission_id>/ai-grade", methods=["POST"])
def regrade_submission(submission_id):
    user, error = require_roles("teacher")
    if error:
        return error

    ok, err = require_writable_semester()
    if not ok:
        return err
    sub = db.session.get(Submission, submission_id)
    homework = db.session.get(Homework, sub.homework_id) if sub else None
    course = db.session.get(Course, homework.course_id) if homework else None
    if not sub or course.teacher_id != user.user_id:
        return jsonify({"success": False, "message": "无权批改"}), 403
    ai_grade(homework, sub)
    upsert_grade(course.id, sub.student_id, "assignment", homework.id, sub.ai_score or 0, "AI 重新批改，等待教师复核")
    db.session.commit()
    return jsonify({"success": True, "data": submission_dict(sub)})


@app.route("/api/submissions/<int:submission_id>/review", methods=["POST"])
def review_submission(submission_id):
    user, error = require_roles("teacher")
    if error:
        return error

    ok, err = require_writable_semester()
    if not ok:
        return err
    sub = db.session.get(Submission, submission_id)
    homework = db.session.get(Homework, sub.homework_id) if sub else None
    course = db.session.get(Course, homework.course_id) if homework else None
    if not sub or course.teacher_id != user.user_id:
        return jsonify({"success": False, "message": "无权复核"}), 403
    data = request.get_json() or {}
    sub.teacher_score = round(float(data.get("teacher_score")))
    sub.final_score = sub.teacher_score
    sub.teacher_feedback = data.get("teacher_feedback", "")
    sub.review_status = data.get("review_status", "已通过")
    upsert_grade(course.id, sub.student_id, "assignment", homework.id, sub.teacher_score, sub.teacher_feedback or "教师复核录入")
    db.session.commit()
    return jsonify({"success": True, "data": submission_dict(sub)})


@app.route("/api/courses/<int:course_id>/grades", methods=["GET", "POST"])
def grades(course_id):
    user, error = require_roles("student", "teacher")
    if error:
        return error

    semester = get_request_semester()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    if request.method == "POST":
        ok, err = require_writable_semester()
        if not ok:
            return err
        if user.user_type != "teacher" or course.teacher_id != user.user_id:
            return jsonify({"success": False, "message": "无权录入成绩"}), 403
        data = request.get_json() or {}
        source_type = data.get("source_type", "final")
        if source_type not in ("final", "overall"):
            return jsonify({"success": False, "message": "成绩类型无效，仅支持 final(期末) 或 overall(总评)"}), 400
        score = round(float(data.get("score", 0)))
        if score < 0 or score > 100:
            return jsonify({"success": False, "message": "分数须在 0-100 之间"}), 400
        grade = upsert_grade(
            course_id,
            data.get("student_id", "").strip(),
            source_type,
            None,
            score,
            data.get("comment", ""),
            semester,
        )
        db.session.commit()
        return jsonify({"success": True, "data": grade_dict(grade)})

    query = Grade.query.filter_by(course_id=course_id, semester=semester)
    if user.user_type == "student":
        query = query.filter_by(student_id=user.user_id)
    rows = query.order_by(Grade.updated_at.desc()).all()
    return jsonify({"success": True, "data": [grade_dict(g) for g in rows]})


@app.route("/api/grades")
def all_grades():
    user, error = require_roles("student", "teacher")
    if error:
        return error
    semester = get_request_semester()
    if user.user_type == "student":
        rows = Grade.query.filter_by(student_id=user.user_id, semester=semester).order_by(Grade.updated_at.desc()).all()
    else:
        course_ids = [course.id for course in Course.query.filter_by(teacher_id=user.user_id, semester=semester)]
        rows = Grade.query.filter(Grade.course_id.in_(course_ids), Grade.semester == semester).order_by(Grade.updated_at.desc()).all() if course_ids else []
    return jsonify({"success": True, "data": [grade_dict(g) for g in rows]})


@app.route("/api/courses/<int:course_id>/grade-summary")
def grade_summary(course_id):
    """返回每个学生的成绩汇总：作业平均分、期末成绩、总评成绩。"""
    user, error = require_roles("student", "teacher")
    if error:
        return error
    semester = get_request_semester()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    # 获取该课程的所有作业
    hw_items = Homework.query.filter_by(course_id=course_id, semester=semester).all()
    hw_ids = [h.id for h in hw_items]

    # 获取学生列表
    course_students = CourseStudent.query.filter_by(course_id=course_id, semester=semester).all()
    student_ids = [cs.student_id for cs in course_students]

    # 获取所有提交（取最高分）
    if hw_ids:
        submissions = Submission.query.filter(Submission.homework_id.in_(hw_ids), Submission.semester == semester).all()
    else:
        submissions = []

    # 按学生计算作业平均分
    by_student = {}
    for sid in student_ids:
        stu_subs = [s for s in submissions if s.student_id == sid and s.ai_score is not None]
        if stu_subs:
            avg = sum(s.ai_score for s in stu_subs) / len(stu_subs)
            # 归一化到百分制（假设作业总分各异，取百分比）
            total_pct = 0
            count = 0
            for s in stu_subs:
                hw = next((h for h in hw_items if h.id == s.homework_id), None)
                if hw and hw.total_score and hw.total_score > 0:
                    total_pct += (s.ai_score / hw.total_score) * 100
                    count += 1
            hw_avg = round(total_pct / count) if count else 0
        else:
            hw_avg = None
        by_student[sid] = {"hw_avg": hw_avg, "final": None, "overall": None}

    # 填充教师录入的期末和总评成绩
    grade_rows = Grade.query.filter_by(course_id=course_id, semester=semester).all()
    for g in grade_rows:
        if g.student_id in by_student:
            if g.source_type == "final":
                by_student[g.student_id]["final"] = g.score
            elif g.source_type == "overall":
                by_student[g.student_id]["overall"] = g.score

    # 构造返回数据
    result = []
    for sid in student_ids:
        student = Student.query.filter_by(student_id=sid).first()
        name = (student.name if student and student.name else sid)
        data = by_student.get(sid, {"hw_avg": None, "final": None, "overall": None})
        result.append({
            "student_id": sid,
            "student_name": name,
            "hw_avg": data["hw_avg"],
            "final": data["final"],
            "overall": data["overall"],
        })

    return jsonify({"success": True, "data": result})


@app.route("/api/courses/<int:course_id>/students")
def course_students_list(course_id):
    """获取课程选课学生列表，包含学生姓名等基本信息。
    
    仅 teacher 和 admin 可访问。
    返回：学生学号、姓名、年级、专业、最终成绩
    """
    user, error = require_roles("teacher", "admin")
    if error:
        return error

    semester = get_request_semester()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404

    # teacher 只能查看自己课程的学生
    if user.user_type == "teacher" and course.teacher_id != user.user_id:
        return jsonify({"success": False, "message": "无权查看该课程的学生"}), 403

    cs_rows = CourseStudent.query.filter_by(course_id=course_id, semester=semester).all()
    result = []
    for cs in cs_rows:
        student = Student.query.filter_by(student_id=cs.student_id).first()
        result.append({
            "id": cs.id,
            "student_id": cs.student_id,
            "student_name": student.name if student and student.name else cs.student_id,
            "grade": student.grade if student else "",
            "major": student.major if student else "",
            "final_grade": cs.final_grade,
        })
    return jsonify({"success": True, "data": result})


@app.route("/api/ddls", methods=["GET", "POST"])
def ddls():
    user, error = require_roles("student", "teacher")
    if error:
        return error

    semester = get_request_semester()
    now = datetime.now()
    if request.method == "POST":
        ok, err = require_writable_semester()
        if not ok:
            return err
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        if not title:
            return jsonify({"success": False, "message": "DDL 标题不能为空"}), 400
        item = DdlItem(course_id=data.get("course_id"), owner_id=user.user_id, owner_role=user.user_type, title=title, due_at=parse_dt(data.get("due_at")), status=data.get("status", "pending"), semester=semester)
        db.session.add(item)
        db.session.commit()

    # 自动清理已过期的手动 DDL（due_at 已过且状态不是 done）
    expired = DdlItem.query.filter(
        DdlItem.owner_id == user.user_id,
        DdlItem.owner_role == user.user_type,
        DdlItem.due_at < now,
        DdlItem.status != "done",
        DdlItem.semester == semester,
    ).all()
    for item in expired:
        db.session.delete(item)
    if expired:
        db.session.commit()

    rows = DdlItem.query.filter_by(owner_id=user.user_id, owner_role=user.user_type, semester=semester).order_by(DdlItem.due_at).all()
    if user.user_type == "student":
        ids = student_course_ids(user)
        hw_items = Homework.query.filter(Homework.course_id.in_(ids), Homework.semester == semester).filter(Homework.deadline.isnot(None)).all() if ids else []
        # 获取该学生已提交的作业 ID
        submitted_hw_ids = set()
        if hw_items:
            hw_id_list = [h.id for h in hw_items]
            submitted = Submission.query.filter(
                Submission.homework_id.in_(hw_id_list),
                Submission.student_id == user.user_id,
                Submission.semester == semester,
            ).all()
            submitted_hw_ids = {s.homework_id for s in submitted}
        for item in hw_items:
            # 跳过已提交的作业 DDL
            if item.id in submitted_hw_ids:
                continue
            # 跳过已过期的作业 DDL
            if item.deadline and item.deadline < now:
                continue
            course = db.session.get(Course, item.course_id)
            rows.append(type("DdlView", (), {"id": f"a-{item.id}", "title": f"{course.name}：{item.title}", "due_at": item.deadline, "status": "assignment", "readonly": True})())
    data = [{
        "id": row.id,
        "course_id": getattr(row, "course_id", None),
        "title": row.title,
        "due_at": dt(row.due_at),
        "status": row.status,
        "readonly": bool(getattr(row, "readonly", False)),
    } for row in sorted(rows, key=lambda x: x.due_at)]
    return jsonify({"success": True, "data": data})


@app.route("/api/ddls/<int:ddl_id>", methods=["DELETE"])
def delete_ddl(ddl_id):
    user, error = require_roles("student", "teacher")
    if error:
        return error
    ok, err = require_writable_semester()
    if not ok:
        return err
    item = db.session.get(DdlItem, ddl_id)
    if not item or item.owner_id != user.user_id or item.owner_role != user.user_type:
        return jsonify({"success": False, "message": "DDL 不存在或无权删除"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/agent/ask", methods=["POST"])
def agent_ask():
    """课堂教学数据分析 Agent。
    
    ⚠️ 反幻觉设计：
    1. 统计数据由代码预计算，100% 忠实于数据库
    2. DeepSeek 仅做分析建议，被明确禁止编造数据
    3. local_agent_answer 作为保底，确保始终返回真实数据
    """
    user, error = require_roles("teacher", "admin")
    if error:
        return error
    semester = get_request_semester()
    question = (request.get_json() or {}).get("question", "").strip()
    tcourses = Course.query.filter_by(semester=semester).all() if user.user_type == "admin" else Course.query.filter_by(teacher_id=user.user_id, semester=semester).all()
    course_ids = [c.id for c in tcourses]
    grade_rows = Grade.query.filter(Grade.course_id.in_(course_ids)).all() if course_ids else []
    hw_items = Homework.query.filter(Homework.course_id.in_(course_ids)).all() if course_ids else []
    hw_ids = [item.id for item in hw_items]
    sub_rows = Submission.query.filter(Submission.homework_id.in_(hw_ids)).all() if hw_ids else []
    by_course = []
    for course in tcourses:
        course_grades = [g.score for g in grade_rows if g.course_id == course.id]
        by_course.append({
            **course_dict(course),
            "grade_count": len(course_grades),
            "average_score": round(sum(course_grades) / len(course_grades)) if course_grades else None,
            "fail_count": len([score for score in course_grades if score < 60]),
        })
    stats = {
        "course_count": len(tcourses),
        "total_credits": sum(c.credits or 0 for c in tcourses),
        "assignment_count": len(hw_items),
        "submission_count": len(sub_rows),
        "pending_review_count": len([s for s in sub_rows if s.review_status == "待复核"]),
        "grade_count": len(grade_rows),
        "average_score": round(sum(g.score for g in grade_rows) / len(grade_rows)) if grade_rows else None,
        "fail_count": len([g for g in grade_rows if g.score < 60]),
        "courses": by_course,
    }

    # 保底答案：纯代码生成，100% 真实数据
    base_answer = local_agent_answer(question, stats)

    try:
        analysis = deepseek_chat([
            {"role": "system", "content": (
                "你是课堂教学数据分析 Agent。\n"
                "⚠️ 核心铁律（违反将导致严重教学事故）：\n"
                "1. 你只能使用下方【数据库统计】中提供的精确数值，禁止编造任何数字\n"
                "2. 禁止更改课程名称、学生姓名、成绩等任何数据\n"
                "3. 如果用户问的信息不在统计数据中，必须明确说「当前数据中不包含此信息」\n"
                "4. 你的角色是提供教学管理建议和分析洞察，不是复述数据\n"
                "5. 回答要简洁，建议要有可操作性"
            )},
            {"role": "user", "content": (
                f"【数据库统计】← 唯一数据来源，所有数字必须与此一致：\n"
                f"{json.dumps(stats, ensure_ascii=False)}\n\n"
                f"教师问题：{question}\n\n"
                f"请基于以上统计数据给出分析建议。如需引用数据，必须与上方数值完全一致。"
            )},
        ])
        if analysis:
            answer = f"{base_answer}\n\n📊 **智能分析建议**：{analysis}"
        else:
            answer = base_answer
    except Exception as exc:
        answer = f"{base_answer}\n\n（AI 分析暂不可用：{exc}）"

    return jsonify({"success": True, "data": {"answer": answer, "stats": stats}})


@app.route("/api/ai/status")
def ai_status():
    user, error = require_roles("teacher", "admin")
    if error:
        return error
    return jsonify({"success": True, "data": ai_runtime_status()})


def local_agent_answer(question: str, stats: dict) -> str:
    return (
        f"当前负责课程 {stats['course_count']} 门，共 {stats['total_credits']} 学分；"
        f"已发布作业 {stats['assignment_count']} 个，收到提交 {stats['submission_count']} 份，"
        f"待复核 {stats['pending_review_count']} 份。成绩记录 {stats['grade_count']} 条，"
        f"平均分 {stats['average_score'] if stats['average_score'] is not None else '暂无'}，"
        f"不及格人数 {stats['fail_count']}。"
    )


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "classroom-teaching-service", "port": int(os.environ.get("PORT", 5003)), "database": "cloud-mysql"})


# ═══════════════════════════════════════════════════════════════════════════════
# 学期管理 API
# ═══════════════════════════════════════════════════════════════════════════════


@app.route("/api/semesters")
def list_semesters():
    """返回所有学期列表（从 courses 表去重，按学期倒序）。"""
    user, error = require_roles("student", "teacher", "admin")
    if error:
        return error
    rows = db.session.query(Course.semester).distinct().order_by(Course.semester.desc()).all()
    semesters = [r[0] for r in rows]
    current = get_current_semester()
    return jsonify({"success": True, "data": semesters, "current": current})


@app.route("/api/semesters/current")
def current_semester_api():
    """返回当前活跃学期。"""
    user, error = require_roles("student", "teacher", "admin")
    if error:
        return error
    return jsonify({"success": True, "data": {"semester": get_current_semester()}})


@app.route("/")
def index():
    return Response(
        (FRONTEND_DIR / "index.html").read_text(encoding="utf-8"),
        mimetype="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5003)), debug=os.environ.get("FLASK_DEBUG") == "1")
