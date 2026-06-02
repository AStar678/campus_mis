import os
import random
from datetime import datetime, timedelta
from flask import Flask
from sqlalchemy import text

# 从你的项目中直接引入 db 和模型，确保元数据上下文一致
from extensions import db
from models import Course, CourseStudent, Announcement, Homework, Submission

# ============ 数据库基础配置 ============
DB_HOST = os.environ.get('DB_HOST', '47.93.226.110')
DB_PORT = int(os.environ.get('DB_PORT', 3306))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', '')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/classroom_database'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化关联
db.init_app(app)

def inject_massive_data():
    with app.app_context():
        print("正在重建数据库表结构 (以应用新增的 final_grade 字段)...")
        
        # 核心修复：直接删除旧表并重新建表，同步最新的表结构
        db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0;'))
        db.drop_all()
        db.create_all()
        db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1;'))
        db.session.commit()

        now = datetime.now()
        
        # 1. 创建课程
        print("1/4 正在生成核心课程...")
        courses_data = [
            Course(name='长时序列预测 (LTSF) 进阶模型', teacher_id='1001', description='主讲教授 Siyang Lu。重点剖析 TimesL, HDMixer 以及 DeepMA 自适应框架的设计哲学与底层算子实现。'),
            Course(name='情感脑机接口 (Affective BCI) 导论', teacher_id='1002', description='主讲教授 Jing Wang。涵盖基于 EEG/fNIRS 双模态的特征对齐、导联场矩阵运算及 PRIM (Prior-guided Mamba) 应用。'),
            Course(name='数字图像安全与暗场水印', teacher_id='1003', description='主讲教授 Xiaoyu Ou。探索高频 DCT/DWT 隐形水印技术、通用水印检测网络 (UWPD) 及 AI 投毒攻防体系。')
        ]
        db.session.add_all(courses_data)
        db.session.flush()

        # 2. 生成大批量学生
        print("2/4 正在为每门课程导入大规模学生名册 (约 120 名并发选课记录)...")
        student_ids = [f'2024{str(i).zfill(4)}' for i in range(1, 41)] 
        
        for course in courses_data:
            for sid in student_ids:
                # 随机分配一些已有的期末成绩，模拟期末收尾状态
                final_grade = round(random.uniform(75.0, 98.0), 1) if random.random() > 0.8 else None
                db.session.add(CourseStudent(course_id=course.id, student_id=sid, final_grade=final_grade))
        db.session.flush()

        # 3. 分配作业与 DDL 任务列阵
        print("3/4 正在下发各阶段实验及 DDL 任务...")
        homeworks_data = []
        for course in courses_data:
            for hw_idx in range(1, 4): 
                hw = Homework(
                    course_id=course.id,
                    title=f'核心实验 Lab {hw_idx}',
                    description=f'请基于 Overleaf 撰写实验报告，代码部分需推送至 GitHub，云端服务器运算请防范 OOM。',
                    deadline=now + timedelta(days=random.randint(-5, 15)) 
                )
                homeworks_data.append(hw)
        db.session.add_all(homeworks_data)
        db.session.flush()

        # 4. 模拟海量高维提交记录与 AI 预批改反馈
        print("4/4 正在高频注入全量学生的作业提交流水 (预计产生近 300 条记录)...")
        submissions_data = []
        
        # 针对不同课程的 AI 拟态回复库
        ai_responses = {
            'LTSF': ["降序排列比对规范", "ViewEmbed 视角重构完整", "堆叠滑动平均模块计算逻辑严密"],
            'BCI': ["MNE-Python 预处理流程完善", "通道映射 (Lead-field) 计算正确", "PRIM 空间拓扑结构无误"],
            'Watermark': ["LSB 与频域隐写结合巧妙", "UWPD 检出率达标", "FSNet 对比实验详实"]
        }

        for hw in homeworks_data:
            course_domain = 'LTSF' if hw.course_id == courses_data[0].id else ('BCI' if hw.course_id == courses_data[1].id else 'Watermark')
            
            for sid in student_ids:
                # 模拟 90% 的提交率
                if random.random() < 0.9:
                    ai_score = round(random.uniform(60.0, 95.0), 1)
                    
                    # 模拟教师复核的比例 (大约30%的作业教师已经改过了，覆盖了 AI 成绩)
                    final_score = round(ai_score + random.uniform(-5, 5), 1) if random.random() < 0.3 else None
                    
                    comment = f"【AI代码审查完毕】: {random.choice(ai_responses[course_domain])}。时空复杂度评估为合格水平。"

                    submissions_data.append(Submission(
                        homework_id=hw.id,
                        student_id=sid,
                        content=f"# 提交者: {sid}\nimport torch\n# 模型初始化代码... \n# 实验结果已附至 PDF 附件。",
                        submit_time=now - timedelta(days=random.randint(0, 10)),
                        ai_score=ai_score,
                        ai_comment=comment,
                        final_score=final_score
                    ))

        # 采用批量分片提交防内存溢出
        batch_size = 100
        for i in range(0, len(submissions_data), batch_size):
            db.session.add_all(submissions_data[i:i+batch_size])
            db.session.flush()

        db.session.commit()
        print(f"\n🎉 场景构建完成！成功注入了 {len(courses_data)} 门高阶课程、{len(student_ids)} 名学生及 {len(submissions_data)} 份作业批改流水。")

if __name__ == '__main__':
    inject_massive_data()