-- Archetype System Migration
-- Adds archetype-based personalization for deep user profiling

-- ============================================================================
-- 1. Archetypes Reference Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS archetypes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name_ru VARCHAR(100) NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    description TEXT,
    communication_style TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_archetypes_code ON archetypes(code);
CREATE INDEX idx_archetypes_active ON archetypes(is_active);

COMMENT ON TABLE archetypes IS 'Reference table for archetype types (Hero, Sage, Caregiver, etc.)';
COMMENT ON COLUMN archetypes.code IS 'Unique archetype identifier (hero, sage, caregiver, etc.)';
COMMENT ON COLUMN archetypes.communication_style IS 'Description of how to communicate with this archetype';

-- ============================================================================
-- 2. Insert Base Archetypes
-- ============================================================================

INSERT INTO archetypes (code, name_ru, name_en, description, communication_style) VALUES
('hero', 'Герой', 'Hero',
 'Стремится к достижениям, преодолению препятствий, действию и результатам',
 'Энергично, мотивирующе, с фокусом на действие и результат. Используй слова силы, победы, преодоления.'),

('sage', 'Мудрец', 'Sage',
 'Ищет знания, понимание, истину, аналитическое мышление',
 'Спокойно, рассудительно, с глубиной и аналитикой. Давай пространство для размышлений.'),

('caregiver', 'Заботливый', 'Caregiver',
 'Помогает другим, заботится о близких, защищает слабых',
 'Мягко, поддерживающе, с эмпатией и теплотой. Подчеркивай заботу о других.'),

('rebel', 'Бунтарь', 'Rebel',
 'Нарушает правила, ищет свободу, вызывает статус-кво',
 'Дерзко, провокационно, с вызовом. Поддерживай индивидуальность и свободу.'),

('creator', 'Творец', 'Creator',
 'Создаёт новое, выражает себя, стремится к самореализации',
 'Вдохновляюще, с акцентом на самовыражение и уникальность.'),

('explorer', 'Исследователь', 'Explorer',
 'Открывает новое, ищет опыт, путешествует в неизведанное',
 'Любопытно, авантюрно, с фокусом на открытия и новый опыт.'),

('lover', 'Любовник', 'Lover',
 'Ценит близость, красоту, страсть, глубокие отношения',
 'Чувственно, эмоционально, с глубиной переживаний и страсти.'),

('jester', 'Шут', 'Jester',
 'Находит радость в жизни, смеётся над проблемами, не принимает всё всерьёз',
 'Легко, с юмором, игриво. Помогай находить радость в простом.'),

('ruler', 'Правитель', 'Ruler',
 'Контролирует ситуацию, организует, ведёт за собой, берёт ответственность',
 'Авторитетно, структурированно, с уверенностью. Поддерживай лидерство.'),

('magician', 'Маг', 'Magician',
 'Трансформирует реальность, видит скрытое, работает с изменениями',
 'Мистически, с глубиной понимания. Показывай возможности трансформации.')

ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- 3. Update Users Table - Add Archetype Fields
-- ============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS archetype_primary VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS archetype_secondary VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS archetype_data JSONB DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;

-- Create indexes for archetype queries
CREATE INDEX idx_users_archetype_primary ON users(archetype_primary) WHERE archetype_primary IS NOT NULL;
CREATE INDEX idx_users_archetype_secondary ON users(archetype_secondary) WHERE archetype_secondary IS NOT NULL;
CREATE INDEX idx_users_onboarding_completed ON users(onboarding_completed);

COMMENT ON COLUMN users.archetype_primary IS 'Primary archetype code (hero, sage, caregiver, etc.)';
COMMENT ON COLUMN users.archetype_secondary IS 'Secondary archetype code or NULL';
COMMENT ON COLUMN users.archetype_data IS 'JSON data with archetype analysis: confidence, explanation, etc.';
COMMENT ON COLUMN users.onboarding_completed IS 'TRUE if user completed archetype-based onboarding';

-- ============================================================================
-- 4. Onboarding Responses Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS onboarding_responses (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    question_number INT NOT NULL,
    question_text TEXT NOT NULL,
    user_response TEXT NOT NULL,
    ai_analysis JSONB,
    is_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_onboarding_user ON onboarding_responses(user_id);
CREATE INDEX idx_onboarding_user_question ON onboarding_responses(user_id, question_number);
CREATE INDEX idx_onboarding_created_at ON onboarding_responses(created_at);

COMMENT ON TABLE onboarding_responses IS 'Stores user responses during archetype-based onboarding';
COMMENT ON COLUMN onboarding_responses.question_number IS 'Question sequence number (1-4)';
COMMENT ON COLUMN onboarding_responses.ai_analysis IS 'AI analysis result for this response (validity, insights)';
COMMENT ON COLUMN onboarding_responses.is_valid IS 'TRUE if response is meaningful, FALSE if trolling/spam';

-- ============================================================================
-- 5. Migration Info
-- ============================================================================

DO $$
BEGIN
    INSERT INTO events (user_id, type, meta)
    VALUES (
        NULL,
        'migration',
        json_build_object(
            'migration', '009_archetypes_system',
            'date', NOW(),
            'description', 'Added archetype-based personalization system'
        )::jsonb
    );
EXCEPTION WHEN OTHERS THEN
    -- Events table might not exist yet, ignore error
    NULL;
END $$;
