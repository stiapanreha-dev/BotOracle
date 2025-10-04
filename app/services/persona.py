"""
Persona Factory - creates personalized messaging based on user demographics
Implements the humanized admin character with emotional, playful communication
"""
import os
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Configuration
USE_ADMIN_PERSONA = os.getenv("USE_ADMIN_PERSONA", "true").lower() == "true"

def build_address(age: Optional[int], gender: Optional[str]) -> str:
    """Build personalized address based on user demographics"""
    if gender == "female":
        if age and age <= 25:
            return "солнышко"
        else:
            return "дорогая"
    elif gender == "male":
        if age and age <= 25:
            return "дружище"
        else:
            return "уважаемый"
    else:
        # gender == "other" or None
        return "друг"

def get_tone_for_user(age: Optional[int], gender: Optional[str]) -> str:
    """Determine communication tone based on demographics"""
    if age and age <= 25:
        return "playful"
    elif age and age >= 46:
        return "care"
    else:
        return "playful"  # Default for 26-45

class PersonaFactory:
    """Factory for creating personalized admin messages"""

    def __init__(self, user_data: Dict[str, Any]):
        self.age = user_data.get("age")
        self.gender = user_data.get("gender")
        self.address = build_address(self.age, self.gender)
        self.tone = get_tone_for_user(self.age, self.gender)

    def wrap(self, text: str, context: Optional[str] = None) -> str:
        """Wrap message with persona addressing"""
        if not USE_ADMIN_PERSONA:
            return text

        # Add context-specific modifications
        if context == "free_answer":
            return f"{self.address}, {text}"
        elif context == "free_empty":
            return f"{self.address}, {text}"
        elif context == "oracle_limit":
            return f"{self.address}, {text}"
        else:
            return f"{self.address}, {text}"

    def format_daily_repeat(self) -> str:
        """Special message for repeat daily message request"""
        if self.age and self.age <= 25:
            return f"эй, {self.address}, второе предсказание за день? 🙄 не-а. завтра приходи 😉"
        else:
            return f"{self.address}, сегодня уже было сообщение. завтра будет новое 😊"

    def format_free_exhausted(self) -> str:
        """Message when free questions are exhausted"""
        if self.tone == "playful":
            return f"ну всё, {self.address}, я выговорилась 😅 бесплатных больше нет. хочешь дальше — зови оракула 💎"
        else:
            return f"{self.address}, бесплатные ответы закончились. для продолжения нужна подписка 💎"

    def format_oracle_limit(self) -> str:
        """Message when Oracle daily limit is reached"""
        if self.tone == "playful":
            return f"сегодня ты пытливее, чем Google, {self.address} 😅 10 вопросов уже сжёг. завтра продолжим!"
        else:
            return f"{self.address}, лимит 10 вопросов на сегодня исчерпан. завтра будет новый день!"

    def format_subscription_activated(self, plan: str) -> str:
        """Message when subscription is activated"""
        return f"готово ✅ теперь ты VIP, {self.address}. оракул ждёт твоих вопросов. помни: максимум 10 в день."

    def format_free_remaining(self, remaining: int) -> str:
        """Message with remaining free questions count"""
        if self.tone == "playful":
            return f"лови ответ, {self.address} 🔮 осталось {remaining} — думай, на что их потратить 😉"
        else:
            return f"{self.address}, вот твой ответ. осталось бесплатных ответов: {remaining}"

def persona_factory(user_data: Dict[str, Any]) -> PersonaFactory:
    """Create PersonaFactory instance for user"""
    return PersonaFactory(user_data)

# Admin persona responses for different scenarios
ADMIN_RESPONSES = {
    "welcome_new": {
        "playful": "привет, {address}! 🤗 я твой админ. у нас есть бесплатное сообщение каждый день и 5 персональных ответов в подарок.",
        "care": "добро пожаловать, {address}! я буду твоим помощником. дарю тебе ежедневные сообщения и 5 бесплатных ответов."
    },
    "subscription_menu": {
        "playful": f"хочешь по-взрослому, {'{address}'}? 1️⃣ День 2️⃣ Неделя 3️⃣ Месяц — выбирай, я подключу тебе оракула 🔮",
        "care": f"{'{address}'}, выбери подписку: 1️⃣ День 2️⃣ Неделя 3️⃣ Месяц. после оплаты получишь доступ к оракулу."
    }
}

def get_admin_response(response_type: str, persona: PersonaFactory) -> str:
    """Get admin response with persona formatting"""
    responses = ADMIN_RESPONSES.get(response_type, {})
    template = responses.get(persona.tone, responses.get("playful", ""))
    return template.format(address=persona.address)