from datetime import datetime, timedelta
import hashlib
import os

import jwt
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy


FRONTEND_DIR = os.environ.get(
    'FRONTEND_DIR',
    os.path.join(os.path.dirname(__file__), '..', 'frontend')
)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

DB_HOST = os.environ.get('DB_HOST', '47.93.226.110')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'campus-mis-secret-key-2024-classroom-module')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/main_database'
)
app.config['SQLALCHEMY_BINDS'] = {
    'users': os.environ.get(
        'USERS_DATABASE_URL',
        f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/users_database'
    )
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ============ Data models ============

class Student(db.Model):
    __bind_key__ = 'users'
    __tablename__ = 'students'
    student_id = db.Column(db.String(8), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    grade = db.Column(db.String(10))
    major = db.Column(db.String(50))


class Teacher(db.Model):
    __bind_key__ = 'users'
    __tablename__ = 'teachers'
    teacher_id = db.Column(db.String(4), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    college = db.Column(db.String(50))
    title = db.Column(db.String(20))


class Admin(db.Model):
    __bind_key__ = 'users'
    __tablename__ = 'admins'
    admin_id = db.Column(db.String(20), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(50))


class ActiveSession(db.Model):
    __tablename__ = 'active_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(20), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.now)
    token = db.Column(db.String(500), nullable=False)


class Classroom(db.Model):
    __tablename__ = 'classrooms'
    classroom_id = db.Column(db.String(4), primary_key=True)
    building = db.Column(db.String(50))


class Building(db.Model):
    __tablename__ = 'buildings'
    building_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_name = db.Column(db.String(50), nullable=False)


class BuildingAdjacency(db.Model):
    __tablename__ = 'building_adjacency'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    building_a = db.Column(db.Integer, db.ForeignKey('buildings.building_id'), nullable=False)
    building_b = db.Column(db.Integer, db.ForeignKey('buildings.building_id'), nullable=False)
    distance = db.Column(db.Float, nullable=False)


class SubService(db.Model):
    __tablename__ = 'sub_services'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service_name = db.Column(db.String(50))
    service_ip = db.Column(db.String(50))
    service_port = db.Column(db.Integer)
    description = db.Column(db.String(200))


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.String(4), nullable=True)
    target_grade = db.Column(db.String(10))
    target_major = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.now)


class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    __table_args__ = (db.UniqueConstraint('course_id', 'student_id', name='uq_course_student'),)


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text)
    due_at = db.Column(db.DateTime)
    created_by = db.Column(db.String(4), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    content = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.now)
    ai_score = db.Column(db.Float)
    ai_feedback = db.Column(db.Text)
    teacher_score = db.Column(db.Float)
    teacher_feedback = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_student'),)


class ClassroomAnnouncement(db.Model):
    __tablename__ = 'classroom_announcements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(4), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class CourseGrade(db.Model):
    __tablename__ = 'course_grades'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    student_id = db.Column(db.String(8), nullable=False)
    score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.String(255))
    updated_by = db.Column(db.String(4), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    __table_args__ = (db.UniqueConstraint('course_id', 'student_id', name='uq_course_grade_student'),)


class DdlItem(db.Model):
    __tablename__ = 'ddl_items'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    owner_id = db.Column(db.String(20), nullable=False)
    owner_type = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    due_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)


