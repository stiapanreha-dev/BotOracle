"""
Keyboards for Bot Oracle
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(has_subscription: bool = False) -> ReplyKeyboardMarkup:
    """Main menu keyboard - Oracle button available for everyone"""
    # All users get the Oracle button (behavior differs based on subscription)
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔮 Задать вопрос Оракулу")],
            [KeyboardButton(text="📨 Сообщение дня")],
            [KeyboardButton(text="💎 Подписка"), KeyboardButton(text="ℹ️ Мой статус")],
        ],
        resize_keyboard=True,
        persistent=True
    )

def get_subscription_menu() -> InlineKeyboardMarkup:
    """Subscription options inline keyboard (old callback version)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣ День (99₽)", callback_data="BUY_DAY")],
            [InlineKeyboardButton(text="2️⃣ Неделя (299₽)", callback_data="BUY_WEEK")],
            [InlineKeyboardButton(text="3️⃣ Месяц (899₽)", callback_data="BUY_MONTH")],
        ]
    )

def get_subscription_menu_with_urls(url_day: str, url_week: str, url_month: str) -> InlineKeyboardMarkup:
    """Subscription options with direct payment URLs"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣ День (99₽)", url=url_day)],
            [InlineKeyboardButton(text="2️⃣ Неделя (299₽)", url=url_week)],
            [InlineKeyboardButton(text="3️⃣ Месяц (899₽)", url=url_month)],
        ]
    )

def get_subscription_menu_with_urls(url_day: str, url_week: str, url_month: str) -> InlineKeyboardMarkup:
    """Subscription options with direct payment URLs"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣ День (99₽)", url=url_day)],
            [InlineKeyboardButton(text="2️⃣ Неделя (299₽)", url=url_week)],
            [InlineKeyboardButton(text="3️⃣ Месяц (899₽)", url=url_month)],
        ]
    )

def get_gender_keyboard() -> ReplyKeyboardMarkup:
    """Gender selection keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")],
            [KeyboardButton(text="Другое")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )