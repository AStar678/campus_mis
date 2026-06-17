-- ============================================================
-- 校园MIS 模拟选课数据
-- 数据库：course_schedule_database
-- 说明：创建 8 门与课堂教学同名的课程 + 教学班 + 30 名学生选课记录
-- ============================================================

USE course_schedule_database;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- 清空旧数据
DELETE FROM cs_schedule_results;
DELETE FROM cs_course_requests;
DELETE FROM cs_schedule_runs;
DELETE FROM cs_course_sections;
DELETE FROM cs_courses;
ALTER TABLE cs_schedule_results AUTO_INCREMENT = 1;
ALTER TABLE cs_course_requests AUTO_INCREMENT = 1;

-- ── 8 门课程（课程名需与 classroom_database.courses.name 完全一致才能同步）──
INSERT INTO cs_courses (course_id, course_name, teacher_id, capacity, credits, hours_per_week, preferred_building, allowed_majors, allowed_grades, prerequisite_note, status, created_at) VALUES
('S001', '人工智能导论',           '1013', 40, 2, 2, '思源楼',       'all', 'all', '无', 'open', NOW()),
('S002', '深度学习',               '1013', 35, 2, 2, '软件工程实验楼', 'all', 'all', '人工智能导论', 'open', NOW()),
('S003', '软件工程',               '1008', 45, 2, 2, '软件工程实验楼', 'all', 'all', '无', 'open', NOW()),
('S004', '数据结构与算法',         '1016', 40, 2, 2, '1号楼',        'all', 'all', '程序设计基础', 'open', NOW()),
('S005', '计算机网络',             '1012', 40, 2, 2, '1号楼',        'all', 'all', '无', 'open', NOW()),
('S006', 'Python程序设计实训',     '1015', 40, 2, 2, '软件工程实验楼', 'all', 'all', '无', 'open', NOW()),
('S007', 'Web前端开发',            '1006', 40, 2, 2, '软件工程实验楼', 'all', 'all', '无', 'open', NOW()),
('S008', 'Java高级编程',           '1007', 40, 2, 2, '软件工程实验楼', 'all', 'all', 'Python程序设计实训', 'open', NOW());

-- ── 教学班（每门课 1 个班）──
INSERT INTO cs_course_sections (section_id, course_id, section_name, teacher_id, capacity, preferred_building, required_room_type, unavailable_slot_ids, status, created_at) VALUES
('S001-01', 'S001', '人工智能导论 A班', '1013', 40, '思源楼',       '普通教室', '', 'open', NOW()),
('S002-01', 'S002', '深度学习 A班',     '1013', 35, '软件工程实验楼', '普通教室', '', 'open', NOW()),
('S003-01', 'S003', '软件工程 A班',     '1008', 45, '软件工程实验楼', '普通教室', '', 'open', NOW()),
('S004-01', 'S004', '数据结构与算法 A班', '1016', 40, '1号楼',      '普通教室', '', 'open', NOW()),
('S005-01', 'S005', '计算机网络 A班',   '1012', 40, '1号楼',        '普通教室', '', 'open', NOW()),
('S006-01', 'S006', 'Python实训 A班',   '1015', 40, '软件工程实验楼', '机房',   '', 'open', NOW()),
('S007-01', 'S007', 'Web前端 A班',      '1006', 40, '软件工程实验楼', '机房',   '', 'open', NOW()),
('S008-01', 'S008', 'Java高级 A班',     '1007', 40, '软件工程实验楼', '机房',   '', 'open', NOW());

