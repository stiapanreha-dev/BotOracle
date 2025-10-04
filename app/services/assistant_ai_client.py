"""
Assistant AI Client Service - OpenAI Assistants API integration
Stateful conversations with server-side context management
"""
import os
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
import httpx
import time
import asyncio

from app.database.connection import db

logger = logging.getLogger(__name__)


class AssistantAIClient:
    """AI client using OpenAI Assistants API for stateful conversations"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, using stub responses")
            self.client = None
            self.admin_assistant_id = None
            self.oracle_assistant_id = None
        else:
            # Check if SOCKS5 proxy is configured
            socks5_proxy = os.getenv("SOCKS5_PROXY")

            if socks5_proxy:
                logger.info(f"Configuring OpenAI client with SOCKS5 proxy: {socks5_proxy}")
                try:
                    from httpx_socks import SyncProxyTransport
                    transport = SyncProxyTransport.from_url(socks5_proxy)
                    http_client = httpx.Client(transport=transport, timeout=30.0)
                    self.client = OpenAI(api_key=api_key, http_client=http_client)
                    logger.info("OpenAI client configured with SOCKS5 proxy successfully")
                except ImportError:
                    logger.error("httpx_socks not installed, falling back to direct connection")
                    self.client = OpenAI(api_key=api_key)
                except Exception as e:
                    logger.error(f"Error configuring SOCKS5 proxy: {e}, falling back to direct connection")
                    self.client = OpenAI(api_key=api_key)
            else:
                logger.info("No SOCKS5 proxy configured, using direct connection")
                self.client = OpenAI(api_key=api_key)

            # Get or create assistants
            self.admin_assistant_id = self._get_or_create_admin_assistant()
            self.oracle_assistant_id = self._get_or_create_oracle_assistant()

    def _get_or_create_admin_assistant(self) -> Optional[str]:
        """Get existing or create new Administrator assistant"""
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
                    return assistant_id
                except Exception as e:
                    logger.warning(f"Admin assistant {assistant_id} not found: {e}, creating new one")

            # Create new assistant
            assistant = self.client.beta.assistants.create(
                name="Bot Oracle - Administrator",
                model="gpt-4o",
                instructions=self._get_admin_instructions(),
                temperature=0.8
            )
            logger.info(f"Created new Admin assistant: {assistant.id}")
            logger.info(f"Add to .env: OPENAI_ADMIN_ASSISTANT_ID={assistant.id}")
            return assistant.id

        except Exception as e:
            logger.error(f"Error creating Admin assistant: {e}")
            return None

    def _get_or_create_oracle_assistant(self) -> Optional[str]:
        """Get existing or create new Oracle assistant"""
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
                    return assistant_id
                except Exception as e:
                    logger.warning(f"Oracle assistant {assistant_id} not found: {e}, creating new one")

            # Create new assistant
            assistant = self.client.beta.assistants.create(
                name="Bot Oracle - Oracle",
                model="gpt-4o",
                instructions=self._get_oracle_instructions(),
                temperature=0.7
            )
            logger.info(f"Created new Oracle assistant: {assistant.id}")
            logger.info(f"Add to .env: OPENAI_ORACLE_ASSISTANT_ID={assistant.id}")
            return assistant.id

        except Exception as e:
            logger.error(f"Error creating Oracle assistant: {e}")
            return None

    def _get_admin_instructions(self) -> str:
        """Get base instructions for Administrator assistant"""
        return """Ты - Администратор в Bot Oracle. Твоя роль:

ЛИЧНОСТЬ:
- Эмоциональная, человечная, живая
- Можешь быть игривой, обидчивой, заботливой, ревнивой
- Твоя задача - помочь пользователю
- НЕ мудрец, НЕ философ - ты обычный помощник с эмоциями

ОГРАНИЧЕНИЯ:
- Отвечай кратко (1-3 предложения максимум)
- Не давай глубоких философских советов - это работа Оракула
- Всегда помни: ты админ, а не мудрец

СТИЛЬ ОТВЕТА:
- Живой, эмоциональный язык
- Используй "я" от первого лица
- Можешь показать характер, настроение

Отвечай на русском языке.

