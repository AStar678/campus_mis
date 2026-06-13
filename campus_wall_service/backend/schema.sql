CREATE DATABASE IF NOT EXISTS campus_wall_database
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE campus_wall_database;

CREATE TABLE IF NOT EXISTS wall_posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_id VARCHAR(20) NOT NULL,
    author_type VARCHAR(10) NOT NULL,
    title VARCHAR(100),
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    risk_level VARCHAR(20) NOT NULL DEFAULT 'normal',
    matched_keywords VARCHAR(255),
    image_paths TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_by VARCHAR(20),
    deleted_at DATETIME,
    delete_reason VARCHAR(255),
    INDEX idx_wall_posts_status_created (status, created_at),
    INDEX idx_wall_posts_author (author_type, author_id),
    INDEX idx_wall_posts_risk_level (risk_level)
) COMMENT='校园墙帖子';

CREATE TABLE IF NOT EXISTS wall_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT,
    alert_type VARCHAR(30) NOT NULL DEFAULT 'post_keyword',
    alert_level VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    keywords VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    handled_by VARCHAR(20),
    handled_at DATETIME,
    INDEX idx_wall_alerts_status_created (status, created_at),
    INDEX idx_wall_alerts_level (alert_level),
    CONSTRAINT fk_wall_alert_post
        FOREIGN KEY (post_id) REFERENCES wall_posts(id)
        ON DELETE SET NULL
) COMMENT='校园墙舆情告警';

CREATE TABLE IF NOT EXISTS wall_moderation_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    admin_id VARCHAR(20) NOT NULL,
    action VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_wall_moderation_post (post_id),
    INDEX idx_wall_moderation_admin (admin_id),
    CONSTRAINT fk_wall_moderation_post
        FOREIGN KEY (post_id) REFERENCES wall_posts(id)
        ON DELETE CASCADE
) COMMENT='校园墙管理操作日志';
