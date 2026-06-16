from collections import Counter, defaultdict
from datetime import datetime, timedelta
import json
import os
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, unquote
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case, or_
from werkzeug.utils import secure_filename


BASE_DIR = os.path.dirname(__file__)
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR",
    os.path.abspath(os.path.join(BASE_DIR, "..", "frontend")),
)
UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    os.path.abspath(os.path.join(BASE_DIR, "..", "uploads")),
)

DB_HOST = os.environ.get("DB_HOST", "47.93.226.110")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "")
DB_PASS_RAW = os.environ.get("DB_PASS_RAW", unquote(DB_PASS))
DB_PASS_QUOTED = quote_plus(DB_PASS_RAW)
WALL_DB_NAME = os.environ.get("WALL_DB_NAME", "campus_wall_database")
MAIN_SERVICE_URL = os.environ.get("MAIN_SERVICE_URL", "http://127.0.0.1:5001").rstrip("/")
VERIFY_TOKEN_URL = os.environ.get(
    "VERIFY_TOKEN_URL",
    f"{MAIN_SERVICE_URL}/api/verify-token",
)
TREND_ALERT_THRESHOLD = int(os.environ.get("TREND_ALERT_THRESHOLD", 3))
MAX_IMAGES_PER_POST = int(os.environ.get("MAX_IMAGES_PER_POST", 3))
MAX_IMAGE_SIZE = int(os.environ.get("MAX_IMAGE_SIZE", 5 * 1024 * 1024))
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASS_QUOTED}@{DB_HOST}:{DB_PORT}/{WALL_DB_NAME}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


HIGH_RISK_KEYWORDS = [
    "打架",
    "霸凌",
    "欺凌",
    "自杀",
    "跳楼",
    "诈骗",
    "火灾",
    "爆炸",
    "食物中毒",
    "泄露",
    "谣言",
    "暴力",
    "失踪",
    "群体事件",
]

TREND_KEYWORDS = [
    "考试",
    "宿舍",
    "食堂",
    "课程",
    "社团",
    "图书馆",
    "老师",
    "收费",
    "安全",
    "网络",
    "活动",
    "就业",
]

ALL_TRACKED_KEYWORDS = HIGH_RISK_KEYWORDS + TREND_KEYWORDS


class WallPost(db.Model):
    __tablename__ = "wall_posts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    author_id = db.Column(db.String(20), nullable=False, index=True)
    author_type = db.Column(db.String(10), nullable=False, index=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    risk_level = db.Column(db.String(20), nullable=False, default="normal", index=True)
    matched_keywords = db.Column(db.String(255))
    image_paths = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    deleted_by = db.Column(db.String(20))
    deleted_at = db.Column(db.DateTime)
    delete_reason = db.Column(db.String(255))


class WallAlert(db.Model):
    __tablename__ = "wall_alerts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey("wall_posts.id"))
    alert_type = db.Column(db.String(30), nullable=False, default="post_keyword")
    alert_level = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(255))
    keywords = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    handled_by = db.Column(db.String(20))
    handled_at = db.Column(db.DateTime)

    post = db.relationship("WallPost")


class WallModerationLog(db.Model):
    __tablename__ = "wall_moderation_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    post_id = db.Column(db.Integer, db.ForeignKey("wall_posts.id"), nullable=False, index=True)
    admin_id = db.Column(db.String(20), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)


