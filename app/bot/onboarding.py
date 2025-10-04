"""
Onboarding handlers for Oracle Lounge
Handles archetype-based onboarding: 4 situational questions to determine user archetype
"""
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
import logging

from app.bot.states import OnboardingStates
from app.database.models import UserModel, OnboardingModel, ArchetypeModel
from app.services.smart_messages import (
    generate_welcome,
    generate_onboarding_questions,
    validate_response,
    analyze_archetype,
    smart_messages
)

logger = logging.getLogger(__name__)
router = Router()

# Maximum attempts for invalid responses per question
MAX_INVALID_ATTEMPTS = 2

@router.message(F.text == "/start")
async def start_command(message: types.Message, state: FSMContext):
    """Start command - begin archetype-based onboarding"""
    try:
        # Get or create user
        user = await UserModel.get_or_create_user(
            message.from_user.id,
            message.from_user.username
        )

        # Check if user already completed onboarding
        if user.get('onboarding_completed'):
            # User already onboarded, show welcome back message
            await message.answer(
                "С возвращением! 🌟 Рад тебя видеть снова."
            )

            # Check subscription and send appropriate main menu
            from app.bot.keyboards import get_main_menu
            from app.database.models import SubscriptionModel
            subscription = await SubscriptionModel.get_active_subscription(user['id'])
            has_subscription = subscription is not None

            await message.answer("Выбери действие:", reply_markup=get_main_menu(has_subscription))

            await state.clear()
            return

        # Clear any previous onboarding attempts
        await OnboardingModel.clear_user_responses(user['id'])

        # Generate AI welcome message
        welcome = await generate_welcome()

        # Generate 4 onboarding questions
        questions = await generate_onboarding_questions()

        # Save questions and initial state to FSM
        await state.update_data(
            user_id=user['id'],
            questions=questions,
            current_question=1,
            invalid_attempts=0
        )

        # Send welcome and first question
        await message.answer(welcome, reply_markup=ReplyKeyboardRemove())
        await message.answer(
            f"Вопрос 1 из 4:\n\n{questions[0]}"
        )

        await state.set_state(OnboardingStates.waiting_for_q1)

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        error_msg = await smart_messages.generate_error_message("onboarding_start")
        await message.answer(error_msg)

async def process_question_response(message: types.Message, state: FSMContext, question_num: int):
    """Generic handler for processing onboarding question responses"""
    try:
        data = await state.get_data()
        user_id = data['user_id']
        questions = data['questions']
        invalid_attempts = data.get('invalid_attempts', 0)

        # Get current question
        question_text = questions[question_num - 1]
        user_response = message.text.strip()

        # Validate response with AI
        validation = await validate_response(question_text, user_response)

        if not validation['is_valid']:
            # Response is invalid (trolling, too short, etc.)
            invalid_attempts += 1

            if invalid_attempts >= MAX_INVALID_ATTEMPTS:
                # Max attempts reached, reset onboarding
                error_msg = await smart_messages.generate_invalid_response_message(
                    question_num, 0
                )
                await message.answer(error_msg)
                await OnboardingModel.clear_user_responses(user_id)
                await state.clear()
                return

            # Give another chance
            attempts_left = MAX_INVALID_ATTEMPTS - invalid_attempts
            error_msg = await smart_messages.generate_invalid_response_message(
                question_num, attempts_left
            )
            await message.answer(error_msg)
            await state.update_data(invalid_attempts=invalid_attempts)
            return

        # Response is valid, save it
        await OnboardingModel.save_response(
            user_id=user_id,
            question_number=question_num,
            question_text=question_text,
            user_response=user_response,
            is_valid=True,
            ai_analysis=validation
        )

        # Reset invalid attempts counter
        await state.update_data(invalid_attempts=0)

        # Move to next question or complete onboarding
        if question_num < 4:
            # Ask next question
            next_num = question_num + 1
            next_question = questions[next_num - 1]

            await message.answer(f"Вопрос {next_num} из 4:\n\n{next_question}")

            # Set next state
            next_state = {
                2: OnboardingStates.waiting_for_q2,
                3: OnboardingStates.waiting_for_q3,
                4: OnboardingStates.waiting_for_q4
            }[next_num]

            await state.set_state(next_state)
        else:
            # All questions answered, analyze archetype
            await message.answer("Анализирую твои ответы... ⏳")

            # Get all responses
            responses = await OnboardingModel.get_user_responses(user_id)
            response_data = [
                {
                    'question': r['question_text'],
                    'response': r['user_response']
                }
                for r in responses
            ]

            # Analyze archetype
            archetype_result = await analyze_archetype(response_data)

            # Update user archetype
            await ArchetypeModel.update_user_archetype(
                user_id=user_id,
                primary=archetype_result['primary'],
                secondary=archetype_result.get('secondary'),
                archetype_data={
                    'confidence': archetype_result['confidence'],
                    'explanation': archetype_result['explanation']
                }
            )

            # Generate final message
            final_msg = await smart_messages.generate_onboarding_final_message(
                archetype_result['primary'],
                archetype_result['confidence']
            )

            await message.answer(final_msg)

            # Show features and main menu
            await message.answer(
                "🎁 Что у меня есть для тебя:\n"
                "• Ежедневное сообщение (жми «Сообщение дня»)\n"
                "• Общение со мной — неограниченно и бесплатно\n"
                "• 5 бесплатных вопросов Оракулу (кнопка 🔮)\n"
                "• Премиум подписка для полного доступа к Оракулу\n\n"
                "Попробуй написать любой вопрос или получи сегодняшнее сообщение! ✨",
                reply_markup=ReplyKeyboardRemove()
            )

            # Create main menu (new users don't have subscription)
            from app.bot.keyboards import get_main_menu
            await message.answer("Выбери действие:", reply_markup=get_main_menu(has_subscription=False))

            await state.set_state(OnboardingStates.completed)

            # Initialize user preferences
            await UserModel.init_user_preferences(user_id)

            logger.info(
                f"User {message.from_user.id} completed archetype onboarding: "
                f"primary={archetype_result['primary']}, "
                f"secondary={archetype_result.get('secondary')}, "
                f"confidence={archetype_result['confidence']}"
            )

    except Exception as e:
        logger.error(f"Error processing question {question_num}: {e}")
        error_msg = await smart_messages.generate_error_message("onboarding_question")
        await message.answer(error_msg)


@router.message(OnboardingStates.waiting_for_q1)
async def process_q1(message: types.Message, state: FSMContext):
    """Process answer to question 1"""
    await process_question_response(message, state, 1)


@router.message(OnboardingStates.waiting_for_q2)
async def process_q2(message: types.Message, state: FSMContext):
    """Process answer to question 2"""
    await process_question_response(message, state, 2)


@router.message(OnboardingStates.waiting_for_q3)
async def process_q3(message: types.Message, state: FSMContext):
    """Process answer to question 3"""
    await process_question_response(message, state, 3)


@router.message(OnboardingStates.waiting_for_q4)
async def process_q4(message: types.Message, state: FSMContext):
    """Process answer to question 4"""
    await process_question_response(message, state, 4)


# NOTE: No catch-all handler here to allow oracle_handlers to process messages
# Onboarding only handles /start and FSM states