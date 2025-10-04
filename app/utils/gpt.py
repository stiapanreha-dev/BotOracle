from openai import AsyncOpenAI
from app.config import config
import logging
import httpx
from httpx_socks import AsyncProxyTransport

logger = logging.getLogger(__name__)

def get_openai_client():
    """Get OpenAI client with optional proxy support"""
    http_client = None

    if config.SOCKS5_PROXY:
        # Create SOCKS5 proxy transport
        transport = AsyncProxyTransport.from_url(config.SOCKS5_PROXY)
        http_client = httpx.AsyncClient(transport=transport)
        logger.info(f"Using SOCKS5 proxy: {config.SOCKS5_PROXY}")

    return AsyncOpenAI(
        api_key=config.OPENAI_API_KEY,
        http_client=http_client
    )

SYSTEM_PROMPT = """
Ты — доброжелательный аналитик и консультант.
Отвечай на русском языке коротко и ясно, структурируй ответ в 3–5 пунктов.
Будь полезным, конкретным и практичным в своих советах.
Избегай общих фраз, давай действенные рекомендации.
"""

async def get_gpt_response(user_question: str) -> tuple[str, int]:
    client = get_openai_client()

    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_question}
            ],
            max_tokens=800,
            temperature=0.7
        )

        answer = response.choices[0].message.content.strip()
        tokens_used = response.usage.total_tokens

        logger.info(f"GPT response generated, tokens used: {tokens_used}")
        return answer, tokens_used

    except Exception as e:
        logger.error(f"GPT request failed: {e}")
        return "Извините, произошла ошибка при обработке вашего вопроса. Попробуйте позже.", 0
    finally:
        # Close the http client if we created one
        if hasattr(client, '_client') and client._client:
            await client._client.aclose()