# ============ Helpers ============

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(user_id, user_type):
    payload = {
        'user_id': user_id,
        'user_type': user_type,
        'exp': datetime.now() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


def verify_token_str(token):
    try:
        return jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    payload = verify_token_str(token)
    if not payload:
        return None
    session = ActiveSession.query.filter_by(token=token).first()
    return payload if session else None


def require_user(*roles):
    payload = get_current_user()
    if not payload:
        return None, (jsonify({'success': False, 'message': '未登录或Token已过期'}), 401)
    if roles and payload['user_type'] not in roles:
        return None, (jsonify({'success': False, 'message': '无权访问该功能'}), 403)
    return payload, None


def parse_datetime(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError('时间格式无效')


def dt(value):
    return value.strftime('%Y-%m-%d %H:%M') if value else None


def course_to_dict(course):
    teacher = db.session.get(Teacher, course.teacher_id) if course.teacher_id else None
    return {
        'id': course.id,
        'code': course.code,
        'name': course.name,
        'description': course.description or '',
        'teacher_id': course.teacher_id or '',
        'teacher_label': course.teacher_id or '未分配',
        'teacher_college': teacher.college if teacher else '',
        'target_grade': course.target_grade or '',
        'target_major': course.target_major or '',
        'created_at': dt(course.created_at)
    }


def assignment_to_dict(assignment, student_id=None):
    submission = None
    if student_id:
        submission = AssignmentSubmission.query.filter_by(
            assignment_id=assignment.id,
            student_id=student_id
        ).first()
    return {
        'id': assignment.id,
        'course_id': assignment.course_id,
        'title': assignment.title,
        'content': assignment.content or '',
        'due_at': dt(assignment.due_at),
        'created_by': assignment.created_by,
        'created_at': dt(assignment.created_at),
        'submission': submission_to_dict(submission) if submission else None
    }


def submission_to_dict(submission):
    return {
        'id': submission.id,
        'assignment_id': submission.assignment_id,
        'student_id': submission.student_id,
        'content': submission.content,
        'submitted_at': dt(submission.submitted_at),
        'ai_score': submission.ai_score,
        'ai_feedback': submission.ai_feedback or '',
        'teacher_score': submission.teacher_score,
        'teacher_feedback': submission.teacher_feedback or ''
    }


def student_can_access_course(student_id, course):
    student = db.session.get(Student, student_id)
    if not student:
        return False
    if CourseEnrollment.query.filter_by(course_id=course.id, student_id=student_id).first():
        return True
    grade_ok = not course.target_grade or course.target_grade == student.grade
    major_ok = not course.target_major or course.target_major == student.major
    return grade_ok and major_ok


def teacher_owns_course(teacher_id, course_id):
    return Course.query.filter_by(id=course_id, teacher_id=teacher_id).first() is not None


def ai_review_submission(content, total_score=100):
    stripped = (content or '').strip()
    length = len(stripped)
    score = 60
    if length >= 80:
        score += 10
    if length >= 200:
        score += 10
    if any(key in stripped for key in ['分析', '步骤', '证明', '总结', '原因']):
        score += 8
    if any(key in stripped for key in ['代码', '实验', '结果', '数据', '结论']):
        score += 7
    score = min(float(total_score), float(score))
    feedback = 'AI初评：'
    if length < 80:
        feedback += '提交内容偏短，建议补充解题过程、关键依据和结论。'
    else:
        feedback += '提交内容较完整，建议教师重点复核关键推理、格式规范和原创性。'
    return score, feedback


# ============ Auth APIs ============

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    user_id = data.get('user_id', '').strip()
    password = data.get('password', '').strip()
    user_type = data.get('user_type', '').strip()

    if not all([user_id, password, user_type]):
        return jsonify({'success': False, 'message': '请填写完整信息'}), 400

    hashed = hash_password(password)
    if user_type == 'student':
        user = Student.query.filter_by(student_id=user_id, password=hashed).first()
    elif user_type == 'teacher':
        user = Teacher.query.filter_by(teacher_id=user_id, password=hashed).first()
    elif user_type == 'admin':
        user = Admin.query.filter_by(admin_id=user_id, password=hashed).first()
    else:
        return jsonify({'success': False, 'message': '无效的用户类型'}), 400

    if not user:
        return jsonify({'success': False, 'message': '账号或密码错误'}), 401

    ActiveSession.query.filter_by(user_id=user_id, user_type=user_type).delete()
    token = generate_token(user_id, user_type)
    db.session.add(ActiveSession(user_id=user_id, user_type=user_type, token=token))
    db.session.commit()
    return jsonify({'success': True, 'token': token, 'user_type': user_type, 'user_id': user_id})


@app.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        ActiveSession.query.filter_by(token=token).delete()
        db.session.commit()
    return jsonify({'success': True, 'message': '已登出'})


@app.route('/api/verify-token', methods=['GET'])
def verify_token_api():
    token = request.args.get('token', '') or request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token_str(token)
    if not payload:
        return jsonify({'valid': False, 'message': 'Token无效或已过期'}), 401
    session = ActiveSession.query.filter_by(token=token).first()
    if not session:
        return jsonify({'valid': False, 'message': '会话不存在'}), 401
    return jsonify({'valid': True, 'user_id': payload['user_id'], 'user_type': payload['user_type']})


@app.route('/api/user-info', methods=['GET'])
def user_info():
    payload, error = require_user()
    if error:
        return error

    user_id = payload['user_id']
    user_type = payload['user_type']
    info = {'user_id': user_id, 'user_type': user_type}

    if user_type == 'student':
        user = db.session.get(Student, user_id)
        if user:
            info.update({'grade': user.grade, 'major': user.major})
    elif user_type == 'teacher':
        user = db.session.get(Teacher, user_id)
        if user:
            info.update({'college': user.college, 'title': user.title})
    elif user_type == 'admin':
        user = db.session.get(Admin, user_id)
        if user:
            info.update({'name': user.name})

    return jsonify({'success': True, 'data': info})


# ============ Shared campus APIs ============

@app.route('/api/services', methods=['GET'])
def get_services():
    services = SubService.query.all()
    result = [{
        'id': s.id,
        'service_name': s.service_name,
        'service_ip': s.service_ip,
        'service_port': s.service_port,
        'description': s.description
    } for s in services]
    return jsonify({'success': True, 'data': result})


@app.route('/api/buildings', methods=['GET'])
def get_buildings():
    buildings = Building.query.all()
    result = [{'id': b.building_id, 'name': b.building_name} for b in buildings]
    return jsonify({'success': True, 'data': result})


@app.route('/api/campus-map', methods=['GET'])
def get_campus_map():
    buildings = Building.query.all()
    adjacency = BuildingAdjacency.query.all()
    nodes = [{'id': b.building_id, 'name': b.building_name} for b in buildings]
    edges = [{'from': a.building_a, 'to': a.building_b, 'distance': a.distance} for a in adjacency]
    return jsonify({'success': True, 'data': {'nodes': nodes, 'edges': edges}})


@app.route('/api/classrooms', methods=['GET'])
def get_classrooms():
    building = request.args.get('building', '')
    classrooms = Classroom.query.filter_by(building=building).all() if building else Classroom.query.all()
    result = [{'id': c.classroom_id, 'building': c.building} for c in classrooms]
    return jsonify({'success': True, 'data': result})


# ============ Classroom teaching APIs ============

@app.route('/api/teaching/teachers', methods=['GET'])
def list_teachers():
    payload, error = require_user('admin')
    if error:
        return error
    teachers = Teacher.query.order_by(Teacher.teacher_id).all()
    data = [{'teacher_id': t.teacher_id, 'college': t.college or '', 'title': t.title or ''} for t in teachers]
    return jsonify({'success': True, 'data': data})


@app.route('/api/teaching/students', methods=['GET'])
def list_students():
    payload, error = require_user('teacher', 'admin')
    if error:
        return error
    students = Student.query.order_by(Student.student_id).all()
    data = [{'student_id': s.student_id, 'grade': s.grade or '', 'major': s.major or ''} for s in students]
    return jsonify({'success': True, 'data': data})


@app.route('/api/teaching/courses', methods=['GET', 'POST'])
def courses_api():
    payload, error = require_user('student', 'teacher', 'admin')
    if error:
        return error

    if request.method == 'POST':
        payload, error = require_user('admin')
        if error:
            return error
        data = request.get_json() or {}
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()
        teacher_id = data.get('teacher_id', '').strip() or None
        if not code or not name:
            return jsonify({'success': False, 'message': '课程编号和课程名称不能为空'}), 400
        if teacher_id and not db.session.get(Teacher, teacher_id):
            return jsonify({'success': False, 'message': '授课教师不存在'}), 400
        if Course.query.filter_by(code=code).first():
            return jsonify({'success': False, 'message': '课程编号已存在'}), 409
        course = Course(
            code=code,
            name=name,
            description=data.get('description', '').strip(),
            teacher_id=teacher_id,
            target_grade=data.get('target_grade', '').strip(),
            target_major=data.get('target_major', '').strip()
        )
        db.session.add(course)
        db.session.commit()
        return jsonify({'success': True, 'data': course_to_dict(course)})

    user_type = payload['user_type']
    user_id = payload['user_id']
    if user_type == 'teacher':
        courses = Course.query.filter_by(teacher_id=user_id).order_by(Course.created_at.desc()).all()
    elif user_type == 'student':
        all_courses = Course.query.order_by(Course.created_at.desc()).all()
        courses = [c for c in all_courses if student_can_access_course(user_id, c)]
    else:
        courses = Course.query.order_by(Course.created_at.desc()).all()
    return jsonify({'success': True, 'data': [course_to_dict(c) for c in courses]})


@app.route('/api/teaching/courses/<int:course_id>', methods=['PUT', 'DELETE'])
def course_detail_api(course_id):
    payload, error = require_user('admin')
    if error:
        return error
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': '课程不存在'}), 404

    if request.method == 'DELETE':
        CourseEnrollment.query.filter_by(course_id=course_id).delete()
        CourseGrade.query.filter_by(course_id=course_id).delete()
        ClassroomAnnouncement.query.filter_by(course_id=course_id).delete()
        assignments = Assignment.query.filter_by(course_id=course_id).all()
        for assignment in assignments:
            AssignmentSubmission.query.filter_by(assignment_id=assignment.id).delete()
            db.session.delete(assignment)
        db.session.delete(course)
        db.session.commit()
        return jsonify({'success': True, 'message': '课程已删除'})

    data = request.get_json() or {}
    teacher_id = data.get('teacher_id', '').strip() or None
    if teacher_id and not db.session.get(Teacher, teacher_id):
        return jsonify({'success': False, 'message': '授课教师不存在'}), 400
    if data.get('code', '').strip() and data.get('code', '').strip() != course.code:
        exists = Course.query.filter_by(code=data.get('code').strip()).first()
        if exists:
            return jsonify({'success': False, 'message': '课程编号已存在'}), 409
        course.code = data.get('code').strip()
    course.name = data.get('name', course.name).strip() or course.name
    course.description = data.get('description', course.description or '').strip()
    course.teacher_id = teacher_id
    course.target_grade = data.get('target_grade', course.target_grade or '').strip()
    course.target_major = data.get('target_major', course.target_major or '').strip()
    db.session.commit()
    return jsonify({'success': True, 'data': course_to_dict(course)})


@app.route('/api/teaching/courses/<int:course_id>/assign-teacher', methods=['POST'])
def assign_teacher(course_id):
    payload, error = require_user('admin')
    if error:
        return error
    data = request.get_json() or {}
    teacher_id = data.get('teacher_id', '').strip()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': '课程不存在'}), 404
    if not db.session.get(Teacher, teacher_id):
        return jsonify({'success': False, 'message': '授课教师不存在'}), 400
    course.teacher_id = teacher_id
    db.session.commit()
    return jsonify({'success': True, 'data': course_to_dict(course)})


@app.route('/api/teaching/courses/<int:course_id>/assignments', methods=['GET', 'POST'])
def assignments_api(course_id):
    payload, error = require_user('student', 'teacher')
    if error:
        return error
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': '课程不存在'}), 404

    if payload['user_type'] == 'teacher':
        if course.teacher_id != payload['user_id']:
            return jsonify({'success': False, 'message': '只能管理自己的课程'}), 403
        if request.method == 'POST':
            data = request.get_json() or {}
            title = data.get('title', '').strip()
            if not title:
                return jsonify({'success': False, 'message': '作业标题不能为空'}), 400
            try:
                due_at = parse_datetime(data.get('due_at'))
            except ValueError as exc:
                return jsonify({'success': False, 'message': str(exc)}), 400
            assignment = Assignment(
                course_id=course_id,
                title=title,
                content=data.get('content', '').strip(),
                due_at=due_at,
                created_by=payload['user_id']
            )
            db.session.add(assignment)
            if due_at:
                db.session.add(DdlItem(
                    course_id=course_id,
                    owner_id=payload['user_id'],
                    owner_type='teacher',
                    title=f'{course.name}：{title}',
                    due_at=due_at
                ))
            db.session.commit()
            return jsonify({'success': True, 'data': assignment_to_dict(assignment)})
        assignments = Assignment.query.filter_by(course_id=course_id).order_by(Assignment.created_at.desc()).all()
        return jsonify({'success': True, 'data': [assignment_to_dict(a) for a in assignments]})

    if not student_can_access_course(payload['user_id'], course):
        return jsonify({'success': False, 'message': '未加入该课程'}), 403
    assignments = Assignment.query.filter_by(course_id=course_id).order_by(Assignment.created_at.desc()).all()
    return jsonify({'success': True, 'data': [assignment_to_dict(a, payload['user_id']) for a in assignments]})


@app.route('/api/teaching/assignments/<int:assignment_id>/submit', methods=['POST'])
def submit_assignment(assignment_id):
    payload, error = require_user('student')
    if error:
        return error
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        return jsonify({'success': False, 'message': '作业不存在'}), 404
    course = db.session.get(Course, assignment.course_id)
    if not student_can_access_course(payload['user_id'], course):
        return jsonify({'success': False, 'message': '未加入该课程'}), 403
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'message': '提交内容不能为空'}), 400
    submission = AssignmentSubmission.query.filter_by(
        assignment_id=assignment_id,
        student_id=payload['user_id']
    ).first()
    if not submission:
        submission = AssignmentSubmission(assignment_id=assignment_id, student_id=payload['user_id'], content=content)
        db.session.add(submission)
    else:
        submission.content = content
        submission.submitted_at = datetime.now()
    score, feedback = ai_review_submission(content)
    submission.ai_score = score
    submission.ai_feedback = feedback
    db.session.commit()
    return jsonify({'success': True, 'data': submission_to_dict(submission)})


