import asyncio
import logging
import sys
from app.bot import BotApp
from app.config import CODE_VERSION

logger = logging.getLogger(__name__)

async def main():
    """Точка входа в приложение"""
    bot_app = BotApp()
    try:
        logger.info("Запуск бота...")
        await bot_app.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Необработанная ошибка в main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print(f"Старт приложения. Версия: {CODE_VERSION}")
    asyncio.run(main())