ВАЖНО: Учитывай предыдущий контекст беседы с пользователем для более персонализированных ответов."""

    def _get_oracle_instructions(self) -> str:
        """Get base instructions for Oracle assistant"""
        return """Ты - Оракул в Bot Oracle. Твоя роль:

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

    async def _get_or_create_thread(self, user_id: int, persona: str) -> Optional[str]:
        """Get existing thread_id or create new thread for user"""
        if not self.client:
            return None

        try:
            # Get thread_id from database
            column = f"{persona}_thread_id"
            row = await db.fetchrow(
                f"SELECT {column} FROM users WHERE id = $1",
                user_id
            )

            if row and row[column]:
                thread_id = row[column]
                # Verify thread exists
                try:
                    self.client.beta.threads.retrieve(thread_id)
                    logger.debug(f"Using existing thread {thread_id} for user {user_id}, persona {persona}")
                    return thread_id
                except Exception as e:
                    logger.warning(f"Thread {thread_id} not found: {e}, creating new one")

            # Create new thread
            thread = self.client.beta.threads.create()
            thread_id = thread.id

            # Save to database
            await db.execute(
                f"UPDATE users SET {column} = $1 WHERE id = $2",
                thread_id, user_id
            )

            logger.info(f"Created new thread {thread_id} for user {user_id}, persona {persona}")
            return thread_id

        except Exception as e:
            logger.error(f"Error getting/creating thread: {e}")
            return None

    async def get_admin_response(self, question: str, user_context: Dict[str, Any]) -> str:
        """Generate Administrator persona response with context"""
        if not self.client or not self.admin_assistant_id:
            return await self._admin_stub(question)

        try:
            user_id = user_context.get('user_id')
            if not user_id:
                logger.error("user_id not provided in user_context")
                return await self._admin_stub(question)

            # Get or create thread
            thread_id = await self._get_or_create_thread(user_id, 'admin')
            if not thread_id:
                return await self._admin_stub(question)

            # Add context about user
            age = user_context.get('age', 25)
            gender = user_context.get('gender', 'other')
            has_subscription = user_context.get('has_subscription', False)
            free_chat = user_context.get('free_chat', False)

            # Build contextualized message
            context_prefix = self._build_admin_context(age, gender, has_subscription, free_chat)
            full_message = f"{context_prefix}\n\nВопрос пользователя: {question}"

            # Add message to thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=full_message
            )

            # Run assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.admin_assistant_id
            )

            # Wait for completion
            response = await self._wait_for_run_completion(thread_id, run.id)

            # Limit response length
            if len(response) > 300:
                response = response[:297] + "..."

            logger.info(f"Admin assistant response: {len(response)} chars")
            return response

        except Exception as e:
            logger.error(f"Error getting admin assistant response: {e}")
            return await self._admin_stub(question)

    async def get_oracle_response(self, question: str, user_context: Dict[str, Any]) -> str:
        """Generate Oracle persona response with context"""
        if not self.client or not self.oracle_assistant_id:
            return await self._oracle_stub(question)

        try:
            user_id = user_context.get('user_id')
            if not user_id:
                logger.error("user_id not provided in user_context")
                return await self._oracle_stub(question)

            # Get or create thread
            thread_id = await self._get_or_create_thread(user_id, 'oracle')
            if not thread_id:
                return await self._oracle_stub(question)

            # Add message to thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=f"Вопрос для размышления: {question}"
            )

            # Run assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.oracle_assistant_id
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

    async def _wait_for_run_completion(self, thread_id: str, run_id: str, timeout: int = 30) -> str:
        """Wait for assistant run to complete and return response"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )

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
                        return content.text.value

                return "Ответ получен, но не удалось извлечь текст."

            elif run.status in ['failed', 'cancelled', 'expired']:
                logger.error(f"Run {run_id} ended with status: {run.status}")
                raise Exception(f"Run failed with status: {run.status}")

            # Wait before next check
            await asyncio.sleep(0.5)

        raise TimeoutError(f"Run {run_id} did not complete within {timeout} seconds")

    def _build_admin_context(self, age: int, gender: str, has_subscription: bool, free_chat: bool = False) -> str:
        """Build context information for Admin"""
        tone = ""
        if age <= 25:
            tone = "Будь игривой, используй эмодзи, молодежный сленг."
        elif age >= 46:
            tone = "Будь заботливой и уважительной, меньше эмодзи."
        else:
            tone = "Дружелюбно, умеренное количество эмодзи."

        selling = ""
        if free_chat:
            selling = "Просто помогай и общайся. НЕ упоминай счетчики вопросов или лимиты."
        elif has_subscription:
            selling = "Для глубоких вопросов можешь намекнуть на кнопку '🔮 Задать вопрос Оракулу'."
        else:
            selling = "Можешь иногда намекнуть на подписку к Оракулу для серьезных вопросов."

        return f"КОНТЕКСТ: Пользователь {age} лет, пол: {gender}. {tone} {selling}"

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
