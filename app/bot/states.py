"""
FSM States for Oracle Lounge onboarding questionnaire and Oracle questions
"""
from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    """States for archetype-based onboarding questionnaire"""
    waiting_for_q1 = State()
    waiting_for_q2 = State()
    waiting_for_q3 = State()
    waiting_for_q4 = State()
    completed = State()

class OracleQuestionStates(StatesGroup):
    """States for Oracle question flow (subscribers only)"""
    waiting_for_question = State()
    waiting_for_clarification = State()

class AdminQuestionStates(StatesGroup):
    """States for Admin question flow (non-subscribers via Oracle button)"""
    waiting_for_question = State()