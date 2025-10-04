"""
AI Router - Dynamic routing between Chat Completions and Assistants API
Controlled by USE_ASSISTANTS_API environment variable
"""
import os
import logging
from typing import Dict, Any, AsyncGenerator

logger = logging.getLogger(__name__)

# Check which implementation to use
USE_ASSISTANTS_API = os.getenv("USE_ASSISTANTS_API", "false").lower() in ["true", "1", "yes"]

if USE_ASSISTANTS_API:
    logger.info("🔀 AI Router: Using OpenAI Assistants API (stateful sessions)")
    from app.services.assistant_ai_client import (
        call_admin_ai as _call_admin_ai,
        call_oracle_ai as _call_oracle_ai,
        call_oracle_ai_stream as _call_oracle_ai_stream
    )
else:
    logger.info("🔀 AI Router: Using Chat Completions API (stateless)")
    from app.services.ai_client import (
        call_admin_ai as _call_admin_ai,
        call_oracle_ai as _call_oracle_ai,
        call_oracle_ai_stream as _call_oracle_ai_stream
    )


async def call_admin_ai(question: str, user_context: Dict[str, Any] = None) -> str:
    """
    Route Administrator AI calls to selected implementation

    Args:
        question: User's question
        user_context: Dict with user info (age, gender, has_subscription, user_id)

    Returns:
        AI generated response
    """
    return await _call_admin_ai(question, user_context or {})


async def call_oracle_ai(question: str, user_context: Dict[str, Any] = None) -> str:
    """
    Route Oracle AI calls to selected implementation

    Args:
        question: User's question
        user_context: Dict with user info (age, gender, user_id)

    Returns:
        AI generated response
    """
    return await _call_oracle_ai(question, user_context or {})


async def call_oracle_ai_stream(question: str, user_context: Dict[str, Any] = None) -> AsyncGenerator[str, None]:
    """
    Route Oracle AI streaming calls to selected implementation

    Args:
        question: User's question
        user_context: Dict with user info (age, gender, user_id)

    Yields:
        Text chunks from AI response
    """
    async for chunk in _call_oracle_ai_stream(question, user_context or {}):
        yield chunk
