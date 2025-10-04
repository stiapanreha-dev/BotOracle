-- Add postpone_on_reply parameter to contact_cadence
-- This controls how many hours to postpone scheduled tasks when user sends a message

ALTER TABLE contact_cadence
ADD COLUMN IF NOT EXISTS postpone_on_reply INT DEFAULT 24;

COMMENT ON COLUMN contact_cadence.postpone_on_reply IS
'Hours to postpone scheduled PING/NUDGE tasks when user replies (default: 24)';

-- Set default value for existing records
UPDATE contact_cadence
SET postpone_on_reply = 24
WHERE postpone_on_reply IS NULL;