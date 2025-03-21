import logging
import asyncpg
from datetime import datetime
from app.services.monitoring import monitoring

logger = logging.getLogger(__name__)

class ChatHistory:
    """Класс для работы с историей чата в базе данных"""
    
    @staticmethod
    async def create_tables(pool):
        """Создает необходимые таблицы если они не существуют"""
        async with pool.acquire() as conn:
            monitoring.increment_db_operation()
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT,
                    user_id BIGINT,
                    message_id BIGINT,
                    role TEXT,
                    content TEXT CHECK (LENGTH(content) <= 4000),
                    timestamp DOUBLE PRECISION,
                    reset_id INTEGER DEFAULT 0,
                    tokens INTEGER DEFAULT 0
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_reset_ids (
                    chat_id BIGINT PRIMARY KEY,
                    reset_id INTEGER DEFAULT 0
                )
            """)
            
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_chat_id ON chat_history (chat_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history (timestamp)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_reset_id ON chat_history (reset_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history (user_id)")
    
    @staticmethod
    async def save_message(pool, chat_id, user_id, message_id, role, content, reset_id=None):
        """Сохраняет сообщение в базу данных"""
        try:
            content = content.encode('utf-8', 'ignore').decode('utf-8')
            content = content[:4000] if len(content) > 4000 else content
            
            if reset_id is None:
                reset_id = await ChatHistory.get_reset_id(pool, chat_id)
                
            monitoring.increment_db_operation()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO chat_history (chat_id, user_id, message_id, role, content, timestamp, reset_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    chat_id, user_id, message_id, role, content, datetime.now().timestamp(), reset_id
                )
            logger.info(f"Сообщение сохранено: chat_id={chat_id}, user_id={user_id}, role={role}")
            return True
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка PostgreSQL при сохранении сообщения: {e}")
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при сохранении сообщения: {e}")
            return False
    
    @staticmethod
    async def get_chat_history(pool, chat_id, limit=30):
        """Получает историю чата для указанного chat_id"""
        reset_id = await ChatHistory.get_reset_id(pool, chat_id)
        
        try:
            monitoring.increment_db_operation()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT role, content
                    FROM chat_history
                    WHERE chat_id = $1 AND reset_id = $2
                    ORDER BY timestamp DESC
                    LIMIT $3
                    """,
                    chat_id, reset_id, limit
                )
                return [{"role": row['role'], "content": row['content']} for row in reversed(rows)]
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка базы данных при получении истории чата: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении истории чата: {e}")
            return []
    
    @staticmethod
    async def get_reset_id(pool, chat_id):
        """Получает текущий reset_id для чата"""
        try:
            monitoring.increment_db_operation()
            async with pool.acquire() as conn:
                reset_id = await conn.fetchval(
                    "SELECT reset_id FROM chat_reset_ids WHERE chat_id = $1",
                    chat_id
                )
                if reset_id is None:
                    # Если записи нет, создаём с reset_id = 0
                    await conn.execute(
                        "INSERT INTO chat_reset_ids (chat_id, reset_id) VALUES ($1, 0) ON CONFLICT (chat_id) DO NOTHING",
                        chat_id
                    )
                    return 0
                return reset_id
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка получения reset_id: {e}")
            return 0
    
    @staticmethod
    async def increment_reset_id(pool, chat_id):
        """Увеличивает reset_id на 1 для указанного чата"""
        try:
            monitoring.increment_db_operation()
            async with pool.acquire() as conn:
                # Увеличиваем reset_id на 1, если запись существует, или создаём новую
                await conn.execute(
                    """
                    INSERT INTO chat_reset_ids (chat_id, reset_id)
                    VALUES ($1, 1)
                    ON CONFLICT (chat_id)
                    DO UPDATE SET reset_id = chat_reset_ids.reset_id + 1
                    """,
                    chat_id
                )
                new_reset_id = await conn.fetchval(
                    "SELECT reset_id FROM chat_reset_ids WHERE chat_id = $1",
                    chat_id
                )
                return new_reset_id
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка увеличения reset_id: {e}")
            return 0
    
    @staticmethod
    async def cleanup_old_messages(pool, days=30):
        """Удаляет сообщения старше указанного количества дней"""
        try:
            monitoring.increment_db_operation()
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM chat_history WHERE timestamp < EXTRACT(EPOCH FROM NOW() - INTERVAL '$1 days')",
                    days
                )
                logger.info(f"Очистка старых сообщений (старше {days} дней) завершена")
                return True
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка PostgreSQL при очистке старых сообщений: {e}")
            return False
    
    @staticmethod
    async def get_chat_messages_stats(pool, chat_id, period=None):
        """
        Получает статистику сообщений в чате за указанный период
        
        :param pool: Пул соединений с БД
        :param chat_id: ID чата
        :param period: Период (day, month, year, all). По умолчанию - all
        :return: Словарь со статистикой
        """
        try:
            monitoring.increment_db_operation()
            
            # Определяем timestamp начала периода
            timestamp_condition = ""
            if period == "day":
                # Сообщения за последние 24 часа
                timestamp_condition = "AND timestamp > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 day')"
            elif period == "month":
                # Сообщения за последние 30 дней
                timestamp_condition = "AND timestamp > EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')"
            elif period == "year":
                # Сообщения за последние 365 дней
                timestamp_condition = "AND timestamp > EXTRACT(EPOCH FROM NOW() - INTERVAL '365 days')"
            
            async with pool.acquire() as conn:
                # Получаем общее количество сообщений за период
                query = f"""
                SELECT COUNT(*) 
                FROM chat_history 
                WHERE chat_id = $1 AND role = 'user' {timestamp_condition}
                """
                total_messages = await conn.fetchval(query, chat_id)
                
                # Получаем статистику по пользователям
                query = f"""
                SELECT user_id, COUNT(*) as message_count
                FROM chat_history
                WHERE chat_id = $1 AND role = 'user' {timestamp_condition}
                GROUP BY user_id
                ORDER BY message_count DESC
                """
                rows = await conn.fetch(query, chat_id)
                
                # Формируем результат
                users_stats = []
                for row in rows:
                    users_stats.append({
                        "user_id": row["user_id"],
                        "message_count": row["message_count"]
                    })
                
                return {
                    "total_messages": total_messages,
                    "users": users_stats
                }
                
        except asyncpg.PostgresError as e:
            logger.error(f"Ошибка PostgreSQL при получении статистики сообщений: {e}")
            return {"total_messages": 0, "users": []}
        except Exception as e:
            logger.error(f"Ошибка при получении статистики сообщений: {e}")
            return {"total_messages": 0, "users": []}

    @staticmethod
    async def get_usernames_by_ids(pool, bot, user_ids):
        """
        Получает имена пользователей по их ID
        
        :param pool: Пул соединений с БД
        :param bot: Экземпляр бота для получения информации о пользователях
        :param user_ids: Список ID пользователей
        :return: Словарь {user_id: username}
        """
        result = {}
        try:
            for user_id in user_ids:
                try:
                    # Пытаемся получить информацию о пользователе через API Telegram
                    chat_member = await bot.get_chat_member(chat_id=user_id, user_id=user_id)
                    user = chat_member.user
                    
                    # Формируем имя пользователя
                    if user.username:
                        name = f"@{user.username}"
                    else:
                        name = user.full_name or f"User {user_id}"
                    
                    result[user_id] = name
                except Exception as e:
                    logger.warning(f"Не удалось получить имя пользователя {user_id}: {e}")
                    result[user_id] = f"User {user_id}"
        except Exception as e:
            logger.error(f"Ошибка при получении имен пользователей: {e}")
        
        return result