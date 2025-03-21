import logging
import asyncio
import json
from datetime import datetime
import asyncpg
from app.services.drive import GoogleDriveService
from app.services.monitoring import monitoring
from app.config import DRIVE_ENABLED

logger = logging.getLogger(__name__)

class ChatExportService:
    """Сервис для экспорта истории чатов в JSON"""
    
    def __init__(self, db_pool, admin_chat_id=None, bot=None):
        self.db_pool = db_pool
        self.admin_chat_id = admin_chat_id
        self.bot = bot
        self.drive_service = GoogleDriveService() if DRIVE_ENABLED else None
    
    async def export_all_chats_history(self):
        """Экспортирует историю всех чатов в JSON-файл и загружает на Google Drive"""
        logger.info("Начало экспорта истории чатов")
        
        try:
            # Получаем список всех уникальных chat_id
            chat_ids = await self._get_all_chat_ids()
            
            if not chat_ids:
                logger.warning("Нет данных для экспорта: не найдены активные чаты")
                return None
            
            logger.info(f"Найдено {len(chat_ids)} чатов для экспорта")
            
            # Инициализируем структуру данных для экспорта
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_chats": len(chat_ids),
                "chats": {}
            }
            
            # Для каждого чата получаем историю сообщений
            for chat_id in chat_ids:
                chat_data = await self._get_chat_data(chat_id)
                # Преобразуем chat_id в строку для использования в качестве ключа в JSON
                export_data["chats"][str(chat_id)] = chat_data
            
            # Если Google Drive не включен, возвращаем данные без загрузки
            if not DRIVE_ENABLED or not self.drive_service:
                logger.info("Экспорт в Google Drive отключен")
                return export_data
            
            # Загружаем данные на Google Drive
            timestamp = datetime.now().strftime("%Y%m%d")
            file_url = self.drive_service.upload_json(
                export_data,
                f"chat_history_export_{timestamp}"
            )
            
            if file_url:
                logger.info(f"История чатов успешно экспортирована на Google Drive: {file_url}")
                
                # Отправляем уведомление администратору, если настроено
                if self.bot and self.admin_chat_id:
                    await self.bot.send_message(
                        chat_id=self.admin_chat_id,
                        text=f"История чатов успешно экспортирована на Google Drive:\n{file_url}"
                    )
                
                return file_url
            
            logger.error("Не удалось загрузить историю чатов на Google Drive")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте истории чатов: {e}")
            return None
    
    async def _get_all_chat_ids(self):
        """Получает список всех уникальных chat_id"""
        try:
            monitoring.increment_db_operation()
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT chat_id FROM chat_history ORDER BY chat_id"
                )
                return [row['chat_id'] for row in rows]
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка получения списка чатов: {e}")
            return []
    
    async def _get_chat_data(self, chat_id):
        """Получает данные о чате и его сообщениях"""
        try:
            chat_data = {
                "total_messages": 0,
                "users": {},
                "messages": []
            }
            
            # Получаем общую статистику по чату
            monitoring.increment_db_operation()
            async with self.db_pool.acquire() as conn:
                # Получаем общее количество сообщений
                chat_data["total_messages"] = await conn.fetchval(
                    "SELECT COUNT(*) FROM chat_history WHERE chat_id = $1",
                    chat_id
                )
                
                # Получаем статистику по пользователям
                user_stats = await conn.fetch(
                    """
                    SELECT user_id, COUNT(*) as message_count 
                    FROM chat_history 
                    WHERE chat_id = $1 
                    GROUP BY user_id 
                    ORDER BY message_count DESC
                    """,
                    chat_id
                )
                
                for row in user_stats:
                    user_id = str(row['user_id'])  # Преобразуем в строку для использования в качестве ключа
                    chat_data["users"][user_id] = {
                        "message_count": row['message_count']
                    }
                
                # Получаем историю сообщений (ограничиваем до 1000 последних сообщений)
                messages = await conn.fetch(
                    """
                    SELECT 
                        id, user_id, message_id, role, content, 
                        timestamp, reset_id, tokens
                    FROM chat_history 
                    WHERE chat_id = $1 
                    ORDER BY timestamp DESC 
                    LIMIT 1000
                    """,
                    chat_id
                )
                
                for msg in messages:
                    # Преобразуем timestamp в читаемый формат
                    timestamp_str = datetime.fromtimestamp(msg['timestamp']).isoformat() \
                        if msg['timestamp'] else None
                    
                    chat_data["messages"].append({
                        "id": msg['id'],
                        "user_id": msg['user_id'],
                        "message_id": msg['message_id'],
                        "role": msg['role'],
                        "content": msg['content'],
                        "timestamp": timestamp_str,
                        "reset_id": msg['reset_id'],
                        "tokens": msg['tokens']
                    })
            
            return chat_data
            
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка получения данных чата {chat_id}: {e}")
            return {
                "total_messages": 0,
                "users": {},
                "messages": [],
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Ошибка при обработке данных чата {chat_id}: {e}")
            return {
                "total_messages": 0,
                "users": {},
                "messages": [],
                "error": str(e)
            } 