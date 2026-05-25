-- 校园教务管理MIS系统 数据库初始化脚本
-- 创建数据库
CREATE DATABASE IF NOT EXISTS campus_mis DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE campus_mis;

-- ============================================================
-- 用户表 (登录认证用)
-- ============================================================
DROP TABLE IF EXISTS teachings;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS teachers;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'teacher', 'admin') NOT NULL,
    ref_id VARCHAR(50) DEFAULT NULL COMMENT '关联学号或工号',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 学生表
-- ============================================================
CREATE TABLE students (
    student_id VARCHAR(50) PRIMARY KEY COMMENT '学号',
    name VARCHAR(100) NOT NULL COMMENT '姓名',
    gender ENUM('男','女') DEFAULT '男',
    college VARCHAR(100) COMMENT '学院',
    major VARCHAR(100) COMMENT '专业',
    class_name VARCHAR(100) COMMENT '班级',
    gpa DECIMAL(3,2) DEFAULT 0.00 COMMENT 'GPA',
    enrollment_year INT COMMENT '入学年份',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 教师表
-- ============================================================
CREATE TABLE teachers (
    teacher_id VARCHAR(50) PRIMARY KEY COMMENT '工号',
    name VARCHAR(100) NOT NULL COMMENT '姓名',
    college VARCHAR(100) COMMENT '学院',
    title VARCHAR(50) COMMENT '职称',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 课程表 (同一个课不同时间视为2个课)
-- ============================================================
CREATE TABLE courses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    course_id VARCHAR(50) NOT NULL COMMENT '课程号',
    name VARCHAR(200) NOT NULL COMMENT '课程名称',
    classroom VARCHAR(100) COMMENT '教室',
    schedule_time VARCHAR(100) COMMENT '上课时间',
    capacity INT DEFAULT 30 COMMENT '容量',
    credits DECIMAL(2,1) DEFAULT 2.0 COMMENT '学分',
    semester VARCHAR(50) COMMENT '学期',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 选课表
-- ============================================================
CREATE TABLE enrollments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    course_id INT NOT NULL,
    grade DECIMAL(5,2) DEFAULT NULL COMMENT '选课成绩',
    status ENUM('enrolled','dropped','completed') DEFAULT 'enrolled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 授课表
-- ============================================================
CREATE TABLE teachings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id VARCHAR(50) NOT NULL,
    course_id INT NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 初始测试数据
-- ============================================================

-- 默认管理员账号 (密码: admin123, 使用bcrypt加密)
INSERT INTO users (username, password_hash, role, ref_id) VALUES
('admin', '$2b$12$daC0zGIN9caYttvpEG0YauiX.ns1QQwOOsjDEjpoqGoKxd0bwQVBe', 'admin', NULL);

-- 测试学生数据
INSERT INTO students (student_id, name, gender, college, major, class_name, gpa, enrollment_year) VALUES
('2024001', '张三', '男', '计算机学院', '软件工程', '软工2401', 3.50, 2024),
('2024002', '李四', '女', '计算机学院', '计算机科学', '计科2401', 3.80, 2024),
('2024003', '王五', '男', '信息学院', '信息安全', '信安2401', 3.20, 2024);

-- 测试学生对应的登录账号 (密码: 123456)
INSERT INTO users (username, password_hash, role, ref_id) VALUES
('2024001', '$2b$12$o8.x/blrL8ozA3NVkE00VuhwmbkgMyytKL6x/dQ0lUMUhiiIZOxQq', 'student', '2024001'),
('2024002', '$2b$12$o8.x/blrL8ozA3NVkE00VuhwmbkgMyytKL6x/dQ0lUMUhiiIZOxQq', 'student', '2024002'),
('2024003', '$2b$12$o8.x/blrL8ozA3NVkE00VuhwmbkgMyytKL6x/dQ0lUMUhiiIZOxQq', 'student', '2024003');

-- 测试教师数据
INSERT INTO teachers (teacher_id, name, college, title) VALUES
('T001', '刘教授', '计算机学院', '教授'),
('T002', '陈副教授', '信息学院', '副教授');

-- 测试教师对应的登录账号 (密码: 123456)
INSERT INTO users (username, password_hash, role, ref_id) VALUES
('T001', '$2b$12$o8.x/blrL8ozA3NVkE00VuhwmbkgMyytKL6x/dQ0lUMUhiiIZOxQq', 'teacher', 'T001'),
('T002', '$2b$12$o8.x/blrL8ozA3NVkE00VuhwmbkgMyytKL6x/dQ0lUMUhiiIZOxQq', 'teacher', 'T002');

-- 测试课程数据
INSERT INTO courses (course_id, name, classroom, schedule_time, capacity, credits, semester) VALUES
('CS101', '数据库原理', 'A301', '周一 1-2节', 60, 3.0, '2025-2026-1'),
('CS102', '操作系统', 'B205', '周二 3-4节', 50, 3.5, '2025-2026-1'),
('CS103', 'Python程序设计', 'C102', '周三 5-6节', 45, 2.0, '2025-2026-1');

-- 授课关系
INSERT INTO teachings (teacher_id, course_id) VALUES
('T001', 1),
('T001', 2),
('T002', 3);
