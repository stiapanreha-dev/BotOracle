# Bot Oracle - Deployment Guide

## 🎭 Обновленная архитектура

Bot Oracle теперь реализует полную концепцию из обновленного ТЗ с двумя персонами и CRM-системой:

### ✨ Новые функции:
- **Двухролевая система**: Администратор (эмоциональный) + Оракул (мудрый)
- **GPT-5 интеграция**: Настоящий ИИ вместо заглушек для обеих ролей
- **Анкета пользователя**: возраст + пол → персонализированное общение
- **CRM проактивные контакты**: PING, NUDGE_SUB, DAILY_MSG_PROMPT и др.
- **Эмоциональные шаблоны**: разная тональность для разных возрастов
- **Индивидуальные лимиты**: 5 бесплатных + 10/день по подписке

## 🚀 Быстрое развертывание

### 1. Применить миграцию базы данных

```bash
# На сервере
ssh Pi4-2
cd /home/lexun/ai-consultant

# Применить миграцию
docker compose -f docker-compose.prod.yml exec db psql -U app -d app -f /migrations/002_bot_oracle_upgrade.sql
```

### 2. Переключиться на новую версию

```bash
# Скопировать новые файлы
cp app/main_oracle.py app/main.py

# Обновить переменные окружения
cp .env.oracle.example .env
# ВАЖНО: добавить реальный OPENAI_API_KEY для GPT-5!

# Пересобрать контейнер
docker compose -f docker-compose.prod.yml build --no-cache app
docker compose -f docker-compose.prod.yml restart app
```

### 3. Проверить работу

```bash
# Проверить логи
docker compose -f docker-compose.prod.yml logs app -f

# Проверить API
curl https://consultant.sh3.su/health

# Проверить CRM планировщик
curl -X POST "https://consultant.sh3.su/admin/trigger/crm-planning" \
  -H "Authorization: Bearer supersecret_admin_token"
```

## 🔧 Новые API endpoints

### CRM Management
- `POST /admin/trigger/crm-planning` - Запустить планирование CRM задач
- `POST /admin/trigger/crm-dispatch` - Выполнить запланированные задачи
- `GET /admin/crm/tasks?status=pending&limit=50` - Просмотр CRM задач

### AI Testing
- `POST /admin/test/ai-responses` - Тестирование GPT-5 ответов персон

### Тестирование
```bash
# Планирование задач для всех пользователей
curl -X POST "https://consultant.sh3.su/admin/trigger/crm-planning" \
  -H "Authorization: Bearer supersecret_admin_token"

# Выполнение задач
curl -X POST "https://consultant.sh3.su/admin/trigger/crm-dispatch" \
  -H "Authorization: Bearer supersecret_admin_token"

# Просмотр задач
curl "https://consultant.sh3.su/admin/crm/tasks?status=scheduled&limit=10" \
  -H "Authorization: Bearer supersecret_admin_token"

# Тестирование GPT-5 (Администратор)
curl -X POST "https://consultant.sh3.su/admin/test/ai-responses?question=Как%20дела?&persona=admin&age=22&gender=female" \
  -H "Authorization: Bearer supersecret_admin_token"

# Тестирование GPT-5 (Оракул)
curl -X POST "https://consultant.sh3.su/admin/test/ai-responses?question=В%20чем%20смысл%20жизни?&persona=oracle&age=35&gender=male" \
  -H "Authorization: Bearer supersecret_admin_token"
```

## 📊 CRM система

### Типы проактивных контактов:
- **PING** - "как дела?" каждые 2 дня
- **DAILY_MSG_PROMPT** - предложение получить сообщение дня
- **NUDGE_SUB** - мягкий push на подписку (не чаще 1/48ч, макс 2/неделю)
- **RECOVERY** - возврат неактивных пользователей (после 3+ дней молчания)
- **LIMIT_INFO** - уведомление об остатке лимитов
- **POST_SUB_ONBOARD** - приветствие после покупки подписки

### Ограничения антиспама:
- Макс 3 проактивных контакта/день на пользователя
- Тихие часы: 22:00-08:00 (по локальному времени)
- NUDGE_SUB: не чаще 1 раза в 48 часов, макс 2 раза в неделю

