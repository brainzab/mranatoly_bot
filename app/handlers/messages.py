import logging
import random
from aiogram import types
from aiogram.types import ReactionTypeEmoji
from app.services.ai import AiHandler
from app.database.models import ChatHistory
from app.config import (
    TARGET_USER_ID, TARGET_CHAT_ID, RESPONSES_SOSAL, 
    RARE_RESPONSE_SOSAL, RESPONSE_LETAL, RESPONSES_SCAMIL, TARGET_REACTION
)
from app.services.monitoring import monitoring, monitor_function

logger = logging.getLogger(__name__)

class MessageHandlers:
    def __init__(self, bot, db_pool):
        self.bot = bot
        self.db_pool = db_pool
        self.bot_info = None
    
    async def init_bot_info(self):
        """Инициализирует информацию о боте"""
        if not self.bot_info:
            self.bot_info = await self.bot.get_me()
    
    @monitor_function
    async def handle_message(self, message: types.Message):
        """Основной обработчик всех входящих сообщений"""
        try:
            if not message.from_user or not message.text:
                return
            
            await self.init_bot_info()
            
            # Увеличиваем счетчик сообщений
            monitoring.increment_message()
            
            # Логируем входящее сообщение
            chat_id = message.chat.id
            user_id = message.from_user.id
            message_id = message.message_id
            logger.info(f"Сообщение от {user_id} в чате {chat_id}: {message.text[:50]}...")
            
            # Сохраняем сообщение в базу данных если нужно
            if chat_id == TARGET_CHAT_ID:
                await self._save_message_safe(chat_id, user_id, message_id, "user", message.text)
            
            # Обрабатываем реакции если нужно
            await self._process_reactions(message)
            
            # Обрабатываем шаблонные ответы
            if await self._process_template_responses(message):
                return
            
            # Проверяем, нужно ли обрабатывать как запрос к AI
            await self._process_ai_request(message)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}")
            monitoring.log_error(e, {"message": message.text})

    async def _save_message_safe(self, chat_id, user_id, message_id, role, content):
        """Безопасное сохранение сообщения с обработкой ошибок"""
        try:
            await ChatHistory.save_message(
                self.db_pool, chat_id, user_id, message_id, role, content
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {e}")

    async def _process_reactions(self, message):
        """Обрабатывает реакции на сообщения"""
        if message.from_user.id == TARGET_USER_ID:
            try:
                await self.bot.set_message_reaction(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reaction=[ReactionTypeEmoji(emoji=TARGET_REACTION)]
                )
            except Exception as e:
                logger.error(f"Ошибка при установке реакции: {e}")

    async def _process_template_responses(self, message):
        """Обрабатывает шаблонные ответы на определенные сообщения"""
        message_text = message.text.lower()
        
        if message_text in ['сосал?', 'sosal?']:
            response = RARE_RESPONSE_SOSAL if random.random() < 0.1 else random.choice(RESPONSES_SOSAL)
            sent_message = await message.reply(response)
            if message.chat.id == TARGET_CHAT_ID:
                await self._save_message_safe(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", response)
            return True
            
        elif message_text == 'летал?':
            sent_message = await message.reply(RESPONSE_LETAL)
            if message.chat.id == TARGET_CHAT_ID:
                await self._save_message_safe(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", RESPONSE_LETAL)
            return True
            
        elif message_text == 'скамил?':
            response = random.choice(RESPONSES_SCAMIL)
            sent_message = await message.reply(response)
            if message.chat.id == TARGET_CHAT_ID:
                await self._save_message_safe(message.chat.id, self.bot_info.id, sent_message.message_id, "assistant", response)
            return True
            
        return False

    async def _process_ai_request(self, message):
        """Обрабатывает запросы к AI"""
        message_text = message.text.lower()
        bot_username = f"@{self.bot_info.username.lower()}"
        bot_id = self.bot_info.id
        
        is_reply_to_bot = (message.reply_to_message and 
                          message.reply_to_message.from_user and 
                          message.reply_to_message.from_user.id == bot_id)
        is_tagged = bot_username in message_text
        
        if not (is_tagged or is_reply_to_bot):
            return
        
        query = message_text.replace(bot_username, "").strip() if is_tagged else message_text
        if not query:
            sent_message = await message.reply("И хуле ты мне пишешь пустоту, петушара?")
            if message.chat.id == TARGET_CHAT_ID:
                await self._save_message_safe(message.chat.id, bot_id, sent_message.message_id, "assistant", "И хуле ты мне пишешь пустоту, петушара?")
            return
        
        # Получаем историю чата
        chat_history = await ChatHistory.get_chat_history(self.db_pool, message.chat.id)
        
        # Если это ответ на сообщение бота, добавляем это сообщение в историю
        if is_reply_to_bot and message.reply_to_message.text:
            chat_history.append({"role": "assistant", "content": message.reply_to_message.text})
        
        # Увеличиваем счетчик AI-запросов
        monitoring.increment_ai_request()
        
        # Отправляем запрос к AI
        ai_response = await AiHandler.get_ai_response(chat_history, query)
        
        # Отправляем ответ
        sent_message = await message.reply(ai_response)
        
        # Сохраняем ответ бота в историю чата
        if message.chat.id == TARGET_CHAT_ID:
            await self._save_message_safe(message.chat.id, bot_id, sent_message.message_id, "assistant", ai_response)