-- ── 学生选课（30人 × 2~4门课 ≈ 80条）──
-- 2024级 软件工程 学生（偏爱 Python / Web / Java / 软件工程）
INSERT INTO cs_course_requests (student_id, course_id, section_id, preference_level, status, created_at) VALUES
('20240002', 'S003', 'S003-01', 1, 'submitted', NOW()),
('20240002', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240002', 'S007', 'S007-01', 3, 'submitted', NOW()),
('20240002', 'S008', 'S008-01', 4, 'submitted', NOW()),
('20240003', 'S003', 'S003-01', 1, 'submitted', NOW()),
('20240003', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240003', 'S007', 'S007-01', 3, 'submitted', NOW()),
('20240004', 'S003', 'S003-01', 1, 'submitted', NOW()),
('20240004', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240004', 'S004', 'S004-01', 3, 'submitted', NOW()),
('20240005', 'S003', 'S003-01', 1, 'submitted', NOW()),
('20240005', 'S008', 'S008-01', 2, 'submitted', NOW()),
('20240010', 'S006', 'S006-01', 1, 'submitted', NOW()),
('20240010', 'S007', 'S007-01', 2, 'submitted', NOW()),
('20240010', 'S003', 'S003-01', 3, 'submitted', NOW()),
('20240015', 'S003', 'S003-01', 1, 'submitted', NOW()),
('20240015', 'S004', 'S004-01', 2, 'submitted', NOW()),
('20240015', 'S006', 'S006-01', 3, 'submitted', NOW()),
('20240020', 'S007', 'S007-01', 1, 'submitted', NOW()),
('20240020', 'S008', 'S008-01', 2, 'submitted', NOW()),
('20240020', 'S005', 'S005-01', 3, 'submitted', NOW()),
('20240025', 'S003', 'S003-01', 1, 'submitted', NOW()),
('20240025', 'S008', 'S008-01', 2, 'submitted', NOW());

-- 2024级 人工智能 学生（偏爱 人工智能 / 深度学习 / 数据结构 / Python）
INSERT INTO cs_course_requests (student_id, course_id, section_id, preference_level, status, created_at) VALUES
('20240006', 'S001', 'S001-01', 1, 'submitted', NOW()),
('20240006', 'S002', 'S002-01', 2, 'submitted', NOW()),
('20240006', 'S004', 'S004-01', 3, 'submitted', NOW()),
('20240011', 'S001', 'S001-01', 1, 'submitted', NOW()),
('20240011', 'S002', 'S002-01', 2, 'submitted', NOW()),
('20240011', 'S006', 'S006-01', 3, 'submitted', NOW()),
('20240016', 'S001', 'S001-01', 1, 'submitted', NOW()),
('20240016', 'S004', 'S004-01', 2, 'submitted', NOW()),
('20240021', 'S002', 'S002-01', 1, 'submitted', NOW()),
('20240021', 'S001', 'S001-01', 2, 'submitted', NOW()),
('20240026', 'S001', 'S001-01', 1, 'submitted', NOW()),
('20240026', 'S002', 'S002-01', 2, 'submitted', NOW()),
('20240026', 'S004', 'S004-01', 3, 'submitted', NOW());

-- 2024级 计算机科学 学生（偏爱 数据结构 / 网络 / 深度学习）
INSERT INTO cs_course_requests (student_id, course_id, section_id, preference_level, status, created_at) VALUES
('20240001', 'S004', 'S004-01', 1, 'submitted', NOW()),
('20240001', 'S005', 'S005-01', 2, 'submitted', NOW()),
('20240001', 'S002', 'S002-01', 3, 'submitted', NOW()),
('20240009', 'S004', 'S004-01', 1, 'submitted', NOW()),
('20240009', 'S005', 'S005-01', 2, 'submitted', NOW()),
('20240009', 'S001', 'S001-01', 3, 'submitted', NOW()),
('20240014', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240014', 'S004', 'S004-01', 2, 'submitted', NOW()),
('20240019', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240019', 'S004', 'S004-01', 2, 'submitted', NOW()),
('20240019', 'S006', 'S006-01', 3, 'submitted', NOW()),
('20240024', 'S004', 'S004-01', 1, 'submitted', NOW()),
('20240024', 'S002', 'S002-01', 2, 'submitted', NOW()),
('20240024', 'S005', 'S005-01', 3, 'submitted', NOW());

-- 2024级 信息安全 学生（偏爱 网络 / Python / Java）
INSERT INTO cs_course_requests (student_id, course_id, section_id, preference_level, status, created_at) VALUES
('20240007', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240007', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240012', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240012', 'S008', 'S008-01', 2, 'submitted', NOW()),
('20240012', 'S006', 'S006-01', 3, 'submitted', NOW()),
('20240017', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240017', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240022', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240022', 'S007', 'S007-01', 2, 'submitted', NOW()),
('20240027', 'S005', 'S005-01', 1, 'submitted', NOW()),
('20240027', 'S008', 'S008-01', 2, 'submitted', NOW()),
('20240027', 'S001', 'S001-01', 3, 'submitted', NOW());

-- 2024级 数据科学 学生（偏爱 Python / 人工智能 / Web）
INSERT INTO cs_course_requests (student_id, course_id, section_id, preference_level, status, created_at) VALUES
('20240008', 'S006', 'S006-01', 1, 'submitted', NOW()),
('20240008', 'S001', 'S001-01', 2, 'submitted', NOW()),
('20240013', 'S006', 'S006-01', 1, 'submitted', NOW()),
('20240013', 'S007', 'S007-01', 2, 'submitted', NOW()),
('20240013', 'S001', 'S001-01', 3, 'submitted', NOW()),
('20240018', 'S006', 'S006-01', 1, 'submitted', NOW()),
('20240018', 'S001', 'S001-01', 2, 'submitted', NOW()),
('20240023', 'S007', 'S007-01', 1, 'submitted', NOW()),
('20240023', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240028', 'S001', 'S001-01', 1, 'submitted', NOW()),
('20240028', 'S006', 'S006-01', 2, 'submitted', NOW()),
('20240028', 'S007', 'S007-01', 3, 'submitted', NOW());

-- 高年级少量选课
INSERT INTO cs_course_requests (student_id, course_id, section_id, preference_level, status, created_at) VALUES
('20230001', 'S002', 'S002-01', 1, 'submitted', NOW()),
('20230001', 'S003', 'S003-01', 2, 'submitted', NOW()),
('20230002', 'S001', 'S001-01', 1, 'submitted', NOW()),
('20230002', 'S002', 'S002-01', 2, 'submitted', NOW()),
('20230002', 'S003', 'S003-01', 3, 'submitted', NOW());

SET FOREIGN_KEY_CHECKS = 1;
