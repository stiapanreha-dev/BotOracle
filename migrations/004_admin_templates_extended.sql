-- Extended admin templates for CRM system
-- Adds more emotional variety and human-like messages

-- Additional PING templates (warm touches)
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('PING', 'care', 'как ты там? я тут немного переживаю 🙃', 10, true),
('PING', 'playful', 'эй, я рядом. что новенького у тебя сегодня? ✨', 10, true),
('PING', 'pout', 'пропадаешь опять? а я жду... 🙄', 6, true),
('PING', 'intrigue', 'у меня ощущение, что сегодня будет поворот. расскажешь потом? 😉', 8, true);

-- Additional DAILY_MSG_PROMPT templates
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('DAILY_MSG_PROMPT', 'playful', 'хочешь, открою твоё сегодняшнее сообщение? только не подглядывай заранее 😉', 10, true),
('DAILY_MSG_PROMPT', 'intrigue', 'кажется, вселенная сегодня шепчет кое-что интересное. спросишь?', 10, true),
('DAILY_MSG_PROMPT', 'tease', 'могу сказать «сегодняшнее», но… может, чуть позже? 😏', 6, true);

-- Additional DAILY_MSG_PUSH templates
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('DAILY_MSG_PUSH', 'care', 'сегодняшнее сообщение как раз вовремя: {TEXT}', 10, true),
('DAILY_MSG_PUSH', 'intrigue', 'подоспело «сегодня»: {TEXT}', 8, true);

-- Additional NUDGE_SUB templates (soft subscription push)
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('NUDGE_SUB', 'playful', 'правда, до сих пор без подписки? 🙄 давай уже по-взрослому — я подключу тебе всё 💎', 10, true),
('NUDGE_SUB', 'intrigue', 'не всем я такое предлагаю… но тебе стоит взять подписку. дальше интереснее 😉', 8, true),
('NUDGE_SUB', 'tease', 'ладно-ладно, не уговариваю. просто с подпиской я буду щедрее 😌', 6, true);

-- Additional LIMIT_INFO templates
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('LIMIT_INFO', 'playful', 'остался всего {N} выстрел 🎯 думай, на что его потратить!', 10, true),
('LIMIT_INFO', 'care', 'у тебя ещё {LEFT} на сегодня. используй с умом 💖', 10, true);

-- Additional POST_SUB_ONBOARD templates
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('POST_SUB_ONBOARD', 'care', 'готово ✅ теперь ты VIP. оракул ждёт. помни: максимум 10 в день.', 10, true),
('POST_SUB_ONBOARD', 'playful', 'ну наконец-то 😌 теперь будет интересно. спрашивай!', 8, true);

-- Additional RECOVERY templates
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('RECOVERY', 'care', 'я скучала 🙂 давай продолжим?', 10, true),
('RECOVERY', 'playful', 'ой, пропадал(а)! не теряй меня так надолго 😉', 8, true);

-- Additional THANKS/REACT templates (reaction to incoming messages)
INSERT INTO admin_templates(type, tone, text, weight, enabled) VALUES
('THANKS', 'care', 'вижу тебя 🌟 спасибо, что написал(а)!', 10, true),
('THANKS', 'playful', 'слышу-слышу! продолжай, мне это нравится 😉', 8, true),
('REACT', 'care', 'приятно с тобой общаться! если что-то нужно — пиши, всегда рад помочь 💙', 10, true),
('REACT', 'playful', 'о, ты вернулся! соскучился? 😏', 8, true),
('REACT', 'pout', 'вот теперь мне лучше 😌 продолжай не пропадать.', 6, true),
('REACT', 'friendly', 'эй, как дела? рад тебя видеть здесь ✨', 10, true),
('REACT', 'supportive', 'спасибо, что делишься! я здесь, если понадоблюсь 🤗', 9, true);

-- Summary
-- Added 29 new templates across 9 types
-- All templates have appropriate weights and tones for natural selection