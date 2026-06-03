-- Campus MIS main service schema.
-- The application uses two databases:
--   users_database: students, teachers, admins
--   main_database: sessions, campus resources, teaching system data

CREATE DATABASE IF NOT EXISTS users_database DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE DATABASE IF NOT EXISTS main_database DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE users_database;

CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(8) PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    grade VARCHAR(10),
    major VARCHAR(50)
) COMMENT='学生基本信息';

CREATE TABLE IF NOT EXISTS teachers (
    teacher_id VARCHAR(4) PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    college VARCHAR(50),
    title VARCHAR(20)
) COMMENT='教师基本信息';

CREATE TABLE IF NOT EXISTS admins (
    admin_id VARCHAR(20) PRIMARY KEY,
    password VARCHAR(128) NOT NULL,
    name VARCHAR(50)
) COMMENT='管理员信息';

INSERT IGNORE INTO students (student_id, password, grade, major) VALUES
('20240001', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '2024', '计算机科学'),
('20240002', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '2024', '软件工程');

INSERT IGNORE INTO teachers (teacher_id, password, college, title) VALUES
('1001', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '计算机学院', '教授'),
('1002', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '计算机学院', '副教授');

INSERT IGNORE INTO admins (admin_id, password, name) VALUES
('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '系统管理员');

USE main_database;

CREATE TABLE IF NOT EXISTS active_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    user_type VARCHAR(10) NOT NULL,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    token VARCHAR(500) NOT NULL
) COMMENT='当前登录用户会话';

CREATE TABLE IF NOT EXISTS classrooms (
    classroom_id VARCHAR(4) PRIMARY KEY,
    building VARCHAR(50)
) COMMENT='教室信息';

CREATE TABLE IF NOT EXISTS buildings (
    building_id INT AUTO_INCREMENT PRIMARY KEY,
    building_name VARCHAR(50) NOT NULL
) COMMENT='校园建筑信息';

CREATE TABLE IF NOT EXISTS building_adjacency (
    id INT AUTO_INCREMENT PRIMARY KEY,
    building_a INT NOT NULL,
    building_b INT NOT NULL,
    distance FLOAT NOT NULL,
    FOREIGN KEY (building_a) REFERENCES buildings(building_id),
    FOREIGN KEY (building_b) REFERENCES buildings(building_id)
) COMMENT='建筑间距离邻接表';

CREATE TABLE IF NOT EXISTS sub_services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_name VARCHAR(50),
    service_ip VARCHAR(50),
    service_port INT,
    description VARCHAR(200)
) COMMENT='分服务注册信息';

CREATE TABLE IF NOT EXISTS courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    teacher_id VARCHAR(4),
    target_grade VARCHAR(10),
    target_major VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) COMMENT='课程信息';

CREATE TABLE IF NOT EXISTS course_enrollments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    student_id VARCHAR(8) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_course_student (course_id, student_id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
) COMMENT='学生课程关联';

CREATE TABLE IF NOT EXISTS assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    content TEXT,
    due_at DATETIME,
    created_by VARCHAR(4) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id)
) COMMENT='课堂作业';

CREATE TABLE IF NOT EXISTS assignment_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    student_id VARCHAR(8) NOT NULL,
    content TEXT NOT NULL,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ai_score FLOAT,
    ai_feedback TEXT,
    teacher_score FLOAT,
    teacher_feedback TEXT,
    UNIQUE KEY uq_assignment_student (assignment_id, student_id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id)
) COMMENT='作业提交与批改';

CREATE TABLE IF NOT EXISTS classroom_announcements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    title VARCHAR(120) NOT NULL,
    content TEXT NOT NULL,
    created_by VARCHAR(4) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id)
) COMMENT='课堂公告';

CREATE TABLE IF NOT EXISTS course_grades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT NOT NULL,
    student_id VARCHAR(8) NOT NULL,
    score FLOAT NOT NULL,
    comment VARCHAR(255),
    updated_by VARCHAR(4) NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_course_grade_student (course_id, student_id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
) COMMENT='课程成绩';

CREATE TABLE IF NOT EXISTS ddl_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT,
    owner_id VARCHAR(20) NOT NULL,
    owner_type VARCHAR(10) NOT NULL,
    title VARCHAR(120) NOT NULL,
    due_at DATETIME NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id)
) COMMENT='DDL管理子系统预留表';

INSERT IGNORE INTO classrooms (classroom_id, building) VALUES
('A101', '1号楼'),
('A201', '1号楼'),
('B101', '2号楼');

INSERT INTO sub_services (service_name, service_ip, service_port, description)
SELECT '课堂教学服务', '127.0.0.1', 5003, '作业发布、课堂公告、AI批改'
WHERE NOT EXISTS (SELECT 1 FROM sub_services WHERE service_port = 5003);
