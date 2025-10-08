-- Migration 013: Conversation History for Chat Completions API
-- Stores message history to provide context in stateless Chat Completions API

CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona VARCHAR(20) NOT NULL, -- 'admin' or 'oracle'
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT valid_persona CHECK (persona IN ('admin', 'oracle')),
    CONSTRAINT valid_role CHECK (role IN ('user', 'assistant', 'system'))
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_conversation_history_user_persona ON conversation_history(user_id, persona, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_history_created_at ON conversation_history(created_at);

-- Function to clean old messages (keep last 50 per user+persona)
CREATE OR REPLACE FUNCTION cleanup_old_conversation_history()
RETURNS void AS $$
BEGIN
    DELETE FROM conversation_history
    WHERE id IN (
        SELECT id FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY user_id, persona ORDER BY created_at DESC) as rn
            FROM conversation_history
        ) t
        WHERE t.rn > 50
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE conversation_history IS 'Stores conversation history for Chat Completions API to maintain context';
COMMENT ON COLUMN conversation_history.persona IS 'Which AI persona: admin (Administrator/Leia) or oracle';
COMMENT ON COLUMN conversation_history.role IS 'Message role: user (from user), assistant (from AI), system (system prompts)';
