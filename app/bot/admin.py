from aiogram import types, Router
from aiogram.filters import Command
from datetime import datetime, date, timedelta
from io import BytesIO

from app.database.models import MetricsModel
from app.database.connection import db
from app.config import config
import logging

logger = logging.getLogger(__name__)
admin_router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    if not text:
        return text
    return str(text).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`').replace('(', '\\(').replace(')', '\\)')

@admin_router.message(Command("admin_today"))
async def admin_today(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    try:
        today = date.today()
        metrics = await MetricsModel.calculate_daily_metrics(today)

        text = f"""
📊 **Статистика за {today.strftime('%d.%m.%Y')}**

👥 DAU: {metrics['dau']}
🆕 Новые пользователи: {metrics['new_users']}
🔄 Активные пользователи: {metrics['active_users']}
🚫 Заблокировано всего: {metrics['blocked_total']}
📨 Получили сообщение дня: {metrics['daily_sent']}
💎 Активные подписчики: {metrics['paid_active']}
🆕💎 Новые подписчики: {metrics['paid_new']}
❓ Задано вопросов: {metrics['questions']}
💰 Выручка: {metrics['revenue']} ₽
"""

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin today command error: {e}")
        await message.answer("❌ Ошибка при получении статистики")

@admin_router.message(Command("admin_range"))
async def admin_range(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Формат: /admin_range YYYY-MM-DD YYYY-MM-DD")
            return

        date1_str, date2_str = parts[1], parts[2]
        date1 = datetime.strptime(date1_str, '%Y-%m-%d').date()
        date2 = datetime.strptime(date2_str, '%Y-%m-%d').date()

        if date1 > date2:
            date1, date2 = date2, date1

        rows = await db.fetch(
            """
            SELECT * FROM fact_daily_metrics
            WHERE d BETWEEN $1 AND $2
            ORDER BY d
            """,
            date1, date2
        )

        if not rows:
            await message.answer("📭 Нет данных за указанный период")
            return

        # Calculate totals
        total_dau = sum(row['dau'] for row in rows)
        total_new = sum(row['new_users'] for row in rows)
        total_revenue = sum(row['revenue'] for row in rows)
        total_questions = sum(row['questions'] for row in rows)
        avg_dau = total_dau / len(rows) if rows else 0

        text = f"""
📊 **Статистика за период {date1_str} — {date2_str}**

📅 Дней: {len(rows)}
👥 Общий DAU: {total_dau}
📊 Средний DAU: {avg_dau:.1f}
🆕 Новых пользователей: {total_new}
❓ Всего вопросов: {total_questions}
💰 Общая выручка: {total_revenue} ₽

Для подробной выгрузки используйте /admin_export
"""

        await message.answer(text, parse_mode="Markdown")

    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Admin range command error: {e}")
        await message.answer("❌ Ошибка при получении статистики")

@admin_router.message(Command("admin_export"))
async def admin_export(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Формат: /admin_export YYYY-MM-DD YYYY-MM-DD")
            return

        date1_str, date2_str = parts[1], parts[2]
        date1 = datetime.strptime(date1_str, '%Y-%m-%d').date()
        date2 = datetime.strptime(date2_str, '%Y-%m-%d').date()

        if date1 > date2:
            date1, date2 = date2, date1

        rows = await db.fetch(
            """
            SELECT * FROM fact_daily_metrics
            WHERE d BETWEEN $1 AND $2
            ORDER BY d
            """,
            date1, date2
        )

        if not rows:
            await message.answer("📭 Нет данных за указанный период")
            return

        # Create TSV content
        headers = ['date', 'dau', 'new_users', 'active_users', 'blocked_total',
                  'daily_sent', 'paid_active', 'paid_new', 'questions', 'revenue']

        tsv_lines = ['\t'.join(headers)]

        for row in rows:
            line = '\t'.join([str(row[header] if row[header] is not None else 0) for header in headers])
            tsv_lines.append(line)

        tsv_content = '\n'.join(tsv_lines)

        # Create file
        file_buffer = BytesIO(tsv_content.encode('utf-8'))
        filename = f"stats_{date1_str}_{date2_str}.tsv"

        file = types.BufferedInputFile(file_buffer.getvalue(), filename=filename)

        await message.answer_document(
            file,
            caption=f"📊 Экспорт статистики за период {date1_str} — {date2_str}"
        )

    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Admin export command error: {e}")
        await message.answer("❌ Ошибка при создании экспорта")

@admin_router.message(Command("admin_paid"))
async def admin_paid(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    try:
        rows = await db.fetch(
            """
            SELECT u.tg_user_id, u.username, s.plan_code, s.ends_at
            FROM subscriptions s
            JOIN users u ON s.user_id = u.id
            WHERE s.status = 'active' AND s.ends_at > now()
            ORDER BY s.ends_at DESC
            LIMIT 50
            """
        )

        if not rows:
            await message.answer("📭 Нет активных подписчиков")
            return

        text = "💎 **Активные подписчики (последние 50):**\n\n"

        for row in rows:
            username = f"@{row['username']}" if row['username'] else f"ID:{row['tg_user_id']}"
            plan = row['plan_code']
            end_date = row['ends_at'].strftime('%d.%m.%Y')
            text += f"• {username} — {plan} до {end_date}\n"

        if len(text) > 4000:
            text = text[:3900] + "\n\n... (список обрезан)"

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin paid command error: {e}")
        await message.answer("❌ Ошибка при получении списка подписчиков")

@admin_router.message(Command("admin_blocked"))
async def admin_blocked(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    try:
        rows = await db.fetch(
            """
            SELECT tg_user_id, username, blocked_at
            FROM users
            WHERE is_blocked = true
            ORDER BY blocked_at DESC
            LIMIT 50
            """
        )

        if not rows:
            await message.answer("✅ Нет заблокированных пользователей")
            return

        text = "🚫 **Заблокированные пользователи (последние 50):**\n\n"

        for row in rows:
            username = f"@{row['username']}" if row['username'] else f"ID:{row['tg_user_id']}"
            blocked_date = row['blocked_at'].strftime('%d.%m.%Y') if row['blocked_at'] else "неизвестно"
            text += f"• {username} — {blocked_date}\n"

        if len(text) > 4000:
            text = text[:3900] + "\n\n... (список обрезан)"

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin blocked command error: {e}")
        await message.answer("❌ Ошибка при получении списка заблокированных")

@admin_router.message(Command("admin_stats"))
async def admin_stats(message: types.Message):
    """Общая статистика бота"""
    if not is_admin(message.from_user.id):
        return

    try:
        # Extract bot ID from token to exclude bot from statistics
        bot_id = int(config.BOT_TOKEN.split(':')[0]) if config.BOT_TOKEN else 0

        # Общая статистика (исключаем бота)
        total_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE tg_user_id != $1", bot_id)
        active_subs = await db.fetchval("SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND ends_at > now()")
        total_questions = await db.fetchval("SELECT COUNT(*) FROM questions")
        blocked_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE is_blocked = true AND tg_user_id != $1", bot_id)

        # Статистика за сегодня (исключаем бота)
        today = date.today()
        today_users = await db.fetchval("SELECT COUNT(*) FROM users WHERE DATE(first_seen_at) = $1 AND tg_user_id != $2", today, bot_id)
        today_questions = await db.fetchval("SELECT COUNT(*) FROM questions WHERE DATE(created_at) = $1", today)

        text = f"""📊 **Статистика бота**

👥 **Пользователи:**
• Всего: {total_users}
• Новых сегодня: {today_users}
• Заблокированных: {blocked_users}

💎 **Подписки:**
• Активных: {active_subs}

❓ **Вопросы:**
• Всего: {total_questions}
• Сегодня: {today_questions}

📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        await message.answer("❌ Ошибка при получении статистики")

@admin_router.message(Command("admin_users"))
async def admin_users(message: types.Message):
    """Список всех пользователей"""
    if not is_admin(message.from_user.id):
        return

    try:
        # Extract bot ID from token to exclude bot from user list
        bot_id = int(config.BOT_TOKEN.split(':')[0]) if config.BOT_TOKEN else 0

        rows = await db.fetch(
            """
            SELECT tg_user_id, username, first_seen_at, last_seen_at, is_blocked,
                   (SELECT COUNT(*) FROM questions WHERE questions.user_id = users.id) as questions_count
            FROM users
            WHERE tg_user_id != $1
            ORDER BY first_seen_at DESC
            LIMIT 50
            """,
            bot_id
        )

        if not rows:
            await message.answer("👥 Пользователей пока нет")
            return

        text = "👥 **Пользователи (последние 50):**\n\n"

        for row in rows:
            username = f"@{row['username']}" if row['username'] else f"ID:{row['tg_user_id']}"
            status = "🚫" if row['is_blocked'] else "✅"
            questions = row['questions_count'] or 0
            join_date = row['first_seen_at'].strftime('%d.%m') if row['first_seen_at'] else "?"

            # Escape markdown special characters in username
            username_escaped = escape_markdown(username)
            text += f"{status} {username_escaped} — {questions}❓ — {join_date}\n"

        if len(text) > 4000:
            text = text[:3900] + "\n\n... (список обрезан)"

        await message.answer(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin users error: {e}")
        await message.answer("❌ Ошибка при получении списка пользователей")

@admin_router.message(Command("admin_message"))
async def admin_message(message: types.Message):
    """Отправка сообщения всем пользователям"""
    if not is_admin(message.from_user.id):
        return

    try:
        # Извлекаем текст сообщения
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            await message.answer("❌ Укажите текст сообщения:\n`/admin_message Ваше сообщение здесь`", parse_mode="Markdown")
            return

        broadcast_text = command_parts[1]

        # Получаем всех активных пользователей
        users = await db.fetch("SELECT tg_user_id FROM users WHERE is_blocked = false")

        if not users:
            await message.answer("❌ Нет активных пользователей для рассылки")
            return

        # Отправляем сообщение
        sent_count = 0
        failed_count = 0

        await message.answer(f"📤 Начинаю рассылку для {len(users)} пользователей...")

        for user in users:
            try:
                await message.bot.send_message(user['tg_user_id'], broadcast_text)
                sent_count += 1
            except Exception:
                failed_count += 1

        await message.answer(f"""✅ Рассылка завершена:
• Отправлено: {sent_count}
• Не доставлено: {failed_count}""")

    except Exception as e:
        logger.error(f"Admin message error: {e}")
        await message.answer("❌ Ошибка при рассылке сообщений")

@admin_router.message(Command("admin_block"))
async def admin_block_user(message: types.Message):
    """Блокировка пользователя"""
    if not is_admin(message.from_user.id):
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            await message.answer("❌ Укажите ID пользователя:\n`/admin_block 123456789`", parse_mode="Markdown")
            return

        try:
            target_user_id = int(command_parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя")
            return

        # Проверяем, существует ли пользователь
        user = await db.fetchrow("SELECT id, username FROM users WHERE tg_user_id = $1", target_user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Блокируем пользователя
        await db.execute(
            "UPDATE users SET is_blocked = true, blocked_at = now() WHERE tg_user_id = $1",
            target_user_id
        )

        username = f"@{user['username']}" if user['username'] else f"ID:{target_user_id}"
        await message.answer(f"🚫 Пользователь {escape_markdown(username)} заблокирован", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin block error: {e}")
        await message.answer("❌ Ошибка при блокировке пользователя")

@admin_router.message(Command("admin_unblock"))
async def admin_unblock_user(message: types.Message):
    """Разблокировка пользователя"""
    if not is_admin(message.from_user.id):
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            await message.answer("❌ Укажите ID пользователя:\n`/admin_unblock 123456789`", parse_mode="Markdown")
            return

        try:
            target_user_id = int(command_parts[1])
        except ValueError:
            await message.answer("❌ Неверный формат ID пользователя")
            return

        # Проверяем, существует ли пользователь
        user = await db.fetchrow("SELECT id, username FROM users WHERE tg_user_id = $1", target_user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Разблокируем пользователя
        await db.execute(
            "UPDATE users SET is_blocked = false, blocked_at = NULL WHERE tg_user_id = $1",
            target_user_id
        )

        username = f"@{user['username']}" if user['username'] else f"ID:{target_user_id}"
        await message.answer(f"✅ Пользователь {escape_markdown(username)} разблокирован", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Admin unblock error: {e}")
        await message.answer("❌ Ошибка при разблокировке пользователя")

@admin_router.message(Command("admin_help"))
async def admin_help(message: types.Message):
    """Помощь по админским командам"""
    if not is_admin(message.from_user.id):
        return

    help_text = """🔧 **Админские команды:**

📊 **Статистика:**
• `/admin_stats` — общая статистика бота
• `/admin_today` — статистика за сегодня
• `/admin_range YYYY-MM-DD YYYY-MM-DD` — статистика за период
• `/admin_export` — экспорт данных в CSV

👥 **Пользователи:**
• `/admin_users` — список пользователей (последние 50)
• `/admin_paid` — список пользователей с подписками
• `/admin_blocked` — список заблокированных пользователей

🛠️ **Управление:**
• `/admin_message <текст>` — рассылка всем пользователям
• `/admin_block <user_id>` — заблокировать пользователя
• `/admin_unblock <user_id>` — разблокировать пользователя

ℹ️ **Информация:**
• `/admin_help` — эта справка"""

    await message.answer(help_text, parse_mode="Markdown")

def setup_admin_handlers(dp):
    dp.include_router(admin_router)