"""
CRM Daily Planner - creates proactive engagement tasks for users
Implements human-like contact patterns with frequency limits
"""
import os
import logging
import random
from datetime import datetime, time, timedelta
from typing import List, Dict, Any

from app.database.models import (
    AdminTaskModel, UserPrefsModel, DailyMessageModel,
    SubscriptionModel, AdminTemplateModel
)
from app.database.connection import db

logger = logging.getLogger(__name__)

# Configuration from environment
HUMANIZED_MAX_CONTACTS_PER_DAY = int(os.getenv("HUMANIZED_MAX_CONTACTS_PER_DAY", "3"))
NUDGE_MIN_HOURS = int(os.getenv("NUDGE_MIN_HOURS", "48"))
NUDGE_MAX_PER_WEEK = int(os.getenv("NUDGE_MAX_PER_WEEK", "2"))

class CRMPlanner:
    """Plans daily CRM tasks for all users"""

    def __init__(self):
        self.max_contacts_per_day = HUMANIZED_MAX_CONTACTS_PER_DAY
        self.nudge_min_hours = NUDGE_MIN_HOURS
        self.nudge_max_per_week = NUDGE_MAX_PER_WEEK

    async def plan_for_user(self, user: Dict[str, Any]) -> int:
        """Plan CRM tasks for a single user, returns number of tasks created"""
        try:
            user_id = user['id']

            # Get user preferences
            prefs = await UserPrefsModel.get_prefs(user_id)
            cadence = await UserPrefsModel.get_cadence(user_id)

            if not prefs:
                # Initialize preferences if not exist
                from app.database.models import UserModel
                await UserModel.init_user_preferences(user_id)
                prefs = await UserPrefsModel.get_prefs(user_id)
                cadence = await UserPrefsModel.get_cadence(user_id)

            # Skip if user disabled proactive contacts
            if not prefs.get('allow_proactive', True):
                return 0

            # Count contacts already sent today
            contacts_today = await AdminTaskModel.count_user_contacts_today(user_id)
            max_contacts = prefs.get('max_contacts_per_day', self.max_contacts_per_day)

            remaining_slots = max(0, max_contacts - contacts_today)
            if remaining_slots == 0:
                return 0

            # Determine candidate tasks
            candidates = await self._get_candidate_tasks(user, prefs, cadence)

            # Select tasks for today
            selected_tasks = self._select_tasks(candidates, remaining_slots)

            # Schedule tasks
            tasks_created = 0
            for task_type in selected_tasks:
                due_time = self._calculate_due_time(prefs, cadence)

                await AdminTaskModel.create_task(
                    user_id=user_id,
                    task_type=task_type,
                    due_at=due_time,
                    payload={'planned_date': datetime.now().date().isoformat()}
                )

                tasks_created += 1

            if tasks_created > 0:
                logger.info(f"Created {tasks_created} CRM tasks for user {user_id}")

            return tasks_created

        except Exception as e:
            logger.error(f"Error planning tasks for user {user.get('id')}: {e}")
            return 0

    async def _get_candidate_tasks(self, user: Dict[str, Any], prefs: Dict[str, Any],
                                 cadence: Dict[str, Any]) -> List[str]:
        """Determine which tasks are candidates for this user"""
        candidates = []
        user_id = user['id']

        # DAILY_MSG_PROMPT - if user hasn't received daily message
        daily_sent_today = await DailyMessageModel.is_sent_today(user_id)
        if not daily_sent_today:
            candidates.append('DAILY_MSG_PROMPT')

        # PING - warm check-in
        last_ping = await self._get_last_task_time(user_id, 'PING')
        days_since_ping = cadence.get('days_between_pings', 2)
        if not last_ping or (datetime.now() - last_ping).days >= days_since_ping:
            candidates.append('PING')

        # NUDGE_SUB - subscription nudge (with strict limits)
        subscription = await SubscriptionModel.get_active_subscription(user_id)
        if not subscription:  # Only nudge users without subscription
            if await self._can_nudge_subscription(user_id):
                candidates.append('NUDGE_SUB')

        # RECOVERY - for users who haven't been active
        last_seen = user.get('last_seen_at')
        if last_seen and (datetime.now() - last_seen).days >= 3:
            candidates.append('RECOVERY')

        # LIMIT_INFO - if user has few free questions left
        free_left = user.get('free_questions_left', 0)
        if 0 < free_left <= 2 and not subscription:
            candidates.append('LIMIT_INFO')

        return candidates

    async def _can_nudge_subscription(self, user_id: int) -> bool:
        """Check if we can send subscription nudge (respects frequency limits)"""
        # Check last nudge time (min 48 hours)
        last_nudge = await self._get_last_task_time(user_id, 'NUDGE_SUB')
        if last_nudge and (datetime.now() - last_nudge).total_seconds() < (self.nudge_min_hours * 3600):
            return False

        # Check weekly limit (max 2 per week)
        week_ago = datetime.now() - timedelta(days=7)
        nudges_this_week = await db.fetchval(
            """
            SELECT COUNT(*) FROM admin_tasks
            WHERE user_id = $1 AND type = 'NUDGE_SUB'
            AND status IN ('sent', 'replied')
            AND sent_at > $2
            """,
            user_id, week_ago
        )

        return (nudges_this_week or 0) < self.nudge_max_per_week

    async def _get_last_task_time(self, user_id: int, task_type: str) -> datetime:
        """Get timestamp of last task of given type"""
        result = await db.fetchrow(
            """
            SELECT MAX(sent_at) as last_sent FROM admin_tasks
            WHERE user_id = $1 AND type = $2 AND status IN ('sent', 'replied')
            """,
            user_id, task_type
        )
        return result['last_sent'] if result and result['last_sent'] else None

    def _select_tasks(self, candidates: List[str], max_tasks: int) -> List[str]:
        """Select tasks from candidates with priority and randomization"""
        if not candidates:
            return []

        # Priority weights (higher = more likely to be selected)
        priority_weights = {
            'DAILY_MSG_PROMPT': 3,
            'RECOVERY': 3,
            'LIMIT_INFO': 2,
            'PING': 2,
            'NUDGE_SUB': 1,
        }

        # Weight candidates
        weighted_candidates = []
        for task in candidates:
            weight = priority_weights.get(task, 1)
            weighted_candidates.extend([task] * weight)

        # Random selection without replacement
        selected = []
        available = weighted_candidates.copy()

        for _ in range(min(max_tasks, len(set(candidates)))):
            if not available:
                break

            choice = random.choice(available)
            if choice not in selected:
                selected.append(choice)

            # Remove all instances of selected task
            available = [t for t in available if t != choice]

        return selected

    def _calculate_due_time(self, prefs: Dict[str, Any], cadence: Dict[str, Any]) -> datetime:
        """Calculate when task should be executed"""
        # Get preferred time windows
        windows = cadence.get('prefers_windows', {
            "morning": [9, 12],
            "day": [12, 17],
            "evening": [17, 21]
        })

        # Handle JSON string from database
        if isinstance(windows, str):
            import json
            windows = json.loads(windows)

        # Select random window with weights (morning slightly preferred)
        window_choices = list(windows.keys())
        window_weights = [0.4, 0.3, 0.3]  # morning, day, evening

        selected_window = random.choices(window_choices, weights=window_weights)[0]
        start_hour, end_hour = windows[selected_window]

        # Random time within window
        hour = random.randint(start_hour, end_hour - 1)
        minute = random.randint(0, 59)

        # Check quiet hours
        quiet_start = prefs.get('quiet_start', time(22, 0))
        quiet_end = prefs.get('quiet_end', time(8, 0))

        due_time = datetime.now().replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        # If falls in quiet hours, move to 9:15 AM
        if (quiet_start <= time(hour, minute) or time(hour, minute) <= quiet_end):
            due_time = due_time.replace(hour=9, minute=15)

        # Add some jitter (±15 minutes)
        jitter_minutes = random.randint(-15, 15)
        due_time += timedelta(minutes=jitter_minutes)

        return due_time

    async def plan_all_users(self) -> Dict[str, int]:
        """Plan CRM tasks for all active users"""
        stats = {'total_users': 0, 'total_tasks': 0, 'users_with_tasks': 0}

        try:
            # Get all non-blocked users
            users = await db.fetch(
                """
                SELECT id, tg_user_id, username, age, gender, last_seen_at, free_questions_left
                FROM users
                WHERE is_blocked = false
                AND age IS NOT NULL AND gender IS NOT NULL
                """
            )

            stats['total_users'] = len(users)

            for user in users:
                tasks_created = await self.plan_for_user(dict(user))
                stats['total_tasks'] += tasks_created
                if tasks_created > 0:
                    stats['users_with_tasks'] += 1

            logger.info(
                f"CRM planning completed: {stats['total_users']} users, "
                f"{stats['total_tasks']} tasks created for {stats['users_with_tasks']} users"
            )

        except Exception as e:
            logger.error(f"Error in plan_all_users: {e}")

        return stats

# Global instance
crm_planner = CRMPlanner()

async def plan_daily_tasks() -> Dict[str, int]:
    """Entry point for daily task planning"""
    return await crm_planner.plan_all_users()