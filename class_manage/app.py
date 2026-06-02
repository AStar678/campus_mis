import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from extensions import db
from routes import api_bp

FRONTEND_DIR = os.environ.get('FRONTEND_DIR', os.path.join(os.path.dirname(__file__), 'frontend'))

def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
    CORS(app)

    # 数据库配置
    DB_HOST = os.environ.get('DB_HOST', '47.93.226.110')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASS = os.environ.get('DB_PASS', '')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/classroom_database'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化组件
    db.init_app(app)
    app.register_blueprint(api_bp)

    # 静态页面路由映射
    @app.route('/')
    def serve_index():
        """默认访问根目录，返回调度中心页"""
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.route('/<path:filename>')
    def serve_static(filename):
        """直接访问具体角色的独立HTML文件"""
        return send_from_directory(FRONTEND_DIR, filename)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5003, debug=True)