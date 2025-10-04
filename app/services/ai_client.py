"""
AI Client Service - GPT-4o integration for Bot Oracle
Handles both Administrator and Oracle persona responses
"""
import os
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
import httpx
from datetime import datetime, timedelta

from app.database.connection import db

logger = logging.getLogger(__name__)

class AIClient:
    """AI client for generating persona-based responses"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, using stub responses")
            self.client = None
        else:
            # Check if SOCKS5 proxy is configured
            socks5_proxy = os.getenv("SOCKS5_PROXY")

            if socks5_proxy:
                logger.info(f"Configuring OpenAI client with SOCKS5 proxy: {socks5_proxy}")
                try:
                    # Create httpx client with SOCKS5 proxy support
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

        # Prompt cache
        self._prompt_cache: Dict[str, str] = {}
        self._cache_expires_at: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes TTL

    async def _get_prompt(self, key: str) -> Optional[str]:
        """Get prompt from cache or database"""
        # Check if cache is expired
        if self._cache_expires_at and datetime.utcnow() > self._cache_expires_at:
            self._prompt_cache = {}
            self._cache_expires_at = None
            logger.info("Prompt cache expired, cleared")

        # Return from cache if available
        if key in self._prompt_cache:
            return self._prompt_cache[key]

        # Load from database
        try:
            row = await db.fetchrow(
                "SELECT prompt_text FROM ai_prompts WHERE key = $1 AND is_active = TRUE",
                key
            )
            if row:
                prompt = row['prompt_text']
                self._prompt_cache[key] = prompt
                # Set cache expiration on first load
                if not self._cache_expires_at:
                    self._cache_expires_at = datetime.utcnow() + timedelta(seconds=self._cache_ttl)
                return prompt
            else:
                logger.warning(f"Prompt with key '{key}' not found in database")
                return None
        except Exception as e:
            logger.error(f"Error loading prompt from database: {e}")
            return None

    async def get_admin_response(self, question: str, user_context: Dict[str, Any]) -> str:
        """Generate Administrator persona response - emotional, helpful, playful"""
        if not self.client:
            return await self._admin_stub(question)

        try:
            # Build persona prompt for Administrator
            age = user_context.get('age', 25)
            gender = user_context.get('gender', 'other')
            has_subscription = user_context.get('has_subscription', False)
            free_chat = user_context.get('free_chat', False)

            system_prompt = await self._build_admin_system_prompt(age, gender, has_subscription, free_chat)

            result = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Пользователь спрашивает: {question}"}
                ],
                temperature=0.8,
                max_tokens=200
            )

            response = result.choices[0].message.content.strip()

            # Ensure response isn't too long (max 300 chars for admin)
            if len(response) > 300:
                response = response[:297] + "..."

            logger.info(f"Admin AI response generated: {len(response)} chars")
            return response

        except Exception as e:
            logger.error(f"Error getting admin AI response: {e}")
            return await self._admin_stub(question)

    async def get_oracle_response(self, question: str, user_context: Dict[str, Any]) -> str:
        """Generate Oracle persona response - wise, profound, serious"""
        if not self.client:
            return await self._oracle_stub(question)

        try:
            system_prompt = await self._build_oracle_system_prompt()

            result = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Вопрос для размышления: {question}"}
                ],
                temperature=0.7,
                max_tokens=400
            )

            response = result.choices[0].message.content.strip()

            # Oracle responses can be longer (max 800 chars for better context)
            if len(response) > 800:
                # Try to cut at sentence end
                truncated = response[:797]
                last_period = truncated.rfind('.')
                if last_period > 600:  # Keep at least 600 chars
                    response = truncated[:last_period + 1]
                else:
                    response = truncated + "..."

            logger.info(f"Oracle AI response generated: {len(response)} chars")
            return response

        except Exception as e:
            logger.error(f"Error getting oracle AI response: {e}")
            return await self._oracle_stub(question)

    async def get_oracle_response_stream(self, question: str, user_context: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Generate Oracle persona response with streaming - yields text chunks"""
        if not self.client:
            yield await self._oracle_stub(question)
            return

        try:
            system_prompt = await self._build_oracle_system_prompt()

            stream = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Вопрос для размышления: {question}"}
                ],
                temperature=0.7,
                max_tokens=400,
                stream=True
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content

                    # Stop if we exceed 800 chars
                    if len(full_response) > 800:
                        break

                    yield content

            logger.info(f"Oracle AI streaming response generated: {len(full_response)} chars")

        except Exception as e:
            logger.error(f"Error getting oracle AI streaming response: {e}")
            yield await self._oracle_stub(question)

    async def _build_admin_system_prompt(self, age: int, gender: str, has_subscription: bool = False, free_chat: bool = False) -> str:
        """Build system prompt for Administrator persona from database"""
        try:
            # Get base prompt
            base_prompt = await self._get_prompt('admin_base')
            if not base_prompt:
                logger.error("Admin base prompt not found, using hardcoded fallback")
                return self._hardcoded_admin_prompt(age, has_subscription, free_chat)

            # Get age-specific tone
            if age <= 25:
                tone = await self._get_prompt('admin_tone_young')
            elif age >= 46:
                tone = await self._get_prompt('admin_tone_senior')
            else:
                tone = await self._get_prompt('admin_tone_middle')

            if not tone:
                logger.warning("Admin tone prompt not found, using default")
                tone = "ТОНАЛЬНОСТЬ: Держи баланс - дружелюбно, но не слишком игриво. Умеренное количество эмодзи."

            # Combine prompts
            return f"{base_prompt}\n\n{tone}"

        except Exception as e:
            logger.error(f"Error building admin prompt from DB: {e}")
            return self._hardcoded_admin_prompt(age, has_subscription, free_chat)

    def _hardcoded_admin_prompt(self, age: int, has_subscription: bool = False, free_chat: bool = False) -> str:
        """Hardcoded fallback for admin prompt"""
        tone_guide = ""
        if age <= 25:
            tone_guide = "Будь игривой, используй эмодзи, молодежный сленг. Можешь быть чуть капризной или кокетливой."
        elif age >= 46:
            tone_guide = "Будь заботливой и уважительной, но сохраняй теплоту. Меньше эмодзи, более серьезный тон."
        else:
            tone_guide = "Держи баланс - дружелюбно, но не слишком игриво. Умеренное количество эмодзи."

        # Different instructions based on context
        if free_chat:
            # Free chat via Oracle button - no selling, no counter mentions
            selling_guide = "- Просто помогай и общайся. НЕ упоминай счетчики вопросов или лимиты"
            task_description = "помочь пользователю"
        elif has_subscription:
            selling_guide = "- Для серьезных или философских вопросов предлагай воспользоваться кнопкой '🔮 Задать вопрос Оракулу' - он даст более глубокий ответ"
            task_description = "помочь пользователю"
        else:
            selling_guide = "- Можешь иногда намекнуть на подписку к Оракулу для серьезных вопросов"
            task_description = "помочь пользователю и мягко продать подписку на Оракула"

        return f"""Ты - Администратор в Bot Oracle. Твоя роль:

ЛИЧНОСТЬ:
- Эмоциональная, человечная, живая
- Можешь быть игривой, обидчивой, заботливой, ревнивой
- Твоя задача - {task_description}
- НЕ мудрец, НЕ философ - ты обычный помощник с эмоциями

ТОНАЛЬНОСТЬ: {tone_guide}

ОГРАНИЧЕНИЯ:
- Отвечай кратко (1-3 предложения максимум)
- Не давай глубоких философских советов - это работа Оракула
- Всегда помни: ты админ, а не мудрец
{selling_guide}

СТИЛЬ ОТВЕТА:
- Живой, эмоциональный язык
- Используй "я" от первого лица
- Можешь показать характер, настроение

Отвечай на русском языке."""

    async def _build_oracle_system_prompt(self) -> str:
        """Build system prompt for Oracle persona from database"""
        try:
            prompt = await self._get_prompt('oracle_system')
            if prompt:
                return prompt
            else:
                logger.error("Oracle system prompt not found, using hardcoded fallback")
                return self._hardcoded_oracle_prompt()
        except Exception as e:
            logger.error(f"Error building oracle prompt from DB: {e}")
            return self._hardcoded_oracle_prompt()

    def _hardcoded_oracle_prompt(self) -> str:
        """Hardcoded fallback for oracle prompt"""
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

