# 🚀 План реализации адаптивной CRM системы

**Дата**: 2025-01-17
**Миграция**: ✅ 014_adaptive_cadence.sql (накачена на Railway)

---

## 📋 Этапы реализации

### ✅ Этап 0: Подготовка (COMPLETED)
- [x] Изучение архитектуры CRM (planner, dispatcher, contact_cadence)
- [x] Изучение схемы БД
- [x] Проектирование 3-уровневой системы cadence
- [x] Создание архитектурных диаграмм Mermaid
- [x] Создание миграции БД 014_adaptive_cadence.sql
- [x] Накат миграции на Railway (verified)

---

### 🔄 Этап 1: CadenceManager (models.py)

**Файл**: `app/database/models.py`

**Новый класс: CadenceManager**

Методы:
```python
class CadenceManager:
    @staticmethod
    async def get_cadence_level(user_id: int) -> int
    # Получить текущий уровень (1, 2, 3)

    @staticmethod
    async def update_cadence_level(user_id: int) -> int
    # Пересчитать уровень на основе last_crm_response_at
    # Логика:
    # - days_since = (now - last_crm_response_at).days
    # - if days_since >= 14: level = 3
    # - elif days_since >= 2: level = 2
    # - else: level = 1

    @staticmethod
    async def track_crm_response(user_id: int)
    # Обновить last_crm_response_at = NOW()
    # Восстановить level = 1
    # Логировать событие cadence_level_restored

    @staticmethod
    async def is_response_to_crm(user_id: int) -> bool
    # Проверить: был ли CRM контакт в течение 48h?
    # Запрос к admin_tasks WHERE sent_at > NOW() - INTERVAL '48 hours'

    @staticmethod
    async def stop_cadence(user_id: int, reason: str)
    # Установить level = 3
    # Установить crm_stopped_reason = reason
    # Отменить все pending задачи
    # Создать задачу FAREWELL
```

**Изменения в UserModel:**
```python
# Добавить методы для удобного доступа:
@staticmethod
async def get_crm_info(user_id: int) -> dict
# Вернуть: {cadence_level, last_crm_response_at, crm_stopped_reason}
```

---

### 🔄 Этап 2: Отслеживание ответов (oracle_handlers.py)

**Файл**: `app/bot/oracle_handlers.py`

**Место модификации**: `question_handler()` (строка ~291-718)

**Добавить в начало handler'а (после получения user):**
```python
# Track CRM response if applicable
from app.database.models import CadenceManager

# Check if this is a response to CRM contact
if await CadenceManager.is_response_to_crm(user['id']):
    await CadenceManager.track_crm_response(user['id'])
    logger.info(f"User {user['id']} responded to CRM - cadence restored to Level 1")
```

**Логика:**
1. Проверить: был ли CRM контакт в течение 48h?
2. Если да → обновить last_crm_response_at
3. Если level > 1 → восстановить на level = 1
4. Логировать событие

---

### 🔄 Этап 3: Планирование с учетом level (planner.py)

**Файл**: `app/crm/planner.py`

**Метод**: `plan_for_user()` (строка 32-87)

**Изменения:**

1. **В начале метода** (после получения prefs/cadence):
```python
# Update cadence level based on response time
from app.database.models import CadenceManager
cadence_level = await CadenceManager.update_cadence_level(user_id)

# Level 3: Stop all proactive contacts
if cadence_level == 3:
    logger.info(f"User {user_id} on Level 3 (Stopped) - no tasks created")
    return 0
```

2. **Изменить метод `_get_candidate_tasks()`** (строка 89-122):
```python
async def _get_candidate_tasks(self, user: Dict[str, Any], prefs: Dict[str, Any],
                                cadence: Dict[str, Any], cadence_level: int) -> List[str]:
    """Determine which tasks are candidates for this user"""
    candidates = []
    user_id = user['id']

    # Level 2: Only RECOVERY (no DAILY_MSG as per requirements)
    if cadence_level == 2:
        # Only soft RECOVERY if inactive for 7+ days
        last_seen = user.get('last_seen_at')
        if last_seen and (datetime.now() - last_seen).days >= 7:
            # Check if last RECOVERY was more than 5 days ago
            last_recovery = await self._get_last_task_time(user_id, 'RECOVERY')
            if not last_recovery or (datetime.now() - last_recovery).days >= 5:
                candidates.append('RECOVERY')
        return candidates

    # Level 1: Full CRM logic (existing code)
    # ... [остальной существующий код]
```

**Ключевые изменения:**
- Level 3 → return 0 (никаких задач)
- Level 2 → только RECOVERY раз в 5 дней (NO DAILY_MSG)
- Level 1 → текущая полная логика

---

### 🔄 Этап 4: Прощальное сообщение (planner.py + dispatcher.py)

**A. В planner.py - создание FAREWELL при переходе на Level 3:**

