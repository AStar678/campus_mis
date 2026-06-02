import os
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify
from extensions import db
from models import Course, CourseStudent, Homework, Submission, Announcement

# 创建蓝图，统一 URL 前缀
api_bp = Blueprint('api', __name__, url_prefix='/api/classroom')

# 主服务地址，用于 SSO 单点登录验证
MAIN_SERVICE_URL = 'http://127.0.0.1:5001'

# 配置文件上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==========================================
# 通用中间件与全局接口
# ==========================================

def get_current_user():
    """统一向主服务请求验证 Token 有效性，实现无状态鉴权"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    token = token or request.args.get('token')
    
    if not token:
        return None
        
    try:
        # 向 5001 端口的主服务发起内部校验
        resp = requests.get(f"{MAIN_SERVICE_URL}/api/verify-token", headers={'Authorization': f'Bearer {token}'})
        if resp.status_code == 200:
            return resp.json()  # 返回格式: {'valid': True, 'user_id': 'xxx', 'user_type': 'xxx'}
    except Exception as e:
        print(f"[Auth Error] 无法连接到主鉴权服务: {e}")
        
    return None

@api_bp.route('/user-info', methods=['GET'])
def get_user_info():
    """供前端单页初始加载时，拉取当前上下文的用户信息与角色权限"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': '凭证无效或已过期'}), 401
    return jsonify({'success': True, 'data': user})


# ==========================================
# 学生端接口 (Student API)
# ==========================================

@api_bp.route('/my-courses', methods=['GET'])
def get_my_courses():
    """获取当前学生选修的所有课程列表"""
    user = get_current_user()
    if not user or user['user_type'] != 'student':
        return jsonify({'success': False, 'message': '无权限访问'}), 403
        
    student_id = user['user_id']
    
    # 联表查询：通过 course_students 关联表查出该学生的所有课程
    courses = db.session.query(Course).join(
        CourseStudent, Course.id == CourseStudent.course_id
    ).filter(CourseStudent.student_id == student_id).all()
    
    result = [{
        'id': c.id, 
        'name': c.name, 
        'description': c.description
    } for c in courses]
    
    return jsonify({'success': True, 'data': result})


@api_bp.route('/course/<int:course_id>/details', methods=['GET'])
def get_course_details(course_id):
    """进入特定课程，获取该课程的公告面板和未过期的作业 DDL"""
    user = get_current_user()
    if not user or user['user_type'] != 'student':
        return jsonify({'success': False, 'message': '无权限访问'}), 403

    # 安全校验：确保当前学生确实在修读这门课
    is_enrolled = CourseStudent.query.filter_by(course_id=course_id, student_id=user['user_id']).first()
    if not is_enrolled:
        return jsonify({'success': False, 'message': '越权操作：您未加入该课程'}), 403

    now = datetime.now()
    
    # 1. 抓取公告 (按发布时间倒序，最新的在最上面)
    announcements = Announcement.query.filter_by(course_id=course_id).order_by(Announcement.created_at.desc()).all()
    ann_list = [{
        'id': a.id, 
        'title': a.title, 
        'content': a.content, 
        'created_at': a.created_at.strftime('%Y-%m-%d %H:%M')
    } for a in announcements]

    # 2. 抓取作业与 DDL (仅展示未过期的，按截止时间升序排列)
    homeworks = Homework.query.filter(
        Homework.course_id == course_id, 
        Homework.deadline > now
    ).order_by(Homework.deadline.asc()).all()
    
    hw_list = [{
        'id': hw.id, 
        'title': hw.title, 
        'description': hw.description,
        'deadline': hw.deadline.strftime('%Y-%m-%d %H:%M:%S'),
        'days_left': (hw.deadline - now).days
    } for hw in homeworks]

    return jsonify({
        'success': True, 
        'data': {
            'announcements': ann_list, 
            'homeworks': hw_list
        }
    })


@api_bp.route('/submit-file', methods=['POST'])
def submit_file_homework():
    """处理带附件（代码/PDF）和文本的作业提交，兼容 FormData"""
    user = get_current_user()
    if not user or user['user_type'] != 'student':
        return jsonify({'success': False, 'message': '无权限访问'}), 403
    
    homework_id = request.form.get('homework_id')
    content = request.form.get('content', '')
    file = request.files.get('file')
    
    file_path = None
    save_name = None
    
    # 文件处理逻辑
    if file and file.filename != '':
        # 清洗文件名，附带学号和时间戳防重名防覆盖
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        save_name = f"{user['user_id']}_{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, save_name)
        file.save(file_path)
    
    # AI 预评分逻辑 (此处为 Mock，实际可接入大语言模型)
    # 若附带了有效文件或长篇文本，则判定高分区间
    ai_score = 90.0 if (file or len(content) > 30) else 65.0
    
    # 组装最终存入数据库的内容记录
    final_content = content
    if save_name:
        final_content += f"\n\n[系统记录]: 附件已成功上传至云端归档 -> {save_name}"
        
    # 落库
    sub = Submission(
        homework_id=homework_id, 
        student_id=user['user_id'], 
        content=final_content, 
        ai_score=ai_score, 
        ai_comment="附件及代码文本解析完毕，AI 架构评估通过。"
    )
    db.session.add(sub)
    db.session.commit()
    
    return jsonify({'success': True, 'ai_score': ai_score})