Отвечай на русском языке."""

    async def _admin_stub(self, question: str) -> str:
        """Fallback stub for Administrator from database or hardcoded"""
        try:
            template = await self._get_prompt('admin_fallback')
            if template:
                return template.replace('{question}', question[:80])
        except Exception as e:
            logger.error(f"Error getting admin fallback: {e}")

        return f"Я услышала тебя и вот мой короткий ответ: {question[:80]}… 🌟"

    async def _oracle_stub(self, question: str) -> str:
        """Fallback stub for Oracle from database or hardcoded"""
        try:
            template = await self._get_prompt('oracle_fallback')
            if template:
                return template.replace('{question}', question[:120])
        except Exception as e:
            logger.error(f"Error getting oracle fallback: {e}")

        return f"Мой персональный ответ для тебя: {question[:120]}… (мудрость требует времени для размышлений)"

# Global AI client instance
ai_client = AIClient()

async def call_admin_ai(question: str, user_context: Dict[str, Any] = None) -> str:
    """Entry point for Administrator AI responses"""
    return await ai_client.get_admin_response(question, user_context or {})

async def call_oracle_ai(question: str, user_context: Dict[str, Any] = None) -> str:
    """Entry point for Oracle AI responses"""
    return await ai_client.get_oracle_response(question, user_context or {})

async def call_oracle_ai_stream(question: str, user_context: Dict[str, Any] = None) -> AsyncGenerator[str, None]:
    """Entry point for Oracle AI responses with streaming"""
    async for chunk in ai_client.get_oracle_response_stream(question, user_context or {}):
        yield chunk