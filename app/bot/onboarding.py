"""
Onboarding handlers for Bot Oracle
Handles user questionnaire: age and gender for personalization
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import logging

from app.bot.states import OnboardingStates
from app.database.models import UserModel
from app.services.persona import persona_factory, get_admin_response

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text == "/start")
async def start_command(message: types.Message, state: FSMContext):
    """Start command - begin onboarding questionnaire"""
    try:
        # Get or create user
        user = await UserModel.get_or_create_user(
            message.from_user.id,
            message.from_user.username
        )

        # Check if user already completed onboarding
        if user.get('age') and user.get('gender'):
            # User already onboarded, show welcome back message
            persona = persona_factory(user)
            await message.answer(
                persona.wrap("с возвращением! 🌟 я помню тебя. что будем делать?")
            )

            # Check subscription and send appropriate main menu
            from app.bot.keyboards import get_main_menu
            from app.database.models import SubscriptionModel
            subscription = await SubscriptionModel.get_active_subscription(user['id'])
            has_subscription = subscription is not None

            await message.answer("Выбери действие:", reply_markup=get_main_menu(has_subscription))

            await state.clear()
            return

        # Start onboarding questionnaire
        await message.answer(
            "👋 Привет! Я Bot Oracle — твой персональный помощник.\n\n"
            "Чтобы общаться было комфортнее, давай познакомимся!\n\n"
            "Сколько тебе лет? (напиши число)"
        )
        await state.set_state(OnboardingStates.waiting_for_age)

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@router.message(OnboardingStates.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    """Process user age input"""
    try:
        # Validate age input
        try:
            age = int(message.text.strip())
            if age < 10 or age > 120:
                await message.answer(
                    "🤔 Кажется, возраст должен быть от 10 до 120 лет.\n"
                    "Попробуй ещё раз:"
                )
                return
        except ValueError:
            await message.answer(
                "🤔 Нужно написать число (возраст).\n"
                "Например: 25"
            )
            return

        # Save age to state
        await state.update_data(age=age)

        # Ask for gender
        gender_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")],
                [KeyboardButton(text="Другое")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await message.answer(
            "Отлично! 👍\n\n"
            "Теперь скажи, ты мужчина или женщина?\n"
            "(это поможет мне общаться с тобой в правильном тоне)",
            reply_markup=gender_keyboard
        )
        await state.set_state(OnboardingStates.waiting_for_gender)

    except Exception as e:
        logger.error(f"Error processing age: {e}")
        await message.answer("Произошла ошибка. Попробуйте ещё раз.")

@router.message(OnboardingStates.waiting_for_gender)
async def process_gender(message: types.Message, state: FSMContext):
    """Process user gender input"""
    try:
        gender_text = message.text.strip().lower()

        # Map gender input
        if gender_text in ["мужчина", "муж", "м", "мальчик"]:
            gender = "male"
        elif gender_text in ["женщина", "жен", "ж", "девочка", "девушка"]:
            gender = "female"
        elif gender_text in ["другое", "не указывать", "неопределенно"]:
            gender = "other"
        else:
            await message.answer(
                "🤔 Пожалуйста, выбери один из вариантов:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")],
                        [KeyboardButton(text="Другое")]
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
            return

        # Get age from state
        data = await state.get_data()
        age = data.get('age')

        # Update user profile in database
        await UserModel.update_profile(message.from_user.id, age, gender)

        # Get updated user data and create persona
        user = await UserModel.get_by_tg_id(message.from_user.id)
        persona = persona_factory(user)

        # Complete onboarding
        welcome_text = get_admin_response("welcome_new", persona)

        await message.answer(
            f"{welcome_text}\n\n"
            "🎁 Что у меня есть для тебя:\n"
            "• Ежедневное сообщение (жми «Сообщение дня»)\n"
            "• 5 бесплатных персональных ответов\n"
            "• Доступ к мудрому Оракулу (по подписке)\n\n"
            "Попробуй написать любой вопрос или получи сегодняшнее сообщение! ✨",
            reply_markup=ReplyKeyboardRemove()
        )

        # Create main menu (new users don't have subscription)
        from app.bot.keyboards import get_main_menu
        await message.answer("Выбери действие:", reply_markup=get_main_menu(has_subscription=False))

        await state.set_state(OnboardingStates.completed)

        # Initialize user preferences
        await UserModel.init_user_preferences(user['id'])

        logger.info(f"User {message.from_user.id} completed onboarding: age={age}, gender={gender}")

    except Exception as e:
        logger.error(f"Error processing gender: {e}")
        await message.answer("Произошла ошибка. Попробуйте ещё раз.")

# NOTE: No catch-all handler here to allow oracle_handlers to process messages
# Onboarding only handles /start and FSM states