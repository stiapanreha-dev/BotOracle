import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BOT_URL: str = os.getenv("BOT_URL", "https://t.me/ai_consultant_bot")

    # Robokassa
    ROBO_LOGIN: str = os.getenv("ROBO_LOGIN", "")
    ROBO_PASS1: str = os.getenv("ROBO_PASS1", "")
    ROBO_PASS2: str = os.getenv("ROBO_PASS2", "")
    ROBO_TEST_MODE: bool = os.getenv("ROBO_TEST_MODE", "1") == "1"

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/telegram_bot")

    # Admin
    ADMIN_IDS: List[int] = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "supersecret")

    # App Settings
    FREE_QUESTIONS: int = int(os.getenv("FREE_QUESTIONS", "5"))
    QUESTIONS_PER_DAY: int = int(os.getenv("QUESTIONS_PER_DAY", "5"))
    WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "")
    WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")

    # Subscription prices (in rubles)
    WEEK_PRICE: float = float(os.getenv("WEEK_PRICE", "99"))
    MONTH_PRICE: float = float(os.getenv("MONTH_PRICE", "299"))

    # Proxy settings
    SOCKS5_PROXY: str = os.getenv("SOCKS5_PROXY", "")

config = Config()