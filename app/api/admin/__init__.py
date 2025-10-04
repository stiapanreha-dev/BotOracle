"""
Admin API module - refactored from single file into modular structure
"""
from fastapi import APIRouter

# Import all sub-routers
from app.api.admin import auth
from app.api.admin import stats
from app.api.admin import users
from app.api.admin import subscriptions
from app.api.admin import events
from app.api.admin import tasks
from app.api.admin import templates
from app.api.admin import daily_messages
from app.api.admin import triggers
from app.api.admin import prompts

# Export auth functions for use in other modules
from app.api.admin.auth import verify_admin_token, validate_telegram_webapp_data

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(auth.router, tags=["auth"])
router.include_router(stats.router, tags=["stats"])
router.include_router(users.router, tags=["users"])
router.include_router(subscriptions.router, tags=["subscriptions"])
router.include_router(events.router, tags=["events"])
router.include_router(tasks.router, tags=["tasks"])
router.include_router(templates.router, tags=["templates"])
router.include_router(daily_messages.router, tags=["daily_messages"])
router.include_router(triggers.router, tags=["triggers"])
router.include_router(prompts.router, tags=["prompts"])

__all__ = [
    'router',
    'verify_admin_token',
    'validate_telegram_webapp_data'
]