import logging
from openai import AsyncOpenAI
from app.config import DEEPSEEK_API_KEY, AI_SYSTEM_PROMPT, MAX_TOKENS, AI_TEMPERATURE

logger = logging.getLogger(__name__)

# Настройка клиента DeepSeek
deepseek_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# Класс для работы с AI
class AiHandler:
    @staticmethod
    async def get_ai_response(chat_history, query):
        """Получает ответ от AI на основе истории чата и запроса"""
        try:
            messages = [
                {"role": "system", "content": AI_SYSTEM_PROMPT}
            ] + chat_history + [{"role": "user", "content": query}]
            
            logger.info(f"Отправка запроса к AI: {query[:50]}...")
            
            # Можно добавить повторные попытки здесь, если API нестабильно
            for attempt in range(3):
                try:
                    response = await deepseek_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        max_tokens=MAX_TOKENS,
                        temperature=AI_TEMPERATURE
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    logger.warning(f"Попытка {attempt+1}/3 запроса к AI не удалась: {e}")
                    if attempt == 2:  # последняя попытка
                        raise
            
            # Этот код не должен выполняться, но для полноты:
            return "Ошибка получения ответа от AI"
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            return f"Ошибка, ёбана: {str(e)}"