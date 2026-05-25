"""API网关 - 主应用
负责统一入口、请求路由转发、Token校验
"""
import jwt
import requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from config import Config

app = Flask(__name__)
CORS(app, supports_credentials=True)


def verify_token(token):
    """验证JWT Token"""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def is_public_route(path):
    """判断是否为公开路由（不需要认证）"""
    for route in Config.PUBLIC_ROUTES:
        if path.startswith(route):
            return True
    return False


def get_target_service(path):
    """根据路径确定目标服务"""
    for prefix, service_name in Config.ROUTE_MAP.items():
        if path.startswith(prefix):
            return service_name, Config.SERVICES.get(service_name)
    return None, None


def proxy_request(target_url, headers_extra=None):
    """转发请求到目标服务"""
    # 构建转发的headers
    headers = {}
    for key, value in request.headers:
        if key.lower() not in ('host', 'content-length'):
            headers[key] = value

    # 添加额外的headers（如用户信息）
    if headers_extra:
        headers.update(headers_extra)

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=30
        )

        # 构建响应
        response = Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'application/json')
        )
        return response

    except requests.exceptions.ConnectionError:
        return jsonify({
            'code': 503,
            'message': '服务暂时不可用，请稍后重试'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'code': 504,
            'message': '服务响应超时'
        }), 504


@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def gateway(path):
    """统一网关入口"""
    full_path = f'/api/{path}'

    # 确定目标服务
    service_name, service_url = get_target_service(full_path)
    if not service_url:
        return jsonify({'code': 404, 'message': '服务未找到'}), 404

    # 公开路由直接转发
    if is_public_route(full_path):
        target_url = f'{service_url}{full_path}'
        return proxy_request(target_url)

    # 非公开路由需要验证Token
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'code': 401, 'message': '未提供认证Token'}), 401

    token = auth_header[7:]
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'message': 'Token无效或已过期'}), 401

    # 将用户信息附加到请求头，传递给下游服务
    headers_extra = {
        'X-User-Id': str(payload.get('user_id', '')),
        'X-User-Name': payload.get('username', ''),
        'X-User-Role': payload.get('role', ''),
        'X-User-Ref-Id': payload.get('ref_id', '') or ''
    }

    target_url = f'{service_url}{full_path}'
    return proxy_request(target_url, headers_extra)


@app.route('/health', methods=['GET'])
def health():
    """网关健康检查"""
    # 检查所有下游服务状态
    services_status = {}
    for name, url in Config.SERVICES.items():
        try:
            resp = requests.get(f'{url}/api/{name}/health', timeout=5)
            services_status[name] = 'up' if resp.status_code == 200 else 'down'
        except Exception:
            services_status[name] = 'down'

    return jsonify({
        'status': 'ok',
        'service': 'api-gateway',
        'downstream_services': services_status
    })


if __name__ == '__main__':
    print("=" * 50)
    print("  Campus MIS API Gateway")
    print(f"  Running on port {Config.GATEWAY_PORT}")
    print("  Registered services:")
    for name, url in Config.SERVICES.items():
        print(f"    - {name}: {url}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=Config.GATEWAY_PORT, debug=True)
