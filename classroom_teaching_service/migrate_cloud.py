"""Migrate classroom_teaching_service to cloud MySQL database."""
import pymysql

DB_HOST = '47.93.226.110'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = ''

def run():
    # === 1. Add name to users_database ===
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database='users_database', charset='utf8mb4')
    cursor = conn.cursor()

    student_names = {
        '20230001': '赵一凡', '20230002': '钱思远',
        '20240001': '孙浩然', '20240002': '李文博', '20240003': '周星宇',
        '20240004': '吴雨桐', '20240005': '郑思琪', '20240006': '王子墨',
        '20240007': '冯晨曦', '20240008': '陈嘉禾', '20240009': '褚明轩',
        '20240010': '卫思齐', '20240011': '蒋雅琪', '20240012': '沈逸飞',
        '20240013': '韩梦琪', '20240014': '杨子涵', '20240015': '朱俊杰',
        '20240016': '秦雨萱', '20240017': '尤浩宇', '20240018': '许诗涵',
        '20240019': '何嘉瑞', '20240020': '吕天翔', '20240021': '施映月',
        '20240022': '张弘毅', '20240023': '孔令仪', '20240024': '曹睿泽',
        '20240025': '严子轩', '20240026': '华思远', '20240027': '金明哲',
        '20240028': '魏书瑶', '20240029': '陶乐天', '20240030': '姜逸辰',
        '20240031': '戚诗韵', '20240032': '谢天赐', '20240033': '邹雅晴',
        '20240034': '喻子琪', '20240035': '柏晨阳', '20240036': '水若兰',
        '20240037': '窦翊凡', '20240038': '章睿轩', '20240039': '云舒婉',
        '20240040': '苏清扬',
        '20250001': '潘悦来', '20250002': '葛知远', '20250003': '奚星澜',
        '20250004': '范语嫣', '20250005': '彭鹤轩', '20250006': '郎诗云',
        '20250007': '鲁启航', '20250008': '韦皓月', '20250009': '昌瑞祺',
        '20250010': '马思源', '20250011': '苗雅楠', '20250012': '凤朝阳',
        '20250013': '花映雪', '20250014': '方逸群', '20250015': '俞书翰',
        '20250016': '任梓涵', '20250017': '袁嘉柏', '20250018': '柳若溪',
        '20250019': '酆乐安', '20250020': '鲍思齐',
    }
    for sid, name in student_names.items():
        cursor.execute('UPDATE students SET name=%s WHERE student_id=%s AND name IS NULL', (name, sid))

    teacher_names = {
        '1001': '陆思阳', '1002': '王靖', '1003': '欧小宇',
        '1004': '林清华', '1005': '张明德', '1006': '刘雪梅',
        '1007': '赵建国', '1008': '孙丽华', '1009': '周文杰',
        '1010': '吴秀英', '1011': '郑伟民', '1012': '王海燕',
        '1013': '冯志强', '1014': '陈玉兰', '1015': '褚国庆',
        '1016': '卫红梅',
    }
    for tid, name in teacher_names.items():
        cursor.execute('UPDATE teachers SET name=%s WHERE teacher_id=%s AND name IS NULL', (name, tid))
    conn.commit()
    print("[OK] users_database: names populated")
    conn.close()

    # === 2. Alter classroom_database tables ===
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database='classroom_database', charset='utf8mb4')
    cursor = conn.cursor()

    # Add columns to courses
    course_cols = [
        ("code", "VARCHAR(32) DEFAULT '' COMMENT '课程编号'"),
        ("class_time", "VARCHAR(120) DEFAULT '' COMMENT '上课时间'"),
        ("location", "VARCHAR(120) DEFAULT '' COMMENT '教室位置'"),
        ("credits", "FLOAT DEFAULT 2.0 COMMENT '学分'"),
        ("language", "VARCHAR(20) DEFAULT '中文' COMMENT '授课语言'"),
        ("course_type", "VARCHAR(20) DEFAULT '必修' COMMENT '课程类型'"),
        ("teaching_method", "VARCHAR(40) DEFAULT '线下' COMMENT '教学方式'"),
        ("target_grade", "VARCHAR(16) DEFAULT '' COMMENT '目标年级'"),
        ("target_major", "VARCHAR(64) DEFAULT '' COMMENT '目标专业'"),
        ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
    ]
    cursor.execute("SHOW COLUMNS FROM courses")
    existing_cols = {r[0] for r in cursor.fetchall()}
    for col_name, col_def in course_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE courses ADD COLUMN {col_name} {col_def}")
            print(f"  courses: added {col_name}")

    # Add columns to announcements
    cursor.execute("SHOW COLUMNS FROM announcements")
    existing_cols = {r[0] for r in cursor.fetchall()}
    if 'created_by' not in existing_cols:
        cursor.execute("ALTER TABLE announcements ADD COLUMN created_by VARCHAR(32) DEFAULT '' COMMENT '发布者ID'")
        print("  announcements: added created_by")

    # Add columns to homeworks (as assignments)
    cursor.execute("SHOW COLUMNS FROM homeworks")
    existing_cols = {r[0] for r in cursor.fetchall()}
    hw_cols = [
        ("answer_pdf", "VARCHAR(255) DEFAULT '' COMMENT '参考答案PDF路径'"),
        ("answer_text", "TEXT COMMENT '参考答案文本'"),
        ("total_score", "FLOAT DEFAULT 100 COMMENT '满分'"),
        ("created_by", "VARCHAR(32) DEFAULT '' COMMENT '创建者ID'"),
        ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
    ]
    for col_name, col_def in hw_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE homeworks ADD COLUMN {col_name} {col_def}")
            print(f"  homeworks: added {col_name}")

    # Add columns to submissions
    cursor.execute("SHOW COLUMNS FROM submissions")
    existing_cols = {r[0] for r in cursor.fetchall()}
    sub_cols = [
        ("pdf_path", "VARCHAR(255) DEFAULT '' COMMENT '学生提交PDF路径'"),
        ("extracted_text", "TEXT COMMENT '提取的文本'"),
        ("ai_detail", "TEXT COMMENT 'AI评分明细JSON'"),
        ("ai_feedback", "TEXT COMMENT 'AI反馈'"),
        ("teacher_score", "FLOAT DEFAULT NULL COMMENT '教师评分'"),
        ("teacher_feedback", "TEXT COMMENT '教师反馈'"),
        ("review_status", "VARCHAR(20) DEFAULT '待复核' COMMENT '复核状态'"),
    ]
    for col_name, col_def in sub_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE submissions ADD COLUMN {col_name} {col_def}")
            print(f"  submissions: added {col_name}")

    # Create grades table
    cursor.execute("SHOW TABLES LIKE 'grades'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE grades (
                id INT NOT NULL AUTO_INCREMENT,
                course_id INT NOT NULL,
                student_id VARCHAR(8) NOT NULL COMMENT '学号',
                source_type VARCHAR(32) DEFAULT 'course' COMMENT '来源类型',
                source_id INT DEFAULT NULL COMMENT '来源ID',
                score FLOAT NOT NULL,
                comment VARCHAR(255) DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_grades_course (course_id),
                KEY idx_grades_student (student_id),
                CONSTRAINT fk_grades_course FOREIGN KEY (course_id) REFERENCES courses(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='成绩明细表'
        """)
        print("  Created table: grades")

    # Create ddl_items table
    cursor.execute("SHOW TABLES LIKE 'ddl_items'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE ddl_items (
                id INT NOT NULL AUTO_INCREMENT,
                course_id INT DEFAULT NULL,
                owner_id VARCHAR(32) NOT NULL,
                owner_role VARCHAR(16) NOT NULL,
                title VARCHAR(160) NOT NULL,
                due_at DATETIME NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                PRIMARY KEY (id),
                KEY idx_ddl_owner (owner_id, owner_role)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='DDL待办事项'
        """)
        print("  Created table: ddl_items")

    conn.commit()
    print("[OK] classroom_database: schema updated")
    conn.close()

    # Generate course codes for existing courses
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database='classroom_database', charset='utf8mb4')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM courses WHERE code IS NULL OR code = ''")
    rows = cursor.fetchall()
    for cid, cname in rows:
        code = f"CLS{cid:03d}"
        cursor.execute("UPDATE courses SET code=%s WHERE id=%s", (code, cid))
    conn.commit()
    print(f"[OK] Generated course codes for {len(rows)} courses")
    conn.close()


if __name__ == '__main__':
    run()
    print("\n=== Migration complete! ===")
