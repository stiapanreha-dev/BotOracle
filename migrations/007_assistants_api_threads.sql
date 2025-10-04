-- Migration 007: Add OpenAI Assistants API thread IDs support
-- Adds thread_id fields for stateful conversations with OpenAI Assistants API

-- Add thread_id columns for both Administrator and Oracle personas
ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_thread_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oracle_thread_id TEXT;

-- Create index for faster lookups by thread_id
CREATE INDEX IF NOT EXISTS idx_users_admin_thread_id ON users(admin_thread_id) WHERE admin_thread_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_oracle_thread_id ON users(oracle_thread_id) WHERE oracle_thread_id IS NOT NULL;

-- Add comment to document the feature
COMMENT ON COLUMN users.admin_thread_id IS 'OpenAI Assistants API thread ID for Administrator persona conversations';
COMMENT ON COLUMN users.oracle_thread_id IS 'OpenAI Assistants API thread ID for Oracle persona conversations';
