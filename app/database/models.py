from datetime import datetime, date
from typing import Optional, Dict, Any
from app.database.connection import db
from app.config import config
import logging
import json

logger = logging.getLogger(__name__)

class UserModel:
    @staticmethod
    async def get_or_create_user(tg_user_id: int, username: str = None) -> dict:
        user = await db.fetchrow(
            "SELECT * FROM users WHERE tg_user_id = $1",
            tg_user_id
        )

        if not user:
            # Create new user with 5 free questions, no profile yet
            await db.execute(
                """
                INSERT INTO users (tg_user_id, username, first_seen_at, free_questions_left)
                VALUES ($1, $2, now(), $3)
                """,
                tg_user_id, username, config.FREE_QUESTIONS
            )

            await EventModel.log_event(
                user_id=None,
                event_type='start',
                meta={'tg_user_id': tg_user_id, 'username': username}
            )

            user = await db.fetchrow(
                "SELECT * FROM users WHERE tg_user_id = $1",
                tg_user_id
            )

        return dict(user)

    @staticmethod
    async def get_by_tg_id(tg_user_id: int) -> Optional[dict]:
        """Get user by telegram ID"""
        user = await db.fetchrow(
            "SELECT * FROM users WHERE tg_user_id = $1",
            tg_user_id
        )
        return dict(user) if user else None

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[dict]:
        """Get user by internal ID"""
        user = await db.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )
        return dict(user) if user else None

    @staticmethod
    async def update_profile(tg_user_id: int, age: int, gender: str):
        """Update user profile with age and gender"""
        await db.execute(
            "UPDATE users SET age = $1, gender = $2 WHERE tg_user_id = $3",
            age, gender, tg_user_id
        )

    @staticmethod
    async def update_user_info(user_id: int, age: int = None, gender: str = None):
        """Update user info by internal user ID"""
        if age is not None and gender is not None:
            await db.execute(
                "UPDATE users SET age = $1, gender = $2 WHERE id = $3",
                age, gender, user_id
            )
        elif age is not None:
            await db.execute(
                "UPDATE users SET age = $1 WHERE id = $2",
                age, user_id
            )
        elif gender is not None:
            await db.execute(
                "UPDATE users SET gender = $1 WHERE id = $2",
                gender, user_id
            )

    @staticmethod
    async def init_user_preferences(user_id: int):
        """Initialize user preferences and cadence settings"""
        # Create user preferences if not exists
        await db.execute(
            """
            INSERT INTO user_prefs (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id
        )

        # Create contact cadence if not exists
        await db.execute(
            """
            INSERT INTO contact_cadence (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id
        )

    @staticmethod
    async def update_last_seen(user_id: int):
        await db.execute(
            "UPDATE users SET last_seen_at = now() WHERE id = $1",
            user_id
        )

    @staticmethod
    async def set_blocked(user_id: int, blocked: bool = True):
        await db.execute(
            "UPDATE users SET is_blocked = $1, blocked_at = now() WHERE id = $2",
            blocked, user_id
        )

    @staticmethod
    async def use_free_question(user_id: int) -> bool:
        result = await db.execute(
            """
            UPDATE users
            SET free_questions_left = free_questions_left - 1
            WHERE id = $1 AND free_questions_left > 0
            """,
            user_id
        )
        return result == "UPDATE 1"

class SubscriptionModel:
    @staticmethod
    async def get_active_subscription(user_id: int) -> Optional[dict]:
        subscription = await db.fetchrow(
            """
            SELECT * FROM subscriptions
            WHERE user_id = $1 AND status = 'active' AND ends_at > now()
            ORDER BY ends_at DESC LIMIT 1
            """,
            user_id
        )
        return dict(subscription) if subscription else None

    @staticmethod
    async def create_subscription(user_id: int, plan_code: str, amount: float,
                                inv_id: int = None) -> int:
        days = 1 if plan_code == 'DAY' else (7 if plan_code == 'WEEK' else 30)

        subscription_id = await db.fetchval(
            """
            INSERT INTO subscriptions (user_id, plan_code, ends_at, robokassa_inv_id, amount)
            VALUES ($1, $2, now() + interval '%s days', $3, $4)
            RETURNING id
            """ % days,
            user_id, plan_code, str(inv_id) if inv_id else None, amount
        )

        await EventModel.log_event(
            user_id=user_id,
            event_type='subscription_started',
            meta={'plan_code': plan_code, 'amount': amount, 'days': days}
        )

        return subscription_id

    @staticmethod
    async def extend_subscription(user_id: int, plan_code: str, amount: float):
        days = 1 if plan_code == 'DAY' else (7 if plan_code == 'WEEK' else 30)

        await db.execute(
            """
            UPDATE subscriptions
            SET ends_at = GREATEST(ends_at, now()) + interval '%s days'
            WHERE user_id = $1 AND status = 'active'
            """ % days,
            user_id
        )

class QuestionModel:
    @staticmethod
    async def count_today_questions(user_id: int) -> int:
        count = await db.fetchval(
            """
            SELECT COUNT(*) FROM questions
            WHERE user_id = $1 AND DATE(created_at) = CURRENT_DATE
            """,
            user_id
        )
        return count or 0

    @staticmethod
    async def save_question(user_id: int, question: str, answer: str, tokens: int = 0):
        await db.execute(
            """
            INSERT INTO questions (user_id, question_text, answer_text, tokens_used)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, question, answer, tokens
        )

        await EventModel.log_event(
            user_id=user_id,
            event_type='question_asked',
            meta={'tokens': tokens}
        )

class DailyMessageModel:
    @staticmethod
    async def get_random_message() -> Optional[dict]:
        message = await db.fetchrow(
            """
            SELECT * FROM daily_messages
            WHERE is_active = true
            ORDER BY RANDOM()
            LIMIT 1
            """
        )
        return dict(message) if message else None

    @staticmethod
    async def mark_sent(user_id: int, message_id: int = None):
        """Mark daily message as sent. message_id is optional for AI-generated messages."""
        await db.execute(
            "INSERT INTO daily_sent (user_id) VALUES ($1)",
            user_id
        )

    @staticmethod
    async def is_sent_today(user_id: int) -> bool:
        count = await db.fetchval(
            """
            SELECT COUNT(*) FROM daily_sent
            WHERE user_id = $1 AND sent_date = CURRENT_DATE
            """,
            user_id
        )
        return (count or 0) > 0

class EventModel:
    @staticmethod
    async def log_event(user_id: Optional[int], event_type: str, meta: Dict[str, Any] = None):
        await db.execute(
            "INSERT INTO events (user_id, type, meta) VALUES ($1, $2, $3)",
            user_id, event_type, json.dumps(meta or {})
        )

class MetricsModel:
    @staticmethod
    async def calculate_daily_metrics(target_date: date = None) -> dict:
        if not target_date:
            target_date = date.today()

        metrics = await db.fetchrow(
            """
            SELECT
                COUNT(DISTINCT e1.user_id) as dau,
                COUNT(DISTINCT CASE WHEN e1.type = 'start' THEN e1.user_id END) as new_users,
                COUNT(DISTINCT CASE WHEN e1.type IN ('daily_sent', 'question_asked') THEN e1.user_id END) as active_users,
                COUNT(DISTINCT CASE WHEN e1.type = 'message_failed_blocked' THEN e1.user_id END) as blocked_today,
                COUNT(DISTINCT CASE WHEN e1.type = 'daily_sent' THEN e1.user_id END) as daily_sent,
                COUNT(DISTINCT CASE WHEN e1.type = 'question_asked' THEN e1.user_id END) as questions,
                COALESCE(SUM(CASE WHEN e1.type = 'payment_success' THEN (e1.meta->>'amount')::numeric ELSE 0 END), 0) as revenue
            FROM events e1
            WHERE DATE(e1.occurred_at) = $1
            """,
            target_date
        )

        # Count active subscriptions
        paid_active = await db.fetchval(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM subscriptions
            WHERE status = 'active' AND $1 BETWEEN DATE(started_at) AND DATE(ends_at)
            """,
            target_date
        ) or 0

        # Count new paid subscriptions today
        paid_new = await db.fetchval(
            """
            SELECT COUNT(DISTINCT user_id)
            FROM subscriptions
            WHERE DATE(started_at) = $1
            """,
            target_date
        ) or 0

        # Total blocked users
        blocked_total = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE is_blocked = true"
        ) or 0

        return {
            'date': target_date,
            'dau': metrics['dau'] or 0,
            'new_users': metrics['new_users'] or 0,
            'active_users': metrics['active_users'] or 0,
            'blocked_total': blocked_total,
            'daily_sent': metrics['daily_sent'] or 0,
            'paid_active': paid_active,
            'paid_new': paid_new,
            'questions': metrics['questions'] or 0,
            'revenue': float(metrics['revenue'] or 0)
        }

    @staticmethod
    async def save_daily_metrics(metrics: dict):
        await db.execute(
            """
            INSERT INTO fact_daily_metrics
            (d, dau, new_users, active_users, blocked_total, daily_sent, paid_active, paid_new, questions, revenue)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (d) DO UPDATE SET
                dau = EXCLUDED.dau,
                new_users = EXCLUDED.new_users,
                active_users = EXCLUDED.active_users,
                blocked_total = EXCLUDED.blocked_total,
                daily_sent = EXCLUDED.daily_sent,
                paid_active = EXCLUDED.paid_active,
                paid_new = EXCLUDED.paid_new,
                questions = EXCLUDED.questions,
                revenue = EXCLUDED.revenue
            """,
            metrics['date'], metrics['dau'], metrics['new_users'], metrics['active_users'],
            metrics['blocked_total'], metrics['daily_sent'], metrics['paid_active'],
            metrics['paid_new'], metrics['questions'], metrics['revenue']
        )


