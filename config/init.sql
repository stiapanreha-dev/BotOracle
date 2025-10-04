-- Database initialization script

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  tg_user_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  first_seen_at TIMESTAMP DEFAULT now(),
  last_seen_at TIMESTAMP DEFAULT now(),
  tz TEXT DEFAULT 'UTC',
  is_blocked BOOLEAN DEFAULT FALSE,
  blocked_at TIMESTAMP,
  free_questions_left INT DEFAULT 5,
  daily_message_time TIME DEFAULT '09:00:00'
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  plan_code TEXT NOT NULL,   -- 'WEEK', 'MONTH'
  started_at TIMESTAMP DEFAULT now(),
  ends_at TIMESTAMP NOT NULL,
  status TEXT DEFAULT 'active',      -- 'active','expired','canceled'
  robokassa_inv_id TEXT,
  amount NUMERIC(10,2),
  currency TEXT DEFAULT 'RUB'
);

CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  inv_id BIGINT UNIQUE,                       -- Robokassa invoice ID (numeric)
  plan_code TEXT NOT NULL,                    -- 'WEEK', 'MONTH'
  amount NUMERIC(10,2) NOT NULL,
  status TEXT DEFAULT 'pending',              -- 'success','fail','pending'
  created_at TIMESTAMP DEFAULT now(),
  paid_at TIMESTAMP,
  raw_payload JSONB
);

CREATE TABLE IF NOT EXISTS daily_messages (
  id SERIAL PRIMARY KEY,
  text TEXT NOT NULL,
  is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS daily_sent (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  message_id INT REFERENCES daily_messages(id),
  sent_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS questions (
  id SERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  question_text TEXT NOT NULL,
  answer_text TEXT,
  created_at TIMESTAMP DEFAULT now(),
  tokens_used INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  user_id INT REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL, -- 'start','daily_sent','question_asked','payment_success','subscription_started','message_failed_blocked'
  meta JSONB DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fact_daily_metrics (
  d DATE PRIMARY KEY,
  dau INT DEFAULT 0,
  new_users INT DEFAULT 0,
  active_users INT DEFAULT 0,
  blocked_total INT DEFAULT 0,
  daily_sent INT DEFAULT 0,
  paid_active INT DEFAULT 0,
  paid_new INT DEFAULT 0,
  questions INT DEFAULT 0,
  revenue NUMERIC(12,2) DEFAULT 0
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_tg_user_id ON users(tg_user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_daily_sent_user_date ON daily_sent(user_id, sent_date);

-- Insert some sample daily messages
INSERT INTO daily_messages (text) VALUES
('🌅 Доброе утро! Помните: каждый новый день — это новая возможность стать лучше.'),
('💪 Сила не в том, чтобы никогда не падать, а в том, чтобы каждый раз подниматься.'),
('🎯 Успех — это сумма маленьких усилий, повторяемых день за днем.'),
('🌱 Не бойтесь медленного прогресса, бойтесь стоять на месте.'),
('✨ Верьте в себя, даже когда никто другой в вас не верит.'),
('🔥 Ваши ограничения существуют только в вашем сознании.'),
('🎨 Творите свою жизнь, как художник создает шедевр.'),
('🌟 Каждый эксперт когда-то был начинающим.'),
('💡 Инвестируйте в себя — это лучшая инвестиция в мире.'),
('🚀 Мечтайте масштабно, начинайте с малого, действуйте сейчас.')
ON CONFLICT DO NOTHING;