def dt(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else None


def parse_positive_int(value, default, minimum=1, maximum=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    return request.args.get("token", "").strip()


def verify_token(token):
    if not token:
        return None

    req = Request(VERIFY_TOKEN_URL, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    if not data.get("valid"):
        return None
    return {"user_id": data.get("user_id"), "user_type": data.get("user_type")}


def require_user(*allowed_types):
    user = verify_token(get_bearer_token())
    if not user:
        return None, (jsonify({"success": False, "message": "未登录或 token 无效"}), 401)
    if allowed_types and user["user_type"] not in allowed_types:
        return None, (jsonify({"success": False, "message": "无权限访问该接口"}), 403)
    return user, None


def analyze_post_text(title, content):
    text = f"{title or ''} {content or ''}"
    high_hits = [word for word in HIGH_RISK_KEYWORDS if word in text]
    if high_hits:
        return "high", high_hits
    return "normal", []


def extract_trend_keywords(post):
    text = f"{post.title or ''} {post.content or ''}"
    return [word for word in ALL_TRACKED_KEYWORDS if word in text]


def image_paths_to_list(image_paths):
    if not image_paths:
        return []
    try:
        paths = json.loads(image_paths)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(paths, list):
        return []
    images = []
    for path in paths:
        if isinstance(path, str) and path:
            normalized = path.replace("\\", "/")
            images.append({"path": normalized, "url": f"/uploads/{normalized}"})
    return images


def risk_label(level):
    return "高风险" if level == "high" else "无风险"


def post_to_dict(post, include_deleted_fields=False):
    risk_level = post.risk_level or "normal"
    data = {
        "id": post.id,
        "author_id": post.author_id,
        "author_type": post.author_type,
        "title": post.title or "",
        "content": post.content,
        "status": post.status,
        "risk_level": risk_level,
        "risk_label": risk_label(risk_level),
        "matched_keywords": post.matched_keywords or "",
        "images": image_paths_to_list(post.image_paths),
        "created_at": dt(post.created_at),
        "updated_at": dt(post.updated_at),
    }
    if include_deleted_fields:
        data.update(
            {
                "deleted_by": post.deleted_by or "",
                "deleted_at": dt(post.deleted_at),
                "delete_reason": post.delete_reason or "",
            }
        )
    return data


def is_post_owner(user, post):
    return (
        user["user_type"] in ("student", "teacher")
        and post.author_type == user["user_type"]
        and post.author_id == user["user_id"]
    )


def is_allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_images(files):
    images = [file for file in files if file and file.filename]
    if len(images) > MAX_IMAGES_PER_POST:
        raise ValueError(f"每条动态最多上传{MAX_IMAGES_PER_POST}张照片")

    saved_paths = []
    now = datetime.now()
    subdir = os.path.join(str(now.year), f"{now.month:02d}")
    target_dir = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(target_dir, exist_ok=True)

    for image in images:
        filename = secure_filename(image.filename)
        if not filename or not is_allowed_image(filename):
            raise ValueError("仅支持 jpg、jpeg、png、gif、webp 格式图片")

        image.stream.seek(0, os.SEEK_END)
        size = image.stream.tell()
        image.stream.seek(0)
        if size > MAX_IMAGE_SIZE:
            raise ValueError("单张图片不能超过5MB")

        ext = filename.rsplit(".", 1)[1].lower()
        saved_name = f"{uuid4().hex}.{ext}"
        image.save(os.path.join(target_dir, saved_name))
        saved_paths.append(f"{subdir}/{saved_name}".replace("\\", "/"))

    return saved_paths


def alert_to_dict(alert):
    return {
        "id": alert.id,
        "post_id": alert.post_id,
        "alert_type": alert.alert_type,
        "alert_level": alert.alert_level,
        "reason": alert.reason or "",
        "keywords": alert.keywords or "",
        "status": alert.status,
        "created_at": dt(alert.created_at),
        "handled_by": alert.handled_by or "",
        "handled_at": dt(alert.handled_at),
        "post": post_to_dict(alert.post, include_deleted_fields=True) if alert.post else None,
    }


def create_alerts_for_post(post, high_risk_keywords):
    now = datetime.now()
    alerts = []

    if high_risk_keywords:
        keywords = ",".join(high_risk_keywords)
        alerts.append(
            WallAlert(
                post_id=post.id,
                alert_type="post_keyword",
                alert_level="critical",
                reason=f"帖子命中高风险舆情关键词：{keywords}",
                keywords=keywords,
                created_at=now,
            )
        )

    since = now - timedelta(hours=24)
    for keyword in extract_trend_keywords(post):
        recent_count = WallPost.query.filter(
            WallPost.created_at >= since,
            WallPost.status == "active",
            or_(WallPost.title.like(f"%{keyword}%"), WallPost.content.like(f"%{keyword}%")),
        ).count()
        if recent_count < TREND_ALERT_THRESHOLD:
            continue

        existing = WallAlert.query.filter(
            WallAlert.alert_type == "trend_spike",
            WallAlert.keywords == keyword,
            WallAlert.created_at >= since,
            WallAlert.status == "pending",
        ).first()
        if existing:
            continue

        alerts.append(
            WallAlert(
                post_id=post.id,
                alert_type="trend_spike",
                alert_level="warning",
                reason=f"近24小时关键词「{keyword}」出现 {recent_count} 次，请关注舆论变化",
                keywords=keyword,
                created_at=now,
            )
        )

    db.session.add_all(alerts)
    return alerts


@app.route("/", methods=["GET"])
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/uploads/<path:filename>", methods=["GET"])
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/wall/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "campus-wall-service", "port": 5005})


@app.route("/api/wall/me", methods=["GET"])
def current_user():
    user, error = require_user("student", "teacher", "admin")
    if error:
        return error
    return jsonify({"success": True, "data": user})


@app.route("/api/wall/posts", methods=["GET"])
def list_posts():
    user, error = require_user("student", "teacher", "admin")
    if error:
        return error

    keyword = request.args.get("keyword", "").strip()
    author_type = request.args.get("author_type", "").strip()
    status = request.args.get("status", "").strip()
    risk_level = request.args.get("risk_level", "").strip()
    include_deleted = request.args.get("include_deleted", "").lower() == "true"
    mine = request.args.get("mine", "").lower() == "true"
    page = parse_positive_int(request.args.get("page"), default=1, minimum=1, maximum=100000)
    page_size = parse_positive_int(request.args.get("page_size"), default=10, minimum=1, maximum=50)

    query = WallPost.query
    if mine and user["user_type"] in ("student", "teacher"):
        query = query.filter(
            WallPost.author_id == user["user_id"],
            WallPost.author_type == user["user_type"],
        )
        if status in ("active", "deleted"):
            query = query.filter(WallPost.status == status)
    elif user["user_type"] != "admin" or not include_deleted:
        query = query.filter(WallPost.status == "active")
    elif status in ("active", "deleted"):
        query = query.filter(WallPost.status == status)

    if author_type in ("student", "teacher"):
        query = query.filter(WallPost.author_type == author_type)
    if risk_level in ("normal", "high"):
        query = query.filter(WallPost.risk_level == risk_level)
    if keyword:
        query = query.filter(or_(WallPost.title.like(f"%{keyword}%"), WallPost.content.like(f"%{keyword}%")))

    total = query.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = min(page, total_pages)
    posts = (
        query.order_by(WallPost.created_at.desc(), WallPost.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    include_deleted_fields = user["user_type"] == "admin" or mine
    return jsonify(
        {
            "success": True,
            "data": {
                "items": [
                    post_to_dict(post, include_deleted_fields=include_deleted_fields)
                    for post in posts
                ],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                    "has_prev": page > 1,
                    "has_next": page < total_pages,
                },
            },
        }
    )


@app.route("/api/wall/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    user, error = require_user("student", "teacher", "admin")
    if error:
        return error

    post = db.session.get(WallPost, post_id)
    if not post:
        return jsonify({"success": False, "message": "帖子不存在"}), 404
    if user["user_type"] != "admin" and post.status != "active" and not is_post_owner(user, post):
        return jsonify({"success": False, "message": "帖子不存在或已删除"}), 404

    return jsonify({
        "success": True,
        "data": post_to_dict(
            post,
            include_deleted_fields=user["user_type"] == "admin" or is_post_owner(user, post),
        ),
    })


@app.route("/api/wall/posts", methods=["POST"])
def create_post():
    user, error = require_user("student", "teacher")
    if error:
        return error

    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
        image_files = request.files.getlist("images")
    else:
        data = request.get_json() or {}
        image_files = []

    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "message": "动态内容不能为空"}), 400
    if len(title) > 100:
        return jsonify({"success": False, "message": "标题不能超过100字"}), 400
    if len(content) > 2000:
        return jsonify({"success": False, "message": "动态内容不能超过2000字"}), 400

    try:
        image_paths = save_uploaded_images(image_files)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    risk_level, keywords = analyze_post_text(title, content)
    post = WallPost(
        author_id=user["user_id"],
        author_type=user["user_type"],
        title=title,
        content=content,
        risk_level=risk_level,
        matched_keywords=",".join(keywords),
        image_paths=json.dumps(image_paths, ensure_ascii=False) if image_paths else None,
    )
    db.session.add(post)
    db.session.flush()
    create_alerts_for_post(post, keywords)
    db.session.commit()
    return jsonify({"success": True, "data": post_to_dict(post)}), 201


@app.route("/api/wall/posts/<int:post_id>", methods=["PUT"])
def update_post(post_id):
    user, error = require_user("student", "teacher")
    if error:
        return error

    post = db.session.get(WallPost, post_id)
    if not post:
        return jsonify({"success": False, "message": "帖子不存在"}), 404
    if not is_post_owner(user, post):
        return jsonify({"success": False, "message": "只能更新自己发布的帖子"}), 403
    if post.status != "active":
        return jsonify({"success": False, "message": "已删除的帖子不能更新"}), 400

    if request.content_type and request.content_type.startswith("multipart/form-data"):
        data = request.form
        image_files = request.files.getlist("images")
        replace_images = data.get("replace_images", "").lower() == "true" or bool(image_files)
    else:
        data = request.get_json() or {}
        image_files = []
        replace_images = bool(data.get("replace_images"))

    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"success": False, "message": "动态内容不能为空"}), 400
    if len(title) > 100:
        return jsonify({"success": False, "message": "标题不能超过100字"}), 400
    if len(content) > 2000:
        return jsonify({"success": False, "message": "动态内容不能超过2000字"}), 400

    image_paths = None
    if replace_images:
        try:
            image_paths = save_uploaded_images(image_files)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400

    risk_level, keywords = analyze_post_text(title, content)
    post.title = title
    post.content = content
    post.risk_level = risk_level
    post.matched_keywords = ",".join(keywords)
    if replace_images:
        post.image_paths = json.dumps(image_paths, ensure_ascii=False) if image_paths else None

    create_alerts_for_post(post, keywords)
    db.session.commit()
    return jsonify({"success": True, "data": post_to_dict(post)})


