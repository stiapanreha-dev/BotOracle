from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import uuid

from app.database.models import UserModel, SubscriptionModel, QuestionModel, DailyMessageModel, PaymentModel
from app.utils.gpt import get_gpt_response
from app.utils.robokassa import generate_payment_url
from app.config import config
import logging

logger = logging.getLogger(__name__)
router = Router()

# Texts
WELCOME_TEXT = """
🤖 Привет! Я — ваш ежедневный консультант.

🆓 **Бесплатно:** одно вдохновляющее сообщение каждый день
💎 **По подписке:** персональные ответы от ИИ-консультанта

Выберите действие:
"""

NO_SUBSCRIPTION_TEXT = """
💡 Персональные ответы доступны по подписке.

Оформите её — и сможете задавать вопросы нашему ИИ-консультанту!
"""

@router.message(Command("start"))
async def start_handler(message: types.Message):
    user = await UserModel.get_or_create_user(
        message.from_user.id,
        message.from_user.username
    )

    await UserModel.update_last_seen(user['id'])

    kb = InlineKeyboardBuilder()
    kb.button(text="📨 Сообщение дня", callback_data="daily")
    kb.button(text="❓ Задать вопрос", callback_data="ask")
    kb.button(text="💳 Подписка", callback_data="subscription")
    kb.button(text="ℹ️ FAQ", callback_data="faq")
    kb.adjust(2)

    await message.answer(WELCOME_TEXT, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.message(Command("subscribe"))
async def subscribe_command(message: types.Message):
    logger.info(f"Subscribe command received from user {message.from_user.id}")
    user = await UserModel.get_or_create_user(
        message.from_user.id,
        message.from_user.username
    )

    subscription = await SubscriptionModel.get_active_subscription(user['id'])

    if subscription:
        end_date = subscription['ends_at'].strftime("%d.%m.%Y %H:%M")
        text = f"✅ **Ваша подписка активна до:** {end_date}\n\n"
        text += "Вы можете продлить подписку или задать вопрос."
    else:
        text = "💳 **Выберите тариф подписки:**\n\n"
        text += f"📅 **Неделя** — {config.WEEK_PRICE} ₽\n"
        text += f"📆 **Месяц** — {config.MONTH_PRICE} ₽\n\n"
        text += "После оплаты вы сможете задавать персональные вопросы!"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"📅 Неделя — {config.WEEK_PRICE} ₽", callback_data="pay_week")
    kb.button(text=f"📆 Месяц — {config.MONTH_PRICE} ₽", callback_data="pay_month")
    kb.button(text="🏠 Главное меню", callback_data="menu")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "daily")
