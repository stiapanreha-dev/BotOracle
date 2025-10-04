"""
Bot Oracle Main Application
Runs both Telegram bot and FastAPI web server with enhanced CRM functionality
"""
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import configuration
from app.config import config

# Import database
from app.database.connection import init_db

# Import bot components
from app.bot.onboarding import router as onboarding_router
from app.bot.oracle_handlers import router as oracle_router

# Import API components
from app.api.admin import router as admin_router
from app.api.robokassa import router as robokassa_router

# Import scheduler
from app.scheduler import init_scheduler

# Configuration
BOT_TOKEN = config.BOT_TOKEN
BASE_URL = os.getenv("BASE_URL", "https://consultant.sh3.su")

# Create FastAPI app
app = FastAPI(
    title="Bot Oracle API",
    description="API for Bot Oracle - Telegram bot with Administrator and Oracle personas",
    version="2.0.0"
)

# Include API routers
app.include_router(admin_router)
app.include_router(robokassa_router)

async def create_bot_app():
    """Create and configure bot application"""
    # Initialize bot
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")

    # Create dispatcher with FSM storage
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(onboarding_router)
    dp.include_router(oracle_router)

    logger.info("Bot configured with onboarding and oracle handlers")

    return bot, dp

async def run_bot():
    """Run Telegram bot"""
    try:
        logger.info("Starting Telegram bot...")

        # Initialize database
        await init_db()

        # Create bot and dispatcher
        bot, dp = await create_bot_app()

        # Initialize and start scheduler
        scheduler = init_scheduler(bot)
        await scheduler.start()

        logger.info("Bot Oracle started successfully!")

        # Start polling
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise

async def run_api():
    """Run FastAPI web server"""
    try:
        logger.info("Starting FastAPI server...")

        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)

        await server.serve()

    except Exception as e:
        logger.error(f"Error running API: {e}")
        raise

async def main():
    """Main application entry point"""
    try:
        logger.info("🤖 Bot Oracle starting...")
        logger.info("🎭 Two-persona system: Administrator + Oracle")
        logger.info("🎯 CRM proactive engagement enabled")
        logger.info("👥 Personalized interactions based on user demographics")

        # Run bot and API concurrently
        await asyncio.gather(
            run_bot(),
            run_api()
        )

    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot Oracle shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        exit(1)