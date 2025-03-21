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