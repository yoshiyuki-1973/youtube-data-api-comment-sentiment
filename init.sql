-- YouTube Analytics Database Initialization

CREATE DATABASE IF NOT EXISTS youtube_analytics;
USE youtube_analytics;

-- videos table
CREATE TABLE IF NOT EXISTS videos (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_id VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    channel_id VARCHAR(30) NOT NULL,
    channel_title VARCHAR(255),
    published_at DATETIME,
    view_count BIGINT DEFAULT 0,
    like_count BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    fetched_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_video_id (video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- video_comment_summary table
CREATE TABLE IF NOT EXISTS video_comment_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_id VARCHAR(20) NOT NULL,
    total_comments INT DEFAULT 0,
    positive_count INT DEFAULT 0,
    negative_count INT DEFAULT 0,
    other_count INT DEFAULT 0,
    positive_ratio DECIMAL(5,4),
    negative_ratio DECIMAL(5,4),
    analyzed_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_video_id (video_id),
    FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
