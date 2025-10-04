#!/usr/bin/env python3
"""
Local development runner for Bot Oracle
Runs in polling mode instead of webhook
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for local development"""
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage

    # Import database
    from app.database.connection import db

    # Import bot components
    from app.bot.onboarding import router as onboarding_router
    from app.bot.oracle_handlers import router as oracle_router

    # Import scheduler
    from app.scheduler import init_scheduler

    BOT_TOKEN = os.getenv("BOT_TOKEN")

    logger.info("🤖 Bot Oracle starting in LOCAL MODE...")
    logger.info("🎭 Two-persona system: Administrator + Oracle")
    logger.info("🎯 CRM proactive engagement enabled")
    logger.info("👥 Personalized interactions based on user demographics")
    logger.info("📡 Running in POLLING mode (no webhook)")

    # Connect to database
    await db.connect()
    logger.info("Database connected")

    # Initialize bot
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")

    # Create dispatcher with FSM storage
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(onboarding_router)
    dp.include_router(oracle_router)

    logger.info("Bot configured with onboarding and oracle handlers")

    # Initialize scheduler
    scheduler = init_scheduler(bot)
    await scheduler.start()
    logger.info("Scheduler started")

    logger.info("Bot Oracle startup completed! Starting polling...")

    try:
        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Cleanup
        logger.info("Shutting down...")
        await scheduler.stop()
        await db.disconnect()
        await bot.session.close()
        logger.info("Shutdown completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")