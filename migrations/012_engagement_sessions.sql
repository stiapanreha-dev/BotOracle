-- Migration 012: Engagement Sessions for Conversion Funnel
-- Tracks user engagement after daily messages to optimize subscription conversion

-- Create engagement_sessions table
CREATE TABLE IF NOT EXISTS engagement_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'engaging',
    messages_count INTEGER DEFAULT 0,
    problem_summary TEXT,
    suggested_question TEXT,
    offered_at TIMESTAMP,
    converted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('engaging', 'collecting', 'offered', 'paused', 'converted'))
);

-- Create session_messages table
CREATE TABLE IF NOT EXISTS session_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES engagement_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_role CHECK (role IN ('user', 'admin'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_engagement_sessions_user_id ON engagement_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_engagement_sessions_status ON engagement_sessions(status);
CREATE INDEX IF NOT EXISTS idx_engagement_sessions_started_at ON engagement_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_session_messages_session_id ON session_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_session_messages_created_at ON session_messages(created_at);

-- Composite index for active sessions lookup
CREATE INDEX IF NOT EXISTS idx_engagement_sessions_active ON engagement_sessions(user_id, status)
    WHERE status IN ('engaging', 'collecting');

-- Comments for documentation
COMMENT ON TABLE engagement_sessions IS 'Tracks user engagement sessions after daily messages for conversion optimization';
COMMENT ON COLUMN engagement_sessions.status IS 'Session status: engaging (initial), collecting (gathering context), offered (proposal sent), paused (low engagement), converted (accepted offer)';
COMMENT ON COLUMN engagement_sessions.messages_count IS 'Number of messages exchanged in this session';
COMMENT ON COLUMN engagement_sessions.problem_summary IS 'AI-generated summary of user problems from conversation';
COMMENT ON COLUMN engagement_sessions.suggested_question IS 'AI-generated question to propose to Oracle';
COMMENT ON TABLE session_messages IS 'Stores conversation messages within engagement sessions';