async def daily_message_handler(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")
    logger.info(f"Daily message callback: {callback.data}")

    user = await UserModel.get_or_create_user(
        callback.from_user.id,
        callback.from_user.username
    )

    # Check if already sent today
    if await DailyMessageModel.is_sent_today(user['id']):
        await callback.message.answer("📨 Вы уже получили сообщение дня! Возвращайтесь завтра за новым.")
        return

    # Get random message
    daily_msg = await DailyMessageModel.get_random_message()
    if not daily_msg:
        await callback.message.answer("😔 Извините, сообщения временно недоступны.")
        return

    # Send message and mark as sent
    await callback.message.answer(f"📨 **Сообщение дня:**\n\n{daily_msg['text']}", parse_mode="Markdown")
    await DailyMessageModel.mark_sent(user['id'], daily_msg['id'])

    # Return to main menu
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Главное меню", callback_data="menu")
    await callback.message.answer("Что еще я могу для вас сделать?", reply_markup=kb.as_markup())

@router.callback_query(F.data == "ask")
async def ask_question_handler(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")

    user = await UserModel.get_or_create_user(
        callback.from_user.id,
        callback.from_user.username
    )

    # Check subscription
    subscription = await SubscriptionModel.get_active_subscription(user['id'])

    if subscription:
        # Check daily limit
        today_questions = await QuestionModel.count_today_questions(user['id'])
        if today_questions >= config.QUESTIONS_PER_DAY:
            await callback.message.answer(
                f"📊 Вы уже задали {config.QUESTIONS_PER_DAY} вопросов сегодня. "
                "Лимит обновится завтра!"
            )
            return

        await callback.message.answer(
            f"💬 Задайте свой вопрос (осталось {config.QUESTIONS_PER_DAY - today_questions} на сегодня).\n\n"
            "Я отвечу в течение нескольких секунд."
        )

    elif user['free_questions_left'] > 0:
        await callback.message.answer(
            f"💬 Задайте свой вопрос.\n\n"
            f"📊 У вас осталось {user['free_questions_left']} бесплатных вопросов."
        )

    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Оформить подписку", callback_data="subscription")
        kb.button(text="🏠 Главное меню", callback_data="menu")
        kb.adjust(1)

        await callback.message.answer(
            NO_SUBSCRIPTION_TEXT,
            reply_markup=kb.as_markup()
        )

@router.callback_query(F.data == "subscription")
async def subscription_handler(callback: types.CallbackQuery):
    logger.info(f"Subscription callback received from user {callback.from_user.id}")
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")
        # Continue processing even if answer fails

    user = await UserModel.get_or_create_user(
        callback.from_user.id,
        callback.from_user.username
    )

    subscription = await SubscriptionModel.get_active_subscription(user['id'])

    if subscription:
        end_date = subscription['ends_at'].strftime("%d.%m.%Y %H:%M")
        text = f"✅ **Ваша подписка активна до:** {end_date}\n\n"
        text += "Вы можете продлить подписку или задать вопрос."
    else:
        text = "💳 **Выберите тариф подписки:**\n\n"
        text += f"📅 **Неделя** — {config.WEEK_PRICE} ₽\n"
        text += f"📆 **Месяц** — {config.MONTH_PRICE} ₽\n\n"
        text += "После оплаты вы сможете задавать персональные вопросы!"

    kb = InlineKeyboardBuilder()
    kb.button(text=f"📅 Неделя — {config.WEEK_PRICE} ₽", callback_data="pay_week")
    kb.button(text=f"📆 Месяц — {config.MONTH_PRICE} ₽", callback_data="pay_month")
    kb.button(text="🏠 Главное меню", callback_data="menu")
    kb.adjust(1)

    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("pay_"))
async def payment_handler(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")
    logger.info(f"Payment handler called for callback: {callback.data} from user {callback.from_user.id}")

    plan = callback.data.split("_")[1]  # week or month

    user = await UserModel.get_or_create_user(
        callback.from_user.id,
        callback.from_user.username
    )

    # Generate payment
    amount = config.WEEK_PRICE if plan == "week" else config.MONTH_PRICE
    plan_code = "WEEK" if plan == "week" else "MONTH"
    # Generate unique numeric invoice ID for Robokassa (must be 1-2147483647)
    inv_id = int(datetime.now().timestamp())

    # Create payment record in database
    await PaymentModel.create_payment(user['id'], inv_id, plan_code, amount)

    # Avoid special characters in description for Robokassa
    username = callback.from_user.username or str(callback.from_user.id)
    # Remove @ symbol and use only safe characters
    username = username.replace('@', '').replace(' ', '')
    description = f"Subscription {plan} for user {username}"

    payment_url = generate_payment_url(amount, inv_id, description)

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить", url=payment_url)
    kb.button(text="🏠 Главное меню", callback_data="menu")
    kb.adjust(1)

    period = "неделю" if plan == "week" else "месяц"
    text = f"💳 **Оплата подписки на {period}**\n\n"
    text += f"💰 Сумма: {amount} ₽\n"
    text += f"🔢 Номер заказа: `{inv_id}`\n\n"
    text += "После успешной оплаты подписка будет активирована автоматически."

    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "faq")
async def faq_handler(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")

    text = """
❓ **Часто задаваемые вопросы**

**Что такое «сообщение дня»?**
Ежедневно бот отправляет мотивирующую цитату или совет — абсолютно бесплатно.

**Как работают персональные вопросы?**
Вы задаете любой вопрос, а ИИ-консультант дает подробный ответ с практическими советами.

**Сколько вопросов можно задать?**
• Бесплатно: 5 вопросов при регистрации
• По подписке: 5 вопросов в день

**Как оформить подписку?**
Нажмите «Подписка» → выберите тариф → оплатите через Robokassa.

**Технические проблемы?**
Пишите администратору — мы поможем!
"""

    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Главное меню", callback_data="menu")

    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "menu")
async def menu_handler(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")
    await start_handler(callback.message)

@router.callback_query()
async def debug_callback_handler(callback: types.CallbackQuery):
    logger.info(f"Unhandled callback received: {callback.data} from user {callback.from_user.id}")
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback {callback.id}: {e}")

@router.message(lambda message: not message.text or not message.text.startswith('/'))
async def question_handler(message: types.Message):
    if not message.text:
        return
    logger.info(f"Question handler received message: {message.text} from user {message.from_user.id}")

    user = await UserModel.get_or_create_user(
        message.from_user.id,
        message.from_user.username
    )

    await UserModel.update_last_seen(user['id'])

    # Check subscription first
    subscription = await SubscriptionModel.get_active_subscription(user['id'])
    can_ask = False

    if subscription:
        # Check daily limit
        today_questions = await QuestionModel.count_today_questions(user['id'])
        if today_questions < config.QUESTIONS_PER_DAY:
            can_ask = True
        else:
            await message.answer(
                f"📊 Вы уже задали {config.QUESTIONS_PER_DAY} вопросов сегодня. "
                "Лимит обновится завтра!"
            )
            return
    elif user['free_questions_left'] > 0:
        can_ask = True
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Оформить подписку", callback_data="subscription")

        await message.answer(
            "🔒 Бесплатные вопросы закончились. Чтобы продолжать, оформите подписку.",
            reply_markup=kb.as_markup()
        )
        return

    if can_ask:
        # Send "thinking" message
        thinking_msg = await message.answer("🤔 Обрабатываю ваш вопрос...")

        # Get GPT response
        answer, tokens = await get_gpt_response(message.text)

        # Delete thinking message
        await thinking_msg.delete()

        # Send answer
        await message.answer(f"💡 **Ответ:**\n\n{answer}", parse_mode="Markdown")

        # Save question
        await QuestionModel.save_question(user['id'], message.text, answer, tokens)

        # Update counters
        if not subscription:
            await UserModel.use_free_question(user['id'])
            remaining = user['free_questions_left'] - 1
            if remaining > 0:
                await message.answer(f"📊 Осталось бесплатных вопросов: {remaining}")
            else:
                kb = InlineKeyboardBuilder()
                kb.button(text="💳 Оформить подписку", callback_data="subscription")
                await message.answer(
                    "🎉 Бесплатные вопросы закончились! Оформите подписку для продолжения.",
                    reply_markup=kb.as_markup()
                )
        else:
            remaining_today = config.QUESTIONS_PER_DAY - await QuestionModel.count_today_questions(user['id'])
            if remaining_today > 0:
                await message.answer(f"📊 Осталось вопросов сегодня: {remaining_today}")

def setup_handlers(dp):
    dp.include_router(router)