**Метод**: `update_cadence_level()` в CadenceManager

```python
async def update_cadence_level(user_id: int) -> int:
    # ... расчет level ...

    # Если переход на Level 3 - создать FAREWELL
    if new_level == 3 and old_level < 3:
        await CadenceManager.stop_cadence(user_id, 'no_response_14d')

        # Create FAREWELL task
        from app.database.models import AdminTaskModel
        await AdminTaskModel.create_task(
            user_id=user_id,
            task_type='FAREWELL',
            due_at=datetime.now() + timedelta(hours=1),  # Delayed 1h
            payload={'reason': 'no_response_14d'}
        )
```

**B. В dispatcher.py - обработка FAREWELL:**

**Метод**: `_get_task_message()` (строка 102-156)

Уже поддерживает FAREWELL через шаблоны (строка 150-151):
```python
# Fallback to template-based generation for other types
template = await AdminTemplateModel.get_template(task_type, persona.tone)
```

**Ничего не нужно менять** - dispatcher уже умеет обрабатывать любые типы через шаблоны!

---

### 🔄 Этап 5: Автовосстановление (уже реализовано в Этапе 2)

В `track_crm_response()` уже есть логика восстановления на Level 1.

---

## 🧪 Тестовые сценарии

### Сценарий 1: Снижение до Level 2
```python
# 1. Создать тестового пользователя
# 2. Установить last_crm_response_at = NOW() - INTERVAL '3 days'
# 3. Запустить planner
# Ожидание: cadence_level = 2, только RECOVERY задачи
```

### Сценарий 2: Снижение до Level 3
```python
# 1. Установить last_crm_response_at = NOW() - INTERVAL '15 days'
# 2. Запустить planner
# Ожидание: cadence_level = 3, создана FAREWELL задача, все pending отменены
```

### Сценарий 3: Восстановление с Level 2
```python
# 1. Пользователь на Level 2
# 2. Создать CRM контакт (RECOVERY)
# 3. Пользователь отвечает в течение 48h
# Ожидание: cadence_level восстановлен на 1, событие залогировано
```

### Сценарий 4: Восстановление с Level 3
```python
# 1. Пользователь на Level 3
# 2. Пользователь сам пишет в бот
# Ожидание: cadence_level восстановлен на 1, CRM возобновляется
```

---

## 📊 Метрики для мониторинга

После внедрения отслеживать:
- Распределение пользователей по levels (1/2/3)
- % восстановления с Level 2 → 1
- % восстановления с Level 3 → 1
- Среднее время на Level 2 перед переходом на Level 3
- Эффективность FAREWELL сообщений

---

## ✅ Чеклист готовности

- [x] CadenceManager добавлен в models.py (строки 686-859)
  - ✅ get_cadence_level()
  - ✅ update_cadence_level()
  - ✅ track_crm_response()
  - ✅ is_response_to_crm()
  - ✅ stop_cadence()
- [x] Отслеживание ответов в handlers (oracle_handlers.py:318-327)
  - ✅ Проверка CRM контакта в 48ч окне
  - ✅ Автовосстановление на Level 1 при ответе на CRM
  - ✅ Автовосстановление на Level 1 при ЛЮБОЙ активности с Level 2/3
- [x] Planner обновлен с level-aware логикой (planner.py:48-69, 97-143)
  - ✅ Level 3 → 0 задач
  - ✅ Level 2 → только RECOVERY раз в 5 дней
  - ✅ Level 1 → полная CRM логика
- [x] Dispatcher обрабатывает FAREWELL (уже работает через шаблоны)
  - ✅ 3 FAREWELL шаблона в миграции 014
  - ✅ Dispatcher.get_task_message() поддерживает любые типы
- [x] Все сценарии протестированы на Railway
  - ✅ Scenario 1: Level 1→2 (снижение после 2 дней)
  - ✅ Scenario 2: Level 2→3 (снижение после 14 дней + FAREWELL)
  - ✅ Scenario 3: Level 2→1 (восстановление на ответ в 48ч окне)
  - ✅ Scenario 4: Level 3→1 (восстановление на любую активность)
- [x] Логирование работает
  - ✅ models.py:746, 787 - изменения level
  - ✅ handlers.py:321 - ответы на CRM
  - ✅ planner.py:53, 112 - Level 2/3 статусы
- [x] Метрики собираются (через EventModel)
  - ✅ cadence_level_changed
  - ✅ cadence_level_restored
  - ✅ cadence_stopped
  - ⚠️ Dashboard для аналитики не реализован (опционально)
- [x] Документация обновлена

---

**Статус**: ✅ Deployed & Fully Tested on Railway
**Дата завершения**: 2025-01-17
**Коммиты**:
  - Initial implementation: 0a4321e
  - Bug fix (ANY activity restoration): bc95543
