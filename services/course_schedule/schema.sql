-- 选课与智能排课分服务业务表。
-- 本服务独立维护 course_schedule_database，公共教室、楼栋和楼栋距离数据从 main_database 只读获取。

CREATE DATABASE IF NOT EXISTS course_schedule_database
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE course_schedule_database;

CREATE TABLE IF NOT EXISTS cs_courses (
    course_id VARCHAR(20) PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    teacher_id VARCHAR(20),
    capacity INT NOT NULL DEFAULT 40,
    credits DECIMAL(4,1) NOT NULL DEFAULT 2.0,
    hours_per_week INT NOT NULL DEFAULT 2,
    preferred_building VARCHAR(50),
    allowed_majors VARCHAR(200) NOT NULL DEFAULT 'all',
    allowed_grades VARCHAR(100) NOT NULL DEFAULT 'all',
    prerequisite_note VARCHAR(300) NOT NULL DEFAULT '无',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cs_selection_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    term_name VARCHAR(80) NOT NULL DEFAULT '2025-2026 学年第二学期',
    phase VARCHAR(30) NOT NULL DEFAULT 'selecting',
    phase_label VARCHAR(50) NOT NULL DEFAULT '正式选课阶段',
    start_at DATETIME,
    end_at DATETIME,
    max_preferences INT NOT NULL DEFAULT 3,
    min_credits DECIMAL(4,1) NOT NULL DEFAULT 2.0,
    max_credits DECIMAL(4,1) NOT NULL DEFAULT 8.0,
    notice VARCHAR(300) NOT NULL DEFAULT '排课结果以管理员发布为准。',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cs_course_sections (
    section_id VARCHAR(30) PRIMARY KEY,
    course_id VARCHAR(20) NOT NULL,
    section_name VARCHAR(100) NOT NULL,
    teacher_id VARCHAR(20),
    capacity INT NOT NULL DEFAULT 40,
    preferred_building VARCHAR(50),
    required_room_type VARCHAR(30) NOT NULL DEFAULT '普通教室',
    unavailable_slot_ids VARCHAR(200) NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cs_section_course (course_id),
    CONSTRAINT fk_cs_section_course
        FOREIGN KEY (course_id) REFERENCES cs_courses(course_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cs_course_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    course_id VARCHAR(20) NOT NULL,
    section_id VARCHAR(30),
    preference_level INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cs_request_student_course (student_id, course_id),
    INDEX idx_cs_request_student (student_id),
    INDEX idx_cs_request_course (course_id),
    INDEX idx_cs_request_section (section_id),
    CONSTRAINT fk_cs_request_course
        FOREIGN KEY (course_id) REFERENCES cs_courses(course_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_cs_request_section
        FOREIGN KEY (section_id) REFERENCES cs_course_sections(section_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS cs_time_slots (
    slot_id INT AUTO_INCREMENT PRIMARY KEY,
    weekday INT NOT NULL,
    start_time VARCHAR(5) NOT NULL,
    end_time VARCHAR(5) NOT NULL,
    label VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS cs_schedule_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_by VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    summary VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cs_schedule_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    course_id VARCHAR(20) NOT NULL,
    section_id VARCHAR(30),
    classroom_id VARCHAR(4) NOT NULL,
    slot_id INT NOT NULL,
    enrolled_count INT NOT NULL DEFAULT 0,
    score FLOAT NOT NULL DEFAULT 0,
    reason VARCHAR(500),
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cs_result_course (course_id),
    INDEX idx_cs_result_section (section_id),
    INDEX idx_cs_result_run (run_id),
    CONSTRAINT fk_cs_result_run
        FOREIGN KEY (run_id) REFERENCES cs_schedule_runs(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_cs_result_course
        FOREIGN KEY (course_id) REFERENCES cs_courses(course_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_cs_result_section
        FOREIGN KEY (section_id) REFERENCES cs_course_sections(section_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_cs_result_slot
        FOREIGN KEY (slot_id) REFERENCES cs_time_slots(slot_id)
);
