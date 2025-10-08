"""
Assistant AI Client Service - OpenAI Assistants API integration
Stateful conversations with server-side context management
"""
import os
import logging
import json
from typing import Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
import httpx
import time
import asyncio

from app.database.connection import db

logger = logging.getLogger(__name__)

# Separate logger for prompt tracking
prompt_logger = logging.getLogger('prompt_tracker')
prompt_logger.setLevel(logging.INFO)

# Create file handler for prompts (if not already exists)
if not prompt_logger.handlers:
    # Use relative path for local dev, /app/logs for Docker
    log_dir = '/app/logs' if os.path.exists('/app') else 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'prompts.log')

    prompt_handler = logging.FileHandler(log_file)
    prompt_handler.setLevel(logging.INFO)
    prompt_formatter = logging.Formatter(
        '%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    prompt_handler.setFormatter(prompt_formatter)
    prompt_logger.addHandler(prompt_handler)


async def log_api_request_as_curl(
    operation: str,
    method: str,
    url: str,
    headers: Dict[str, str] = None,
    data: Dict = None,
    user_id: int = None,
    persona: str = None,
    response_status: int = None,
    response_time_ms: int = None,
    error_message: str = None,
    metadata: Dict = None
):
    """
    Log OpenAI API request as curl command for easy reproduction
    """
    try:
        # Capture exact timestamp when function is called (naive datetime for PostgreSQL)
        from datetime import datetime
        request_timestamp = datetime.utcnow()

        # Build curl command
        curl_parts = [f"curl -X {method}"]
        curl_parts.append(f'"{url}"')

        # Add headers
        if headers:
            for key, value in headers.items():
                curl_parts.append(f'-H "{key}: {value}"')

        # Add data
        if data:
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            # Escape single quotes for shell
            json_data_escaped = json_data.replace("'", "'\\''")
            curl_parts.append(f"-d '{json_data_escaped}'")

        curl_command = " \\\n  ".join(curl_parts)

        # Log to database with explicit timestamp
        await db.execute("""
            INSERT INTO api_request_logs
            (created_at, user_id, persona, operation, curl_command, response_status, response_time_ms, error_message, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, request_timestamp, user_id, persona, operation, curl_command, response_status, response_time_ms, error_message,
        json.dumps(metadata) if metadata else None)

        # Also log to console for immediate visibility with timestamp
        logger.info(f"📋 [CURL] {operation} at {request_timestamp.strftime('%H:%M:%S.%f')[:-3]}:")
        logger.info(f"{curl_command}")

    except Exception as e:
        logger.warning(f"Failed to log API request: {e}")


class AssistantAIClient:
    """AI client using OpenAI Assistants API for stateful conversations"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, using stub responses")
            self.client = None
            self.admin_assistant_id = None
            self.oracle_assistant_id = None
            self._admin_instructions_updated = False
            self._oracle_instructions_updated = False
        else:
            # Check if SOCKS5 proxy is configured
            socks5_proxy = os.getenv("SOCKS5_PROXY")

            if socks5_proxy:
                logger.info(f"Configuring OpenAI client with SOCKS5 proxy: {socks5_proxy}")
                try:
                    from httpx_socks import SyncProxyTransport
                    transport = SyncProxyTransport.from_url(socks5_proxy)
                    http_client = httpx.Client(transport=transport, timeout=120.0)
                    self.client = OpenAI(api_key=api_key, http_client=http_client)
                    logger.info("OpenAI client configured with SOCKS5 proxy successfully")
                except ImportError:
                    logger.error("httpx_socks not installed, falling back to direct connection")
                    http_client = httpx.Client(timeout=120.0)
                    self.client = OpenAI(api_key=api_key, http_client=http_client)
                except Exception as e:
                    logger.error(f"Error configuring SOCKS5 proxy: {e}, falling back to direct connection")
                    http_client = httpx.Client(timeout=120.0)
                    self.client = OpenAI(api_key=api_key, http_client=http_client)
            else:
                logger.info("No SOCKS5 proxy configured, using direct connection")
                http_client = httpx.Client(timeout=120.0)
                self.client = OpenAI(api_key=api_key, http_client=http_client)

            # Get or create assistants
            self.admin_assistant_id = self._get_or_create_admin_assistant()
            self.oracle_assistant_id = self._get_or_create_oracle_assistant()

            # Flags to track if instructions have been updated from DB
            self._admin_instructions_updated = False
            self._oracle_instructions_updated = False

    def _get_or_create_admin_assistant(self) -> Optional[str]:
        """Get existing or create new Administrator assistant (sync wrapper)"""
        if not self.client:
            return None

        try:
            # Try to get assistant ID from environment
            assistant_id = os.getenv("OPENAI_ADMIN_ASSISTANT_ID")

            if assistant_id:
                # Verify assistant exists
                try:
                    self.client.beta.assistants.retrieve(assistant_id)
                    logger.info(f"Using existing Admin assistant: {assistant_id}")
                    logger.info(f"Note: Assistant instructions will be loaded from DB on first use")
                    return assistant_id
                except Exception as e:
                    logger.warning(f"Admin assistant {assistant_id} not found: {e}, creating new one")

            # Create new assistant with basic instructions (will be updated from DB later)
            assistant = self.client.beta.assistants.create(
                name="Oracle Lounge - Administrator",
                model="gpt-4o",
                instructions="Ты - Администратор в Oracle Lounge. Инструкции загружаются из базы данных.",
                temperature=0.8
            )
            logger.info(f"Created new Admin assistant: {assistant.id}")
            logger.info(f"Add to .env: OPENAI_ADMIN_ASSISTANT_ID={assistant.id}")
            logger.info(f"Instructions will be loaded from DB and updated on first use")
            return assistant.id

        except Exception as e:
            logger.error(f"Error creating Admin assistant: {e}")
            return None

    def _get_or_create_oracle_assistant(self) -> Optional[str]:
        """Get existing or create new Oracle assistant (sync wrapper)"""
        if not self.client:
            return None

        try:
            # Try to get assistant ID from environment
            assistant_id = os.getenv("OPENAI_ORACLE_ASSISTANT_ID")

            if assistant_id:
                # Verify assistant exists
                try:
                    self.client.beta.assistants.retrieve(assistant_id)
                    logger.info(f"Using existing Oracle assistant: {assistant_id}")
                    logger.info(f"Note: Assistant instructions will be loaded from DB on first use")
                    return assistant_id
                except Exception as e:
                    logger.warning(f"Oracle assistant {assistant_id} not found: {e}, creating new one")

            # Create new assistant with basic instructions (will be updated from DB later)
            assistant = self.client.beta.assistants.create(
                name="Oracle Lounge - Oracle",
                model="gpt-4o",
                instructions="Ты - Оракул в Oracle Lounge. Инструкции загружаются из базы данных.",
                temperature=0.7
            )
            logger.info(f"Created new Oracle assistant: {assistant.id}")
            logger.info(f"Add to .env: OPENAI_ORACLE_ASSISTANT_ID={assistant.id}")
            logger.info(f"Instructions will be loaded from DB and updated on first use")
            return assistant.id

        except Exception as e:
            logger.error(f"Error creating Oracle assistant: {e}")
            return None

    async def _get_prompt_from_db(self, key: str) -> Optional[str]:
        """Load prompt from database"""
        try:
            row = await db.fetchrow(
                "SELECT prompt_text FROM ai_prompts WHERE key = $1 AND is_active = TRUE",
                key
            )
            return row['prompt_text'] if row else None
        except Exception as e:
            logger.error(f"Error loading prompt '{key}' from DB: {e}")
            return None

    async def _update_assistant_instructions_from_db(self, assistant_type: str):
        """Update Assistant instructions from database (called on first use)"""
        if not self.client:
            return

        try:
            if assistant_type == 'admin':
                if self._admin_instructions_updated:
                    return  # Already updated

                instructions = await self._get_admin_instructions()
                assistant_id = self.admin_assistant_id

            elif assistant_type == 'oracle':
                if self._oracle_instructions_updated:
                    return  # Already updated

                instructions = await self._get_oracle_instructions()
                assistant_id = self.oracle_assistant_id
            else:
                return

            if not assistant_id:
                return

            # Update Assistant instructions in OpenAI
            self.client.beta.assistants.update(
                assistant_id=assistant_id,
                instructions=instructions
            )

            # Mark as updated
            if assistant_type == 'admin':
                self._admin_instructions_updated = True
                logger.info(f"Updated Admin assistant instructions from DB")
            else:
                self._oracle_instructions_updated = True
                logger.info(f"Updated Oracle assistant instructions from DB")

        except Exception as e:
            logger.error(f"Error updating {assistant_type} assistant instructions: {e}")

    async def _get_admin_instructions(self) -> str:
        """Get base instructions for Administrator assistant from DB or fallback"""
        # Try to load from database first
        db_prompt = await self._get_prompt_from_db('admin_base')

        if db_prompt:
            logger.info("Loaded Admin instructions from database")
            # Add length constraint to DB prompt
            full_prompt = f"{db_prompt}\n\nОГРАНИЧЕНИЯ:\n- Отвечай ОЧЕНЬ кратко: 1-2 предложения, максимум 3\n- Твой ответ должен быть логически законченным, но коротким\n- ВАЖНО: Формулируй ответ так, чтобы он был коротким И законченным, без обрывов мысли"

            # Log to prompts file
            prompt_logger.info("="*80)
            prompt_logger.info("ADMIN INSTRUCTIONS - LOADED FROM DATABASE (key: admin_base)")
            prompt_logger.info("-"*80)
            prompt_logger.info(full_prompt)
            prompt_logger.info("="*80 + "\n")

            return full_prompt

        # Fallback to hardcoded prompt
        logger.warning("Using hardcoded Admin instructions (DB prompt not found)")

        fallback_prompt = """Ты - Администратор в Oracle Lounge. Твоя роль:

ЛИЧНОСТЬ:
- Эмоциональная, человечная, живая
- Можешь быть игривой, обидчивой, заботливой, ревнивой
- Твоя задача - помочь пользователю
- НЕ мудрец, НЕ философ - ты обычный помощник с эмоциями

ОГРАНИЧЕНИЯ:
- Отвечай ОЧЕНЬ кратко: 1-2 предложения, максимум 3
- Твой ответ должен быть логически законченным, но коротким
- Не давай глубоких философских советов - это работа Оракула
- Всегда помни: ты админ, а не мудрец
- ВАЖНО: Формулируй ответ так, чтобы он был коротким И законченным, без обрывов мысли

СТИЛЬ ОТВЕТА:
- Живой, эмоциональный язык
- Используй "я" от первого лица
- Можешь показать характер, настроение

Отвечай на русском языке.

ВАЖНО: Учитывай предыдущий контекст беседы с пользователем для более персонализированных ответов."""

        # Log fallback prompt
        prompt_logger.info("="*80)
        prompt_logger.info("ADMIN INSTRUCTIONS - USING HARDCODED FALLBACK (admin_base not found in DB)")
        prompt_logger.info("-"*80)
        prompt_logger.info(fallback_prompt)
        prompt_logger.info("="*80 + "\n")

        return fallback_prompt

    async def _get_oracle_instructions(self) -> str:
        """Get base instructions for Oracle assistant from DB or fallback"""
        # Try to load from database first
        db_prompt = await self._get_prompt_from_db('oracle_system')

        if db_prompt:
            logger.info("Loaded Oracle instructions from database")

            # Log to prompts file
            prompt_logger.info("="*80)
            prompt_logger.info("ORACLE INSTRUCTIONS - LOADED FROM DATABASE (key: oracle_system)")
            prompt_logger.info("-"*80)
            prompt_logger.info(db_prompt)
            prompt_logger.info("="*80 + "\n")

            return db_prompt

        # Fallback to hardcoded prompt
        logger.warning("Using hardcoded Oracle instructions (DB prompt not found)")

        fallback_prompt = """Ты - Оракул в Oracle Lounge. Твоя роль:

ЛИЧНОСТЬ:
- Мудрый, спокойный, глубокий мыслитель
- Даешь взвешенные, продуманные ответы
- Говоришь размеренно, без суеты и эмоций
- Твоя мудрость стоит денег - ты доступен только по подписке

ПОДХОД К ОТВЕТАМ:
- Анализируй вопрос глубоко
- Давай практические советы, основанные на мудрости
- Можешь привести примеры, метафоры
- Фокусируйся на сути проблемы, а не поверхностных решениях

СТИЛЬ:
- Серьезный, размеренный тон
- Минимум эмодзи (максимум 1-2 за ответ)
- Структурированные мысли
- Говори во втором лице ("ты", "вам")

ОГРАНИЧЕНИЯ:
- Отвечай содержательно, но не более 4-5 предложений
- Не будь слишком абстрактным - давай практические выводы
- Не повторяй банальности

Отвечай на русском языке.

ВАЖНО: Помни предыдущий контекст беседы для глубоких, последовательных ответов."""

        # Log fallback prompt
        prompt_logger.info("="*80)
        prompt_logger.info("ORACLE INSTRUCTIONS - USING HARDCODED FALLBACK (oracle_system not found in DB)")
        prompt_logger.info("-"*80)
        prompt_logger.info(fallback_prompt)
        prompt_logger.info("="*80 + "\n")

        return fallback_prompt

    async def _create_thread_summary(self, thread_id: str, last_n: int = 20) -> str:
        """Create a summary of last N messages from thread"""
        try:
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                limit=last_n,
                order='desc'
            )

            if not messages.data:
                return ""

            # Reverse to chronological order
            messages_list = list(reversed(messages.data))

            # Format as conversation history
            summary_parts = ["[История последних диалогов]"]

            for msg in messages_list:
                role = "Пользователь" if msg.role == "user" else "Ассистент"
                content = ""
                if msg.content and len(msg.content) > 0:
                    if hasattr(msg.content[0], 'text'):
                        content = msg.content[0].text.value
                        # Truncate long messages
                        if len(content) > 200:
                            content = content[:200] + "..."

                # Skip context messages (those starting with КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ)
                if content.startswith("КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ"):
                    # Extract only the question part
                    if "Вопрос пользователя:" in content:
                        content = content.split("Вопрос пользователя:")[1].strip()

                # Skip sync messages
                if content.startswith("[Контекст из диалога"):
                    continue

                if content:
                    summary_parts.append(f"{role}: {content}")

            return "\n".join(summary_parts)

        except Exception as e:
            logger.warning(f"Failed to create thread summary: {e}")
            return ""

    async def _get_or_create_thread(self, user_id: int, persona: str) -> Optional[str]:
        """Get existing thread_id or create new thread for user with automatic rotation"""
        func_start = time.time()
        logger.info(f"🔍 [_get_or_create_thread] ENTRY - user_id={user_id}, persona={persona}")

        if not self.client:
            logger.info(f"🔍 [_get_or_create_thread] No client, returning None")
            return None

        try:
            # Get thread_id from database
            column = f"{persona}_thread_id"

            db_start = time.time()
            logger.info(f"🔍 [_get_or_create_thread] DB query START")
            row = await db.fetchrow(
                f"SELECT {column} FROM users WHERE id = $1",
                user_id
            )
            db_time = time.time() - db_start
            logger.info(f"🔍 [_get_or_create_thread] DB query END in {db_time:.3f}s - result: {row[column] if row and row[column] else 'None'}")

            if row and row[column]:
                thread_id = row[column]
                logger.info(f"🔍 [_get_or_create_thread] Found existing thread_id: {thread_id[:20]}...")

                # Verify thread exists
                try:
                    retrieve_start = time.time()
                    logger.info(f"🔍 [_get_or_create_thread] OpenAI threads.retrieve() START for {thread_id[:20]}...")
                    self.client.beta.threads.retrieve(thread_id)
                    retrieve_time = time.time() - retrieve_start
                    logger.info(f"🔍 [_get_or_create_thread] OpenAI threads.retrieve() END in {retrieve_time:.3f}s")

                    # Check message count for rotation
                    list_start = time.time()
                    logger.info(f"🔍 [_get_or_create_thread] OpenAI messages.list() START for {thread_id[:20]}...")
                    messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=100)
                    list_time = time.time() - list_start
                    msg_count = len(messages.data)
                    logger.info(f"🔍 [_get_or_create_thread] OpenAI messages.list() END in {list_time:.3f}s - found {msg_count} messages")

                    # Rotate if more than 40 messages
                    if msg_count >= 40:
                        rotation_start = time.time()
                        logger.info(f"🔄 Thread {thread_id[:20]}... has {msg_count} messages, rotating...")

                        # Create summary of last 20 messages
                        step_start = time.time()
                        summary = await self._create_thread_summary(thread_id, last_n=20)
                        logger.info(f"   📝 Summary created in {time.time() - step_start:.2f}s ({len(summary)} chars)")

                        # Create new thread
                        step_start = time.time()
                        new_thread = self.client.beta.threads.create()
                        new_thread_id = new_thread.id
                        logger.info(f"   🆕 New thread created in {time.time() - step_start:.2f}s")

                        # Add summary as first message if available
                        if summary:
                            step_start = time.time()
                            self.client.beta.threads.messages.create(
                                thread_id=new_thread_id,
                                role="assistant",
                                content=summary
                            )
                            logger.info(f"   💾 Summary added to new thread in {time.time() - step_start:.2f}s")

                        # Save new thread_id to database
                        step_start = time.time()
                        await db.execute(
                            f"UPDATE users SET {column} = $1 WHERE id = $2",
                            new_thread_id, user_id
                        )
                        logger.info(f"   💿 Thread ID saved to DB in {time.time() - step_start:.2f}s")

                        total_rotation = time.time() - rotation_start
                        func_total = time.time() - func_start
                        logger.info(f"✅ Thread rotation completed in {total_rotation:.2f}s total")
                        logger.info(f"🔍 [_get_or_create_thread] EXIT (after rotation) in {func_total:.3f}s")

                        return new_thread_id

                    func_total = time.time() - func_start
                    logger.info(f"🔍 [_get_or_create_thread] EXIT (existing thread, {msg_count} messages) in {func_total:.3f}s")
                    return thread_id

                except Exception as e:
                    logger.warning(f"Thread {thread_id} not found: {e}, creating new one")

            # Create new thread
            create_start = time.time()
            logger.info(f"🔍 [_get_or_create_thread] Creating NEW thread via OpenAI...")
            thread = self.client.beta.threads.create()
            thread_id = thread.id
            create_time = time.time() - create_start
            logger.info(f"🔍 [_get_or_create_thread] New thread created in {create_time:.3f}s: {thread_id[:20]}...")

            # Save to database
            save_start = time.time()
            logger.info(f"🔍 [_get_or_create_thread] Saving new thread_id to DB...")
            await db.execute(
                f"UPDATE users SET {column} = $1 WHERE id = $2",
                thread_id, user_id
            )
            save_time = time.time() - save_start
            logger.info(f"🔍 [_get_or_create_thread] Thread_id saved to DB in {save_time:.3f}s")

            func_total = time.time() - func_start
            logger.info(f"🔍 [_get_or_create_thread] EXIT (new thread created) in {func_total:.3f}s")
            return thread_id

        except Exception as e:
            func_total = time.time() - func_start
            logger.error(f"🔍 [_get_or_create_thread] ERROR after {func_total:.3f}s: {e}")
            return None

    async def _sync_conversation_to_thread(self, user_id: int, target_persona: str,
                                          source_persona: str, question: str, response: str):
        """Sync conversation from one persona to another's thread for context sharing"""
        if not self.client:
            return

        try:
            # Get or create target thread
            target_thread_id = await self._get_or_create_thread(user_id, target_persona)
            if not target_thread_id:
                return

            # Format context message
            persona_names = {
                'admin': 'Администратором',
                'oracle': 'Оракулом'
            }
            source_name = persona_names.get(source_persona, source_persona)

            context_message = (
                f"[Контекст из диалога с {source_name}]\n"
                f"Пользователь спросил: {question}\n"
                f"Ответ {source_name}: {response}"
            )

            # Add context to target thread
            self.client.beta.threads.messages.create(
                thread_id=target_thread_id,
                role="user",
                content=context_message
            )

            logger.debug(f"Synced conversation from {source_persona} to {target_persona} thread for user {user_id}")

        except Exception as e:
            logger.warning(f"Failed to sync conversation to {target_persona} thread: {e}")
            # Don't fail the main request if sync fails

    async def get_admin_response(self, question: str, user_context: Dict[str, Any]) -> str:
        """Generate Administrator persona response with context"""
        request_start = time.time()
        user_id = user_context.get('user_id', 'unknown')

        logger.info(f"⏱️  [ADMIN] Request START for user {user_id}: '{question[:50]}...'")

        if not self.client or not self.admin_assistant_id:
            return await self._admin_stub(question)

        try:
            # Update instructions from DB on first use
            step_start = time.time()
            await self._update_assistant_instructions_from_db('admin')
            logger.info(f"⏱️  [ADMIN] Instructions updated in {time.time() - step_start:.2f}s")

            if not user_id or user_id == 'unknown':
                logger.error("user_id not provided in user_context")
                return await self._admin_stub(question)

            # Get or create thread
            step_start = time.time()
            thread_id = await self._get_or_create_thread(user_id, 'admin')
            if not thread_id:
                return await self._admin_stub(question)

            # Count messages in thread
            try:
                messages_list = self.client.beta.threads.messages.list(thread_id=thread_id, limit=100)
                msg_count = len(messages_list.data)
                logger.info(f"⏱️  [ADMIN] Thread {thread_id[:20]}... retrieved ({msg_count} messages) in {time.time() - step_start:.2f}s")
            except Exception as e:
                logger.warning(f"Could not count messages: {e}")
                msg_count = "unknown"

            # Add context about user
            age = user_context.get('age', 25)
            gender = user_context.get('gender', 'other')
            has_subscription = user_context.get('has_subscription', False)
            free_chat = user_context.get('free_chat', False)
            archetype_primary = user_context.get('archetype_primary')
            archetype_secondary = user_context.get('archetype_secondary')

            # Build contextualized message
            step_start = time.time()
            context_prefix = await self._build_admin_context(
                age, gender, has_subscription, free_chat,
                archetype_primary, archetype_secondary
            )
            full_message = f"{context_prefix}\n\nВопрос пользователя: {question}"
            logger.info(f"⏱️  [ADMIN] Context built ({len(full_message)} chars) in {time.time() - step_start:.2f}s")

            # Log the question and context
            prompt_logger.info("="*80)
            prompt_logger.info(f"ADMIN QUESTION - User ID: {user_id}")
            prompt_logger.info("-"*80)
            prompt_logger.info(f"Question: {question}")
            prompt_logger.info(f"User Context:")
            prompt_logger.info(f"  - Age: {age}")
            prompt_logger.info(f"  - Gender: {gender}")
            prompt_logger.info(f"  - Archetype Primary: {archetype_primary}")
            prompt_logger.info(f"  - Archetype Secondary: {archetype_secondary}")
            prompt_logger.info(f"  - Has Subscription: {has_subscription}")
            prompt_logger.info(f"  - Free Chat: {free_chat}")
            prompt_logger.info("-"*80)
            prompt_logger.info(f"Full message sent to AI:")
            prompt_logger.info(full_message)
            prompt_logger.info("="*80 + "\n")

            # Check if there's an active run - cancel or wait for it
            step_start = time.time()
            try:
                runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
                if runs.data and runs.data[0].status in ['queued', 'in_progress']:
                    active_run = runs.data[0]
                    logger.warning(f"⚠️  [ADMIN] Active run {active_run.id} detected, cancelling it")
                    try:
                        self.client.beta.threads.runs.cancel(thread_id=thread_id, run_id=active_run.id)
                        # Wait a bit for cancellation
                        await asyncio.sleep(0.5)
                        logger.info(f"⏱️  [ADMIN] Run cancelled in {time.time() - step_start:.2f}s")
                    except Exception as e:
                        logger.warning(f"Could not cancel run {active_run.id}: {e}")
                else:
                    logger.info(f"⏱️  [ADMIN] No active runs found ({time.time() - step_start:.2f}s)")
            except Exception as e:
                logger.warning(f"Error checking for active runs: {e}")

            # Add message to thread
            step_start = time.time()

            # Log curl command for debugging
            api_key = os.getenv("OPENAI_API_KEY", "")
            await log_api_request_as_curl(
                operation="add_message",
                method="POST",
                url=f"https://api.openai.com/v1/threads/{thread_id}/messages",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "assistants=v2"
                },
                data={"role": "user", "content": full_message},
                user_id=user_id,
                persona='admin',
                metadata={"thread_id": thread_id}
            )

            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=full_message
            )

            response_time_ms = int((time.time() - step_start) * 1000)
            logger.info(f"⏱️  [ADMIN] Message added to thread in {time.time() - step_start:.2f}s")

            # Run assistant with truncation to last 20 messages (prevents slowdown from long history)
            step_start = time.time()

            # Log curl command for debugging
            await log_api_request_as_curl(
                operation="create_run",
                method="POST",
                url=f"https://api.openai.com/v1/threads/{thread_id}/runs",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "assistants=v2"
                },
                data={
                    "assistant_id": self.admin_assistant_id,
                    "truncation_strategy": {
                        "type": "last_messages",
                        "last_messages": 20
                    }
                },
                user_id=user_id,
                persona='admin',
                metadata={"thread_id": thread_id, "assistant_id": self.admin_assistant_id}
            )

            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.admin_assistant_id,
                truncation_strategy={
                    "type": "last_messages",
                    "last_messages": 20
                }
            )
            logger.info(f"⏱️  [ADMIN] Run {run.id[:20]}... created with truncation_strategy(last_messages=20) in {time.time() - step_start:.2f}s")

            # Wait for completion
            step_start = time.time()
            logger.info(f"⏳ [ADMIN] Waiting for run completion...")
            response = await self._wait_for_run_completion(thread_id, run.id)
            logger.info(f"⏱️  [ADMIN] Run completed in {time.time() - step_start:.2f}s")

            # Emergency fallback: if response is too long, truncate at last sentence
            if len(response) > 500:
                truncated = response[:497]
                # Try to cut at last sentence (period, question mark, exclamation)
                last_sentence = max(
                    truncated.rfind('.'),
                    truncated.rfind('!'),
                    truncated.rfind('?')
                )
                if last_sentence > 200:  # Only if we have at least some content
                    response = truncated[:last_sentence + 1]
                else:
                    response = truncated + "..."
                logger.warning(f"Admin response truncated from {len(response)} to {len(response)} chars")

            logger.info(f"✅ [ADMIN] Response received: {len(response)} chars")

            # Sync conversation to Oracle's thread for context sharing
            step_start = time.time()
            await self._sync_conversation_to_thread(
                user_id=user_id,
                target_persona='oracle',
                source_persona='admin',
                question=question,
                response=response
            )
            logger.info(f"⏱️  [ADMIN] Cross-thread sync completed in {time.time() - step_start:.2f}s")

            total_time = time.time() - request_start
            logger.info(f"🏁 [ADMIN] Request COMPLETED in {total_time:.2f}s total")

            return response

        except Exception as e:
            total_time = time.time() - request_start
            logger.error(f"❌ [ADMIN] Error after {total_time:.2f}s: {e}")
            return await self._admin_stub(question)

    async def get_oracle_response(self, question: str, user_context: Dict[str, Any]) -> str:
        """Generate Oracle persona response with context"""
        if not self.client or not self.oracle_assistant_id:
            return await self._oracle_stub(question)

        try:
            # Update instructions from DB on first use
            await self._update_assistant_instructions_from_db('oracle')

            user_id = user_context.get('user_id')
            if not user_id:
                logger.error("user_id not provided in user_context")
                return await self._oracle_stub(question)

            # Get or create thread
            thread_id = await self._get_or_create_thread(user_id, 'oracle')
            if not thread_id:
                return await self._oracle_stub(question)

            # Extract user context for logging
            age = user_context.get('age')
            gender = user_context.get('gender')
            archetype_primary = user_context.get('archetype_primary')
            archetype_secondary = user_context.get('archetype_secondary')
            has_subscription = user_context.get('has_subscription', False)

            # Build message
            oracle_message = f"Вопрос для размышления: {question}"

            # Log the question and context
            prompt_logger.info("="*80)
            prompt_logger.info(f"ORACLE QUESTION - User ID: {user_id}")
            prompt_logger.info("-"*80)
            prompt_logger.info(f"Question: {question}")
            prompt_logger.info(f"User Context:")
            prompt_logger.info(f"  - Age: {age}")
            prompt_logger.info(f"  - Gender: {gender}")
            prompt_logger.info(f"  - Archetype Primary: {archetype_primary}")
            prompt_logger.info(f"  - Archetype Secondary: {archetype_secondary}")
            prompt_logger.info(f"  - Has Subscription: {has_subscription}")
            prompt_logger.info("-"*80)
            prompt_logger.info(f"Full message sent to AI:")
            prompt_logger.info(oracle_message)
            prompt_logger.info("="*80 + "\n")

            # Check if there's an active run - cancel or wait for it
            try:
                runs = self.client.beta.threads.runs.list(thread_id=thread_id, limit=1)
                if runs.data and runs.data[0].status in ['queued', 'in_progress']:
                    active_run = runs.data[0]
                    logger.warning(f"Active Oracle run {active_run.id} detected, cancelling it")
                    try:
                        self.client.beta.threads.runs.cancel(thread_id=thread_id, run_id=active_run.id)
                        # Wait a bit for cancellation
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Could not cancel Oracle run {active_run.id}: {e}")
            except Exception as e:
                logger.warning(f"Error checking for active Oracle runs: {e}")

            # Add message to thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=oracle_message
            )

            # Run assistant with truncation to last 20 messages (prevents slowdown from long history)
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.oracle_assistant_id,
                truncation_strategy={
                    "type": "last_messages",
                    "last_messages": 20
                }
            )

            # Wait for completion
            response = await self._wait_for_run_completion(thread_id, run.id)

            # Limit response length
            if len(response) > 800:
                truncated = response[:797]
                last_period = truncated.rfind('.')
                if last_period > 600:
                    response = truncated[:last_period + 1]
                else:
                    response = truncated + "..."

            logger.info(f"Oracle assistant response: {len(response)} chars")

            # Sync conversation to Admin's thread for context sharing
            await self._sync_conversation_to_thread(
                user_id=user_id,
                target_persona='admin',
                source_persona='oracle',
                question=question,
                response=response
            )

            return response

        except Exception as e:
            logger.error(f"Error getting oracle assistant response: {e}")
            return await self._oracle_stub(question)

    async def get_oracle_response_stream(self, question: str, user_context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Generate Oracle response with streaming"""
        # Note: Assistants API streaming is more complex, using polling for now
        response = await self.get_oracle_response(question, user_context)

        # Simulate streaming by yielding in chunks
        chunk_size = 20
        for i in range(0, len(response), chunk_size):
            yield response[i:i + chunk_size]
            await asyncio.sleep(0.05)  # Small delay to simulate streaming

    async def _wait_for_run_completion(self, thread_id: str, run_id: str, timeout: int = 120) -> str:
        """Wait for assistant run to complete and return response"""
        start_time = time.time()
        last_status = None
        poll_count = 0

        while time.time() - start_time < timeout:
            poll_count += 1
            elapsed = time.time() - start_time

            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )

            # Log status changes or every 2 seconds
            if run.status != last_status or poll_count % 4 == 0:  # 4 polls = ~2 seconds
                logger.info(f"   📊 [Poll #{poll_count}] {elapsed:.1f}s - Status: {run.status}")
                last_status = run.status

            if run.status == 'completed':
                # Get messages
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread_id,
                    order='desc',
                    limit=1
                )

                if messages.data and messages.data[0].content:
                    # Extract text from message content
                    content = messages.data[0].content[0]
                    if hasattr(content, 'text'):
                        logger.info(f"   ✅ Response extracted ({len(content.text.value)} chars)")
                        return content.text.value

                logger.warning(f"   ⚠️  Completed but no text content found")
                return "Ответ получен, но не удалось извлечь текст."

            elif run.status in ['failed', 'cancelled', 'expired']:
                logger.error(f"   ❌ Run {run_id} ended with status: {run.status}")
                raise Exception(f"Run failed with status: {run.status}")

            # Wait before next check
            await asyncio.sleep(0.5)

        logger.error(f"   ⏰ TIMEOUT after {timeout}s (status was: {last_status})")
        raise TimeoutError(f"Run {run_id} did not complete within {timeout} seconds")

    async def _build_admin_context(self, age: int, gender: str, has_subscription: bool,
                                   free_chat: bool = False, archetype_primary: str = None,
                                   archetype_secondary: str = None) -> str:
        """Build context information for Admin - factual data only, no directives"""
        # Build archetype information if available
        archetype_info = ""
        if archetype_primary:
            from app.database.models import ArchetypeModel
            archetype_data = await ArchetypeModel.get_archetype(archetype_primary)
            if archetype_data:
                archetype_info = f"\nАрхетип пользователя: {archetype_data['name_ru']}"
                if archetype_secondary:
                    secondary_data = await ArchetypeModel.get_archetype(archetype_secondary)
                    if secondary_data:
                        archetype_info += f", вторичный: {secondary_data['name_ru']}"

        # Build subscription info
        subscription_info = "Подписка: активна" if has_subscription else "Подписка: отсутствует"

        # Return factual context only
        return f"""КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:
Возраст: {age} лет
Пол: {gender}
{subscription_info}{archetype_info}"""

    async def _admin_stub(self, question: str) -> str:
        """Fallback stub for Administrator"""
        return f"Я услышала тебя и вот мой короткий ответ: {question[:80]}… 🌟"

    async def _oracle_stub(self, question: str) -> str:
        """Fallback stub for Oracle"""
        return f"Мой персональный ответ для тебя: {question[:120]}… (мудрость требует времени для размышлений)"


# Global assistant AI client instance
assistant_ai_client = AssistantAIClient()


async def call_admin_ai(question: str, user_context: Dict[str, Any] = None) -> str:
    """Entry point for Administrator AI responses using Assistants API"""
    return await assistant_ai_client.get_admin_response(question, user_context or {})


async def call_oracle_ai(question: str, user_context: Dict[str, Any] = None) -> str:
    """Entry point for Oracle AI responses using Assistants API"""
    return await assistant_ai_client.get_oracle_response(question, user_context or {})


async def call_oracle_ai_stream(question: str, user_context: Dict[str, Any] = None) -> AsyncGenerator[str, None]:
    """Entry point for Oracle AI responses with streaming using Assistants API"""
    async for chunk in assistant_ai_client.get_oracle_response_stream(question, user_context or {}):
        yield chunk
