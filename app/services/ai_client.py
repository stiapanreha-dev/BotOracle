"""
AI Client Service - GPT-4o integration for Oracle Lounge
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
            archetype_primary = user_context.get('archetype_primary')
            archetype_secondary = user_context.get('archetype_secondary')

            system_prompt = await self._build_admin_system_prompt(
                age, gender, has_subscription, free_chat,
                archetype_primary, archetype_secondary
            )

            result = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Пользователь спрашивает: {question}"}
                ],
                temperature=0.8,
                max_tokens=300  # Increased from 200 to allow more natural responses
            )

            response = result.choices[0].message.content.strip()

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
                logger.warning(f"Admin response truncated from original to {len(response)} chars")

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
            archetype_primary = user_context.get('archetype_primary')
            archetype_secondary = user_context.get('archetype_secondary')

            system_prompt = await self._build_oracle_system_prompt(archetype_primary, archetype_secondary)

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
            archetype_primary = user_context.get('archetype_primary')
            archetype_secondary = user_context.get('archetype_secondary')

            system_prompt = await self._build_oracle_system_prompt(archetype_primary, archetype_secondary)

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

    async def _build_admin_system_prompt(self, age: int, gender: str, has_subscription: bool = False,
                                        free_chat: bool = False, archetype_primary: str = None,
                                        archetype_secondary: str = None) -> str:
        """Build system prompt for Administrator persona from database"""
        try:
            # Get base prompt
            base_prompt = await self._get_prompt('admin_base')
            if not base_prompt:
                logger.error("Admin base prompt not found, using hardcoded fallback")
                return self._hardcoded_admin_prompt(age, has_subscription, free_chat, archetype_primary)

            # Get tone: prioritize archetype-based, fallback to age-based
            if archetype_primary:
                # Archetype-based tone takes priority
                tone = "ТОНАЛЬНОСТЬ: Адаптируй стиль общения под архетип пользователя (см. АРХЕТИП ПОЛЬЗОВАТЕЛЯ ниже)."
            elif age:
                # Age-specific tone for legacy users
                if age <= 25:
                    tone = await self._get_prompt('admin_tone_young')
                elif age >= 46:
                    tone = await self._get_prompt('admin_tone_senior')
                else:
                    tone = await self._get_prompt('admin_tone_middle')

                if not tone:
                    logger.warning("Admin tone prompt not found, using default")
                    tone = "ТОНАЛЬНОСТЬ: Держи баланс - дружелюбно, но не слишком игриво. Умеренное количество эмодзи."
            else:
                # Default neutral tone
                tone = "ТОНАЛЬНОСТЬ: Держи баланс - дружелюбно, но не слишком игриво. Умеренное количество эмодзи."

            # Add archetype information if available
            archetype_context = ""
            if archetype_primary:
                # Get archetype info from database
                from app.database.models import ArchetypeModel
                archetype_info = await ArchetypeModel.get_archetype(archetype_primary)
                if archetype_info:
                    archetype_context = f"\n\nАРХЕТИП ПОЛЬЗОВАТЕЛЯ: {archetype_info['name_ru']}\n"
                    archetype_context += f"Описание: {archetype_info['description']}\n"
                    archetype_context += f"Стиль общения: {archetype_info['communication_style']}"

            # Combine prompts
            return f"{base_prompt}\n\n{tone}{archetype_context}"

        except Exception as e:
            logger.error(f"Error building admin prompt from DB: {e}")
            return self._hardcoded_admin_prompt(age, has_subscription, free_chat, archetype_primary)

    def _hardcoded_admin_prompt(self, age: int, has_subscription: bool = False, free_chat: bool = False,
                                archetype_primary: str = None) -> str:
        """Hardcoded fallback for admin prompt"""
        # Tone: prioritize archetype, fallback to age-based
        tone_guide = ""
        if archetype_primary:
            tone_guide = "Адаптируй стиль общения под архетип пользователя (Мудрец, Герой, и т.д.)."
        elif age:
            if age <= 25:
                tone_guide = "Будь игривой, используй эмодзи, молодежный сленг. Можешь быть чуть капризной или кокетливой."
            elif age >= 46:
                tone_guide = "Будь заботливой и уважительной, но сохраняй теплоту. Меньше эмодзи, более серьезный тон."
            else:
                tone_guide = "Держи баланс - дружелюбно, но не слишком игриво. Умеренное количество эмодзи."
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

        # Add archetype hint if available
        archetype_note = ""
        if archetype_primary:
            archetype_map = {
                'hero': 'Герой (действие, достижения)',
                'sage': 'Мудрец (знания, анализ)',
                'caregiver': 'Заботливый (помощь, эмпатия)',
                'rebel': 'Бунтарь (свобода, вызов)',
                'creator': 'Творец (создание, самовыражение)',
                'explorer': 'Исследователь (открытия)',
                'lover': 'Любовник (близость, страсть)',
                'jester': 'Шут (радость, юмор)',
                'ruler': 'Правитель (контроль, лидерство)',
                'magician': 'Маг (трансформация)'
            }
            archetype_note = f"\n\nАРХЕТИП ПОЛЬЗОВАТЕЛЯ: {archetype_map.get(archetype_primary, archetype_primary)}\nАдаптируй стиль общения под этот архетип."

        return f"""Ты - Администратор в Oracle Lounge. Твоя роль:

