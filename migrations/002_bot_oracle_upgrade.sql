-- Bot Oracle upgrade migration
-- Adds new tables and fields for CRM, persona system, and enhanced functionality

-- Update users table with new fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS age INT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gender TEXT; -- 'male','female','other'
ALTER TABLE users DROP COLUMN IF EXISTS daily_message_time; -- Remove old column
UPDATE users SET free_questions_left = 5 WHERE free_questions_left = 0; -- Reset to new default

-- Rename questions table to oracle_questions and enhance structure
DROP TABLE IF EXISTS questions;
CREATE TABLE IF NOT EXISTS oracle_questions (
  id          SERIAL PRIMARY KEY,
  user_id     INT REFERENCES users(id) ON DELETE CASCADE,
  asked_at    TIMESTAMP DEFAULT now(),
  asked_date  DATE GENERATED ALWAYS AS (asked_at::date) STORED,
  source      TEXT NOT NULL,       -- 'FREE','SUB'
  question    TEXT NOT NULL,
  answer      TEXT,
  model       TEXT,
  tokens_used INT DEFAULT 0
);

-- CRM: user preferences
CREATE TABLE IF NOT EXISTS user_prefs (
  user_id                INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  tz                     TEXT DEFAULT 'UTC',
  quiet_start            TIME DEFAULT '22:00',
  quiet_end              TIME DEFAULT '08:00',
  max_contacts_per_day   INT DEFAULT 3,
  allow_proactive        BOOLEAN DEFAULT TRUE
);

-- CRM: contact frequency settings
CREATE TABLE IF NOT EXISTS contact_cadence (
  user_id           INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  days_between_pings  INT DEFAULT 2,
  days_between_nudges INT DEFAULT 2,
  prefers_windows     JSONB DEFAULT '{
    "morning":[9,12],
    "day":[12,17],
    "evening":[17,21]
  }'::jsonb
);