@app.route("/api/wall/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id):
    user, error = require_user("student", "teacher", "admin")
    if error:
        return error

    post = db.session.get(WallPost, post_id)
    if not post:
        return jsonify({"success": False, "message": "帖子不存在"}), 404
    if user["user_type"] != "admin" and not is_post_owner(user, post):
        return jsonify({"success": False, "message": "只能删除自己发布的帖子"}), 403
    if post.status == "deleted":
        return jsonify({"success": False, "message": "帖子已删除"}), 400

    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    if not reason:
        reason = "管理员删除违规内容" if user["user_type"] == "admin" else "作者删除"
    post.status = "deleted"
    post.deleted_by = user["user_id"]
    post.deleted_at = datetime.now()
    post.delete_reason = reason
    if user["user_type"] == "admin":
        db.session.add(
            WallModerationLog(
                post_id=post.id,
                admin_id=user["user_id"],
                action="delete",
                reason=reason,
            )
        )
    db.session.commit()
    return jsonify({"success": True, "data": post_to_dict(post, include_deleted_fields=True)})


@app.route("/api/wall/analysis/trends", methods=["GET"])
def get_trends():
    _user, error = require_user("admin")
    if error:
        return error

    try:
        days = int(request.args.get("days", 7))
    except ValueError:
        days = 7
    days = max(1, min(days, 30))

    today = datetime.now().date()
    start_day = today - timedelta(days=days - 1)
    since = datetime.combine(start_day, datetime.min.time())
    posts = WallPost.query.filter(WallPost.created_at >= since).all()

    role_counter = Counter(post.author_type for post in posts)
    keyword_counter = Counter()
    daily_counter = defaultdict(int)
    for post in posts:
        daily_counter[post.created_at.strftime("%Y-%m-%d")] += 1
        keyword_counter.update(extract_trend_keywords(post))

    pending_alerts = WallAlert.query.filter(WallAlert.status == "pending").count()
    data = {
        "days": days,
        "total_posts": len(posts),
        "active_posts": sum(1 for post in posts if post.status == "active"),
        "deleted_posts": sum(1 for post in posts if post.status == "deleted"),
        "risk_posts": sum(1 for post in posts if post.risk_level == "high"),
        "pending_alerts": pending_alerts,
        "role_distribution": {
            "student": role_counter.get("student", 0),
            "teacher": role_counter.get("teacher", 0),
        },
        "keywords": [
            {"keyword": keyword, "count": count}
            for keyword, count in keyword_counter.most_common(10)
        ],
        "daily_counts": [
            {
                "date": (start_day + timedelta(days=offset)).strftime("%Y-%m-%d"),
                "count": daily_counter.get((start_day + timedelta(days=offset)).strftime("%Y-%m-%d"), 0),
            }
            for offset in range(days)
        ],
    }
    return jsonify({"success": True, "data": data})


@app.route("/api/wall/analysis/alerts", methods=["GET"])
def list_alerts():
    _user, error = require_user("admin")
    if error:
        return error

    status = request.args.get("status", "").strip()
    alert_level = request.args.get("alert_level", "").strip()
    page = parse_positive_int(request.args.get("page"), default=1, minimum=1, maximum=100000)
    page_size = parse_positive_int(request.args.get("page_size"), default=3, minimum=1, maximum=50)
    query = WallAlert.query
    if status in ("pending", "handled"):
        query = query.filter(WallAlert.status == status)
    if alert_level in ("critical", "warning"):
        query = query.filter(WallAlert.alert_level == alert_level)

    total = query.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = min(page, total_pages)
    level_priority = case(
        (WallAlert.alert_level == "critical", 0),
        (WallAlert.alert_level == "warning", 1),
        else_=2,
    )
    alerts = (
        query.order_by(level_priority, WallAlert.created_at.desc(), WallAlert.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return jsonify(
        {
            "success": True,
            "data": {
                "items": [alert_to_dict(alert) for alert in alerts],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                    "has_prev": page > 1,
                    "has_next": page < total_pages,
                },
            },
        }
    )


@app.route("/api/wall/analysis/alerts/<int:alert_id>/handle", methods=["POST"])
def handle_alert(alert_id):
    user, error = require_user("admin")
    if error:
        return error

    alert = db.session.get(WallAlert, alert_id)
    if not alert:
        return jsonify({"success": False, "message": "告警不存在"}), 404

    alert.status = "handled"
    alert.handled_by = user["user_id"]
    alert.handled_at = datetime.now()
    db.session.commit()
    return jsonify({"success": True, "data": alert_to_dict(alert)})


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5003)), debug=os.environ.get("FLASK_DEBUG") == "1")
