from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date, datetime
import os
import logging

from app.database.models import DailyMessageModel, UserModel, EventModel, MetricsModel
from app.database.connection import db
from app.crm.planner import plan_daily_tasks
from app.crm.dispatcher import dispatch_due_tasks, init_dispatcher

logger = logging.getLogger(__name__)

# Configuration
DISPATCH_INTERVAL_SECONDS = int(os.getenv("DISPATCH_INTERVAL_SECONDS", "60"))

class SchedulerService:
    def __init__(self, bot):
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        # Initialize CRM dispatcher
        init_dispatcher(bot)

    async def start(self):
        # CRM daily task planning at 6:00 AM
        self.scheduler.add_job(
            plan_daily_tasks,
            CronTrigger(hour=6, minute=0),
            id='crm_daily_planning',
            name='Generate daily CRM tasks for all users'
        )

        # CRM task dispatcher (every minute)
        self.scheduler.add_job(
            dispatch_due_tasks,
            CronTrigger(minute='*'),
            id='crm_dispatcher',
            name='Execute due CRM tasks'
        )

        # Check for daily messages every minute (legacy - may be replaced by CRM)
        self.scheduler.add_job(
            self.send_daily_messages_by_user_time,
            CronTrigger(minute='*'),
            id='daily_messages',
            name='Send daily messages based on user time'
        )

        # Daily metrics calculation at 23:55
        self.scheduler.add_job(
            self.calculate_daily_metrics,
            CronTrigger(hour=23, minute=55),
            id='daily_metrics',
            name='Calculate daily metrics'
        )

        # Subscription cleanup at 1:00 AM
        self.scheduler.add_job(
            self.cleanup_expired_subscriptions,
            CronTrigger(hour=1, minute=0),
            id='subscription_cleanup',
            name='Clean up expired subscriptions'
        )

        self.scheduler.start()
        logger.info("Scheduler started with jobs: CRM planning, CRM dispatcher, daily messages, metrics, subscription cleanup")

    async def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    async def send_daily_messages_by_user_time(self):
        """Send daily messages to users based on their individual time settings"""
        from datetime import time
        current_time = datetime.now().time()
        current_hour = current_time.hour
        current_minute = current_time.minute

        logger.info(f"Checking for users to send daily messages at {current_hour:02d}:{current_minute:02d}")

        try:
            # Get random daily message
            daily_message = await DailyMessageModel.get_random_message()
            if not daily_message:
                logger.warning("No daily messages available")
                return

            # Find users who should receive message at this time
            users = await db.fetch(
                """
                SELECT u.id, u.tg_user_id, u.daily_message_time
                FROM users u
                WHERE u.is_blocked = false
                AND u.daily_message_time IS NOT NULL
                AND EXTRACT(HOUR FROM u.daily_message_time) = $1
                AND EXTRACT(MINUTE FROM u.daily_message_time) = $2
                AND NOT EXISTS (
                    SELECT 1 FROM daily_sent ds
                    WHERE ds.user_id = u.id AND ds.sent_date = CURRENT_DATE
                )
                """,
                current_hour, current_minute
            )

            if not users:
                return

            logger.info(f"Found {len(users)} users to send messages to at {current_hour:02d}:{current_minute:02d}")

            sent_count = 0
            blocked_count = 0

            for user in users:
                try:
                    # Send message
                    text = f"📨 **Сообщение дня:**\n\n{daily_message['text']}"
                    await self.bot.send_message(
                        user['tg_user_id'],
                        text,
                        parse_mode="Markdown"
                    )

                    # Mark as sent
                    await DailyMessageModel.mark_sent(user['id'], daily_message['id'])

                    # Log event
                    await EventModel.log_event(
                        user_id=user['id'],
                        event_type='daily_sent',
                        meta={'message_id': daily_message['id'], 'scheduled_time': str(user['daily_message_time'])}
                    )

                    sent_count += 1

                except Exception as e:
                    if "blocked" in str(e).lower() or "forbidden" in str(e).lower():
                        # User blocked the bot
                        await UserModel.set_blocked(user['id'], True)
                        await EventModel.log_event(
                            user_id=user['id'],
                            event_type='message_failed_blocked'
                        )
                        blocked_count += 1
                        logger.info(f"User {user['tg_user_id']} blocked the bot")
                    else:
                        logger.error(f"Failed to send daily message to user {user['tg_user_id']}: {e}")

            if sent_count > 0:
                logger.info(f"Daily messages sent at {current_hour:02d}:{current_minute:02d}: {sent_count} sent, {blocked_count} blocked")

        except Exception as e:
            logger.error(f"Error during daily message distribution by user time: {e}")

    async def send_daily_messages(self):
        logger.info("Starting daily message distribution")

        try:
            # Get random daily message
            daily_message = await DailyMessageModel.get_random_message()
            if not daily_message:
                logger.warning("No daily messages available")
                return

            # Get all active users who haven't received today's message
            users = await db.fetch(
                """
                SELECT u.id, u.tg_user_id
                FROM users u
                WHERE u.is_blocked = false
                AND NOT EXISTS (
                    SELECT 1 FROM daily_sent ds
                    WHERE ds.user_id = u.id AND ds.sent_date = CURRENT_DATE
                )
                """
            )

            sent_count = 0
            blocked_count = 0

            for user in users:
                try:
                    # Send message
                    text = f"📨 **Сообщение дня:**\n\n{daily_message['text']}"
                    await self.bot.send_message(
                        user['tg_user_id'],
                        text,
                        parse_mode="Markdown"
                    )

                    # Mark as sent
                    await DailyMessageModel.mark_sent(user['id'], daily_message['id'])

                    # Log event
                    await EventModel.log_event(
                        user_id=user['id'],
                        event_type='daily_sent',
                        meta={'message_id': daily_message['id']}
                    )

                    sent_count += 1

                except Exception as e:
                    if "blocked" in str(e).lower() or "forbidden" in str(e).lower():
                        # User blocked the bot
                        await UserModel.set_blocked(user['id'], True)
                        await EventModel.log_event(
                            user_id=user['id'],
                            event_type='message_failed_blocked'
                        )
                        blocked_count += 1
                        logger.info(f"User {user['tg_user_id']} blocked the bot")
                    else:
                        logger.error(f"Failed to send daily message to user {user['tg_user_id']}: {e}")

            logger.info(f"Daily messages sent: {sent_count}, blocked: {blocked_count}")

        except Exception as e:
            logger.error(f"Error during daily message distribution: {e}")

    async def calculate_daily_metrics(self):
        logger.info("Starting daily metrics calculation")

        try:
            today = date.today()
            metrics = await MetricsModel.calculate_daily_metrics(today)
            await MetricsModel.save_daily_metrics(metrics)

            logger.info(f"Daily metrics calculated for {today}: DAU={metrics['dau']}, Revenue={metrics['revenue']}")

        except Exception as e:
            logger.error(f"Error calculating daily metrics: {e}")

    async def cleanup_expired_subscriptions(self):
        logger.info("Starting subscription cleanup")

        try:
            # Mark expired subscriptions as expired
            result = await db.execute(
                """
                UPDATE subscriptions
                SET status = 'expired'
                WHERE status = 'active' AND ends_at < now()
                """
            )

            count = int(result.split()[-1]) if result.startswith("UPDATE") else 0
            logger.info(f"Marked {count} subscriptions as expired")

        except Exception as e:
            logger.error(f"Error during subscription cleanup: {e}")

    # Manual trigger methods for testing
    async def trigger_daily_messages(self):
        await self.send_daily_messages()

    async def trigger_metrics_calculation(self):
        await self.calculate_daily_metrics()

    async def trigger_crm_planning(self):
        """Manually trigger CRM daily planning"""
        return await plan_daily_tasks()

    async def trigger_crm_dispatch(self):
        """Manually trigger CRM task dispatch"""
        return await dispatch_due_tasks()

scheduler_service = None

def get_scheduler() -> SchedulerService:
    return scheduler_service

def init_scheduler(bot):
    global scheduler_service
    scheduler_service = SchedulerService(bot)
    return scheduler_service