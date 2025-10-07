"""
Engagement Manager - manages user engagement sessions for subscription conversion.

This module handles:
- Creating engagement sessions after daily messages
- Tracking messages and engagement level
- AI-powered conversation analysis
- Generating personalized Oracle question offers
- Managing session lifecycle (pause, conversion)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.database.connection import db
from app.services.ai_router import call_admin_ai
import logging

logger = logging.getLogger(__name__)


class EngagementManager:
    """Manages engagement sessions for conversion funnel optimization"""

    # Configuration constants
    LOW_ENGAGEMENT_THRESHOLD = 2  # 1-2 messages = low engagement
    HIGH_ENGAGEMENT_THRESHOLD = 3  # 3+ messages = high engagement
    COLLECTION_MIN_MESSAGES = 5  # Minimum messages before AI analysis
    COLLECTION_MAX_MESSAGES = 10  # Maximum messages to collect
    SESSION_TIMEOUT_HOURS = 24  # Auto-pause after 24 hours

    @staticmethod
    async def start_session(user_id: int) -> Optional[int]:
        """
        Create new engagement session for user after daily message.

        Args:
            user_id: Internal user ID (from users table)

        Returns:
            session_id if created, None if user already has active session
        """
        # Check if user already has an active session
        existing = await db.fetchrow(
            """
            SELECT id FROM engagement_sessions
            WHERE user_id = $1
            AND status IN ('engaging', 'collecting', 'offered')
            """,
            user_id
        )

        if existing:
            logger.info(f"User {user_id} already has active engagement session {existing['id']}")
            return None

        # Create new session
        session = await db.fetchrow(
            """
            INSERT INTO engagement_sessions (user_id, status, started_at, updated_at)
            VALUES ($1, 'engaging', NOW(), NOW())
            RETURNING id
            """,
            user_id
        )

        session_id = session['id']
        logger.info(f"Created engagement session {session_id} for user {user_id}")
        return session_id

    @staticmethod
    async def get_active_session(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get active engagement session for user.

        Returns:
            Session dict or None
        """
        session = await db.fetchrow(
            """
            SELECT * FROM engagement_sessions
            WHERE user_id = $1
            AND status IN ('engaging', 'collecting', 'offered')
            ORDER BY started_at DESC
            LIMIT 1
            """,
            user_id
        )

        return dict(session) if session else None

    @staticmethod
    async def track_message(session_id: int, role: str, content: str) -> None:
        """
        Track message in engagement session.

        Args:
            session_id: Engagement session ID
            role: 'user' or 'admin'
            content: Message text
        """
        # Save message
        await db.execute(
            """
            INSERT INTO session_messages (session_id, role, content, created_at)
            VALUES ($1, $2, $3, NOW())
            """,
            session_id, role, content
        )

        # Increment messages count
        await db.execute(
            """
            UPDATE engagement_sessions
            SET messages_count = messages_count + 1,
                updated_at = NOW()
            WHERE id = $1
            """,
            session_id
        )

        logger.debug(f"Tracked {role} message in session {session_id}")

    @staticmethod
    async def should_analyze(session_id: int) -> bool:
        """
        Check if session is ready for AI analysis.

        Returns:
            True if session has 5-10 messages and status is 'collecting'
        """
        session = await db.fetchrow(
            "SELECT status, messages_count FROM engagement_sessions WHERE id = $1",
            session_id
        )

        if not session:
            return False

        # Must be in collecting phase and have enough messages
        return (
            session['status'] == 'collecting' and
            session['messages_count'] >= EngagementManager.COLLECTION_MIN_MESSAGES
        )

    @staticmethod
    async def check_engagement_level(session_id: int) -> str:
        """
        Check engagement level based on USER messages count (not total).
        Admin messages don't count towards engagement threshold.

        Returns:
            'low', 'high', or 'ready_to_analyze'
        """
        # Count only USER messages for engagement level
        user_message_count = await db.fetchval(
            """
            SELECT COUNT(*) FROM session_messages
            WHERE session_id = $1 AND role = 'user'
            """,
            session_id
        )

        if user_message_count is None:
            return 'low'

        # 1-2 user messages = low engagement
        # 3-4 user messages = high engagement (collecting)
        # 5+ user messages = ready to analyze
        if user_message_count <= EngagementManager.LOW_ENGAGEMENT_THRESHOLD:
            return 'low'
        elif user_message_count < EngagementManager.COLLECTION_MIN_MESSAGES:
            return 'high'
        else:
            return 'ready_to_analyze'

    @staticmethod
    async def transition_to_collecting(session_id: int) -> None:
        """Move session from 'engaging' to 'collecting' status"""
        await db.execute(
            """
            UPDATE engagement_sessions
            SET status = 'collecting', updated_at = NOW()
            WHERE id = $1 AND status = 'engaging'
            """,
            session_id
        )
        logger.info(f"Session {session_id} transitioned to collecting phase")

    @staticmethod
    async def analyze_and_offer(session_id: int, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze conversation context and generate Oracle question offer.

        Args:
            session_id: Engagement session ID
            user_context: User demographics (age, gender, archetype, etc.)

        Returns:
            {
                'problem_summary': str,
                'suggested_question': str,
                'offer_message': str
            }
        """
        # Get conversation history
        messages = await db.fetch(
            """
            SELECT role, content, created_at
            FROM session_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id
        )

        if not messages:
            logger.warning(f"No messages found for session {session_id}")
            return None

        # Build conversation context for AI
        conversation_text = "\n".join([
            f"{'Пользователь' if msg['role'] == 'user' else 'Администратор'}: {msg['content']}"
            for msg in messages
        ])

        # Create AI prompt for problem analysis
        analysis_prompt = f"""Проанализируй следующий диалог между Администратором и пользователем.

Контекст пользователя:
- Возраст: {user_context.get('age', 'неизвестен')}
- Пол: {user_context.get('gender', 'неизвестен')}
- Архетип: {user_context.get('archetype', 'неизвестен')}

Диалог:
{conversation_text}

Твоя задача:
1. Определи главную проблематику или вопрос, который беспокоит пользователя
2. Сформулируй глубокий философский вопрос к Оракулу на основе этой проблематики

ВАЖНО: problem_summary должен быть написан во ВТОРОМ ЛИЦЕ (обращение к пользователю как "ты", "тебя", "твой").
Например: "тебя беспокоит...", "ты чувствуешь...", "ты ищешь...", "тебе нужно..."

Ответ дай строго в формате JSON:
{{
  "problem_summary": "Краткое резюме проблемы в 1-2 предложениях во втором лице",
  "suggested_question": "Вопрос к Оракулу"
}}
"""

        # Call AI to analyze conversation
        logger.info(f"Analyzing conversation for session {session_id}")
        analysis = await EngagementManager._call_ai_for_analysis(analysis_prompt)

        if not analysis:
            logger.error(f"Failed to analyze session {session_id}")
            return None

        # Save analysis to session
        await db.execute(
            """
            UPDATE engagement_sessions
            SET problem_summary = $1,
                suggested_question = $2,
                status = 'offered',
                offered_at = NOW(),
                updated_at = NOW()
            WHERE id = $3
            """,
            analysis['problem_summary'],
            analysis['suggested_question'],
            session_id
        )

        # Build offer message
        offer_message = f"""💬 Слушай, по результатам нашего разговора я вижу, что {analysis['problem_summary'].lower()}

А что если задать Оракулу такой вопрос: "{analysis['suggested_question']}"?

Мне кажется, для тебя это сейчас актуально. Хочешь, я передам ему этот вопрос?"""

        logger.info(f"Generated offer for session {session_id}")

        return {
            'problem_summary': analysis['problem_summary'],
            'suggested_question': analysis['suggested_question'],
            'offer_message': offer_message
        }

    @staticmethod
    async def _call_ai_for_analysis(prompt: str) -> Optional[Dict[str, Any]]:
        """Call AI to analyze conversation and extract problem/question"""
        try:
            # Use OpenAI Chat Completions API directly for analysis (no persona)
            import openai
            import json
            import os

            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            # Request JSON response format
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты аналитик диалогов. Анализируй разговоры и извлекай главную проблематику пользователя. Отвечай ТОЛЬКО валидным JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                response_format={"type": "json_object"}  # Force JSON output
            )

            response_text = response.choices[0].message.content
            logger.info(f"AI analysis response: {response_text}")

            # Parse JSON response
            analysis = json.loads(response_text)

            # Validate response structure
            if 'problem_summary' in analysis and 'suggested_question' in analysis:
                return analysis
            else:
                logger.error(f"AI response missing required fields: {analysis}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Response was: {response_text if 'response_text' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Error calling AI for analysis: {e}")
            return None

    @staticmethod
    async def pause_session(session_id: int) -> None:
        """Pause session due to low engagement"""
        await db.execute(
            """
            UPDATE engagement_sessions
            SET status = 'paused', updated_at = NOW()
            WHERE id = $1
            """,
            session_id
        )
        logger.info(f"Session {session_id} paused due to low engagement")

    @staticmethod
    async def mark_converted(session_id: int) -> None:
        """Mark session as converted (user accepted Oracle offer)"""
        await db.execute(
            """
            UPDATE engagement_sessions
            SET status = 'converted', converted = TRUE, updated_at = NOW()
            WHERE id = $1
            """,
            session_id
        )
        logger.info(f"Session {session_id} marked as converted")

    @staticmethod
    async def cleanup_old_sessions(days: int = 7) -> int:
        """
        Clean up old sessions that are inactive.

        Args:
            days: Delete sessions older than this many days

        Returns:
            Number of deleted sessions
        """
        cutoff = datetime.now() - timedelta(days=days)

        result = await db.execute(
            """
            DELETE FROM engagement_sessions
            WHERE updated_at < $1
            AND status IN ('paused', 'converted')
            """,
            cutoff
        )

        # Extract number of deleted rows from result
        deleted_count = int(result.split()[-1]) if result else 0

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old engagement sessions")

        return deleted_count

    @staticmethod
    async def auto_pause_stale_sessions(hours: int = 24) -> int:
        """
        Auto-pause sessions that have been inactive for too long.

        Args:
            hours: Pause sessions inactive for this many hours

        Returns:
            Number of paused sessions
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        result = await db.execute(
            """
            UPDATE engagement_sessions
            SET status = 'paused', updated_at = NOW()
            WHERE updated_at < $1
            AND status IN ('engaging', 'collecting')
            """,
            cutoff
        )

        paused_count = int(result.split()[-1]) if result else 0

        if paused_count > 0:
            logger.info(f"Auto-paused {paused_count} stale engagement sessions")

        return paused_count
