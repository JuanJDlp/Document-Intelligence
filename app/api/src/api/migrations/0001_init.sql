CREATE TABLE IF NOT EXISTS users (
 id CHAR(36) NOT NULL PRIMARY KEY,
 email VARCHAR(254) NOT NULL,
 password_hash VARCHAR(255) NOT NULL,
 full_name VARCHAR(200) NOT NULL,
 role ENUM('user','admin') NOT NULL DEFAULT 'user',
 created_at DATETIME(6) NOT NULL,
 updated_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_users_email (email),
 KEY ix_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
CREATE TABLE IF NOT EXISTS sessions (
 id CHAR(36) NOT NULL PRIMARY KEY,
 user_id CHAR(36) NOT NULL,
 token_hash CHAR(64) NOT NULL,
 created_at DATETIME(6) NOT NULL,
 expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6) NULL,
 UNIQUE KEY uq_sessions_token_hash (token_hash),
 KEY ix_sessions_user_id (user_id),
 KEY ix_sessions_expires_at (expires_at),
 CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