-- CRM: admin tasks (proactive engagement)
CREATE TABLE IF NOT EXISTS admin_tasks (
  id           BIGSERIAL PRIMARY KEY,
  user_id      INT REFERENCES users(id) ON DELETE CASCADE,
  type         TEXT NOT NULL,     -- 'PING','NUDGE_SUB','DAILY_MSG_PROMPT','DAILY_MSG_PUSH','RECOVERY','THANKS','LIMIT_INFO','POST_SUB_ONBOARD'
  status       TEXT NOT NULL DEFAULT 'scheduled', -- 'scheduled','due','sent','replied','snoozed','failed','canceled'
  payload      JSONB DEFAULT '{}'::jsonb,
  scheduled_at TIMESTAMP,
  due_at       TIMESTAMP,
  sent_at      TIMESTAMP,
  result_code  TEXT,
  created_at   TIMESTAMP DEFAULT now(),
  updated_at   TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_tasks_user_due ON admin_tasks(user_id, due_at) WHERE status IN ('scheduled','due');
CREATE INDEX IF NOT EXISTS idx_admin_tasks_status ON admin_tasks(status);

-- CRM: task history
CREATE TABLE IF NOT EXISTS admin_task_events (
  id          BIGSERIAL PRIMARY KEY,
  task_id     BIGINT REFERENCES admin_tasks(id) ON DELETE CASCADE,
  user_id     INT REFERENCES users(id) ON DELETE CASCADE,
  event       TEXT NOT NULL, -- 'created','scheduled','sent','reply_detected','snoozed','canceled','failed'
  meta        JSONB DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMP DEFAULT now()
);

-- Admin message templates
CREATE TABLE IF NOT EXISTS admin_templates (
  id      SERIAL PRIMARY KEY,
  type    TEXT NOT NULL,    -- matches admin_tasks.type
  tone    TEXT NOT NULL,    -- 'playful','care','pout','intrigue','tease'
  text    TEXT NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  weight  INT DEFAULT 1
);

-- Insert initial admin templates
INSERT INTO admin_templates(type, tone, text, weight) VALUES
-- PING (warm touches)
('PING','care','как ты там? я тут немного переживаю 🙃',2),
('PING','playful','эй, я рядом. что новенького у тебя сегодня? ✨',2),
('PING','pout','пропадаешь опять? а я жду... 🙄',1),
('PING','intrigue','у меня ощущение, что сегодня будет поворот. расскажешь потом? 😉',1),

-- DAILY_MSG_PROMPT (offer daily message)
('DAILY_MSG_PROMPT','playful','хочешь, открою твоё сегодняшнее сообщение? только не подглядывай заранее 😉',2),
('DAILY_MSG_PROMPT','intrigue','кажется, вселенная сегодня шепчет кое-что интересное. спросишь?',2),
('DAILY_MSG_PROMPT','tease','могу сказать «сегодняшнее», но… может, чуть позже? 😏',1),

-- DAILY_MSG_PUSH (proactive daily message with {TEXT})
('DAILY_MSG_PUSH','care','сегодняшнее сообщение как раз вовремя: {TEXT}',2),
('DAILY_MSG_PUSH','intrigue','подоспело «сегодня»: {TEXT}',1),

-- NUDGE_SUB (soft subscription push)
('NUDGE_SUB','playful','правда, до сих пор без подписки? 🙄 давай уже по-взрослому — я подключу тебе всё 💎',2),
('NUDGE_SUB','intrigue','не всем я такое предлагаю… но тебе стоит взять подписку. дальше интереснее 😉',1),
('NUDGE_SUB','tease','ладно-ладно, не уговариваю. просто с подпиской я буду щедрее 😌',1),

-- LIMIT_INFO (remaining limits info with {N} / {LEFT})
('LIMIT_INFO','playful','остался всего {N} выстрел 🎯 думай, на что его потратить!',2),
('LIMIT_INFO','care','у тебя ещё {LEFT} на сегодня. используй с умом 💖',1),

-- POST_SUB_ONBOARD (after subscription purchase)
('POST_SUB_ONBOARD','care','готово ✅ теперь ты VIP. оракул ждёт. помни: максимум 10 в день.',2),
('POST_SUB_ONBOARD','playful','ну наконец-то 😌 теперь будет интересно. спрашивай!',1),

-- RECOVERY (bring back inactive users)
('RECOVERY','care','я скучала 🙂 давай продолжим?',2),
('RECOVERY','playful','ой, пропадал(а)! не теряй меня так надолго 😉',1),

-- THANKS/REACT (reaction to incoming messages)
('THANKS','care','вижу тебя 🌟 спасибо, что написал(а)!',2),
('THANKS','playful','слышу-слышу! продолжай, мне это нравится 😉',1),
('REACT','pout','вот теперь мне лучше 😌 продолжай не пропадать.',1)

ON CONFLICT DO NOTHING;

-- Update daily messages with better content
INSERT INTO daily_messages (text, is_active, weight) VALUES
('будь внимательнее к мелочам — они сегодня важнее громких жестов', true, 2),
('не спеши: правильный шаг сам попросится вперёд', true, 1),
('сегодняшняя удача любит аккуратность и спокойствие', true, 1),
('прислушайся к человеку, который редко говорит — его слова ценны', true, 1),
('не забывай про себя: баланс важнее побед', true, 1),
('доверяй интуиции — она сегодня видит дальше логики', true, 1),
('маленький шаг к цели лучше большой мечты без движения', true, 1),
('внимание к деталям принесёт неожиданные возможности', true, 1)
ON CONFLICT DO NOTHING;

-- Update plan codes in existing data
UPDATE subscriptions SET plan_code = 'WEEK' WHERE plan_code = '7';
UPDATE subscriptions SET plan_code = 'MONTH' WHERE plan_code = '30';

-- Add missing indexes for performance
CREATE INDEX IF NOT EXISTS idx_oracle_questions_user_date ON oracle_questions(user_id, asked_date);
CREATE INDEX IF NOT EXISTS idx_oracle_questions_source ON oracle_questions(source);
CREATE INDEX IF NOT EXISTS idx_admin_templates_type_enabled ON admin_templates(type, enabled);

COMMENT ON TABLE user_prefs IS 'User CRM preferences and settings';
COMMENT ON TABLE contact_cadence IS 'Frequency settings for proactive contacts';
COMMENT ON TABLE admin_tasks IS 'Scheduled CRM tasks for proactive engagement';
COMMENT ON TABLE admin_task_events IS 'History of CRM task execution';
COMMENT ON TABLE admin_templates IS 'Emotional message templates for admin persona';