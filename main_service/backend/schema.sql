-- ============================================
-- 校园MIS系统 - 主服务数据库建表SQL
-- 数据库名: campus_mis
-- ============================================

-- 创建数据库
DROP DATABASE IF EXISTS campus_mis;
CREATE DATABASE campus_mis DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE campus_mis;

-- ----------------------------
-- 学生基本信息表
-- ----------------------------
CREATE TABLE students (
    student_id VARCHAR(8) PRIMARY KEY COMMENT '学号（8位）',
    password VARCHAR(128) NOT NULL COMMENT '登录密码（SHA256哈希）',
    grade VARCHAR(10) COMMENT '年级',
    major VARCHAR(50) COMMENT '专业'
) COMMENT='学生基本信息';

-- ----------------------------
-- 教师基本信息表
-- ----------------------------
CREATE TABLE teachers (
    teacher_id VARCHAR(4) PRIMARY KEY COMMENT '工号（4位）',
    password VARCHAR(128) NOT NULL COMMENT '登录密码（SHA256哈希）',
    college VARCHAR(50) COMMENT '学院',
    title VARCHAR(20) COMMENT '职称'
) COMMENT='教师基本信息';

-- ----------------------------
-- 管理员信息表
-- ----------------------------
CREATE TABLE admins (
    admin_id VARCHAR(20) PRIMARY KEY COMMENT '管理员账号',
    password VARCHAR(128) NOT NULL COMMENT '登录密码（SHA256哈希）',
    name VARCHAR(50) COMMENT '管理员姓名'
) COMMENT='管理员信息';

-- ----------------------------
-- 当前登录用户（会话表）
-- ----------------------------
CREATE TABLE active_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL COMMENT '用户ID（学号或工号）',
    user_type VARCHAR(10) NOT NULL COMMENT '用户类型：student/teacher/admin',
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
    token VARCHAR(500) NOT NULL COMMENT 'JWT Token'
) COMMENT='当前登录用户会话';

-- ----------------------------
-- 教室信息表
-- ----------------------------
CREATE TABLE classrooms (
    classroom_id VARCHAR(4) PRIMARY KEY COMMENT '教室编号（4位）',
    building VARCHAR(50) COMMENT '所在楼栋'
) COMMENT='教室信息';

-- ----------------------------
-- 建筑信息表
-- ----------------------------
CREATE TABLE buildings (
    building_id INT AUTO_INCREMENT PRIMARY KEY,
    building_name VARCHAR(50) NOT NULL COMMENT '建筑名称'
) COMMENT='校园建筑信息';

-- ----------------------------
-- 建筑邻接表（存储建筑间距离）
-- ----------------------------
CREATE TABLE building_adjacency (
    id INT AUTO_INCREMENT PRIMARY KEY,
    building_a INT NOT NULL COMMENT '建筑A',
    building_b INT NOT NULL COMMENT '建筑B',
    distance FLOAT NOT NULL COMMENT '两建筑间距离（米）',
    FOREIGN KEY (building_a) REFERENCES buildings(building_id),
    FOREIGN KEY (building_b) REFERENCES buildings(building_id)
) COMMENT='建筑间距离邻接表';

-- ----------------------------
-- 分服务信息表（微服务端口管理）
-- ----------------------------
CREATE TABLE sub_services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_name VARCHAR(50) COMMENT '服务名称',
    service_ip VARCHAR(50) COMMENT '服务IP地址',
    service_port INT COMMENT '服务端口号',
    description VARCHAR(200) COMMENT '服务描述'
) COMMENT='分服务注册信息（微服务端口管理）';

-- ============================================
-- 插入测试数据
-- ============================================

-- 学生测试数据（密码: 123456 -> SHA256）
INSERT INTO students (student_id, password, grade, major) VALUES
('20240001', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '2024', '计算机科学'),
('20240002', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '2024', '软件工程');

-- 教师测试数据（密码: 123456 -> SHA256）
INSERT INTO teachers (teacher_id, password, college, title) VALUES
('1001', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '计算机学院', '教授'),
('1002', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '计算机学院', '副教授');

-- 管理员测试数据（密码: admin123 -> SHA256）
INSERT INTO admins (admin_id, password, name) VALUES
('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '系统管理员');

-- 教室数据
INSERT INTO classrooms (classroom_id, building) VALUES
('A101', '1号楼'),
('A201', '1号楼'),
('B101', '2号楼');

-- 建筑数据
INSERT INTO buildings (building_name) VALUES
('1号楼'),
('2号楼'),
('图书馆'),
('食堂'),
('体育馆');

-- 建筑间距离（邻接表）
INSERT INTO building_adjacency (building_a, building_b, distance) VALUES
(1, 2, 200.0),   -- 1号楼 <-> 2号楼: 200米
(1, 3, 350.0),   -- 1号楼 <-> 图书馆: 350米
(2, 3, 250.0),   -- 2号楼 <-> 图书馆: 250米
(1, 4, 400.0),   -- 1号楼 <-> 食堂: 400米
(2, 4, 300.0),   -- 2号楼 <-> 食堂: 300米
(3, 4, 150.0),   -- 图书馆 <-> 食堂: 150米
(4, 5, 200.0),   -- 食堂 <-> 体育馆: 200米
(3, 5, 500.0);   -- 图书馆 <-> 体育馆: 500米

-- 分服务注册数据（微服务端口管理）
INSERT INTO sub_services (service_name, service_ip, service_port, description) VALUES
('教务服务', '127.0.0.1', 5002, '课程管理、成绩管理、学分计算'),
('课堂服务', '127.0.0.1', 5003, '作业发布、课堂公告、AI批改'),
('选课排课服务', '127.0.0.1', 5004, '学生选课、智能排课'),
('校园墙服务', '127.0.0.1', 5005, '校园社交、动态发布');
