"""认证服务 - 主应用"""
import datetime
import bcrypt
import jwt
from flask import Flask, request, jsonify
from config import Config
from models import db, User

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)


def generate_token(user):
    """生成JWT Token"""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'ref_id': user.ref_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRATION_HOURS),
        'iat': datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    return token


def verify_token(token):
    """验证JWT Token"""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'code': 400, 'message': '用户名和密码不能为空'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'code': 401, 'message': '用户名或密码错误'}), 401

    # 验证密码
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'code': 401, 'message': '用户名或密码错误'}), 401

    # 生成Token
    token = generate_token(user)
    return jsonify({
        'code': 200,
        'message': '登录成功',
        'data': {
            'token': token,
            'user': user.to_dict()
        }
    })


@app.route('/api/auth/verify', methods=['GET'])
def verify():
    """验证Token有效性"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'code': 401, 'message': '未提供有效Token'}), 401

    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'message': 'Token无效或已过期'}), 401

    return jsonify({
        'code': 200,
        'message': 'Token有效',
        'data': {
            'user_id': payload['user_id'],
            'username': payload['username'],
            'role': payload['role'],
            'ref_id': payload.get('ref_id')
        }
    })


@app.route('/api/auth/profile', methods=['GET'])
def profile():
    """获取当前用户信息"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'code': 401, 'message': '未提供有效Token'}), 401

    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'message': 'Token无效或已过期'}), 401

    user = User.query.get(payload['user_id'])
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404

    return jsonify({
        'code': 200,
        'data': user.to_dict()
    })


@app.route('/api/auth/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': Config.SERVICE_NAME})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=True)