@app.route('/api/teaching/assignments/<int:assignment_id>/submissions', methods=['GET'])
def assignment_submissions(assignment_id):
    payload, error = require_user('teacher')
    if error:
        return error
    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        return jsonify({'success': False, 'message': '作业不存在'}), 404
    if not teacher_owns_course(payload['user_id'], assignment.course_id):
        return jsonify({'success': False, 'message': '只能查看自己课程的提交'}), 403
    submissions = AssignmentSubmission.query.filter_by(assignment_id=assignment_id).order_by(
        AssignmentSubmission.submitted_at.desc()
    ).all()
    return jsonify({'success': True, 'data': [submission_to_dict(s) for s in submissions]})


@app.route('/api/teaching/submissions/<int:submission_id>/ai-grade', methods=['POST'])
def ai_grade_submission(submission_id):
    payload, error = require_user('teacher')
    if error:
        return error
    submission = db.session.get(AssignmentSubmission, submission_id)
    if not submission:
        return jsonify({'success': False, 'message': '提交不存在'}), 404
    assignment = db.session.get(Assignment, submission.assignment_id)
    if not teacher_owns_course(payload['user_id'], assignment.course_id):
        return jsonify({'success': False, 'message': '只能批改自己课程的提交'}), 403
    score, feedback = ai_review_submission(submission.content)
    submission.ai_score = score
    submission.ai_feedback = feedback
    db.session.commit()
    return jsonify({'success': True, 'data': submission_to_dict(submission)})


