# Claude Code Configuration

## Project Overview
Bot Oracle - двухперсонный Telegram бот с GPT-5 интеграцией и CRM системой.

## Development Commands

### Testing & Linting
```bash
# Проверка кода (если есть)
python -m pytest tests/

# Линтер (если настроен)
flake8 app/
```

### Database Management
```bash
# Применение миграции
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml exec db psql -U postgres -d telegram_bot -f /migrations/008_timezone_support.sql"

# Подключение к БД
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml exec db psql -U postgres -d telegram_bot"

# Проверка timezone пользователей
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml exec db psql -U postgres -d telegram_bot -c \"SELECT tg_user_id, tz, daily_message_time FROM users;\""
```

### Deployment Commands
```bash
# Полное развертывание на сервере
ssh Pi4-2 "cd /home/lexun/ai-consultant && git pull && docker compose -f docker-compose.prod.yml build --no-cache app && docker compose -f docker-compose.prod.yml up -d app"

# Просмотр логов
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml logs app -f"

# Перезапуск контейнера
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml restart app"
```

### API Testing
```bash
# Проверка здоровья системы
curl -s "https://consultant.sh3.su/health"

# Тестирование админских эндпоинтов
curl -X POST "https://consultant.sh3.su/admin/trigger/daily-messages" -H "Authorization: Bearer supersecret_admin_token"

curl -X POST "https://consultant.sh3.su/admin/trigger/crm-planning" -H "Authorization: Bearer supersecret_admin_token"

curl -X POST "https://consultant.sh3.su/admin/trigger/crm-dispatch" -H "Authorization: Bearer supersecret_admin_token"

# Тестирование GPT-5 интеграции
curl -X POST "https://consultant.sh3.su/admin/test/ai-responses?question=Как%20дела?&persona=admin&age=22&gender=female" -H "Authorization: Bearer supersecret_admin_token"

curl -X POST "https://consultant.sh3.su/admin/test/ai-responses?question=В%20чем%20смысл%20жизни?&persona=oracle&age=35&gender=male" -H "Authorization: Bearer supersecret_admin_token"
```

### Database Utilities
```bash
# Удаление пользователя для тестирования (через API - рекомендуется)
curl -X DELETE "https://consultant.sh3.su/admin/users/USER_ID" -H "Authorization: Bearer supersecret_admin_token"

# Удаление пользователя напрямую через БД
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml exec db psql -U postgres -d telegram_bot -c \"DELETE FROM users WHERE tg_user_id = USER_ID;\""

# Добавление 1 дня премиум подписки пользователю
curl -X POST "https://consultant.sh3.su/admin/users/USER_ID/premium" -H "Authorization: Bearer supersecret_admin_token"

# Проверка таблиц Oracle
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml exec db psql -U postgres -d telegram_bot -c \"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'admin_%';\""
```

### Prompt Logging & Debugging
```bash
# Просмотр логов промптов (показывает какие промпты загружаются из БД)
ssh Pi4-2 "docker compose -f /home/lexun/ai-consultant/docker-compose.prod.yml exec app cat /app/logs/prompts.log"

# Live мониторинг промптов
ssh Pi4-2 "docker compose -f /home/lexun/ai-consultant/docker-compose.prod.yml exec app tail -f /app/logs/prompts.log"

# Последние 50 строк
ssh Pi4-2 "docker compose -f /home/lexun/ai-consultant/docker-compose.prod.yml exec app tail -n 50 /app/logs/prompts.log"
```

**Что логируется:**
- Загрузка Admin/Oracle instructions из БД или fallback
- Полный текст промпта (DB или hardcoded)
- Каждый вопрос пользователя с контекстом (age, gender, archetype, subscription)
- Полное сообщение отправленное в AI

**Пример лога:**
```
2025-10-04 21:40:17 - ADMIN INSTRUCTIONS - LOADED FROM DATABASE (key: admin_base)
2025-10-04 21:40:17 - [полный текст промпта]
2025-10-04 21:40:18 - ADMIN QUESTION - User ID: 15
2025-10-04 21:40:18 - Question: Расскажи мне про Python
2025-10-04 21:40:18 - User Context: Age: 25, Gender: male, Archetype: rebel
2025-10-04 21:40:18 - Full message sent to AI: [контекст + вопрос]
```

## Architecture Notes

