-- API Request Logs для debugging OpenAI запросов
-- Позволяет воспроизвести любой запрос через curl

CREATE TABLE IF NOT EXISTS api_request_logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    persona VARCHAR(20), -- 'admin' or 'oracle'
    operation VARCHAR(50), -- 'create_thread', 'add_message', 'create_run', 'get_messages', etc
    curl_command TEXT NOT NULL,
    response_status INTEGER, -- HTTP status code
    response_time_ms INTEGER, -- Response time in milliseconds
    error_message TEXT,
    metadata JSONB -- Additional context (thread_id, run_id, etc)
);

-- Index for quick lookups
CREATE INDEX idx_api_logs_created_at ON api_request_logs(created_at DESC);
CREATE INDEX idx_api_logs_user_id ON api_request_logs(user_id);
CREATE INDEX idx_api_logs_operation ON api_request_logs(operation);

-- Cleanup old logs (keep last 7 days)
-- Run this manually or via cron: DELETE FROM api_request_logs WHERE created_at < NOW() - INTERVAL '7 days';
