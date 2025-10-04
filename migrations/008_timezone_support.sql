-- Timezone support for daily messages
-- Changes default timezone from UTC to Europe/Moscow for Russian users

-- Update default timezone for users table
ALTER TABLE users ALTER COLUMN tz SET DEFAULT 'Europe/Moscow';

-- Update default timezone for user_prefs table (for consistency)
ALTER TABLE user_prefs ALTER COLUMN tz SET DEFAULT 'Europe/Moscow';

-- Update existing users to Europe/Moscow (assuming all users are Russian)
UPDATE users SET tz = 'Europe/Moscow' WHERE tz = 'UTC';
UPDATE user_prefs SET tz = 'Europe/Moscow' WHERE tz = 'UTC';

-- Note: daily_message_time stays as user's local time (e.g., 09:00 in their timezone)
-- Scheduler will now convert UTC time to user's timezone before comparing

COMMENT ON COLUMN users.tz IS 'User timezone (IANA timezone name, e.g., Europe/Moscow, Asia/Tokyo)';
COMMENT ON COLUMN user_prefs.tz IS 'User timezone for CRM tasks (IANA timezone name)';