### Bot Oracle System
- **Двухперсонная система**: Administrator/Лея (эмоциональная, флиртующая) + Oracle (мудрый, философский)
  - **Visual distinction**: 💬 префикс для ответов Admin, 🔮 для Oracle
- **GPT-5 интеграция**: Настоящий ИИ для обеих ролей с fallback
- **Database-driven prompts**: Промпты загружаются из таблицы `ai_prompts` с fallback на hardcoded
  - `admin_base` - базовая личность Администратора
  - `oracle_system` - базовая личность Оракула
  - Можно редактировать через Admin Panel → AI Prompts
- **AI API выбор** (через `USE_ASSISTANTS_API` env var):
  - **Chat Completions API** (по умолчанию, `USE_ASSISTANTS_API=false`):
    - Быстрые ответы (0.7-1s)
    - История диалога хранится в БД (`conversation_history` таблица)
    - Последние 20 сообщений передаются в контексте
    - Автоматическая ротация (хранит последние 50 сообщений на user+persona)
  - **Assistants API** (опционально, `USE_ASSISTANTS_API=true`):
    - Stateful sessions с thread_id на стороне OpenAI
    - Медленнее (может быть 30-80s на create_run из-за OpenAI throttling)
    - Cross-thread context sharing между Admin и Oracle
    - Automatic thread rotation при 40+ сообщениях
- **Система вопросов**:
  - **Обычные текстовые сообщения**: БЕСПЛАТНО для всех (не расходуют счетчик)
    - Идут к Администратору/Лее
    - Лея может предложить обратиться к Оракулу в ответе
  - **Переход к Оракулу**:
    - Когда Лея упоминает Оракула → появляется inline кнопка "🔮 Да, хочу спросить Оракула"
    - После нажатия следующее сообщение идёт к Оракулу
  - **Кнопка "🔮 Задать вопрос Оракулу"** (не-премиум): использует счетчик 5 бесплатных вопросов
  - **Кнопка "🔮 Задать вопрос Оракулу"** (премиум): доступ к Оракулу (10 вопросов/день)
  - **Источники для аналитики**: `CHAT_FREE` (текст), `ADMIN_BUTTON` (кнопка), `SUB` (оракул)
- **CRM система**: Проактивные контакты с антиспам ограничениями
- **Персонализация**:
  - **Archetype-based**: 10 архетипов Юнга (Rebel, Hero, Sage и т.д.)
  - **Demographic**: возраст и пол пользователя
  - Admin адаптирует стиль общения под архетип пользователя
- **Контекстные промпты**: Администратор меняет тактику в зависимости от статуса подписки
  - Подписчики: предложение использовать кнопку "🔮 Задать вопрос Оракулу"
  - Неподписчики: мягкая продажа подписки на Оракула
- **Onboarding**: 4 вопроса для определения профиля пользователя
  - Q1: Возраст (10-100, валидация числа)
  - Q2: Пол (male/female)
  - Q3-Q4: Ситуационные вопросы для определения архетипа (AI-generated, validated)

### Key Files
- `app/main.py` - Основное приложение (webhook режим)
- `app/bot/oracle_handlers.py` - Обработчики двухперсонной системы
  - Передает has_subscription и user_id в контекст AI
  - Добавляет emoji префиксы (💬 Admin, 🔮 Oracle)
- `app/bot/onboarding.py` - FSM онбординг (4 вопроса)
  - Q1: Возраст (простая валидация 10-100)
  - Q2: Пол (male/female)
  - Q3-Q4: Архетип (AI-generated, validated, analyzed)
- `app/services/ai_router.py` - Роутер между Chat Completions и Assistants API (выбор по USE_ASSISTANTS_API)
- `app/services/ai_client.py` - Chat Completions API (по умолчанию, быстро)
  - `get_admin_response()` - принимает has_subscription в user_context
  - `get_oracle_response()` - генерирует ответы Оракула
  - `_get_conversation_history()` - загружает последние 20 сообщений из БД
  - `_save_to_history()` - сохраняет user/assistant сообщения в БД
  - `_build_admin_system_prompt()` - строит промпт с учетом подписки и архетипа
  - История диалога передается в messages при каждом запросе
