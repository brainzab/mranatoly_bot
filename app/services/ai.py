import logging
from openai import AsyncOpenAI
from app.config import DEEPSEEK_API_KEY, AI_SYSTEM_PROMPT, MAX_TOKENS, AI_TEMPERATURE
from app.services.api import retry_async
import re

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
            
            # Используем retry_async вместо собственной реализации повторных попыток
            response = await retry_async(
                AiHandler._request_ai_completion, 
                messages=messages, 
                max_retries=3, 
                retry_delay=1
            )
            
            # Обрабатываем маркдаун-разметку для Telegram
            processed_response = AiHandler._process_markdown(response)
            
            return processed_response
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            return f"Ошибка, ёбана: {str(e)}"

    @staticmethod
    async def _request_ai_completion(messages):
        """Выполняет запрос к AI API"""
        response = await deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=AI_TEMPERATURE
        )
        return response.choices[0].message.content
        
    @staticmethod
    def _process_markdown(text):
        """Исправляет Markdown-разметку для корректного отображения в Telegram"""
        # Сначала экранируем все одиночные звездочки, которые не являются частью форматирования
        text = re.sub(r'(?<!\*)\*(?!\*)', '\\*', text)
        
        # Заменяем ** на соответствующие Telegram разметки для жирного текста
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        
        # Заменяем __ на соответствующие Telegram разметки для курсива
        text = re.sub(r'__(.+?)__', r'_\1_', text)
        
        # Заменяем _ на соответствующие Telegram разметки для курсива
        text = re.sub(r'(?<!\_)\_(?!\_)(.+?)(?<!\_)\_(?!\_)', r'_\1_', text)
        
        # Заменяем ` на соответствующие Telegram разметки для моноширинного текста
        text = re.sub(r'`(.+?)`', r'`\1`', text)
        
        # Заменяем ``` на соответствующие Telegram разметки для блока кода
        text = re.sub(r'```(.+?)```', r'```\1```', text)
        
        return text