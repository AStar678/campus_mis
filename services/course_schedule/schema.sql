-- Course Scheduling Service tables.
-- These tables are owned by services/course_schedule and use the cs_ prefix.

CREATE TABLE IF NOT EXISTS cs_courses (
    course_id VARCHAR(20) PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    teacher_id VARCHAR(20),
    capacity INT NOT NULL DEFAULT 40,
    hours_per_week INT NOT NULL DEFAULT 2,
    preferred_building VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cs_course_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    course_id VARCHAR(20) NOT NULL,
    preference_level INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'submitted',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cs_request_student_course (student_id, course_id),
    INDEX idx_cs_request_student (student_id),
    INDEX idx_cs_request_course (course_id),
    CONSTRAINT fk_cs_request_course
        FOREIGN KEY (course_id) REFERENCES cs_courses(course_id)
        ON DELETE CASCADE
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
    classroom_id VARCHAR(4) NOT NULL,
    slot_id INT NOT NULL,
    enrolled_count INT NOT NULL DEFAULT 0,
    score FLOAT NOT NULL DEFAULT 0,
    reason VARCHAR(500),
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cs_result_course (course_id),
    INDEX idx_cs_result_run (run_id),
    CONSTRAINT fk_cs_result_run
        FOREIGN KEY (run_id) REFERENCES cs_schedule_runs(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_cs_result_course
        FOREIGN KEY (course_id) REFERENCES cs_courses(course_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_cs_result_slot
        FOREIGN KEY (slot_id) REFERENCES cs_time_slots(slot_id)
);