# ==========================================
# 教师端接口 (Teacher API)
# ==========================================

@api_bp.route('/homework', methods=['POST'])
def create_homework():
    """发布新作业与 DDL 任务"""
    user = get_current_user()
    if not user or user['user_type'] != 'teacher':
        return jsonify({'success': False, 'message': '越权操作：仅教师可发布作业'}), 403
    
    data = request.json
    try:
        # 将前端传来的时间字符串安全转换为 datetime 对象
        deadline_dt = datetime.strptime(data['deadline'], '%Y-%m-%d %H:%M:%S')
        
        hw = Homework(
            course_id=data['course_id'], 
            title=data['title'], 
            description=data['description'], 
            deadline=deadline_dt
        )
        db.session.add(hw)
        db.session.commit()
        return jsonify({'success': True, 'message': '作业及 DDL 发布成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'发布异常，请检查时间格式: {str(e)}'}), 400


# ==========================================
# 管理端接口 (Admin API)
# ==========================================

@api_bp.route('/courses', methods=['POST'])
def create_course():
    """录入全新课程并分配授课教师"""
    user = get_current_user()
    if not user or user['user_type'] != 'admin':
        return jsonify({'success': False, 'message': '越权操作：仅教务管理员可操作'}), 403
    
    data = request.json
    
    try:
        new_course = Course(
            name=data['name'], 
            teacher_id=data['teacher_id'], 
            description=data.get('description', '')
        )
        db.session.add(new_course)
        db.session.commit()
        return jsonify({'success': True, 'message': '课程注册及教资绑定成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': '课程创建失败，请检查数据完整性'}), 400
    

# ==========================================
# 教师端扩展接口 (Teacher API)
# ==========================================

@api_bp.route('/teacher/my-courses', methods=['GET'])
def get_teacher_courses():
    """获取教师主讲的课程列表"""
    user = get_current_user()
    if not user or user['user_type'] != 'teacher':
        return jsonify({'success': False}), 403
        
    courses = Course.query.filter_by(teacher_id=user['user_id']).all()
    return jsonify({'success': True, 'data': [{'id': c.id, 'name': c.name} for c in courses]})

@api_bp.route('/teacher/course/<int:course_id>/dashboard', methods=['GET'])
def get_teacher_dashboard(course_id):
    """获取课程的管理大盘：学生名单、作业列表及整体成绩分布"""
    user = get_current_user()
    if not user or user['user_type'] != 'teacher':
        return jsonify({'success': False}), 403

    # 1. 获取选课学生及期末成绩
    students = CourseStudent.query.filter_by(course_id=course_id).all()
    student_list = [{'student_id': s.student_id, 'final_grade': s.final_grade} for s in students]

    # 2. 获取该课程的全部作业
    homeworks = Homework.query.filter_by(course_id=course_id).order_by(Homework.deadline.desc()).all()
    hw_list = [{'id': hw.id, 'title': hw.title, 'deadline': hw.deadline.strftime('%Y-%m-%d %H:%M')} for hw in homeworks]

    # 3. 获取所有作业的提交记录，用于构建成绩单二维表
    hw_ids = [hw.id for hw in homeworks]
    submissions = Submission.query.filter(Submission.homework_id.in_(hw_ids)).all() if hw_ids else []
    
    sub_map = {}
    for sub in submissions:
        if sub.student_id not in sub_map:
            sub_map[sub.student_id] = {}
        # 优先展示教师最终成绩，若无则展示 AI 成绩
        sub_map[sub.student_id][sub.homework_id] = {
            'sub_id': sub.id,
            'score': sub.final_score if sub.final_score is not None else sub.ai_score,
            'is_ai': sub.final_score is None,
            'content': sub.content,
            'ai_comment': sub.ai_comment
        }

    return jsonify({
        'success': True, 
        'data': {'students': student_list, 'homeworks': hw_list, 'grades': sub_map}
    })

@api_bp.route('/teacher/grade-submission', methods=['POST'])
def grade_submission():
    """教师人工批改/复核具体作业"""
    user = get_current_user()
    data = request.json
    sub = Submission.query.get(data['submission_id'])
    if sub:
        sub.final_score = data['score']
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '记录不存在'})

@api_bp.route('/teacher/grade-final', methods=['POST'])
def grade_final():
    """录入期末总评成绩"""
    user = get_current_user()
    data = request.json
    cs = CourseStudent.query.filter_by(course_id=data['course_id'], student_id=data['student_id']).first()
    if cs:
        cs.final_grade = data['final_grade']
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})


@api_bp.route('/announcement', methods=['POST'])
def create_announcement():
    """发布课堂通知"""
    user = get_current_user()
    if not user or user['user_type'] != 'teacher':
        return jsonify({'success': False, 'message': '越权操作：仅教师可发布通知'}), 403
    
    data = request.json
    try:
        ann = Announcement(
            course_id=data['course_id'],
            title=data['title'],
            content=data['content']
        )
        db.session.add(ann)
        db.session.commit()
        return jsonify({'success': True, 'message': '课堂通知发布成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': '通知发布异常'}), 400