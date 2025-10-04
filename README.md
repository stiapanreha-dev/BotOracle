# Bot Oracle - Telegram Bot with Dual Persona AI

Интеллектуальный Telegram-бот с двухперсонной системой (Администратор + Оракул), GPT-4 интеграцией, CRM-системой и персонализированным общением.

## Оглавление

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Двухперсонная система](#двухперсонная-система)
- [CRM система](#crm-система)
- [API Reference](#api-reference)
- [База данных](#база-данных)
- [Развертывание](#развертывание)
- [Разработка](#разработка)
- [Мониторинг](#мониторинг)
- [Troubleshooting](#troubleshooting)

---

## Возможности

### Основные функции
- 🎭 **Двухперсонная система** - Администратор (эмоциональный помощник) и Оракул (мудрый советник)
- 🤖 **GPT-4 интеграция** - настоящий AI для генерации персонализированных ответов
- 👤 **Персонализация** - адаптация тона и обращений по возрасту и полу пользователя
- 💎 **Система подписок** - интеграция с Robokassa (неделя/месяц/год)
- 📊 **CRM система** - проактивные контакты с антиспам защитой
- 📈 **Аналитика** - детальная статистика пользователей и метрики
- 🔄 **Планировщик задач** - автоматическое выполнение CRM задач и метрик

### Технологии
- **Python 3.11** - основной язык разработки
- **aiogram 3.x** - Telegram Bot API framework
- **FastAPI** - веб-сервер и REST API
- **PostgreSQL** - база данных
- **OpenAI API** - GPT-4 интеграция
- **Docker Compose** - контейнеризация
- **APScheduler** - планировщик задач

---

## Архитектура

### Структура проекта

```
ai-consultant/
├── app/
│   ├── api/                    # FastAPI endpoints
│   │   ├── admin.py            # Admin API (статистика, триггеры)
│   │   └── robokassa.py        # Robokassa callbacks
│   ├── bot/                    # Telegram bot логика
│   │   ├── onboarding.py       # Анкета пользователя (FSM)
│   │   ├── oracle_handlers.py  # Обработчики вопросов
│   │   ├── keyboards.py        # Клавиатуры
│   │   └── states.py           # FSM состояния
│   ├── crm/                    # CRM система
│   │   ├── planner.py          # Планирование задач
│   │   └── dispatcher.py       # Выполнение задач
│   ├── database/               # База данных
│   │   ├── connection.py       # Подключение
│   │   └── models.py           # ORM модели
│   ├── services/               # Сервисы
│   │   ├── ai_client.py        # OpenAI клиент (SOCKS5 proxy)
│   │   └── persona.py          # Персонализация
│   ├── utils/                  # Утилиты
│   │   ├── gpt.py              # GPT хелперы
│   │   └── robokassa.py        # Robokassa SDK
│   ├── config.py               # Конфигурация
│   ├── scheduler.py            # APScheduler
│   └── main.py                 # Точка входа
├── config/
│   ├── init.sql                # Инициализация БД
│   └── nginx.conf              # Nginx конфиг
├── migrations/
│   └── 002_bot_oracle_upgrade.sql  # Миграция Oracle
├── docker-compose.prod.yml     # Production конфиг
├── Dockerfile                  # Образ приложения
├── requirements.txt            # Python зависимости
└── README.md                   # Эта документация
```

### Компоненты системы

```
┌─────────────────────────────────────────────────────────────┐
│                        Users (Telegram)                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Webhook
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ Telegram Bot │  │  Admin API  │  │  Robokassa API   │   │
│  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘   │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     Business Logic                           │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   Onboarding  │  │  CRM System  │  │  Subscriptions  │  │
│  └───────┬───────┘  └──────┬───────┘  └────────┬────────┘  │
│          │                  │                   │            │
│  ┌───────▼──────────────────▼───────────────────▼────────┐  │
│  │              Database Models (PostgreSQL)             │  │
│  └────────────────────────────┬──────────────────────────┘  │
└───────────────────────────────┼─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     External Services                        │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │  OpenAI API  │  │  Robokassa  │  │   SOCKS5 Proxy   │   │
│  └──────────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Быстрый старт

### 1. Клонирование проекта

```bash
git clone <your-repository-url>
cd ai-consultant
```

### 2. Настройка окружения

```bash
# Создать .env файл
cp .env.example .env

# Отредактировать .env с вашими токенами
nano .env
```

### 3. Локальный запуск

```bash
# Запустить через Docker Compose
docker compose -f docker-compose.prod.yml up -d

# Проверить логи
docker compose -f docker-compose.prod.yml logs app -f

# Проверить здоровье
curl http://localhost:8888/health
```

### 4. Первый запуск бота

1. Откройте бота в Telegram
2. Отправьте `/start`
3. Пройдите анкету (возраст + пол)
4. Задайте вопрос - получите ответ от Администратора

---

## Конфигурация

### Переменные окружения (.env)

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_here
BASE_URL=https://consultant.sh3.su

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here
SOCKS5_PROXY=socks5://192.168.100.198:1080  # Опционально

# Database
POSTGRES_DB=telegram_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
DATABASE_URL=postgresql://postgres:password@db:5432/telegram_bot

# Robokassa
ROBO_LOGIN=your_robokassa_login
ROBO_PASS1=your_robokassa_password1
ROBO_PASS2=your_robokassa_password2
ROBO_TEST_MODE=0

# Admin
ADMIN_TOKEN=supersecret_admin_token
ADMIN_IDS=123456789,987654321

# Business Logic
FREE_QUESTIONS=5                      # Бесплатные вопросы
DAILY_QUESTION_LIMIT=10               # Лимит для подписчиков
HUMANIZED_MAX_CONTACTS_PER_DAY=3      # Макс проактивных контактов/день
NUDGE_MIN_HOURS=48                    # Минимум между NUDGE
NUDGE_MAX_PER_WEEK=2                  # Максимум NUDGE в неделю
```

### Настройка Telegram Bot

1. Создать бота через [@BotFather](https://t.me/BotFather)
2. Получить токен и добавить в `.env`
3. Настроить команды:
   ```
   start - Начать работу с ботом
   ```

### Настройка Robokassa

1. Зарегистрировать магазин на [robokassa.com](https://robokassa.com)
2. Получить пароли (Password #1 и #2)
3. Настроить URL callbacks:
   - **Result URL**: `https://consultant.sh3.su/api/robokassa/result`
   - **Success URL**: `https://consultant.sh3.su/api/robokassa/success`
   - **Fail URL**: `https://consultant.sh3.su/api/robokassa/fail`
4. Включить метод GET для Result URL

### Настройка SOCKS5 Proxy (опционально)

Для обхода geographic restrictions OpenAI API:

```env
SOCKS5_PROXY=socks5://your_proxy_host:1080
```

Клиент автоматически использует прокси если переменная установлена.

---

## Двухперсонная система

### Администратор 🎭

**Роль**: Эмоциональный помощник, первая линия контакта

**Характеристики**:
- Эмоциональная, человечная, живая
- Может быть игривой, обидчивой, заботливой
- Помогает пользователю и мягко продает подписку
- НЕ философ - обычный помощник с эмоциями

**Тональность по возрасту**:
- **≤25 лет**: Игривая, эмодзи, молодежный сленг, кокетливая
- **26-45 лет**: Сбалансированная, дружелюбная, умеренные эмодзи
- **46+ лет**: Заботливая, уважительная, теплая, минимум эмодзи

**Ограничения**:
- 1-3 предложения максимум
- Не дает глубоких философских советов
- Максимум 300 символов

**Доступность**:
- Для всех пользователей
- 5 бесплатных вопросов

### Оракул 🔮

**Роль**: Мудрый советник, доступен только по подписке

**Характеристики**:
- Мудрый, спокойный, глубокий мыслитель
- Дает взвешенные, продуманные ответы
- Говорит размеренно, без суеты и эмоций
- Мудрость стоит денег - только для подписчиков

**Подход к ответам**:
- Анализирует вопрос глубоко
- Дает практические советы
- Приводит примеры, метафоры
- Фокусируется на сути проблемы

**Стиль**:
- Серьезный, размеренный тон
- Минимум эмодзи (1-2 за ответ)
- Структурированные мысли
- Обращение во втором лице ("ты", "вам")

**Ограничения**:
- 4-5 предложений
- Практические выводы
- Максимум 800 символов

**Доступность**:
- Только для подписчиков
- 10 вопросов в день

### Персонализация

#### По возрасту

| Возраст | Обращение | Тональность |
|---------|-----------|-------------|
| ≤25 лет | "солнышко", "дружище" | Игривая, молодежный сленг |
| 26-45 лет | "друг", "товарищ" | Нейтральная, сбалансированная |
| 46+ лет | "дорогая", "уважаемый" | Заботливая, уважительная |

#### По полу

| Пол | Обращение (молодой) | Обращение (старший) |
|-----|---------------------|---------------------|
| Женский | "солнышко" | "дорогая" |
| Мужской | "дружище" | "уважаемый" |
| Другое | "друг" | "товарищ" |

---

## CRM система

### Типы проактивных контактов

#### PING
- **Описание**: Дружеский "как дела?"
- **Частота**: Каждые 2 дня
- **Цель**: Поддержание контакта
- **Пример**: "Привет, {имя}! Как твои дела? 😊"

#### DAILY_MSG_PROMPT
- **Описание**: Предложение получить мотивирующее сообщение
- **Частота**: По расписанию
- **Цель**: Вовлечение в контент
- **Пример**: "Хочешь получить мотивирующую цитату на сегодня?"

#### NUDGE_SUB
- **Описание**: Мягкий push на покупку подписки
- **Частота**: Не чаще 1 раза в 48 часов, максимум 2 раза в неделю
- **Цель**: Конверсия в подписчиков
- **Пример**: "Знаешь, у нас есть Оракул, который дает более глубокие советы..."

#### RECOVERY
- **Описание**: Возврат неактивных пользователей
- **Частота**: После 3+ дней молчания
- **Цель**: Реактивация
- **Пример**: "Давно не виделись! Скучаю по тебе 🥺"

#### LIMIT_INFO
- **Описание**: Уведомление об остатке лимитов
- **Частота**: При приближении к лимиту
- **Цель**: Информирование
- **Пример**: "Осталось 2 бесплатных вопроса"

#### POST_SUB_ONBOARD
- **Описание**: Приветствие после покупки подписки
- **Частота**: Сразу после оплаты
- **Цель**: Онбординг подписчика
- **Пример**: "Добро пожаловать в клуб подписчиков! 💎"

### Антиспам защита

#### Ограничения на день
- **Максимум 3 проактивных контакта** на пользователя в день
- Считаются только отправленные сообщения
- Сбрасывается в полночь по UTC

#### Тихие часы
- **22:00 - 08:00** по локальному времени пользователя
- Задачи не выполняются в это время
- Переносятся на следующее утро

#### NUDGE ограничения
- Минимум **48 часов** между NUDGE сообщениями
- Максимум **2 NUDGE в неделю** на пользователя
- Отсчет недели - rolling window (последние 7 дней)

### Планировщик

```python
# Расписание выполнения задач
06:00 UTC - Ежедневное планирование CRM задач для всех пользователей
*/1 minute - Выполнение запланированных задач (due_at <= now)
23:55 UTC - Расчет ежедневных метрик
01:00 UTC - Очистка просроченных подписок
```

### Postpone механизм

При получении сообщения от пользователя:
- Все задачи типа **PING** и **NUDGE_SUB** откладываются на +24 часа от момента активности
- Учитываются только задачи в статусе `scheduled` или `due`
- Учитываются только задачи, запланированные в ближайшие 48 часов

---

## API Reference

### Health Check

```http
GET /health
```

**Ответ**:
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2025-09-30T12:00:00Z"
}
```

### Admin Endpoints

Все admin endpoints требуют авторизации через Bearer token.

#### Статистика

```http
GET /admin/stats
Authorization: Bearer {ADMIN_TOKEN}
```

**Параметры**:
- `start_date` (опционально) - дата начала периода (YYYY-MM-DD)
- `end_date` (опционально) - дата окончания периода (YYYY-MM-DD)

**Ответ**:
```json
{
  "total_users": 150,
  "active_subscriptions": 42,
  "revenue_today": 1500.00,
  "questions_today": 87
}
```

#### Триггеры CRM

```http
POST /admin/trigger/crm-planning
Authorization: Bearer {ADMIN_TOKEN}
```

Запустить планирование CRM задач для всех пользователей.

```http
POST /admin/trigger/crm-dispatch
Authorization: Bearer {ADMIN_TOKEN}
```

Выполнить все запланированные CRM задачи.

```http
POST /admin/trigger/daily-messages
Authorization: Bearer {ADMIN_TOKEN}
```

Отправить ежедневные сообщения.

#### CRM задачи

```http
GET /admin/crm/tasks
Authorization: Bearer {ADMIN_TOKEN}
```

**Параметры**:
- `status` - статус задач (scheduled, due, sent, failed)
- `type` - тип задачи (PING, NUDGE_SUB, etc.)
- `limit` - количество задач (по умолчанию 50)

**Ответ**:
```json
{
  "tasks": [
    {
      "id": 123,
      "user_id": 456,
      "type": "PING",
      "status": "scheduled",
      "due_at": "2025-09-30T14:00:00Z",
      "created_at": "2025-09-30T06:00:00Z"
    }
  ],
  "total": 1
}
```

#### Тестирование AI

```http
POST /admin/test/ai-responses
Authorization: Bearer {ADMIN_TOKEN}
```

**Параметры**:
- `question` - вопрос для тестирования
- `persona` - персона (admin или oracle)
- `age` - возраст пользователя
- `gender` - пол пользователя (male, female, other)

**Пример**:
```bash
curl -X POST "https://consultant.sh3.su/admin/test/ai-responses?question=Как%20дела?&persona=admin&age=22&gender=female" \
  -H "Authorization: Bearer supersecret_admin_token"
```

**Ответ**:
```json
{
  "persona": "admin",
  "question": "Как дела?",
  "answer": "Привет, солнышко! У меня всё отлично, спасибо 😊 А у тебя как?",
  "user_context": {
    "age": 22,
    "gender": "female"
  }
}
```

### Robokassa Callbacks

```http
POST /api/robokassa/result
```

Обработка платежей (Result URL).

```http
POST /api/robokassa/success
```

Страница успешной оплаты (Success URL).

```http
POST /api/robokassa/fail
```

Страница неудачной оплаты (Fail URL).

---

## База данных

### Схема

```sql
-- Основные таблицы
users                   # Пользователи
subscriptions           # Подписки
questions               # Вопросы и ответы
daily_messages          # Сообщения дня
events                  # События для аналитики

-- CRM таблицы
admin_tasks             # CRM задачи
admin_templates         # Шаблоны сообщений
contact_cadence         # История контактов
user_prefs              # Предпочтения пользователей

-- Oracle таблицы
oracle_questions        # Вопросы к Оракулу

-- Метрики
fact_daily_metrics      # Агрегированная статистика
```

### Модель Users

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tg_user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    full_name VARCHAR(255),
    age INTEGER,
    gender VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_blocked BOOLEAN DEFAULT FALSE,
    last_activity TIMESTAMP
);
```

### Модель Subscriptions

```sql
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    plan VARCHAR(50),
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    payment_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Модель Admin Tasks

```sql
CREATE TABLE admin_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR(50),
    status VARCHAR(20),
    due_at TIMESTAMP,
    sent_at TIMESTAMP,
    postpone_on_reply INTEGER DEFAULT 24,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Миграции

Применить миграцию Oracle:

```bash
ssh Pi4-2 "cd /home/lexun/ai-consultant && \
  docker compose -f docker-compose.prod.yml exec db \
  psql -U postgres -d telegram_bot -f /migrations/002_bot_oracle_upgrade.sql"
```

---

## Развертывание

### Production (Pi4-2)

#### 1. Первоначальная настройка

```bash
# Подключиться к серверу
ssh Pi4-2

# Клонировать репозиторий
cd /home/lexun
git clone <your-repository-url>
cd ai-consultant

# Настроить .env
nano .env
```

#### 2. Запуск

```bash
# Собрать и запустить
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Проверить логи
docker compose -f docker-compose.prod.yml logs app -f
```

#### 3. Обновление кода

С volume mounting (быстрее):

```bash
# На локальной машине
git push

# На сервере
cd /home/lexun/ai-consultant
git pull
docker compose -f docker-compose.prod.yml restart app
```

Без volume mounting (полная пересборка):

```bash
cd /home/lexun/ai-consultant
git pull
docker compose -f docker-compose.prod.yml build --no-cache app
docker compose -f docker-compose.prod.yml up -d app
```

#### 4. Миграции базы данных

```bash
docker compose -f docker-compose.prod.yml exec db \
  psql -U postgres -d telegram_bot -f /migrations/002_bot_oracle_upgrade.sql
```

### Volume Mounting

Для быстрой разработки без пересборки:

```yaml
# docker-compose.prod.yml
app:
  volumes:
    - ./logs:/app/logs
    - ./app:/app/app              # Hot-reload кода
    - ./migrations:/app/migrations
```

После изменения кода:
```bash
docker compose -f docker-compose.prod.yml restart app
```

---

## Разработка

### Локальная разработка

#### Установка зависимостей

```bash
# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

#### Запуск локально (polling mode)

```bash
# Запустить бота в polling режиме
python3 run_local.py
```

#### Запуск локально (webhook mode)

```bash
# Запустить бота в webhook режиме
./start_local.sh

# В другом терминале
python3 run_webhook_local.py
```

### Тестирование

#### API тесты

```bash
# Health check
curl http://localhost:8888/health

# Admin stats
curl -H "Authorization: Bearer supersecret_admin_token" \
  http://localhost:8888/admin/stats

# Тестирование AI
curl -X POST "http://localhost:8888/admin/test/ai-responses?question=Привет&persona=admin&age=25&gender=male" \
  -H "Authorization: Bearer supersecret_admin_token"
```

#### CRM тесты

```bash
# Запустить планирование
curl -X POST http://localhost:8888/admin/trigger/crm-planning \
  -H "Authorization: Bearer supersecret_admin_token"

# Запустить отправку
curl -X POST http://localhost:8888/admin/trigger/crm-dispatch \
  -H "Authorization: Bearer supersecret_admin_token"

# Проверить задачи
curl http://localhost:8888/admin/crm/tasks?status=scheduled \
  -H "Authorization: Bearer supersecret_admin_token"
```

### Добавление функционала

#### 1. Создать модель

```python
# app/database/models.py
class NewFeature:
    @staticmethod
    async def create_feature(db, user_id: int, data: dict):
        # Реализация
        pass
```

#### 2. Создать handler

```python
# app/bot/handlers.py
@router.message(Command("new_feature"))
async def new_feature_handler(message: Message):
    # Реализация
    pass
```

#### 3. Создать API endpoint

```python
# app/api/admin.py
@router.post("/admin/new-feature")
async def trigger_new_feature():
    # Реализация
    pass
```

#### 4. Создать миграцию

```sql
-- migrations/003_new_feature.sql
CREATE TABLE new_feature (
    id SERIAL PRIMARY KEY,
    ...
);
```

---

## Мониторинг

### Логи

```bash
# Все логи
docker compose -f docker-compose.prod.yml logs -f

# Только приложение
docker compose -f docker-compose.prod.yml logs app -f

# Фильтр по ключевым словам
docker compose -f docker-compose.prod.yml logs app -f | grep -i "error\|crm\|task"
```

### Метрики

```bash
# Проверить здоровье
curl https://consultant.sh3.su/health

# Статистика
curl -H "Authorization: Bearer supersecret_admin_token" \
  https://consultant.sh3.su/admin/stats

# CRM задачи
curl -H "Authorization: Bearer supersecret_admin_token" \
  https://consultant.sh3.su/admin/crm/tasks?status=due
```

### База данных

```bash
# Подключиться к БД
docker compose -f docker-compose.prod.yml exec db \
  psql -U postgres -d telegram_bot

# Проверить пользователей
SELECT count(*), is_blocked FROM users GROUP BY is_blocked;

# Проверить подписки
SELECT plan, count(*) FROM subscriptions WHERE is_active = true GROUP BY plan;

# Проверить CRM задачи
SELECT type, status, count(*) FROM admin_tasks GROUP BY type, status;
```

---

## Troubleshooting

### Бот не отвечает

**Проблема**: Бот не реагирует на команды

**Решение**:
1. Проверить логи:
   ```bash
   docker compose logs app -f
   ```
2. Проверить webhook:
   ```bash
   curl https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo
   ```
3. Проверить токен в `.env`
4. Перезапустить контейнер:
   ```bash
   docker compose restart app
   ```

### OpenAI API ошибки

**Проблема**: `Error code: 403 - 'unsupported_country_region_territory'`

**Решение**:
1. Настроить SOCKS5 прокси в `.env`:
   ```env
   SOCKS5_PROXY=socks5://your_proxy_host:1080
   ```
2. Перезапустить контейнер
3. Проверить логи на сообщение "OpenAI client configured with SOCKS5 proxy"

### CRM задачи не выполняются

**Проблема**: Задачи создаются, но не отправляются

**Решение**:
1. Проверить статус задач:
   ```sql
   SELECT type, status, count(*) FROM admin_tasks
   WHERE created_at > now() - interval '1 day'
   GROUP BY type, status;
   ```
2. Проверить антиспам ограничения:
   ```sql
   SELECT user_id, date, contact_count
   FROM contact_cadence
   WHERE date = current_date;
   ```
3. Проверить планировщик в логах:
   ```bash
   docker compose logs app -f | grep "scheduler\|crm"
   ```

### База данных не подключается

**Проблема**: `Database connection failed`

**Решение**:
1. Проверить что контейнер БД запущен:
   ```bash
   docker compose ps
   ```
2. Проверить DATABASE_URL в `.env`
3. Проверить пароль PostgreSQL
4. Пересоздать контейнер БД:
   ```bash
   docker compose down
   docker compose up -d
   ```

### Платежи не проходят

**Проблема**: Robokassa callbacks не работают

**Решение**:
1. Проверить настройки в личном кабинете Robokassa
2. Проверить Result URL доступен извне:
   ```bash
   curl https://consultant.sh3.su/api/robokassa/result
   ```
3. Проверить пароли в `.env`
4. Проверить логи при получении callback:
   ```bash
   docker compose logs app -f | grep robokassa
   ```

---

## FAQ

### Как добавить нового администратора?

Добавить Telegram ID в `.env`:
```env
ADMIN_IDS=123456789,987654321,111222333
```

### Как изменить цены подписок?

В файле `app/bot/keyboards.py` найти функцию `get_subscription_keyboard()` и изменить суммы.

### Как изменить лимиты вопросов?

В `.env`:
```env
FREE_QUESTIONS=5              # Бесплатные
DAILY_QUESTION_LIMIT=10       # Для подписчиков
```

### Как добавить новый тип CRM задачи?

1. Добавить тип в `app/crm/planner.py`
2. Создать шаблоны в `admin_templates`
3. Добавить логику планирования в `schedule_crm_tasks()`

### Как изменить тональность персон?

В файлах:
- `app/services/ai_client.py` - system prompts для GPT-4
- `app/services/persona.py` - обращения и префиксы

---

## Лицензия

Проект создан для заказчика. Все права защищены.

---

## Контакты

При возникновении вопросов или проблем создайте issue в репозитории или обратитесь к разработчику.

**Made with ❤️ and powered by GPT-4**