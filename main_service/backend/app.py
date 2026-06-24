from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import jwt
import hashlib
import os

# 前端文件路径（兼容本地开发和 Docker）
FRONTEND_DIR = os.environ.get('FRONTEND_DIR', os.path.join(os.path.dirname(__file__), '..', 'frontend'))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# ============ 配置 ============
DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')

app.config['SECRET_KEY'] = 'campus-mis-secret-key-2024'
# 主数据库：main_database（会话、服务注册、建筑等）
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/main_database'
# 用户数据库：users_database（学生、教师、管理员）
app.config['SQLALCHEMY_BINDS'] = {
    'users': f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/users_database'
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============ 数据模型 ============

class Student(db.Model):
    __bind_key__ = 'users'
    __tablename__ = 'students'
    student_id = db.Column(db.String(8), primary_key=True)  # 8位学号
    password = db.Column(db.String(128), nullable=False)
    grade = db.Column(db.String(10))
    major = db.Column(db.String(50))

class Teacher(db.Model):
    __bind_key__ = 'users'
    __tablename__ = 'teachers'
    teacher_id = db.Column(db.String(4), primary_key=True)  # 4位工号
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
    user_type = db.Column(db.String(10), nullable=False)  # student/teacher/admin
    login_time = db.Column(db.DateTime, default=datetime.now)
    token = db.Column(db.String(500), nullable=False)

class Classroom(db.Model):
    __tablename__ = 'classrooms'
    classroom_id = db.Column(db.String(4), primary_key=True)  # 4位编号
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
    distance = db.Column(db.Float, nullable=False)  # 距离（米）

class SubService(db.Model):
    __tablename__ = 'sub_services'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service_name = db.Column(db.String(50))
    service_ip = db.Column(db.String(50))
    service_port = db.Column(db.Integer)
    description = db.Column(db.String(200))

# ============ 工具函数 ============

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
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_current_user():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    payload = verify_token_str(token)
    if not payload:
        return None
    # 检查 session 是否存在
    session = ActiveSession.query.filter_by(token=token).first()
    if not session:
        return None
    return payload

# ============ API 路由 ============

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user_id = data.get('user_id', '').strip()
    password = data.get('password', '').strip()
    user_type = data.get('user_type', '').strip()

    if not all([user_id, password, user_type]):
        return jsonify({'success': False, 'message': '请填写完整信息'}), 400

    hashed = hash_password(password)

    # 根据角色查询对应表
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

    # 清除该用户旧的 session（避免累积）
    ActiveSession.query.filter_by(user_id=user_id, user_type=user_type).delete()

    # 生成 token
    token = generate_token(user_id, user_type)

    # 记录登录 session
    session = ActiveSession(user_id=user_id, user_type=user_type, token=token)
    db.session.add(session)
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
    """供分服务调用，验证 token 有效性"""
    token = request.args.get('token', '')
    if not token:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')

    payload = verify_token_str(token)
    if not payload:
        return jsonify({'valid': False, 'message': 'Token无效或已过期'}), 401

    session = ActiveSession.query.filter_by(token=token).first()
    if not session:
        return jsonify({'valid': False, 'message': '会话不存在'}), 401

    return jsonify({
        'valid': True,
        'user_id': payload['user_id'],
        'user_type': payload['user_type']
    })

@app.route('/api/user-info', methods=['GET'])
def user_info():
    payload = get_current_user()
    if not payload:
        return jsonify({'success': False, 'message': '未登录或Token已过期'}), 401

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

@app.route('/api/services', methods=['GET'])
def get_services():
    """获取已注册的分服务列表"""
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
    """获取所有建筑信息"""
    buildings = Building.query.all()
    result = [{'id': b.building_id, 'name': b.building_name} for b in buildings]
    return jsonify({'success': True, 'data': result})

@app.route('/api/campus-map', methods=['GET'])
def get_campus_map():
    """获取校园地图（建筑+邻接距离）"""
    buildings = Building.query.all()
    adjacency = BuildingAdjacency.query.all()

    nodes = [{'id': b.building_id, 'name': b.building_name} for b in buildings]
    edges = [{
        'from': a.building_a,
        'to': a.building_b,
        'distance': a.distance
    } for a in adjacency]

    return jsonify({'success': True, 'data': {'nodes': nodes, 'edges': edges}})

@app.route('/api/classrooms', methods=['GET'])
def get_classrooms():
    """获取教室列表，可按楼栋筛选"""
    building = request.args.get('building', '')
    if building:
        classrooms = Classroom.query.filter_by(building=building).all()
    else:
        classrooms = Classroom.query.all()
    result = [{'id': c.classroom_id, 'building': c.building} for c in classrooms]
    return jsonify({'success': True, 'data': result})

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'service': 'main-service', 'port': 5001})

# ============ 页面路由 ============

@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

# ============ 启动 ============

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