- `app/services/assistant_ai_client.py` - Assistants API (stateful sessions с thread_id)
  - Создает/использует OpenAI Assistants для Admin и Oracle
  - Управляет thread_id для каждого пользователя (хранится в БД)
  - Поддерживает полную историю диалога на стороне OpenAI
  - **Database-driven prompts**: загружает промпты из `ai_prompts` таблицы
  - **Cross-thread sync**: `_sync_conversation_to_thread()` синхронизирует контекст между персонами
  - **Prompt logging**: логирует все промпты и вопросы в `/app/logs/prompts.log`
- `app/services/smart_messages.py` - AI-generated system messages
  - `generate_onboarding_questions()` - генерирует 2 архетипических вопроса
  - `validate_response()` - валидация ответов пользователя
  - `analyze_archetype()` - определение архетипа по ответам
- `app/services/persona.py` - Система персонализации
- `app/database/models.py` - Database models
  - `UserModel.update_user_info()` - сохранение возраста/пола по user_id
  - `ArchetypeModel.update_user_archetype()` - сохранение архетипа
- `app/crm/planner.py` - Планировщик CRM задач
- `app/crm/dispatcher.py` - Исполнитель CRM задач
- `app/api/admin/users.py` - API для управления пользователями
  - `GET /admin/users` - список пользователей с фильтрами
  - `GET /admin/users/{user_id}` - детальная информация о пользователе
  - `DELETE /admin/users/{user_id}` - удаление пользователя со всеми данными
  - `POST /admin/users/{user_id}/premium` - добавление 1 дня премиум подписки
- `app/static/admin/` - Frontend админ панели (HTML + JS)
- `app/scheduler.py` - Планировщик задач с поддержкой timezone
  - `send_daily_messages_by_user_time()` - отправка сообщений с учетом часового пояса пользователя
  - Конвертирует UTC время в локальное время пользователя для сравнения
- `migrations/007_assistants_api_threads.sql` - Миграция для thread_id полей (Assistants API)
- `migrations/008_timezone_support.sql` - Миграция для поддержки timezone (Europe/Moscow по умолчанию)
- `migrations/012_api_request_logs.sql` - Логирование OpenAI API запросов как curl команды
- `migrations/013_conversation_history.sql` - История диалогов для Chat Completions API

### Environment Variables
```
OPENAI_API_KEY=your_openai_api_key_here
FREE_QUESTIONS=5
HUMANIZED_MAX_CONTACTS_PER_DAY=3
NUDGE_MIN_HOURS=48
NUDGE_MAX_PER_WEEK=2
ADMIN_TOKEN=supersecret_admin_token

# AI API выбор
USE_ASSISTANTS_API=false  # false=Chat Completions (быстро), true=Assistants API (медленно но stateful)

# Только для Assistants API (если USE_ASSISTANTS_API=true)
OPENAI_ADMIN_ASSISTANT_ID=asst_xxx  # ID администратора (создается автоматически)
OPENAI_ORACLE_ASSISTANT_ID=asst_yyy  # ID оракула (создается автоматически)
```

## Common Issues & Solutions

### Import Errors
- Убедитесь что `app/crm/__init__.py` существует
- Проверьте все пути импортов после переименования файлов

### Database Connection
- База данных называется `telegram_bot`, не `app`
- Пользователь БД: `postgres`, пароль: `password`

### Timezone & Daily Messages
- **Формат timezone**: IANA timezone name (Europe/Moscow, Asia/Tokyo и т.д.)
- **По умолчанию**: Europe/Moscow для всех новых пользователей
- **daily_message_time**: хранится в локальном времени пользователя (например, 09:00 MSK)
- **Scheduler**: конвертирует UTC в локальное время пользователя для сравнения
- **Требования**: pytz должен быть установлен (requirements.txt)
- **Пример**: Пользователь с tz='Europe/Moscow' и daily_message_time='20:00' получит сообщение в 20:00 по МСК (17:00 UTC)

### Chat Completions API (по умолчанию)

**Преимущества:**
- ✅ Быстрые ответы (0.7-1 секунда)
- ✅ Контекст диалога сохраняется в БД (таблица `conversation_history`)
- ✅ Автоматическая ротация (хранит последние 50 сообщений на user+persona)
- ✅ Полный контроль над данными

**Как работает:**
- При каждом запросе загружаются последние 20 сообщений из БД
- Передаются в `messages` массиве: `[system, history..., current_question]`
- После ответа сохраняются user и assistant сообщения в БД
- Функция `cleanup_old_conversation_history()` удаляет старые сообщения (>50 на user+persona)

