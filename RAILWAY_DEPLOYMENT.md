# Развертывание Bot Oracle на Railway

Полное руководство по деплою Telegram бота Bot Oracle на платформе Railway.

## Преимущества Railway

- ✅ **Простой деплой**: Git push → автоматический деплой
- ✅ **Встроенная PostgreSQL**: Plugin для базы данных
- ✅ **Бесплатный план**: $5/месяц кредитов для старта
- ✅ **HTTPS из коробки**: Автоматические SSL сертификаты
- ✅ **Логи и мониторинг**: Web-интерфейс для отладки
- ✅ **Environment Variables**: Удобное управление переменными

## Предварительные требования

1. **Railway аккаунт**: [railway.app](https://railway.app)
2. **GitHub репозиторий** с кодом проекта
3. **Telegram Bot Token** от @BotFather
4. **OpenAI API Key** для GPT-5 интеграции

## Шаг 1: Создание проекта на Railway

### 1.1 Подключение репозитория

1. Зайдите на [railway.app](https://railway.app)
2. Нажмите **"New Project"**
3. Выберите **"Deploy from GitHub repo"**
4. Авторизуйте Railway доступ к GitHub
5. Выберите репозиторий `ai-consultant`

### 1.2 Добавление PostgreSQL

1. В проекте нажмите **"+ New"**
2. Выберите **"Database"** → **"Add PostgreSQL"**
3. Railway автоматически создаст БД и установит переменную `DATABASE_URL`

## Шаг 2: Настройка переменных окружения

Перейдите в **Settings → Variables** вашего сервиса и добавьте:

### Обязательные переменные

```bash
# Telegram Bot
BOT_TOKEN=your_bot_token_here
BOT_URL=https://t.me/your_bot_name

# Webhook (Railway автоматически предоставляет домен)
WEBHOOK_HOST=https://${RAILWAY_PUBLIC_DOMAIN}
WEBHOOK_PATH=/webhook

# Database (автоматически от Railway Postgres)
DATABASE_URL=${DATABASE_URL}

# Admin
ADMIN_IDS=your_telegram_user_id
ADMIN_TOKEN=your_secure_admin_token

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# Mode
LOCAL_MODE=false
```

### Платежные настройки

```bash
# Robokassa
ROBO_LOGIN=your_robo_login
ROBO_PASS1=your_robo_password1
ROBO_PASS2=your_robo_password2
ROBO_TEST_MODE=0

# Pricing
WEEK_PRICE=99
MONTH_PRICE=499
```

### CRM и лимиты

```bash
FREE_QUESTIONS=5
QUESTIONS_PER_DAY=5
USE_ADMIN_PERSONA=true
HUMANIZED_MAX_CONTACTS_PER_DAY=3
NUDGE_MIN_HOURS=48
NUDGE_MAX_PER_WEEK=2
DISPATCH_INTERVAL_SECONDS=60
```

### Опциональные переменные

```bash
# SOCKS5 прокси (для России, если нужен)
SOCKS5_PROXY=socks5://your-proxy:1080

# Assistants API (stateful диалоги)
USE_ASSISTANTS_API=false
OPENAI_ADMIN_ASSISTANT_ID=
OPENAI_ORACLE_ASSISTANT_ID=
```

**Полный список переменных**: см. `.env.railway.example`

## Шаг 3: Инициализация базы данных

### 3.1 Подключение к PostgreSQL

Railway предоставляет встроенный SQL-редактор:

1. Откройте **PostgreSQL сервис** в проекте
2. Перейдите во вкладку **"Data"**
3. Нажмите **"Query"**

### 3.2 Запуск миграций

Выполните миграции по порядку:

```sql
-- 1. Базовая схема (init.sql)
-- Скопируйте содержимое config/init.sql

-- 2. Дополнительные миграции (по порядку)
-- migrations/001_*.sql
-- migrations/002_*.sql
-- ...
-- migrations/008_timezone_support.sql
```

**Альтернатива**: Подключитесь через CLI:

```bash
# Установите Railway CLI
npm i -g @railway/cli

# Войдите в аккаунт
railway login

# Подключитесь к проекту
railway link

# Подключение к БД
railway connect postgres

# Выполните миграции
\i /path/to/config/init.sql
\i /path/to/migrations/001_*.sql
# ...
```

## Шаг 4: Деплой приложения

### 4.1 Автоматический деплой

Railway автоматически деплоит при каждом push в main ветку:

```bash
git add .
git commit -m "Configure for Railway deployment"
git push origin main
```

### 4.2 Проверка деплоя

1. Откройте **Deployments** в Railway Dashboard
2. Дождитесь статуса **"Success"**
3. Проверьте логи: **View Logs**

### 4.3 Проверка работоспособности

```bash
# Получите Railway URL из Dashboard (Settings → Domains)
export RAILWAY_URL="your-app.railway.app"

# Проверка health endpoint
curl https://$RAILWAY_URL/health

# Ожидаемый ответ:
# {"status":"ok","version":"v1.0.0","commit":"abc1234"}
```

## Шаг 5: Настройка Telegram Webhook

### 5.1 Автоматическая настройка

Бот автоматически установит webhook при старте (см. `app/main.py`):

```python
await bot.set_webhook(
    url=f"{WEBHOOK_HOST}{WEBHOOK_PATH}",
    allowed_updates=["message", "callback_query"]
)
```

### 5.2 Проверка webhook

```bash
# Через Telegram API
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"

# Ожидаемый ответ:
# "url": "https://your-app.railway.app/webhook"
# "has_custom_certificate": false
# "pending_update_count": 0
```

### 5.3 Тестирование бота

1. Откройте бот в Telegram
2. Отправьте `/start`
3. Проверьте онбординг (4 вопроса)
4. Отправьте текстовое сообщение → должен ответить 💬 Администратор
5. Нажмите **"🔮 Задать вопрос Оракулу"** → должен ответить 🔮 Оракул

## Шаг 6: Мониторинг и отладка

### 6.1 Логи в Railway

```bash
# В Web-интерфейсе
Railway Dashboard → Your Service → Logs

# Через CLI
railway logs

# С фильтрацией
railway logs --filter "ERROR"
railway logs --filter "CRM"
```

### 6.2 Проверка здоровья системы

```bash
# Health endpoint
curl https://your-app.railway.app/health

# Тестирование Admin Panel
curl https://your-app.railway.app/admin/ \
  -H "Authorization: Bearer your_admin_token"

# Тестирование GPT-5 ответов
curl -X POST "https://your-app.railway.app/admin/test/ai-responses?question=Привет&persona=admin&age=25&gender=female" \
  -H "Authorization: Bearer your_admin_token"
```

### 6.3 Метрики и статистика

Railway предоставляет:
- **CPU/Memory usage** (Metrics вкладка)
- **Deployment history** (Deployments)
- **Build logs** (Deployments → Build Logs)
- **Runtime logs** (Logs)

## Шаг 7: Настройка кастомного домена (опционально)

### 7.1 Добавление домена

1. Railway Dashboard → **Settings → Domains**
2. Нажмите **"Custom Domain"**
3. Введите домен: `consultant.yourdomain.com`
4. Настройте DNS:

```
Type: CNAME
Name: consultant
Value: your-app.railway.app
```

### 7.2 Обновление переменных

После добавления домена обновите:

```bash
WEBHOOK_HOST=https://consultant.yourdomain.com
```

## Общие проблемы и решения

### Проблема 1: Webhook не работает

**Симптомы**: Бот не отвечает на сообщения

**Решение**:
```bash
# Проверьте webhook
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"

# Сбросьте webhook
curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Перезапустите сервис в Railway
Railway Dashboard → Deployments → Restart
```

### Проблема 2: База данных не инициализирована

**Симптомы**: Ошибки `relation "users" does not exist`

**Решение**:
```bash
# Подключитесь к БД через Railway CLI
railway connect postgres

# Выполните init.sql
\i /path/to/config/init.sql
```

### Проблема 3: OpenAI API ошибки

**Симптомы**: Fallback промпты вместо GPT-5

**Решение**:
```bash
# Проверьте API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Проверьте логи
railway logs --filter "OpenAI"
```

### Проблема 4: CRM задачи не выполняются

**Симптомы**: Нет проактивных сообщений

**Решение**:
```bash
# Проверьте scheduler в логах
railway logs --filter "CRM"

# Должны быть записи:
# "CRM planning started"
# "CRM dispatcher started"

# Проверьте переменные
HUMANIZED_MAX_CONTACTS_PER_DAY=3
NUDGE_MIN_HOURS=48
```

## Управление через Admin Panel

После успешного деплоя доступна админ панель:

**URL**: `https://your-app.railway.app/admin/`

**Вкладки**:
- **Dashboard**: статистика, CRM тестирование
- **Users**: управление пользователями (добавление премиум, удаление)
- **Tasks**: CRM задачи
- **Templates**: шаблоны сообщений
- **AI Prompts**: промпты для AI
- **AI Sessions**: активные Assistants API сессии

**Команда в боте**: `/admin` (только для ADMIN_IDS)

## Обновление приложения

```bash
# 1. Внесите изменения в код
git add .
git commit -m "Update: your changes"

# 2. Push в main ветку
git push origin main

# 3. Railway автоматически пересоберет и задеплоит

# 4. Проверьте логи
railway logs

# 5. Проверьте health
curl https://your-app.railway.app/health
```

## Бэкап базы данных

```bash
# Через Railway CLI
railway connect postgres

# Экспорт БД
pg_dump > backup.sql

# Импорт БД
psql < backup.sql
```

## Стоимость

**Railway Pricing**:
- **Starter Plan**: $5/месяц кредитов (500 часов)
- **Developer Plan**: $20/месяц кредитов (более высокие лимиты)

**Приблизительная стоимость Bot Oracle**:
- **Приложение**: ~$5/месяц (1 instance, small size)
- **PostgreSQL**: включено в план
- **Bandwidth**: зависит от трафика

**OpenAI API**:
- GPT-4: ~$0.03-0.06 за 1K токенов
- GPT-5 (когда будет доступен): уточняйте на platform.openai.com

## Полезные команды Railway CLI

```bash
# Установка CLI
npm i -g @railway/cli

# Вход в аккаунт
railway login

# Подключение к проекту
railway link

# Просмотр логов
railway logs
railway logs -f  # follow mode

# Выполнение команд в контейнере
railway run python -m app.main

# Переменные окружения
railway variables
railway variables set KEY=VALUE

# Подключение к БД
railway connect postgres

# Статус деплоя
railway status

# Открыть Dashboard
railway open
```

## Дополнительные ресурсы

- **Railway Docs**: https://docs.railway.app
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **OpenAI API**: https://platform.openai.com/docs
- **Project README**: [README.md](README.md)
- **Oracle Deployment**: [ORACLE_DEPLOYMENT.md](ORACLE_DEPLOYMENT.md)

## Поддержка

При возникновении проблем:

1. Проверьте логи: `railway logs`
2. Проверьте health endpoint: `/health`
3. Проверьте переменные: Railway Dashboard → Variables
4. Проверьте webhook: `getWebhookInfo` через Telegram API
5. Обратитесь к документации Railway

---

**Успешного деплоя! 🚀**
