"""
Bot Oracle main handlers implementing two-role system:
1. Administrator - emotional, proactive, handles daily messages and free questions
2. Oracle - wise, calm, answers only subscription questions (10/day limit)
"""
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatAction
from datetime import date
import logging

from app.database.models import (
    UserModel, DailyMessageModel, OracleQuestionModel,
    SubscriptionModel, AdminTaskModel
)
from app.services.persona import persona_factory, get_admin_response
from app.bot.keyboards import get_main_menu, get_subscription_menu
from app.bot.states import OnboardingStates, OracleQuestionStates, AdminQuestionStates

logger = logging.getLogger(__name__)
router = Router()

# AI integration - using router to switch between implementations
from app.services.ai_router import call_admin_ai, call_oracle_ai, call_oracle_ai_stream
import asyncio

@router.message(F.text == "📨 Сообщение дня")
async def daily_message_handler(message: types.Message):
    """Handle daily message requests - generates personalized AI message"""
    logger.info(f"Daily message button pressed by user {message.from_user.id}")
    try:
        user = await UserModel.get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("Напиши /start чтобы начать!")
            return

        # Check if user completed onboarding
        if not user.get('age') or not user.get('gender'):
            await message.answer("Сначала давай познакомимся! Напиши /start")
            return

        persona = persona_factory(user)

        # Check if already received today
        if await DailyMessageModel.is_sent_today(user['id']):
            repeat_message = persona.format_daily_repeat()
            await message.answer(repeat_message)
            return

        # Generate personalized daily message using AI
        await message.answer(persona.wrap("генерирую для тебя сегодняшнее сообщение... 🎨"))

        # Build prompt for AI to generate daily message
        age = user.get('age', 25)
        gender = user.get('gender', 'other')

        # Variety of styles and emotions for random selection
        import random
        styles = ['мотивирующий', 'вдохновляющий', 'поддерживающий', 'философский', 'дружеский']
        emotions = ['позитивная', 'спокойная', 'энергичная', 'мудрая', 'теплая']

        style = random.choice(styles)
        emotion = random.choice(emotions)

        prompt = f"""Создай короткое мотивирующее/вдохновляющее сообщение дня для пользователя.

Характеристики пользователя:
- Возраст: {age}
- Пол: {gender}

Стиль: {style}
Эмоция: {emotion}

Требования:
- 1-2 предложения максимум
- Личное обращение, эмоциональное
- Без банальностей
- На русском языке
- Без эмодзи (их добавит персона)"""

        # Show typing status while generating
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

        # Generate message using Administrator AI
        user_context = {'age': age, 'gender': gender, 'user_id': user['id']}
        ai_message = await call_admin_ai(prompt, user_context)

        # Send generated message
        await message.answer(persona.wrap(ai_message))

        # Mark as sent (AI-generated, no template ID needed)
        await DailyMessageModel.mark_sent(user['id'])

        # Update last seen
        await UserModel.update_last_seen(user['id'])

        logger.info(f"Daily message generated for user {user['id']}: style={style}, emotion={emotion}")

    except Exception as e:
        logger.error(f"Error in daily message handler: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "💎 Подписка")
async def subscription_menu_handler(message: types.Message):
    """Handle subscription menu"""
    logger.info(f"Subscription button pressed by user {message.from_user.id}")
    try:
        user = await UserModel.get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("Напиши /start чтобы начать!")
            return

        # Check if user completed onboarding
        if not user.get('age') or not user.get('gender'):
            await message.answer("Сначала давай познакомимся! Напиши /start")
            return

        persona = persona_factory(user)

        # Check current subscription
        subscription = await SubscriptionModel.get_active_subscription(user['id'])

        if subscription:
            await message.answer(
                persona.wrap(f"у тебя уже есть подписка до {subscription['ends_at'].strftime('%d.%m.%Y')} ✅\n"
                           "можешь задавать вопросы оракулу (до 10 в день)")
            )
        else:
            # Generate payment URLs for all plans
            from app.utils.robokassa import generate_payment_url
            from datetime import datetime
            from app.database.models import PaymentModel

            # Create payments and URLs
            inv_id_day = int(datetime.now().timestamp())
            inv_id_week = inv_id_day + 1
            inv_id_month = inv_id_day + 2

            await PaymentModel.create_payment(user['id'], inv_id_day, 'DAY', 99.0)
            await PaymentModel.create_payment(user['id'], inv_id_week, 'WEEK', 299.0)
            await PaymentModel.create_payment(user['id'], inv_id_month, 'MONTH', 899.0)

            url_day = generate_payment_url(99.0, str(inv_id_day), "Подписка на день")
            url_week = generate_payment_url(299.0, str(inv_id_week), "Подписка на неделю")
            url_month = generate_payment_url(899.0, str(inv_id_month), "Подписка на месяц")

            # Import here to avoid circular imports
            from app.bot.keyboards import get_subscription_menu_with_urls

            menu_text = get_admin_response("subscription_menu", persona)
            await message.answer(menu_text, reply_markup=get_subscription_menu_with_urls(url_day, url_week, url_month))

        await UserModel.update_last_seen(user['id'])

    except Exception as e:
        logger.error(f"Error in subscription menu: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "ℹ️ Мой статус")
async def status_handler(message: types.Message):
    """Show user status and limits"""
    try:
        user = await UserModel.get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("Напиши /start чтобы начать!")
            return

        persona = persona_factory(user)

        # Get subscription info
        subscription = await SubscriptionModel.get_active_subscription(user['id'])

        status_text = "📊 Твой статус:\n\n"

        if subscription:
            oracle_used = await OracleQuestionModel.count_today_questions(user['id'], 'SUB')
            status_text += f"✅ Подписка активна до {subscription['ends_at'].strftime('%d.%m.%Y')}\n"
            status_text += f"🔮 Вопросов оракулу сегодня: {oracle_used}/10\n"
        else:
            status_text += f"🎁 Бесплатных ответов: {user.get('free_questions_left', 0)}/5\n"
            status_text += f"💎 Подписка: не активна\n"

        daily_sent = await DailyMessageModel.is_sent_today(user['id'])
        status_text += f"📨 Сообщение дня: {'✅ получено' if daily_sent else '⏳ доступно'}\n"

        await message.answer(persona.wrap(status_text))
        await UserModel.update_last_seen(user['id'])

    except Exception as e:
        logger.error(f"Error in status handler: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "🔮 Задать вопрос Оракулу")
async def oracle_question_button_handler(message: types.Message, state: FSMContext):
    """Handle Oracle question button - route to Oracle (subscribers) or Admin (non-subscribers)"""
    logger.info(f"Oracle question button pressed by user {message.from_user.id}")
    try:
        user = await UserModel.get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("Напиши /start чтобы начать!")
            return

        # Check if user completed onboarding
        if not user.get('age') or not user.get('gender'):
            await message.answer("Сначала давай познакомимся! Напиши /start")
            return

        persona = persona_factory(user)

        # Check if user has active subscription
        subscription = await SubscriptionModel.get_active_subscription(user['id'])

        if not subscription:
            # No subscription - use limited questions (5 free)
            free_left = user.get('free_questions_left', 0)

            if free_left <= 0:
                # No free questions left
                await message.answer(
                    persona.wrap("у тебя закончились бесплатные вопросы 😔\n\n💎 Получи подписку для безлимитного доступа:"),
                    reply_markup=get_subscription_menu()
                )
                return

            await state.set_state(AdminQuestionStates.waiting_for_question)

            await message.answer(
                persona.wrap(f"задавай свой вопрос! 💬\n\n"
                           f"_У тебя осталось {free_left} {'вопрос' if free_left == 1 else 'вопроса' if free_left < 5 else 'вопросов'} из 5 бесплатных_"),
                parse_mode="Markdown"
            )
            return

        # Has subscription - route to Oracle
        # Check daily limit
        oracle_used = await OracleQuestionModel.count_today_questions(user['id'], 'SUB')

        if oracle_used >= 10:
            # Daily Oracle limit reached
            limit_message = persona.format_oracle_limit()
            await message.answer(limit_message)
            return

        # Set FSM state to waiting for Oracle question
        await state.set_state(OracleQuestionStates.waiting_for_question)

        remaining = 10 - oracle_used
        await message.answer(
            f"🔮 **Оракул готов ответить на твой вопрос.**\n\n"
            f"Осталось {remaining} вопрос{'ов' if remaining > 1 else ''} на сегодня.\n\n"
            f"_Напиши свой вопрос текстом:_",
            parse_mode="Markdown"
        )

        await UserModel.update_last_seen(user['id'])

    except Exception as e:
        logger.error(f"Error in oracle question button handler: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(lambda message: not message.text.startswith('/') and message.text not in ["📨 Сообщение дня", "💎 Подписка", "ℹ️ Мой статус", "🔮 Задать вопрос Оракулу"])
async def question_handler(message: types.Message, state: FSMContext):
    """Handle all text questions - route to Administrator or Oracle based on FSM state"""
    try:
        # Check if user is in onboarding
        current_state = await state.get_state()
        if current_state in [OnboardingStates.waiting_for_age.state, OnboardingStates.waiting_for_gender.state]:
            # Let onboarding handler process this
            return

        user = await UserModel.get_by_tg_id(message.from_user.id)
        if not user:
            await message.answer("Напиши /start чтобы начать!")
            return

        # Check if user completed onboarding
        if not user.get('age') or not user.get('gender'):
            await message.answer("Сначала давай познакомимся! Напиши /start")
            return

        persona = persona_factory(user)
        question = message.text.strip()

        # Check if user has active subscription
        subscription = await SubscriptionModel.get_active_subscription(user['id'])

        # Check if user is in Oracle question state (button was pressed)
        is_oracle_question = current_state == OracleQuestionStates.waiting_for_question.state
        is_admin_question = current_state == AdminQuestionStates.waiting_for_question.state

        if is_admin_question and not subscription:
            # ADMIN BUTTON MODE - non-subscriber asking via Oracle button (USES counter)
            free_left = user.get('free_questions_left', 0)

            if free_left <= 0:
                # No free questions left
                exhausted_message = persona.format_free_exhausted()
                await message.answer(
                    f"{exhausted_message}\n\n💎 Получи подписку:",
                    reply_markup=get_subscription_menu()
                )
                await state.clear()
                return

            # Show typing status while generating
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

            user_context = {
                'age': user.get('age'),
                'gender': user.get('gender'),
                'has_subscription': False,
                'free_chat': False,
                'user_id': user['id']
            }
            answer = await call_admin_ai(question, user_context)

            # Use one free question AFTER successful AI response
            success = await UserModel.use_free_question(user['id'])
            if not success:
                await message.answer(persona.wrap("упс, что-то пошло не так. попробуй ещё раз"))
                await state.clear()
                return

            # Save question (track as ADMIN_BUTTON for analytics)
            await OracleQuestionModel.save_question(
                user['id'], question, answer, source='ADMIN_BUTTON'
            )

            remaining = free_left - 1
            if remaining > 0:
                response = persona.format_free_remaining(remaining)
                full_response = f"{answer}\n\n{response}"
            else:
                response = persona.format_free_exhausted()
                full_response = f"{answer}\n\n{response}\n\n💎 Получи подписку:"
                await message.answer(full_response, reply_markup=get_subscription_menu())
                await state.clear()
                return

            await message.answer(full_response)

            # Clear FSM state after response
            await state.clear()

        elif is_oracle_question and subscription:
            # ORACLE MODE - subscription active
            oracle_used = await OracleQuestionModel.count_today_questions(user['id'], 'SUB')

            if oracle_used >= 10:
                # Daily Oracle limit reached
                limit_message = persona.format_oracle_limit()
                await message.answer(limit_message)
                return

            # Call Oracle AI with streaming (wise, profound response)
            user_context = {'age': user.get('age'), 'gender': user.get('gender'), 'user_id': user['id']}

            # Send initial message
            oracle_msg = await message.answer("🔮 **Оракул размышляет...**", parse_mode="Markdown")

            # Stream the response
            full_answer = ""
            display_text = "🔮 **Оракул отвечает:**\n\n"
            last_update = asyncio.get_event_loop().time()

            async for chunk in call_oracle_ai_stream(question, user_context):
                full_answer += chunk
                display_text_with_answer = display_text + full_answer

                # Update message every 0.5 seconds to avoid rate limits
                current_time = asyncio.get_event_loop().time()
                if current_time - last_update >= 0.5:
                    try:
                        await oracle_msg.edit_text(display_text_with_answer, parse_mode="Markdown")
                        last_update = current_time
                    except Exception:
                        pass  # Ignore errors if message is the same

            # Final update with counter
            remaining = 10 - oracle_used - 1
            final_text = display_text + full_answer

            if remaining > 0:
                final_text += f"\n\n_Осталось {remaining} вопрос{'ов' if remaining > 1 else ''} на сегодня._"
            else:
                final_text += f"\n\n_Лимит вопросов на сегодня исчерпан. Завтра будет новый день._"

            await oracle_msg.edit_text(final_text, parse_mode="Markdown")

            # Save question and answer
            await OracleQuestionModel.save_question(
                user['id'], question, full_answer, source='SUB'
            )

            # Clear FSM state after Oracle response
            await state.clear()

        else:
            # ADMINISTRATOR MODE - ordinary text messages (FREE for everyone, NO counter)
            # Both subscribers and non-subscribers can chat freely via regular text

            # Show typing status while generating
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

            user_context = {
                'age': user.get('age'),
                'gender': user.get('gender'),
                'has_subscription': subscription is not None,
                'free_chat': True,  # Free chat - no counter mentions
                'user_id': user['id']
            }
            answer = await call_admin_ai(question, user_context)

            # Save question without counter (source is CHAT_FREE for analytics)
            await OracleQuestionModel.save_question(
                user['id'], question, answer, source='CHAT_FREE'
            )

            # Simple response without counter info
            await message.answer(answer)

        await UserModel.update_last_seen(user['id'])

        # Create THANKS task for CRM
        await AdminTaskModel.create_task(
            user['id'],
            'THANKS',
            due_at=None,  # Immediate
            payload={'triggered_by': 'user_message'}
        )

        # Reschedule upcoming PING/NUDGE tasks when user replies
        rescheduled_count = await AdminTaskModel.reschedule_upcoming_tasks(
            user['id'],
            task_types=['PING', 'NUDGE_SUB']
        )
        if rescheduled_count > 0:
            logger.info(f"Rescheduled {rescheduled_count} upcoming tasks for user {user['id']}")

    except Exception as e:
        logger.error(f"Error in question handler: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

# Callback handlers for subscription
@router.callback_query(F.data.startswith("BUY_"))
async def buy_subscription_callback(callback: types.CallbackQuery):
    """Handle subscription purchase callbacks"""
    try:
        plan = callback.data.replace("BUY_", "")  # DAY, WEEK, MONTH

        user = await UserModel.get_by_tg_id(callback.from_user.id)
        if not user:
            await callback.answer("Ошибка: пользователь не найден")
            return

        persona = persona_factory(user)

        # Import here to avoid circular imports
        from app.utils.robokassa import generate_payment_url
        from datetime import datetime
        import uuid

        # Create payment record
        inv_id = int(datetime.now().timestamp())
        plan_prices = {"DAY": 99.0, "WEEK": 299.0, "MONTH": 899.0}
        amount = plan_prices.get(plan, 99.0)

        from app.database.models import PaymentModel
        await PaymentModel.create_payment(user['id'], inv_id, plan, amount)

        # Generate payment URL
        plan_descriptions = {"DAY": "Подписка на день", "WEEK": "Подписка на неделю", "MONTH": "Подписка на месяц"}
        description = plan_descriptions.get(plan, "Подписка Bot Oracle")
        payment_url = generate_payment_url(amount, str(inv_id), description)

        await callback.message.answer(
            persona.wrap(f"отличный выбор! переходи к оплате:\n{payment_url}")
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error in subscription callback: {e}")
        await callback.answer("Произошла ошибка. Попробуйте позже.")

@router.message(F.text == "/admin")
async def admin_panel_handler(message: types.Message):
    """Open admin panel for authorized admins"""
    from app.config import config

    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔️ Эта команда доступна только администраторам")
        return

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[
            types.InlineKeyboardButton(
                text="📊 Открыть админ-панель",
                web_app=types.WebAppInfo(url="https://consultant.sh3.su/admin/")
            )
        ]]
    )

    await message.answer(
        "👨‍💼 Добро пожаловать в админ-панель!\n\n"
        "Нажми кнопку ниже, чтобы открыть панель управления.",
        reply_markup=keyboard
    )

@router.message(F.text == "/help")
async def help_handler(message: types.Message):
    """Show help information"""
    help_text = """
🤖 **Bot Oracle - Справка**

**Доступные команды:**
• 📨 Сообщение дня - получить ежедневное сообщение
• 💎 Подписка - управление подпиской
• ℹ️ Мой статус - показать текущий статус
• /help - эта справка

**Как это работает:**
1. **Администратор** (я) - отвечаю на бесплатные вопросы (5 шт), выдаю сообщения дня, помогаю с подпиской
2. **Оракул** - мудрые ответы по подписке (до 10 вопросов в день)

**Подписка:**
• День - 99₽
• Неделя - 299₽
• Месяц - 899₽

Просто задавай вопросы текстом! 💫
    """

    await message.answer(help_text, parse_mode="Markdown")

# Debug handler - catch all unhandled messages
@router.message()
async def debug_unhandled_message(message: types.Message):
    """Log unhandled messages for debugging"""
    logger.warning(f"UNHANDLED MESSAGE: text=\"{message.text}\", from_user={message.from_user.id}")
    await message.answer(f"Debug: получено сообщение \"{message.text}\"")