class OracleQuestionModel:
    @staticmethod
    async def save_question(user_id: int, question: str, answer: str, source: str = 'FREE', tokens: int = 0):
        """Save oracle question and answer"""
        await db.execute(
            """
            INSERT INTO oracle_questions (user_id, question, answer, source, tokens_used)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id, question, answer, source, tokens
        )

        await EventModel.log_event(
            user_id=user_id,
            event_type='oracle_answer',
            meta={'source': source, 'tokens': tokens}
        )

    @staticmethod
    async def count_today_questions(user_id: int, source: str = 'SUB') -> int:
        """Count Oracle questions asked today for subscription users"""
        count = await db.fetchval(
            """
            SELECT COUNT(*) FROM oracle_questions
            WHERE user_id = $1 AND asked_date = CURRENT_DATE AND source = $2
            """,
            user_id, source
        )
        return count or 0


class AdminTaskModel:
    @staticmethod
    async def create_task(user_id: int, task_type: str, due_at: datetime = None, payload: dict = None):
        """Create new admin task"""
        task_id = await db.fetchval(
            """
            INSERT INTO admin_tasks (user_id, type, due_at, payload, created_at)
            VALUES ($1, $2, $3, $4, now())
            RETURNING id
            """,
            user_id, task_type, due_at, json.dumps(payload or {})
        )

        await EventModel.log_event(
            user_id=user_id,
            event_type='admin_task_created',
            meta={'task_id': task_id, 'type': task_type}
        )

        return task_id

    @staticmethod
    async def get_due_tasks(limit: int = 100):
        """Get tasks that are due for execution"""
        return await db.fetch(
            """
            SELECT t.*, u.tg_user_id, u.age, u.gender, u.username,
                   u.archetype_primary, u.archetype_secondary
            FROM admin_tasks t
            JOIN users u ON u.id = t.user_id
            WHERE t.status IN ('scheduled', 'due')
            AND t.due_at <= now()
            AND u.is_blocked = false
            ORDER BY t.due_at
            LIMIT $1
            """,
            limit
        )

    @staticmethod
    async def mark_sent(task_id: int):
        """Mark task as sent"""
        await db.execute(
            """
            UPDATE admin_tasks
            SET status = 'sent', sent_at = now(), updated_at = now()
            WHERE id = $1
            """,
            task_id
        )

    @staticmethod
    async def mark_failed(task_id: int, error_code: str = None):
        """Mark task as failed"""
        await db.execute(
            """
            UPDATE admin_tasks
            SET status = 'failed', result_code = $2, updated_at = now()
            WHERE id = $1
            """,
            task_id, error_code
        )

    @staticmethod
    async def count_user_contacts_today(user_id: int) -> int:
        """Count proactive contacts sent to user today"""
        count = await db.fetchval(
            """
            SELECT COUNT(*) FROM admin_tasks
            WHERE user_id = $1
            AND status IN ('sent', 'replied')
            AND sent_at::date = CURRENT_DATE
            AND type NOT IN ('THANKS', 'REACT')
            """,
            user_id
        )
        return count or 0

    @staticmethod
    async def reschedule_upcoming_tasks(user_id: int, task_types: list, hours_ahead: int = 48):
        """
        Reschedule upcoming tasks (PING, NUDGE_SUB) when user sends a message.
        Only reschedules tasks that are scheduled within next `hours_ahead` hours.
        Returns count of rescheduled tasks.
        """
        # Get postpone_on_reply setting for user
        postpone_hours = await db.fetchval(
            """
            SELECT postpone_on_reply FROM contact_cadence
            WHERE user_id = $1
            """,
            user_id
        )

        # Default to 24 hours if not set
        postpone_hours = postpone_hours or 24

        # Reschedule upcoming tasks from current time
        result = await db.execute(
            """
            UPDATE admin_tasks
            SET due_at = now() + interval '%s hours',
                updated_at = now()
            WHERE user_id = $1
            AND type = ANY($2)
            AND status IN ('scheduled', 'due')
            AND due_at > now()
            AND due_at <= now() + interval '%s hours'
            """ % (postpone_hours, hours_ahead),
            user_id, task_types
        )

        # Parse result "UPDATE N" to get count
        count = int(result.split()[-1]) if result and result.startswith('UPDATE') else 0

        if count > 0:
            logger.info(f"Rescheduled {count} tasks for user {user_id} by {postpone_hours}h")

        return count


class AdminTemplateModel:
    @staticmethod
    async def get_template(task_type: str, tone: str = None):
        """Get random template for task type and tone"""
        if tone:
            templates = await db.fetch(
                """
                SELECT text, weight FROM admin_templates
                WHERE type = $1 AND tone = $2 AND enabled = true
                """,
                task_type, tone
            )

            # Fallback: if no templates for this tone, try without tone filter
            if not templates:
                templates = await db.fetch(
                    """
                    SELECT text, weight FROM admin_templates
                    WHERE type = $1 AND enabled = true
                    """,
                    task_type
                )
        else:
            templates = await db.fetch(
                """
                SELECT text, weight FROM admin_templates
                WHERE type = $1 AND enabled = true
                """,
                task_type
            )

        if not templates:
            return f"[Template for {task_type} not found]"

        # Weighted random selection
        import random
        weighted_templates = []
        for template in templates:
            weighted_templates.extend([template['text']] * (template['weight'] or 1))

        return random.choice(weighted_templates)


class UserPrefsModel:
    @staticmethod
    async def get_prefs(user_id: int):
        """Get user preferences"""
        prefs = await db.fetchrow(
            "SELECT * FROM user_prefs WHERE user_id = $1",
            user_id
        )
        return dict(prefs) if prefs else None

    @staticmethod
    async def get_cadence(user_id: int):
        """Get user contact cadence settings"""
        cadence = await db.fetchrow(
            "SELECT * FROM contact_cadence WHERE user_id = $1",
            user_id
        )
        return dict(cadence) if cadence else None


class PaymentModel:
    @staticmethod
    async def create_payment(user_id: int, inv_id: int, plan_code: str, amount: float) -> int:
        payment_id = await db.fetchval(
            """
            INSERT INTO payments (user_id, inv_id, plan_code, amount, status, created_at)
            VALUES ($1, $2, $3, $4, 'pending', now())
            RETURNING id
            """,
            user_id, inv_id, plan_code, amount
        )
        return payment_id

    @staticmethod
    async def get_payment_by_inv_id(inv_id: int):
        return await db.fetchrow(
            "SELECT * FROM payments WHERE inv_id = $1",
            inv_id
        )

    @staticmethod
    async def mark_payment_success(inv_id: int, raw_payload: dict = None):
        await db.execute(
            """
            UPDATE payments
            SET status = 'success', paid_at = now(), raw_payload = $2
            WHERE inv_id = $1
            """,
            inv_id, json.dumps(raw_payload) if raw_payload else None
        )

    @staticmethod
    async def mark_payment_failed(inv_id: int, raw_payload: dict = None):
        await db.execute(
            """
            UPDATE payments
            SET status = 'failed', raw_payload = $2
            WHERE inv_id = $1
            """,
            inv_id, json.dumps(raw_payload) if raw_payload else None
        )


class ArchetypeModel:
    @staticmethod
    async def get_archetype(code: str) -> Optional[dict]:
        """Get archetype information by code"""
        archetype = await db.fetchrow(
            "SELECT * FROM archetypes WHERE code = $1 AND is_active = TRUE",
            code
        )
        return dict(archetype) if archetype else None

    @staticmethod
    async def get_all_active() -> list:
        """Get all active archetypes"""
        archetypes = await db.fetch(
            "SELECT * FROM archetypes WHERE is_active = TRUE ORDER BY id"
        )
        return [dict(a) for a in archetypes]

    @staticmethod
    async def update_user_archetype(user_id: int, primary: str, secondary: str = None,
                                   archetype_data: dict = None):
        """Update user's archetype information"""
        await db.execute(
            """
            UPDATE users
            SET archetype_primary = $1,
                archetype_secondary = $2,
                archetype_data = $3,
                onboarding_completed = TRUE
            WHERE id = $4
            """,
            primary, secondary, json.dumps(archetype_data or {}), user_id
        )

        await EventModel.log_event(
            user_id=user_id,
            event_type='archetype_assigned',
            meta={
                'primary': primary,
                'secondary': secondary,
                'confidence': archetype_data.get('confidence') if archetype_data else None
            }
        )


class OnboardingModel:
    @staticmethod
    async def save_response(user_id: int, question_number: int, question_text: str,
                           user_response: str, is_valid: bool = True, ai_analysis: dict = None):
        """Save user response during onboarding"""
        response_id = await db.fetchval(
            """
            INSERT INTO onboarding_responses
            (user_id, question_number, question_text, user_response, is_valid, ai_analysis)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            user_id, question_number, question_text, user_response, is_valid,
            json.dumps(ai_analysis) if ai_analysis else None
        )
        return response_id

    @staticmethod
    async def get_user_responses(user_id: int) -> list:
        """Get all onboarding responses for user"""
        responses = await db.fetch(
            """
            SELECT * FROM onboarding_responses
            WHERE user_id = $1
            ORDER BY question_number
            """,
            user_id
        )
        return [dict(r) for r in responses]

    @staticmethod
    async def clear_user_responses(user_id: int):
        """Clear all onboarding responses for user (for retry)"""
        await db.execute(
            "DELETE FROM onboarding_responses WHERE user_id = $1",
            user_id
        )

    @staticmethod
    async def count_user_responses(user_id: int) -> int:
        """Count user's onboarding responses"""
        count = await db.fetchval(
            "SELECT COUNT(*) FROM onboarding_responses WHERE user_id = $1",
            user_id
        )
        return count or 0


class CadenceManager:
    """Manages adaptive CRM cadence levels (1=Normal, 2=Reduced, 3=Stopped)"""

    @staticmethod
    async def get_cadence_level(user_id: int) -> int:
        """Get current cadence level for user (1, 2, or 3)"""
        level = await db.fetchval(
            "SELECT crm_cadence_level FROM users WHERE id = $1",
            user_id
        )
        return level or 1

    @staticmethod
    async def update_cadence_level(user_id: int) -> int:
        """
        Calculate and update cadence level based on last_crm_response_at.
        Level 1 (Normal): < 2 days without response
        Level 2 (Reduced): 2-13 days without response
        Level 3 (Stopped): 14+ days without response
        Returns new level.
        """
        user = await db.fetchrow(
            "SELECT id, crm_cadence_level, last_crm_response_at FROM users WHERE id = $1",
            user_id
        )

        if not user:
            return 1

        last_response = user['last_crm_response_at']
        old_level = user['crm_cadence_level'] or 1

        # Default to Level 1 if never responded to CRM
        if not last_response:
            new_level = 1
        else:
            # Calculate days since last CRM response
            from datetime import datetime
            days_since = (datetime.now() - last_response).days

            if days_since >= 14:
                new_level = 3  # STOPPED
            elif days_since >= 2:
                new_level = 2  # REDUCED
            else:
                new_level = 1  # NORMAL

        # Update level if changed
        if new_level != old_level:
            await db.execute(
                "UPDATE users SET crm_cadence_level = $1 WHERE id = $2",
                new_level, user_id
            )

            await EventModel.log_event(
                user_id=user_id,
                event_type='cadence_level_changed',
                meta={'from_level': old_level, 'to_level': new_level}
            )

            logger.info(f"User {user_id} cadence level changed: {old_level} → {new_level}")

            # If transitioning to Level 3, stop cadence completely
            if new_level == 3 and old_level < 3:
                await CadenceManager.stop_cadence(user_id, 'no_response_14d')

        return new_level

    @staticmethod
    async def track_crm_response(user_id: int):
        """
        Track that user responded to CRM contact.
        Updates last_crm_response_at and restores to Level 1 if needed.
        """
        user = await db.fetchrow(
            "SELECT crm_cadence_level FROM users WHERE id = $1",
            user_id
        )

        old_level = user['crm_cadence_level'] if user else 1

        # Update response time and restore to Level 1
        await db.execute(
            """
            UPDATE users
            SET last_crm_response_at = now(),
                crm_cadence_level = 1,
                crm_stopped_reason = NULL
            WHERE id = $1
            """,
            user_id
        )

        # Cancel pending FAREWELL tasks (if any)
        if old_level > 1:
            await db.execute(
                """
                UPDATE admin_tasks
                SET status = 'cancelled', updated_at = now()
                WHERE user_id = $1
                AND status IN ('scheduled', 'due', 'pending')
                AND type = 'FAREWELL'
                """,
                user_id
            )

        # Log restoration if level changed
        if old_level > 1:
            await EventModel.log_event(
                user_id=user_id,
                event_type='cadence_level_restored',
                meta={'from_level': old_level, 'to_level': 1}
            )

            logger.info(f"User {user_id} re-engaged! Cadence restored from Level {old_level} to Level 1")

    @staticmethod
    async def is_response_to_crm(user_id: int) -> bool:
        """
        Check if there was a CRM contact sent within last 48 hours.
        Used to determine if user message is a response to CRM.
        """
        last_crm = await db.fetchrow(
            """
            SELECT sent_at FROM admin_tasks
            WHERE user_id = $1
            AND status = 'sent'
            AND type IN ('PING', 'NUDGE_SUB', 'DAILY_MSG_PROMPT', 'RECOVERY', 'LIMIT_INFO')
            ORDER BY sent_at DESC
            LIMIT 1
            """,
            user_id
        )

        if not last_crm or not last_crm['sent_at']:
            return False

        # Check if within 48 hours
        from datetime import datetime, timedelta
        hours_since = (datetime.now() - last_crm['sent_at']).total_seconds() / 3600
        return hours_since <= 48

    @staticmethod
    async def stop_cadence(user_id: int, reason: str):
        """
        Stop all CRM cadence for user (set to Level 3).
        Cancels pending tasks and creates FAREWELL task.
        """
        # Set level to 3 and record reason
        await db.execute(
            """
            UPDATE users
            SET crm_cadence_level = 3,
                crm_stopped_reason = $2
            WHERE id = $1
            """,
            user_id, reason
        )

        # Cancel all pending CRM tasks
        cancelled = await db.execute(
            """
            UPDATE admin_tasks
            SET status = 'cancelled', updated_at = now()
            WHERE user_id = $1
            AND status IN ('scheduled', 'due')
            AND type IN ('PING', 'NUDGE_SUB', 'DAILY_MSG_PROMPT', 'RECOVERY', 'LIMIT_INFO')
            """,
            user_id
        )

        # Create FAREWELL task (delayed 1 hour)
        from datetime import datetime, timedelta
        await AdminTaskModel.create_task(
            user_id=user_id,
            task_type='FAREWELL',
            due_at=datetime.now() + timedelta(hours=1),
            payload={'reason': reason}
        )

        await EventModel.log_event(
            user_id=user_id,
            event_type='cadence_stopped',
            meta={'reason': reason, 'cancelled_tasks': cancelled}
        )

        logger.info(f"User {user_id} CRM stopped (reason: {reason})")