ЛИЧНОСТЬ:
- Эмоциональная, человечная, живая
- Можешь быть игривой, обидчивой, заботливой, ревнивой
- Твоя задача - {task_description}
- НЕ мудрец, НЕ философ - ты обычный помощник с эмоциями

ТОНАЛЬНОСТЬ: {tone_guide}

ОГРАНИЧЕНИЯ:
- Отвечай ОЧЕНЬ кратко: 1-2 предложения, максимум 3
- Твой ответ должен быть логически законченным, но коротким
- Не давай глубоких философских советов - это работа Оракула
- Всегда помни: ты админ, а не мудрец
- ВАЖНО: Формулируй ответ так, чтобы он был коротким И законченным, без обрывов мысли
{selling_guide}

СТИЛЬ ОТВЕТА:
- Живой, эмоциональный язык
- Используй "я" от первого лица
- Можешь показать характер, настроение{archetype_note}

Отвечай на русском языке."""

    async def _build_oracle_system_prompt(self, archetype_primary: str = None,
                                         archetype_secondary: str = None) -> str:
        """Build system prompt for Oracle persona from database"""
        try:
            prompt = await self._get_prompt('oracle_system')
            if not prompt:
                logger.error("Oracle system prompt not found, using hardcoded fallback")
                return self._hardcoded_oracle_prompt(archetype_primary)

            # Add archetype information if available
            archetype_context = ""
            if archetype_primary:
                # Get archetype info from database
                from app.database.models import ArchetypeModel
                archetype_info = await ArchetypeModel.get_archetype(archetype_primary)
                if archetype_info:
                    archetype_context = f"\n\nАРХЕТИП ПОЛЬЗОВАТЕЛЯ: {archetype_info['name_ru']}\n"
                    archetype_context += f"Описание: {archetype_info['description']}\n"
                    archetype_context += f"Адаптируй ответ под этот архетип: {archetype_info['communication_style']}"

            return f"{prompt}{archetype_context}"
        except Exception as e:
            logger.error(f"Error building oracle prompt from DB: {e}")
            return self._hardcoded_oracle_prompt(archetype_primary)

    def _hardcoded_oracle_prompt(self, archetype_primary: str = None) -> str:
        """Hardcoded fallback for oracle prompt"""
        # Add archetype hint if available
        archetype_note = ""
        if archetype_primary:
            archetype_map = {
                'hero': 'Герой (действие, достижения)',
                'sage': 'Мудрец (знания, анализ)',
                'caregiver': 'Заботливый (помощь, эмпатия)',
                'rebel': 'Бунтарь (свобода, вызов)',
                'creator': 'Творец (создание, самовыражение)',
                'explorer': 'Исследователь (открытия)',
                'lover': 'Любовник (близость, страсть)',
                'jester': 'Шут (радость, юмор)',
                'ruler': 'Правитель (контроль, лидерство)',
                'magician': 'Маг (трансформация)'
            }
            archetype_note = f"\n\nАРХЕТИП ПОЛЬЗОВАТЕЛЯ: {archetype_map.get(archetype_primary, archetype_primary)}\nАдаптируй глубину и стиль ответа под этот архетип."

        return f"""Ты - Оракул в Oracle Lounge. Твоя роль:

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
- Говори во втором лице ("ты", "вам"){archetype_note}

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

    async def generate_daily_whisper(self, user_context: Dict[str, Any]) -> str:
        """Generate personalized daily whisper based on user profile"""
        if not self.client:
            return await self._daily_whisper_stub(user_context)

        try:
            # Get prompt template from database
            prompt_template = await self._get_prompt('daily_whisper_generator')
            if not prompt_template:
                logger.warning("Daily whisper prompt not found in database, using stub")
                return await self._daily_whisper_stub(user_context)

            # Extract user context
            age = user_context.get('age', 25)
            gender = user_context.get('gender', 'other')
            gender_ru = 'мужской' if gender == 'male' else 'женский' if gender == 'female' else 'другое'

            # Get archetype info
            archetype_primary = user_context.get('archetype_primary', 'explorer')
            archetype_map = {
                'innocent': ('Невинный/Простодушный', 'оптимизм, вера в добро, стремление к простоте'),
                'sage': ('Мудрец', 'поиск истины, анализ, глубокое понимание'),
                'explorer': ('Искатель', 'свобода, открытия, стремление к новому'),
                'outlaw': ('Бунтарь', 'независимость, разрушение старого, революция'),
                'magician': ('Маг', 'трансформация, влияние, создание реальности'),
                'hero': ('Герой', 'мужество, преодоление, достижение цели'),
                'lover': ('Любовник', 'страсть, близость, эстетика'),
                'jester': ('Шут', 'радость, легкость, игра'),
                'everyperson': ('Обыватель', 'принадлежность, реализм, солидарность'),
                'caregiver': ('Заботливый', 'помощь другим, сострадание, защита'),
                'ruler': ('Правитель', 'контроль, порядок, ответственность'),
                'creator': ('Творец', 'самовыражение, инновации, создание')
            }
            archetype_name, archetype_desc = archetype_map.get(archetype_primary, ('Искатель', 'поиск себя и смысла'))

            # Format the prompt
            system_prompt = prompt_template.format(
                age=age,
                gender=gender_ru,
                archetype=archetype_name,
                archetype_description=archetype_desc
            )

            # Generate whisper
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Создай шепот дня для этого пользователя."}
                ],
                temperature=0.9,  # Higher creativity for varied whispers
                max_tokens=150
            )

            whisper = response.choices[0].message.content.strip()

            # Remove quotes if AI wrapped the response
            if whisper.startswith('"') and whisper.endswith('"'):
                whisper = whisper[1:-1]
            if whisper.startswith('«') and whisper.endswith('»'):
                whisper = whisper[1:-1]

            logger.info(f"Generated daily whisper for user (age={age}, gender={gender}, archetype={archetype_primary})")
            return whisper

        except Exception as e:
            logger.error(f"Error generating daily whisper: {e}")
            return await self._daily_whisper_stub(user_context)

    async def _daily_whisper_stub(self, user_context: Dict[str, Any]) -> str:
        """Fallback stub for daily whisper"""
        stubs = [
            "иногда тишина говорит больше, чем тысяча слов",
            "твоя уникальность — не в том, чтобы быть лучше других, а в том, чтобы быть собой",
            "не всё, что кажется концом, действительно заслуживает траура",
            "сегодня позволь себе просто быть — без целей и ожиданий"
        ]
        # Simple rotation based on day
        from datetime import date
        index = date.today().day % len(stubs)
        return stubs[index]

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

async def generate_daily_whisper(user_context: Dict[str, Any] = None) -> str:
    """Entry point for generating personalized daily whisper"""
    return await ai_client.generate_daily_whisper(user_context or {})