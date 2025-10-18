-- Migration: Add message_type to conversation_history
-- Purpose: Enable unified logging of all messages (dialog + CRM) for analytics
-- Date: 2025-10-19

-- Add message_type column
ALTER TABLE conversation_history
ADD COLUMN IF NOT EXISTS message_type VARCHAR(50) DEFAULT 'dialog';

-- Add comment
COMMENT ON COLUMN conversation_history.message_type IS
'Type of message: dialog (user-AI chat), crm_ping, crm_recovery, crm_daily_msg, crm_nudge_sub, crm_limit_info, crm_thanks, crm_farewell, crm_react, crm_post_sub_onboard';

-- Create index for analytics queries
CREATE INDEX IF NOT EXISTS idx_conversation_history_message_type
ON conversation_history(message_type);

-- Create composite index for user analytics
CREATE INDEX IF NOT EXISTS idx_conversation_history_user_type
ON conversation_history(user_id, message_type, created_at DESC);

-- Verify the migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversation_history'
        AND column_name = 'message_type'
    ) THEN
        RAISE NOTICE 'Migration 015: message_type column added successfully';
    ELSE
        RAISE EXCEPTION 'Migration 015: Failed to add message_type column';
    END IF;
END $$;
