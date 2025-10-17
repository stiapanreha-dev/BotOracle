-- Migration 014: Adaptive CRM Cadence System
-- Adds intelligent response tracking and 3-level cadence system
-- Level 1 (Normal): < 2 days without response - full CRM
-- Level 2 (Reduced): 2-13 days without response - gentle only
-- Level 3 (Stopped): 14+ days without response - no proactive contacts

-- ============================================================================
-- 1. Add new fields to users table
-- ============================================================================

-- Track last response to CRM contact (within 48h window)
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_crm_response_at TIMESTAMP;

-- Cadence level: 1 = Normal, 2 = Reduced, 3 = Stopped
ALTER TABLE users ADD COLUMN IF NOT EXISTS crm_cadence_level INT DEFAULT 1;

-- Reason for stopping CRM (when level = 3)
ALTER TABLE users ADD COLUMN IF NOT EXISTS crm_stopped_reason TEXT;

-- ============================================================================
-- 2. Add indexes for performance
-- ============================================================================

-- Index for cadence level queries (used by planner)
CREATE INDEX IF NOT EXISTS idx_users_cadence_level
ON users(crm_cadence_level)
WHERE crm_cadence_level IS NOT NULL;

-- Index for response time queries (used by level calculation)
CREATE INDEX IF NOT EXISTS idx_users_crm_response
ON users(last_crm_response_at)
WHERE last_crm_response_at IS NOT NULL;

-- Composite index for cadence queries (level + response time)
CREATE INDEX IF NOT EXISTS idx_users_cadence_response
ON users(crm_cadence_level, last_crm_response_at);

-- ============================================================================
-- 3. Add comments
-- ============================================================================

COMMENT ON COLUMN users.last_crm_response_at IS
'Timestamp of last user response to CRM contact (within 48h window). Used to calculate cadence level.';

COMMENT ON COLUMN users.crm_cadence_level IS
'CRM cadence level: 1=Normal (full CRM), 2=Reduced (gentle only), 3=Stopped (no proactive contacts). Default: 1';

COMMENT ON COLUMN users.crm_stopped_reason IS
'Reason for stopping CRM (e.g., no_response_14d, user_request, abuse). Only set when crm_cadence_level=3';

-- ============================================================================
-- 4. Initialize existing users to Level 1 (Normal)
-- ============================================================================

-- Set all existing users to Level 1 (default behavior, no changes)
UPDATE users
SET crm_cadence_level = 1
WHERE crm_cadence_level IS NULL;

-- Set last_crm_response_at to last_seen_at for active users
-- (assume they were responding before this migration)
UPDATE users
SET last_crm_response_at = last_seen_at
WHERE last_crm_response_at IS NULL
AND last_seen_at IS NOT NULL
AND last_seen_at > NOW() - INTERVAL '7 days';

-- ============================================================================
-- 5. Add new task type for farewell message
-- ============================================================================

-- Add FAREWELL template (sent when transitioning to Level 3)
INSERT INTO admin_templates(type, tone, text, weight) VALUES
('FAREWELL', 'care', 'не хочу быть навязчивой, так что больше не буду писать первой. но я всегда здесь, если понадоблюсь! ✨', 2),
('FAREWELL', 'playful', 'окей, я поняла намёк 😉 больше не буду беспокоить. но знай — я рядом, когда захочешь вернуться! 💫', 1),
('FAREWELL', 'pout', 'ладно... отпускаю тебя. но помни: я жду, если вдруг соскучишься 🥺', 1)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 6. Migration event log
-- ============================================================================

DO $$
BEGIN
    INSERT INTO events (user_id, type, meta)
    VALUES (
        NULL,
        'migration',
        json_build_object(
            'migration', '014_adaptive_cadence',
            'date', NOW(),
            'description', 'Added adaptive CRM cadence system with 3 levels',
            'new_fields', ARRAY['last_crm_response_at', 'crm_cadence_level', 'crm_stopped_reason'],
            'new_task_type', 'FAREWELL'
        )::jsonb
    );
EXCEPTION WHEN OTHERS THEN
    -- Events table might have issues, ignore error
    NULL;
END $$;

-- ============================================================================
-- Migration complete!
-- Next steps:
-- 1. Update app/database/models.py with CadenceManager
-- 2. Update app/crm/planner.py with level-aware logic
-- 3. Update app/bot/oracle_handlers.py with response tracking
-- ============================================================================
