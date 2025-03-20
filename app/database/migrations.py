import logging
import asyncpg
from app.services.monitoring import monitoring

logger = logging.getLogger(__name__)

async def apply_migrations(pool):
    """
    Применяет необходимые миграции к базе данных
    """
    try:
        monitoring.increment_db_operation()
        async with pool.acquire() as conn:
            # Проверяем, есть ли таблица миграций
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'migrations')"
            )
            
            if not exists:
                await conn.execute(
                    """
                    CREATE TABLE migrations (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(50) NOT NULL,
                        applied_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
            
            # Получаем последнюю примененную миграцию
            last_version = await conn.fetchval(
                "SELECT version FROM migrations ORDER BY id DESC LIMIT 1"
            )
            
            # Список миграций для применения
            migrations = [
                # версия, описание, SQL-запрос
                ("1.0", "Создание первичной структуры", """
                    CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history (user_id);
                """),
                ("1.1", "Добавление поля tokens", """
                    ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS tokens INTEGER DEFAULT 0;
                """),
                # Добавляйте новые миграции здесь
            ]
            
            # Применяем миграции, которые еще не были применены
            for version, description, sql in migrations:
                if last_version is None or version > last_version:
                    logger.info(f"Применение миграции {version}: {description}")
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO migrations (version) VALUES ($1)",
                        version
                    )
                    logger.info(f"Миграция {version} успешно применена")
                    
        logger.info("Все миграции успешно применены")
        return True
    except asyncpg.PostgresError as e:
        logger.error(f"Ошибка базы данных при применении миграций: {e}")
        return False
    except Exception as e:
        logger.error(f"Неизвестная ошибка при применении миграций: {e}")
        return False