"""学生管理服务 - 主应用"""
import jwt
from functools import wraps
from flask import Flask, request, jsonify
from config import Config
from models import db, Student

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def token_required(f):
    """Token验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 从网关转发的请求头中获取用户信息
        user_id = request.headers.get('X-User-Id')
        user_role = request.headers.get('X-User-Role')

        if not user_id:
            # 也支持直接通过 Authorization header 验证
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                try:
                    payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
                    request.current_user = payload
                except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                    return jsonify({'code': 401, 'message': '未授权访问'}), 401
            else:
                return jsonify({'code': 401, 'message': '未授权访问'}), 401
        else:
            request.current_user = {
                'user_id': int(user_id),
                'role': user_role,
                'username': request.headers.get('X-User-Name', '')
            }
        return f(*args, **kwargs)
    return decorated


@app.route('/api/students', methods=['GET'])
@token_required
def get_students():
    """获取学生列表（仅管理员可用）"""
    # 学生角色不允许访问学生列表
    if request.current_user.get('role') == 'student':
        return jsonify({'code': 403, 'message': '权限不足'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    keyword = request.args.get('keyword', '').strip()

    query = Student.query

    # 关键字搜索（学号或姓名）
    if keyword:
        query = query.filter(
            db.or_(
                Student.student_id.like(f'%{keyword}%'),
                Student.name.like(f'%{keyword}%')
            )
        )

    # 分页
    pagination = query.order_by(Student.student_id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    students = [s.to_dict() for s in pagination.items]

    return jsonify({
        'code': 200,
        'data': {
            'list': students,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@app.route('/api/students/<student_id>', methods=['GET'])
@token_required
def get_student(student_id):
    """获取单个学生信息
    学生只能查看自己的信息，管理员可以查看任意学生
    """
    current_role = request.current_user.get('role')
    current_ref_id = request.current_user.get('ref_id') or request.headers.get('X-User-Ref-Id', '')

    # 学生只能查看自己的信息
    if current_role == 'student' and current_ref_id != student_id:
        return jsonify({'code': 403, 'message': '只能查看自己的信息'}), 403

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'code': 404, 'message': '学生不存在'}), 404

    return jsonify({
        'code': 200,
        'data': student.to_dict()
    })


@app.route('/api/students', methods=['POST'])
@token_required
def create_student():
    """新增学生"""
    # 仅管理员可以新增
    if request.current_user.get('role') != 'admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    student_id = data.get('student_id', '').strip()
    name = data.get('name', '').strip()

    if not student_id or not name:
        return jsonify({'code': 400, 'message': '学号和姓名不能为空'}), 400

    # 检查学号是否已存在
    if Student.query.get(student_id):
        return jsonify({'code': 409, 'message': '该学号已存在'}), 409

    student = Student(
        student_id=student_id,
        name=name,
        gender=data.get('gender', '男'),
        college=data.get('college'),
        major=data.get('major'),
        class_name=data.get('class_name'),
        gpa=data.get('gpa', 0.00),
        enrollment_year=data.get('enrollment_year')
    )

    db.session.add(student)
    db.session.commit()

    return jsonify({
        'code': 201,
        'message': '学生创建成功',
        'data': student.to_dict()
    }), 201


@app.route('/api/students/<student_id>', methods=['PUT'])
@token_required
def update_student(student_id):
    """修改学生信息"""
    if request.current_user.get('role') != 'admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'code': 404, 'message': '学生不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    # 更新字段
    if 'name' in data:
        student.name = data['name']
    if 'gender' in data:
        student.gender = data['gender']
    if 'college' in data:
        student.college = data['college']
    if 'major' in data:
        student.major = data['major']
    if 'class_name' in data:
        student.class_name = data['class_name']
    if 'gpa' in data:
        student.gpa = data['gpa']
    if 'enrollment_year' in data:
        student.enrollment_year = data['enrollment_year']

    db.session.commit()

    return jsonify({
        'code': 200,
        'message': '学生信息更新成功',
        'data': student.to_dict()
    })


@app.route('/api/students/<student_id>', methods=['DELETE'])
@token_required
def delete_student(student_id):
    """删除学生"""
    if request.current_user.get('role') != 'admin':
        return jsonify({'code': 403, 'message': '权限不足'}), 403

    student = Student.query.get(student_id)
    if not student:
        return jsonify({'code': 404, 'message': '学生不存在'}), 404

    db.session.delete(student)
    db.session.commit()

    return jsonify({
        'code': 200,
        'message': '学生删除成功'
    })


@app.route('/api/students/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': Config.SERVICE_NAME})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=True)
