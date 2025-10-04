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
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import markdown
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import configuration
from app.config import config

# Import database
from app.database.connection import db

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
app.include_router(robokassa_router, prefix="/api")

# Mount static files for admin panel
app.mount("/admin", StaticFiles(directory="app/static/admin", html=True), name="admin")

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

# Global bot instance for webhook
bot_instance = None
dp_instance = None

@app.on_event("startup")
async def startup_event():
    """Initialize bot and scheduler on app startup"""
    global bot_instance, dp_instance

    try:
        logger.info("🤖 Bot Oracle starting...")
        logger.info("🎭 Two-persona system: Administrator + Oracle")
        logger.info("🎯 CRM proactive engagement enabled")
        logger.info("👥 Personalized interactions based on user demographics")

        # Initialize database
        await db.connect()

        # Create bot and dispatcher
        bot_instance, dp_instance = await create_bot_app()

        # Initialize and start scheduler
        scheduler = init_scheduler(bot_instance)
        await scheduler.start()

        # Set webhook
        webhook_url = f"{BASE_URL}/webhook"
        await bot_instance.set_webhook(webhook_url)

        logger.info(f"Webhook set to {webhook_url}")
        logger.info("Bot Oracle startup completed!")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on app shutdown"""
    global bot_instance

    try:
        logger.info("Bot Oracle shutting down...")

        if bot_instance:
            await bot_instance.delete_webhook()
            await bot_instance.session.close()

        logger.info("Bot Oracle shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@app.post("/webhook")
async def webhook_handler(update: dict):
    """Handle incoming webhook updates"""
    global dp_instance

    if dp_instance:
        from aiogram.types import Update
        telegram_update = Update(**update)
        await dp_instance.feed_update(bot=bot_instance, update=telegram_update)

    return {"status": "ok"}

@app.get("/readme", response_class=HTMLResponse)
async def get_readme():
    """Serve README.md as HTML"""
    try:
        readme_path = Path(__file__).parent.parent / "README.md"

        if not readme_path.exists():
            return HTMLResponse(
                content="<html><body><h1>README.md not found</h1></body></html>",
                status_code=404
            )

        # Read README content
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()

        # Convert markdown to HTML
        html_content = markdown.markdown(
            readme_content,
            extensions=['fenced_code', 'tables', 'toc', 'nl2br']
        )

        # Wrap in styled HTML
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Bot Oracle - Documentation</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    line-height: 1.6;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 2rem;
                    background: #f5f5f5;
                    color: #333;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                    color: #2c3e50;
                }}
                h1 {{
                    border-bottom: 3px solid #3498db;
                    padding-bottom: 0.5em;
                }}
                h2 {{
                    border-bottom: 2px solid #95a5a6;
                    padding-bottom: 0.3em;
                }}
                code {{
                    background: #f8f8f8;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    padding: 2px 6px;
                    font-family: 'Courier New', Courier, monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background: #2c3e50;
                    color: #ecf0f1;
                    padding: 1em;
                    border-radius: 5px;
                    overflow-x: auto;
                    line-height: 1.4;
                }}
                pre code {{
                    background: none;
                    border: none;
                    color: #ecf0f1;
                    padding: 0;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                    background: white;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #3498db;
                    color: white;
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                a {{
                    color: #3498db;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                blockquote {{
                    border-left: 4px solid #3498db;
                    padding-left: 1em;
                    margin-left: 0;
                    color: #555;
                    background: #f9f9f9;
                    padding: 0.5em 1em;
                }}
                ul, ol {{
                    padding-left: 2em;
                }}
                li {{
                    margin: 0.5em 0;
                }}
                .content {{
                    background: white;
                    padding: 2em;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
            </style>
        </head>
        <body>
            <div class="content">
                {html_content}
            </div>
        </body>
        </html>
        """

        return HTMLResponse(content=styled_html)

    except Exception as e:
        logger.error(f"Error serving README: {e}")
        return HTMLResponse(
            content=f"<html><body><h1>Error loading README</h1><p>{str(e)}</p></body></html>",
            status_code=500
        )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Bot Oracle",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)