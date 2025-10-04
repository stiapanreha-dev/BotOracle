"""
FSM States for Bot Oracle onboarding questionnaire and Oracle questions
"""
from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    """States for user onboarding questionnaire"""
    waiting_for_age = State()
    waiting_for_gender = State()
    completed = State()

class OracleQuestionStates(StatesGroup):
    """States for Oracle question flow (subscribers only)"""
    waiting_for_question = State()

class AdminQuestionStates(StatesGroup):
    """States for Admin question flow (non-subscribers via Oracle button)"""
    waiting_for_question = State()