**Очистка истории:**
```bash
# Очистить историю для конкретного пользователя
DELETE FROM conversation_history WHERE user_id = X;

# Очистить для конкретной персоны
DELETE FROM conversation_history WHERE user_id = X AND persona = 'admin';

# Запустить автоматическую очистку (оставит последние 50)
SELECT cleanup_old_conversation_history();
```

### Assistants API (опционально)

**⚠️ Проблемы производительности:**
- ❌ Медленные ответы (30-80+ секунд на create_run)
- ❌ OpenAI API throttling на некоторых API ключах
- ❌ Непредсказуемые задержки

**Создание и настройка:**
- При первом запуске с `USE_ASSISTANTS_API=true` создаются новые Assistants
- ID ассистентов будут выведены в логи: `OPENAI_ADMIN_ASSISTANT_ID=...`
- Добавьте эти ID в .env для переиспользования существующих ассистентов
- Для сброса истории диалога: удалить `admin_thread_id` или `oracle_thread_id` из таблицы users

**Database-driven instructions:**
- При первом использовании Assistant загружает промпты из БД:
  - Admin: загружает `admin_base` из `ai_prompts`
  - Oracle: загружает `oracle_system` из `ai_prompts`
- Обновляет инструкции Assistant в OpenAI через API
- Если промпт не найден в БД - использует hardcoded fallback
- Проверить какой промпт используется: `/app/logs/prompts.log`

**Cross-thread context sharing:**
- После каждого ответа Admin → контекст синхронизируется в Oracle thread
- После каждого ответа Oracle → контекст синхронизируется в Admin thread
- Формат: `[Контекст из диалога с Admin/Oracle] Пользователь спросил: X, Ответ: Y`
- Позволяет персонам знать о чем был разговор с другой персоной

**Управление через OpenAI Platform:**
- Доступ к Assistants: https://platform.openai.com/assistants
- Можно редактировать инструкции, модель, параметры
- Просмотр всех Threads и истории сообщений
- Удаление неиспользуемых Assistants

**Смена OPENAI_API_KEY:**
```bash
# 1. Удалить старые ID из .env
sed -i '/OPENAI_ADMIN_ASSISTANT_ID=/d' .env
sed -i '/OPENAI_ORACLE_ASSISTANT_ID=/d' .env

# 2. Пересоздать контейнер (создадутся новые Assistants)
docker compose -f docker-compose.prod.yml down app
docker compose -f docker-compose.prod.yml up -d app

# 3. Скопировать новые ID из логов в .env
docker compose -f docker-compose.prod.yml logs app | grep "Add to .env"

# 4. Очистить старые thread_id из БД
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d telegram_bot \
  -c "UPDATE users SET admin_thread_id = NULL, oracle_thread_id = NULL;"
```

**Особенности:**
- Assistants API медленнее Chat Completions (асинхронная модель с polling)
- Стоимость: хранение thread и messages оплачивается отдельно
- Typing индикатор показывается во время генерации ответов Администратора
- Каждый пользователь имеет отдельные сессии для Admin и Oracle

### Deployment Issues
- Всегда используйте `--no-cache` при пересборке Docker
- Проверяйте логи после каждого деплоя
- При изменении main.py нужна полная пересборка контейнера

## Testing Checklist

### После деплоя проверить:
- [ ] Здоровье API: `curl -s "https://consultant.sh3.su/health"`
- [ ] Логи содержат: "Bot Oracle startup completed!"
- [ ] Логи содержат: "CRM planning, CRM dispatcher"
- [ ] Логи содержат: "AI Router: Using OpenAI Assistants API" (если USE_ASSISTANTS_API=true)
- [ ] Telegram webhook работает: отправить `/start` в бот
- [ ] Анкета работает: Q1 (возраст), Q2 (пол), Q3-Q4 (архетип)
- [ ] GPT-5 отвечает или fallback срабатывает
- [ ] Typing индикатор отображается при ответах Admin
- [ ] Emoji префиксы отображаются: 💬 Admin, 🔮 Oracle
- [ ] Промпты загружаются из БД (проверить /app/logs/prompts.log)
- [ ] Админские эндпоинты доступны с токеном
- [ ] Админ панель доступна: https://consultant.sh3.su/admin/

### Типичный пользовательский флоу:

**Для не-премиум пользователей:**
1. `/start` → онбординг:
   - Q1: "Сколько тебе лет?" (10-100)
   - Q2: "Твой пол?" (мужской/женский)
   - Q3-Q4: Ситуационные вопросы для определения архетипа
   - Результат: определен возраст, пол и архетип (Rebel, Hero, Sage и т.д.)
2. **Обычные текстовые вопросы** → 💬 Администратор отвечает БЕСПЛАТНО, неограниченно
   - Адаптирует стиль под архетип пользователя
   - Мягко предлагает подписку на Оракула
3. **Кнопка "🔮 Задать вопрос Оракулу"** → использует счетчик (5 бесплатных)
   - Показывает: "Осталось X вопросов из 5 бесплатных"
   - После исчерпания → предложение купить подписку
4. `💎 Подписка` → выбор тарифа

**Для премиум пользователей:**
1. **Обычные текстовые вопросы** → 💬 Администратор отвечает неограниченно
   - Адаптирует стиль под архетип пользователя
   - Предлагает использовать кнопку "🔮 Задать вопрос Оракулу" для глубоких вопросов
2. **Кнопка "🔮 Задать вопрос Оракулу"** → 🔮 доступ к Оракулу (10 вопросов/день)
   - Мудрые, философские ответы на серьезные вопросы
   - Длинные развернутые ответы (700-1000 символов)

**Для всех:**
- CRM система автоматически отправляет проактивные сообщения
- Ежедневные сообщения в настроенное время

## Admin Panel

### Доступ:
- **URL**: https://consultant.sh3.su/admin/
- **Авторизация**: через Telegram WebApp (только для ADMIN_IDS)
- **Команда в боте**: `/admin`

### Функционал:

**Dashboard (Главная):**
- Статистика: пользователи, активность, подписки, выручка
- CRM тестирование

**Вкладки:**
- **Users**: список пользователей, фильтры (All/Active/Paid/Blocked), детали пользователя
- **Subscriptions**: активные/истекшие подписки
- **Events**: события пользователей
- **Tasks**: CRM задачи (создание, редактирование)
- **Templates**: шаблоны CRM сообщений
- **Daily Msgs**: шаблоны ежедневных сообщений
- **AI Prompts**: управление промптами для AI (admin_base, oracle_system и т.д.)
- **AI Sessions**: просмотр активных Assistants API сессий (thread_id для каждого пользователя)

**AI Sessions (доступно при USE_ASSISTANTS_API=true):**
```bash
# Проверить активные сессии
curl -s "https://consultant.sh3.su/admin/sessions" -H "Authorization: Bearer supersecret_admin_token"
```
- Показывает всех пользователей с активными thread_id
- Отображает Admin и Oracle сессии отдельно
- Информация о пользователе: возраст, пол, подписка, последняя активность
- Thread ID для связи с OpenAI Platform

**User Details Modal:**
- Основная информация: возраст, пол, вопросы, подписка
- AI Sessions: admin_thread_id, oracle_thread_id (если есть)
- История: Daily Messages, Oracle Questions, Payments, CRM Logs
- **Действия с пользователем:**
  - **💎 +1 Day Premium** - добавить/продлить премиум подписку на 1 день (для тестирования)
  - **🗑️ Delete User** - полностью удалить пользователя со всеми данными
    - Удаляет из всех таблиц: users, subscriptions, payments, oracle_questions, daily_sent, admin_tasks, events, contact_cadence, user_prefs
    - Позволяет пользователю зарегистрироваться заново с обнулением счетчиков
    - Использует каскадное удаление через foreign keys

## Production Environments

### Pi4-2 Server (Legacy)
- **Server**: Pi4-2
- **Domain**: consultant.sh3.su
- **Docker**: docker-compose.prod.yml
- **Database**: PostgreSQL в контейнере
- **SSL**: Let's Encrypt автоматически

### Railway (Current)
- **Platform**: Railway.app
- **Domain**: botoracle-production.up.railway.app
- **Database**: Railway PostgreSQL
- **Deployment**: Automatic from GitHub (main branch)
- **Config**: railway.toml

## Railway Deployment

### Quick Commands
```bash
# Проверка здоровья
curl -s "https://botoracle-production.up.railway.app/health"

# Проверка webhook
curl -s "https://api.telegram.org/bot8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw/getWebhookInfo"

# Установка webhook (если потерялся)
curl -s "https://api.telegram.org/bot8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw/setWebhook?url=https://botoracle-production.up.railway.app/webhook"

# Тестирование API
curl -X POST "https://botoracle-production.up.railway.app/admin/trigger/daily-messages" -H "Authorization: Bearer supersecret_admin_token"

# Проверка активных AI сессий
curl -s "https://botoracle-production.up.railway.app/admin/sessions" -H "Authorization: Bearer supersecret_admin_token"
```

