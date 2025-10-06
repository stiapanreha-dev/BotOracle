"""
Smart Messages Service - AI-generated system messages
Uses prompts from database to generate personalized system messages
"""
import logging
import json
import os
from typing import Dict, Any, Optional, List
from openai import OpenAI
import httpx

from app.database.connection import db

logger = logging.getLogger(__name__)


class SmartMessagesService:
    """Service for generating AI-powered system messages"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, using stub responses")
            self.client = None
        else:
            # Check if SOCKS5 proxy is configured
            socks5_proxy = os.getenv("SOCKS5_PROXY")

            if socks5_proxy:
                logger.info(f"Configuring Smart Messages with SOCKS5 proxy: {socks5_proxy}")
                try:
                    from httpx_socks import SyncProxyTransport
                    transport = SyncProxyTransport.from_url(socks5_proxy)
                    http_client = httpx.Client(transport=transport, timeout=30.0)
                    self.client = OpenAI(api_key=api_key, http_client=http_client)
                except ImportError:
                    logger.error("httpx_socks not installed, falling back to direct connection")
                    self.client = OpenAI(api_key=api_key)
                except Exception as e:
                    logger.error(f"Error configuring SOCKS5 proxy: {e}, falling back to direct connection")
                    self.client = OpenAI(api_key=api_key)
            else:
                self.client = OpenAI(api_key=api_key)

    async def _get_prompt(self, key: str) -> Optional[str]:
        """Get prompt template from database"""
        try:
            row = await db.fetchrow(
                "SELECT prompt_text FROM ai_prompts WHERE key = $1 AND is_active = TRUE",
                key
            )
            if row:
                return row['prompt_text']
            logger.error(f"Prompt not found for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Error fetching prompt {key}: {e}")
            return None

    async def _get_archetype_info(self, archetype_code: str) -> Dict[str, str]:
        """Get archetype information from database"""
        try:
            row = await db.fetchrow(
                "SELECT name_ru, description, communication_style FROM archetypes WHERE code = $1",
                archetype_code
            )
            if row:
                return {
                    'name': row['name_ru'],
                    'description': row['description'],
                    'communication_style': row['communication_style']
                }
            return {'name': 'Неизвестный', 'description': '', 'communication_style': ''}
        except Exception as e:
            logger.error(f"Error fetching archetype {archetype_code}: {e}")
            return {'name': 'Неизвестный', 'description': '', 'communication_style': ''}

    async def _call_openai(self, prompt: str, temperature: float = 0.7, json_mode: bool = False) -> str:
        """Call OpenAI API with given prompt"""
        if not self.client:
            return "AI unavailable"

        try:
            response_format = {"type": "json_object"} if json_mode else {"type": "text"}

            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты — AI-помощник Oracle Lounge. Следуй инструкциям точно."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format=response_format
            )

            return completion.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "Error generating response"

    # ========================================================================
    # Welcome Messages
    # ========================================================================

    async def generate_welcome_message(self) -> str:
        """Generate welcome message for new user"""
        prompt = await self._get_prompt('welcome_new_user')
        if not prompt:
            return "👋 Привет! Добро пожаловать в Oracle Lounge — пространство для глубоких разговоров."

        response = await self._call_openai(prompt, temperature=0.8)
        return response

    # ========================================================================
    # Onboarding Messages
    # ========================================================================

    async def generate_onboarding_questions(self, age: int, gender: str) -> List[str]:
        """Generate 2 onboarding questions for archetype detection (adapted to age/gender)"""
        prompt_template = await self._get_prompt('onboarding_question_generator')
        if not prompt_template:
            return [
                "Представь: ты оказался в ситуации, где нужно выбрать между безопасностью и свободой. Что бы ты сделал и почему?",
                "У тебя есть идея, которая кажется тебе важной, но все вокруг сомневаются. Твои действия?"
            ]

        # Format prompt with user context
        prompt = prompt_template.format(age=age, gender=gender)
        response = await self._call_openai(prompt, temperature=0.9)

        # Parse questions (separated by double newline)
        questions = [q.strip() for q in response.split('\n\n') if q.strip()]

        # Ensure we have at least 2 questions, take first 2
        if len(questions) < 2:
            logger.warning(f"Expected at least 2 questions, got {len(questions)}, using fallback")
            return [
                "Представь: ты оказался в ситуации, где нужно выбрать между безопасностью и свободой. Что бы ты сделал и почему?",
                "У тебя есть идея, которая кажется тебе важной, но все вокруг сомневаются. Твои действия?"
            ]

        return questions[:2]  # Take first 2 questions

    async def validate_onboarding_response(self, question: str, user_response: str) -> Dict[str, Any]:
        """Validate if user response is meaningful or trolling"""
        prompt_template = await self._get_prompt('onboarding_validate_response')
        if not prompt_template:
            # Simple fallback validation
            word_count = len(user_response.split())
            is_valid = word_count >= 5 and len(user_response) >= 20
            return {
                'is_valid': is_valid,
                'reason': 'Ответ слишком короткий' if not is_valid else 'Ответ содержательный'
            }

        prompt = prompt_template.format(question=question, user_response=user_response)
        response = await self._call_openai(prompt, temperature=0.5, json_mode=True)

        try:
            result = json.loads(response)
            return {
                'is_valid': result.get('is_valid', False),
                'reason': result.get('reason', '')
            }
        except json.JSONDecodeError:
            logger.error(f"Failed to parse validation response: {response}")
            # Fallback
            word_count = len(user_response.split())
            is_valid = word_count >= 5
            return {
                'is_valid': is_valid,
                'reason': 'Ответ слишком короткий' if not is_valid else 'Ответ содержательный'
            }

    async def analyze_archetype(self, responses: List[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze user responses and determine archetype"""
        prompt_template = await self._get_prompt('onboarding_archetype_analysis')
        if not prompt_template:
            # Fallback to random archetype
            return {
                'primary': 'hero',
                'secondary': 'sage',
                'confidence': 0.5,
                'explanation': 'Архетип определен автоматически'
            }

        # Format responses for analysis
        responses_text = "\n\n".join([
            f"Вопрос {i+1}: {r['question']}\nОтвет: {r['response']}"
            for i, r in enumerate(responses)
        ])

        prompt = prompt_template.format(responses=responses_text)
        response = await self._call_openai(prompt, temperature=0.6, json_mode=True)

        try:
            result = json.loads(response)
            return {
                'primary': result.get('primary', 'hero'),
                'secondary': result.get('secondary'),
                'confidence': result.get('confidence', 0.5),
                'explanation': result.get('explanation', '')
            }
        except json.JSONDecodeError:
            logger.error(f"Failed to parse archetype analysis: {response}")
            return {
                'primary': 'hero',
                'secondary': None,
                'confidence': 0.5,
                'explanation': 'Архетип определен автоматически'
            }

    async def generate_invalid_response_message(self, current_question: int, attempts_left: int) -> str:
        """Generate message for invalid/trolling response during onboarding"""
        prompt_template = await self._get_prompt('invalid_onboarding_response')
        if not prompt_template:
            if attempts_left > 0:
                return "Хочется услышать твой настоящий ответ 😊 Расскажи подробнее — как бы ты поступил и почему?"
            return "Кажется, сегодня ты не настроен на серьёзный разговор. Приходи завтра — начнём заново! 😊"

        prompt = prompt_template.format(current_question=current_question, attempts_left=attempts_left)
        response = await self._call_openai(prompt, temperature=0.7)
        return response

    async def generate_onboarding_final_message(self, archetype_code: str, confidence: float) -> str:
        """Generate final message after archetype determination"""
        prompt_template = await self._get_prompt('onboarding_final_message')
        archetype_info = await self._get_archetype_info(archetype_code)

        if not prompt_template:
            return f"Спасибо за откровенность! Я вижу в тебе {archetype_info['name']} — {archetype_info['description']}. Теперь я буду общаться с тобой именно так, как это важно для тебя."

        prompt = prompt_template.format(
            archetype=archetype_code,
            archetype_name=archetype_info['name'],
            archetype_description=archetype_info['description'],
            confidence=confidence
        )

        response = await self._call_openai(prompt, temperature=0.7)
        return response

    # ========================================================================
    # Oracle Messages
    # ========================================================================

    async def generate_clarifying_questions(self, question: str, archetype_code: str) -> Dict[str, Any]:
        """Generate 1-2 clarifying questions before Oracle response"""
        prompt_template = await self._get_prompt('oracle_clarifying_questions')
        archetype_info = await self._get_archetype_info(archetype_code)

        if not prompt_template:
            return {
                'questions': ["Расскажи подробнее о контексте ситуации?"],
                'intro': ""
            }

        prompt = prompt_template.format(
            question=question,
            archetype=archetype_code,
            archetype_description=archetype_info['description'],
            communication_style=archetype_info['communication_style']
        )

        response = await self._call_openai(prompt, temperature=0.8, json_mode=True)

        try:
            result = json.loads(response)
            return {
                'questions': result.get('questions', []),
                'intro': result.get('intro', '')
            }
        except json.JSONDecodeError:
            logger.error(f"Failed to parse clarifying questions: {response}")
            return {
                'questions': ["Расскажи подробнее о контексте ситуации?"],
                'intro': ""
            }

    # ========================================================================
    # CRM Messages
    # ========================================================================

    async def generate_crm_message(self, task_type: str, user_context: Dict[str, Any]) -> str:
        """Generate personalized CRM message based on task type and user context"""
        # Map task types to prompt keys
        prompt_key_map = {
            'PING': 'crm_ping',
            'NUDGE_SUB': 'crm_nudge_sub',
            'RECOVERY': 'crm_recovery',
            'LIMIT_INFO': 'crm_limit_info',
            'THANKS': 'crm_thanks'
        }

        prompt_key = prompt_key_map.get(task_type)
        if not prompt_key:
            logger.warning(f"Unknown task type for CRM generation: {task_type}")
            return "привет! я здесь, если что нужно 🌟"

        prompt_template = await self._get_prompt(prompt_key)
        if not prompt_template:
            # Fallback messages for each type
            fallbacks = {
                'PING': "привет! как у тебя дела? 😊",
                'NUDGE_SUB': "хочешь больше доступа к Оракулу? попробуй премиум подписку 💎",
                'RECOVERY': "давно тебя не видела! как ты? 🌟",
                'LIMIT_INFO': "у тебя осталось мало бесплатных вопросов к Оракулу. хочешь безлимитный доступ? 🔮",
                'THANKS': "спасибо за твой вопрос! 💫"
            }
            return fallbacks.get(task_type, "привет! 😊")

        # Get archetype info if available
        archetype_code = user_context.get('archetype_primary', 'hero')
        archetype_info = await self._get_archetype_info(archetype_code)

        # Format prompt with all context
        prompt = prompt_template.format(
            age=user_context.get('age', 25),
            gender=user_context.get('gender', 'unknown'),
            archetype=archetype_code,
            archetype_name=archetype_info['name'],
            archetype_description=archetype_info['description'],
            communication_style=archetype_info['communication_style'],
            tone=user_context.get('tone', 'friendly'),
            remaining=user_context.get('remaining', 0)
        )

        response = await self._call_openai(prompt, temperature=0.9)
        return response.strip()

    # ========================================================================
    # System Messages
    # ========================================================================

    async def generate_error_message(self, error_type: str = "unknown") -> str:
        """Generate friendly error message"""
        prompt_template = await self._get_prompt('error_message')
        if not prompt_template:
            return "Что-то пошло не так с моей стороны. Попробуй через минуту? 😊"

        prompt = prompt_template.format(error_type=error_type)
        response = await self._call_openai(prompt, temperature=0.8)
        return response

    async def generate_daily_message_intro(self, archetype_code: str, daily_text: str) -> str:
        """Generate intro for daily message based on archetype"""
        prompt_template = await self._get_prompt('daily_message_intro')
        archetype_info = await self._get_archetype_info(archetype_code)

        if not prompt_template:
            return f"Держи мысль на сегодня:"

        prompt = prompt_template.format(
            archetype=archetype_code,
            archetype_description=archetype_info['description'],
            communication_style=archetype_info['communication_style'],
            daily_text=daily_text
        )

        response = await self._call_openai(prompt, temperature=0.7)
        return response


# Global instance
smart_messages = SmartMessagesService()


# Convenience functions
async def generate_welcome() -> str:
    return await smart_messages.generate_welcome_message()


async def generate_onboarding_questions(age: int, gender: str) -> List[str]:
    return await smart_messages.generate_onboarding_questions(age, gender)


async def validate_response(question: str, response: str) -> Dict[str, Any]:
    return await smart_messages.validate_onboarding_response(question, response)


async def analyze_archetype(responses: List[Dict[str, str]]) -> Dict[str, Any]:
    return await smart_messages.analyze_archetype(responses)


async def generate_clarifying_questions(question: str, archetype: str) -> Dict[str, Any]:
    return await smart_messages.generate_clarifying_questions(question, archetype)


async def generate_error_message(error_type: str = "unknown") -> str:
    return await smart_messages.generate_error_message(error_type)


async def generate_crm_message(task_type: str, user_context: Dict[str, Any]) -> str:
    return await smart_messages.generate_crm_message(task_type, user_context)