### Планировщик:
- **06:00** - Ежедневное планирование CRM задач
- **Каждую минуту** - Выполнение запланированных задач
- **23:55** - Расчет метрик
- **01:00** - Очистка просроченных подписок

## 👤 Персонализация

### По возрасту:
- **≤25 лет**: "солнышко", "дружище" + игривый тон
- **26-45 лет**: нейтральный тон
- **46+ лет**: "дорогая", "уважаемый" + заботливый тон

### По полу:
- **Женский**: "солнышко", "дорогая"
- **Мужской**: "дружище", "уважаемый"
- **Другое**: "друг" (нейтрально)

## 🔄 Миграция с текущей системы

### Что изменилось:
1. **Таблица users**: добавлены поля `age`, `gender`
2. **Новые таблицы**: `user_prefs`, `contact_cadence`, `admin_tasks`, `admin_templates`, `oracle_questions`
3. **Планировщик**: добавлены CRM задачи
4. **Обработчики**: полностью переписаны под двухролевую систему

### Совместимость:
- ✅ Существующие пользователи сохранены
- ✅ Подписки и платежи работают как прежде
- ✅ Robokassa интеграция не изменилась
- ⚠️ Пользователи должны пройти анкету при первом запуске

## 🧪 Тестирование

### 1. Проверить анкету
```
/start → вводим возраст → выбираем пол → получаем персонализированное приветствие
```

### 2. Проверить роли
- **Без подписки**: Администратор отвечает на 5 бесплатных вопросов
- **С подпиской**: Оракул отвечает на 10 вопросов/день

### 3. Проверить CRM
```bash
# Создать задачи для тестового пользователя
curl -X POST "https://consultant.sh3.su/admin/trigger/crm-planning" \
  -H "Authorization: Bearer supersecret_admin_token"

# Выполнить задачи
curl -X POST "https://consultant.sh3.su/admin/trigger/crm-dispatch" \
  -H "Authorization: Bearer supersecret_admin_token"
```

## 🐛 Troubleshooting

### База данных
```sql
-- Проверить новые таблицы
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'admin_%' OR table_name LIKE 'user_%';

-- Проверить шаблоны
SELECT type, tone, count(*) FROM admin_templates GROUP BY type, tone;

-- Проверить задачи
SELECT type, status, count(*) FROM admin_tasks GROUP BY type, status;
```

### Логи
```bash
# Следить за CRM активностью
docker compose -f docker-compose.prod.yml logs app -f | grep -i "crm\|admin\|task"

# Проверить планировщик
docker compose -f docker-compose.prod.yml logs app -f | grep -i "scheduler"
```

## 📈 Мониторинг

### Метрики в admin_tasks:
- Количество запланированных задач
- Успешно отправленных сообщений
- Заблокированных пользователей

### Новые события в events:
- `oracle_answer` - ответы от обеих ролей
- `admin_task_created` - создание CRM задач

---

## 🤖 GPT-5 Интеграция

### Роли и промпты:

#### **Администратор** 🎭
- **Тональность**: эмоциональная, игривая (≤25), заботливая (46+)
- **Обращения**: "солнышко", "дружище", "дорогая", "уважаемый"
- **Задачи**: короткие ответы, мягкие продажи, эмоциональная поддержка
- **Ограничения**: максимум 300 символов

#### **Оракул** 🔮
- **Тональность**: мудрая, спокойная, размеренная
- **Стиль**: глубокие размышления, практические советы
- **Задачи**: философские вопросы, жизненные советы, личностный рост
- **Ограничения**: максимум 500 символов

### Настройка качества:
```python
# Администратор
reasoning={"effort": "medium"}  # Средняя сложность
text={"verbosity": "medium"}    # Умеренная подробность

# Оракул
reasoning={"effort": "high"}    # Высокая сложность
text={"verbosity": "high"}      # Подробные ответы
```

### Fallback система:
- Если OpenAI API недоступен → автоматически используются заглушки
- Логирование всех AI запросов и ответов
- Защита от слишком длинных ответов

---

**Bot Oracle готов к запуску! 🎭✨**

Теперь у нас есть полноценный двухперсонный бот с GPT-5, умной CRM-системой и персонализированным общением, который будет проактивно вовлекать пользователей и мягко подталкивать к покупке подписки.