### Deployment Process
1. **Push to GitHub main branch** - автоматически деплоится на Railway
2. **Manual redeploy** - Railway Dashboard → Deployments → Redeploy
3. **Environment variables** - Railway Dashboard → Variables
4. **После деплоя ОБЯЗАТЕЛЬНО** - установить webhook вручную:
```bash
curl -s "https://api.telegram.org/bot8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw/setWebhook?url=https://botoracle-production.up.railway.app/webhook"
```
   **Почему**: При shutdown приложение удаляет webhook, и он может не успеть установиться при startup

### Railway CLI Commands
```bash
# Логин (если нужно)
railway login

# Просмотр логов (live)
railway logs

# Просмотр переменных
railway variables

# Подключение к PostgreSQL
railway connect postgres
```

### Database Management
```bash
# Миграция с Pi4-2 на Railway (один раз)
# 1. Создать дамп на Pi4-2
ssh Pi4-2 "cd /home/lexun/ai-consultant && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U postgres -d telegram_bot" > /tmp/railway_dump.sql

# 2. Импорт в Railway (через Railway Dashboard → PostgreSQL → Connect → получить credentials)
psql "postgresql://postgres:[PASSWORD]@[HOST]/railway" < /tmp/railway_dump.sql

# Резервное копирование Railway БД
pg_dump "postgresql://postgres:[PASSWORD]@[HOST]/railway" > backup_$(date +%Y%m%d).sql
```

### Важные переменные окружения Railway
```bash
# Обязательные
BOT_TOKEN=8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw
BASE_URL=https://botoracle-production.up.railway.app
DATABASE_URL=${DATABASE_URL}  # Автоматически от Railway PostgreSQL
PORT=${PORT}  # Автоматически от Railway (обычно 8080)

# Остальные как в .env
OPENAI_API_KEY=...
ADMIN_TOKEN=supersecret_admin_token
USE_ASSISTANTS_API=true
OPENAI_ADMIN_ASSISTANT_ID=asst_PkhuajnDi5Xla2vGX7Mry4tb
OPENAI_ORACLE_ASSISTANT_ID=asst_kWqW5PgZb0v0XeQF6dhJwsVo
```

### Troubleshooting Railway

**Webhook не работает:**
```bash
# Проверить текущий webhook
curl -s "https://api.telegram.org/bot8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw/getWebhookInfo"

# Если url пустой или неправильный - установить заново
curl -s "https://api.telegram.org/bot8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw/setWebhook?url=https://botoracle-production.up.railway.app/webhook"

# Проверить pending_update_count - если >0, значит сообщения ждут обработки
```

**502 Bad Gateway:**
- Проверить что приложение запустилось: Railway logs должны содержать "Uvicorn running on http://0.0.0.0:8080"
- Проверить healthcheck: Railway Dashboard → Settings → Healthcheck
- PORT должен быть динамический через `os.getenv("PORT", "8000")`

**База данных не подключается:**
- Проверить что DATABASE_URL правильный: Railway Dashboard → PostgreSQL → Variables
- Формат: `postgresql://postgres:password@host:port/railway`
- В логах должно быть: "Database connected successfully"

**Токен бота неправильный:**
- Проверить BOT_TOKEN в Railway Variables
- Должен совпадать с продакшн ботом: `8277675218:AAH5I21LQivDzmfOh39FjPPg81dL8-9QUOw`
- После изменения - redeploy сервиса

### Railway vs Pi4-2 Differences

| Параметр | Pi4-2 | Railway |
|----------|-------|---------|
| Domain | consultant.sh3.su | botoracle-production.up.railway.app |
| Bot Token | Тестовый | Продакшн (8277675218) |
| Database | Docker local | Railway PostgreSQL |
| Port | 8000 (hardcoded) | Dynamic via PORT env |
| Healthcheck | Нет | 300s timeout |
| Deployment | Manual (git pull + docker) | Automatic (push to main) |
| Logs | docker compose logs | railway logs или Dashboard |
| Admin Panel | /admin/ | /admin/ |