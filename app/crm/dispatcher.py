"""
CRM Dispatcher - executes due admin tasks
Sends proactive messages using emotional templates and persona system
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.database.models import (
    AdminTaskModel, AdminTemplateModel, DailyMessageModel,
    UserModel
)
from app.services.persona import persona_factory

logger = logging.getLogger(__name__)

class CRMDispatcher:
    """Dispatches due CRM tasks to users"""

    def __init__(self, bot):
        self.bot = bot

    async def dispatch_due_tasks(self, limit: int = 100) -> Dict[str, int]:
        """Execute all due admin tasks"""
        stats = {'sent': 0, 'failed': 0, 'blocked': 0}

        try:
            # Get due tasks
            tasks = await AdminTaskModel.get_due_tasks(limit)

            for task in tasks:
                result = await self._process_task(dict(task))
                stats[result] += 1

            if stats['sent'] > 0 or stats['failed'] > 0:
                logger.info(
                    f"CRM dispatch completed: {stats['sent']} sent, "
                    f"{stats['failed']} failed, {stats['blocked']} blocked users"
                )

        except Exception as e:
            logger.error(f"Error in dispatch_due_tasks: {e}")

        return stats

    async def _process_task(self, task: Dict[str, Any]) -> str:
        """Process single admin task"""
        try:
            task_id = task['id']
            user_id = task['user_id']
            task_type = task['type']
            tg_user_id = task['tg_user_id']

            # Create persona for user
            user_data = {
                'age': task.get('age'),
                'gender': task.get('gender'),
                'username': task.get('username')
            }
            persona = persona_factory(user_data)

            # Get message text
            message_text = await self._get_task_message(task_type, persona, task)

            try:
                # Send message
                await self.bot.send_message(tg_user_id, message_text, parse_mode="Markdown")

                # Mark task as sent
                await AdminTaskModel.mark_sent(task_id)

                return 'sent'

            except Exception as send_error:
                error_str = str(send_error).lower()
                if any(keyword in error_str for keyword in ['blocked', 'forbidden', 'deactivated']):
                    # User blocked the bot
                    await UserModel.set_blocked(user_id, True)
                    await AdminTaskModel.mark_failed(task_id, 'blocked')

                    logger.info(f"User {tg_user_id} blocked the bot")
                    return 'blocked'
                else:
                    # Other sending error
                    await AdminTaskModel.mark_failed(task_id, f'send_error: {send_error}')
                    logger.error(f"Failed to send task {task_id} to user {tg_user_id}: {send_error}")
                    return 'failed'

        except Exception as e:
            logger.error(f"Error processing task {task.get('id')}: {e}")
            if task.get('id'):
                await AdminTaskModel.mark_failed(task['id'], f'process_error: {e}')
            return 'failed'

    async def _get_task_message(self, task_type: str, persona, task: Dict[str, Any]) -> str:
        """Generate message text for task type"""
        try:
            # Get template based on task type and user's tone preference
            template = await AdminTemplateModel.get_template(task_type, persona.tone)

            # Handle special task types that need content substitution
            if task_type == 'DAILY_MSG_PUSH':
                # Get random daily message and substitute it in template
                daily_msg = await DailyMessageModel.get_random_message()
                if daily_msg:
                    template = template.replace('{TEXT}', daily_msg['text'])
                else:
                    template = template.replace('{TEXT}', 'особое сообщение для тебя сегодня')

            elif task_type == 'LIMIT_INFO':
                # Substitute remaining count
                payload = task.get('payload', {})
                if isinstance(payload, str):
                    import json
                    payload = json.loads(payload)

                remaining = payload.get('remaining', 'несколько')
                template = template.replace('{N}', str(remaining))
                template = template.replace('{LEFT}', str(remaining))

            # Apply persona wrapping
            message = persona.wrap(template)

            return message

        except Exception as e:
            logger.error(f"Error generating message for task {task_type}: {e}")
            return persona.wrap("привет! я здесь, если что нужно 🌟")

    async def create_immediate_reaction(self, user_id: int, reaction_type: str = 'THANKS'):
        """Create immediate reaction task (like THANKS for user messages)"""
        try:
            # Create task with immediate due time
            await AdminTaskModel.create_task(
                user_id=user_id,
                task_type=reaction_type,
                due_at=datetime.now(),
                payload={'immediate': True}
            )

        except Exception as e:
            logger.error(f"Error creating immediate reaction: {e}")

# Global dispatcher instance (will be set when bot is initialized)
crm_dispatcher: Optional[CRMDispatcher] = None

def init_dispatcher(bot) -> CRMDispatcher:
    """Initialize CRM dispatcher with bot instance"""
    global crm_dispatcher
    crm_dispatcher = CRMDispatcher(bot)
    return crm_dispatcher

async def dispatch_due_tasks(limit: int = 100) -> Dict[str, int]:
    """Entry point for task dispatching"""
    if not crm_dispatcher:
        logger.error("CRM dispatcher not initialized")
        return {'sent': 0, 'failed': 0, 'blocked': 0}

    return await crm_dispatcher.dispatch_due_tasks(limit)

async def create_immediate_reaction(user_id: int, reaction_type: str = 'THANKS'):
    """Entry point for creating immediate reactions"""
    if crm_dispatcher:
        await crm_dispatcher.create_immediate_reaction(user_id, reaction_type)