@app.route('/api/teaching/submissions/<int:submission_id>/teacher-grade', methods=['POST'])
def teacher_grade_submission(submission_id):
    payload, error = require_user('teacher')
    if error:
        return error
    submission = db.session.get(AssignmentSubmission, submission_id)
    if not submission:
        return jsonify({'success': False, 'message': '提交不存在'}), 404
    assignment = db.session.get(Assignment, submission.assignment_id)
    if not teacher_owns_course(payload['user_id'], assignment.course_id):
        return jsonify({'success': False, 'message': '只能批改自己课程的提交'}), 403
    data = request.get_json() or {}
    try:
        score = float(data.get('teacher_score'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': '教师评分必须是数字'}), 400
    submission.teacher_score = score
    submission.teacher_feedback = data.get('teacher_feedback', '').strip()
    db.session.commit()
    return jsonify({'success': True, 'data': submission_to_dict(submission)})


@app.route('/api/teaching/courses/<int:course_id>/announcements', methods=['GET', 'POST'])
def announcements_api(course_id):
    payload, error = require_user('student', 'teacher')
    if error:
        return error
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': '课程不存在'}), 404

    if payload['user_type'] == 'teacher':
        if course.teacher_id != payload['user_id']:
            return jsonify({'success': False, 'message': '只能管理自己的课程'}), 403
        if request.method == 'POST':
            data = request.get_json() or {}
            title = data.get('title', '').strip()
            content = data.get('content', '').strip()
            if not title or not content:
                return jsonify({'success': False, 'message': '公告标题和内容不能为空'}), 400
            announcement = ClassroomAnnouncement(
                course_id=course_id,
                title=title,
                content=content,
                created_by=payload['user_id']
            )
            db.session.add(announcement)
            db.session.commit()
            return jsonify({'success': True, 'data': {
                'id': announcement.id,
                'course_id': announcement.course_id,
                'title': announcement.title,
                'content': announcement.content,
                'created_at': dt(announcement.created_at)
            }})
    elif not student_can_access_course(payload['user_id'], course):
        return jsonify({'success': False, 'message': '未加入该课程'}), 403

    announcements = ClassroomAnnouncement.query.filter_by(course_id=course_id).order_by(
        ClassroomAnnouncement.created_at.desc()
    ).all()
    data = [{
        'id': a.id,
        'course_id': a.course_id,
        'title': a.title,
        'content': a.content,
        'created_by': a.created_by,
        'created_at': dt(a.created_at)
    } for a in announcements]
    return jsonify({'success': True, 'data': data})


@app.route('/api/teaching/courses/<int:course_id>/grades', methods=['GET', 'POST'])
def grades_api(course_id):
    payload, error = require_user('student', 'teacher')
    if error:
        return error
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': '课程不存在'}), 404

    if payload['user_type'] == 'student':
        if not student_can_access_course(payload['user_id'], course):
            return jsonify({'success': False, 'message': '未加入该课程'}), 403
        grade = CourseGrade.query.filter_by(course_id=course_id, student_id=payload['user_id']).first()
        return jsonify({'success': True, 'data': [] if not grade else [{
            'id': grade.id,
            'course_id': grade.course_id,
            'student_id': grade.student_id,
            'score': grade.score,
            'comment': grade.comment or '',
            'updated_at': dt(grade.updated_at)
        }]})

    if course.teacher_id != payload['user_id']:
        return jsonify({'success': False, 'message': '只能管理自己的课程成绩'}), 403
    if request.method == 'POST':
        data = request.get_json() or {}
        student_id = data.get('student_id', '').strip()
        if not db.session.get(Student, student_id):
            return jsonify({'success': False, 'message': '学生不存在'}), 400
        try:
            score = float(data.get('score'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': '成绩必须是数字'}), 400
        grade = CourseGrade.query.filter_by(course_id=course_id, student_id=student_id).first()
        if not grade:
            grade = CourseGrade(course_id=course_id, student_id=student_id, score=score, updated_by=payload['user_id'])
            db.session.add(grade)
        grade.score = score
        grade.comment = data.get('comment', '').strip()
        grade.updated_by = payload['user_id']
        db.session.commit()
        return jsonify({'success': True, 'data': {
            'id': grade.id,
            'course_id': grade.course_id,
            'student_id': grade.student_id,
            'score': grade.score,
            'comment': grade.comment or '',
            'updated_at': dt(grade.updated_at)
        }})

    grades = CourseGrade.query.filter_by(course_id=course_id).order_by(CourseGrade.student_id).all()
    data = [{
        'id': g.id,
        'course_id': g.course_id,
        'student_id': g.student_id,
        'score': g.score,
        'comment': g.comment or '',
        'updated_at': dt(g.updated_at)
    } for g in grades]
    return jsonify({'success': True, 'data': data})


@app.route('/api/teaching/ddls', methods=['GET', 'POST'])
def ddl_api():
    payload, error = require_user('student', 'teacher')
    if error:
        return error
    if request.method == 'POST':
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'message': 'DDL标题不能为空'}), 400
        try:
            due_at = parse_datetime(data.get('due_at'))
        except ValueError as exc:
            return jsonify({'success': False, 'message': str(exc)}), 400
        if not due_at:
            return jsonify({'success': False, 'message': '截止时间不能为空'}), 400
        item = DdlItem(
            course_id=data.get('course_id') or None,
            owner_id=payload['user_id'],
            owner_type=payload['user_type'],
            title=title,
            due_at=due_at,
            status=data.get('status', 'pending')
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({'success': True, 'data': {
            'id': item.id,
            'course_id': item.course_id,
            'title': item.title,
            'due_at': dt(item.due_at),
            'status': item.status
        }})

    items = DdlItem.query.filter_by(owner_id=payload['user_id'], owner_type=payload['user_type']).order_by(DdlItem.due_at).all()
    data = [{
        'id': i.id,
        'course_id': i.course_id,
        'title': i.title,
        'due_at': dt(i.due_at),
        'status': i.status
    } for i in items]
    return jsonify({'success': True, 'data': data})


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'service': 'main-service', 'port': 5001})


# ============ Page routes ============

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/favicon.ico')
def favicon():
    return '', 204


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=os.environ.get('FLASK_DEBUG') == '1')
