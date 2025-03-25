import logging
import asyncio
import asyncpg
import pytz
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from functools import partial
from datetime import datetime, timedelta

from app.config import (
    TELEGRAM_TOKEN, DATABASE_URL, CODE_VERSION,
    CHAT_ID, ADMIN_CHAT_ID, BACKUP_ENABLED, MONITORING_ENABLED
)
from app.services.messages import MorningMessageSender
from app.services.monitoring import monitoring
from app.database.models import ChatHistory
from app.database.migrations import apply_migrations
from app.database.backup import backup_database
from app.handlers.commands import CommandHandlers
from app.handlers.messages import MessageHandlers

logger = logging.getLogger(__name__)

class BotApp:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.dp = Dispatcher()
        self.scheduler = None
        self.morning_sender = None
        self.keep_alive_task = None
        self.db_pool = None
        self.command_handlers = None
        self.message_handlers = None

    async def keep_alive(self):
        """Задача для поддержания бота в активном состоянии"""
        while True:
            logger.info("Бот активен")
            await asyncio.sleep(300)

    async def on_startup(self):
        """Выполняется при запуске бота"""
        logger.info(f"Запуск бота версии {CODE_VERSION}")
        
        # Инициализация БД
        self.db_pool = await asyncpg.create_pool(DATABASE_URL)
        await ChatHistory.create_tables(self.db_pool)
        
        # Применяем миграции
        await apply_migrations(self.db_pool)
        
        # Инициализация компонентов бота
        self.morning_sender = MorningMessageSender(self.bot)
        self.command_handlers = CommandHandlers(self.bot, self.db_pool)
        self.message_handlers = MessageHandlers(self.bot, self.db_pool)
        
        # Настройка мониторинга
        if MONITORING_ENABLED:
            monitoring.set_bot(self.bot)
            
        # Запуск планировщика
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
        
        # Утренние сообщения - запускаем через минуту после запуска и затем каждый день в 7:30
        self.scheduler.add_job(
            self.morning_sender.send_morning_message, 
            trigger=CronTrigger(hour=7, minute=30)
        )
        
        # Добавляем еще одну задачу для безопасного запуска утреннего сообщения через минуту после запуска
        self.scheduler.add_job(
            self.morning_sender.send_morning_message,
            trigger='date',
            run_date=datetime.now() + timedelta(minutes=1),
            id='initial_morning_message'
        )
        
        # Вечерняя статистика - отправляем каждый день в 21:00
        self.scheduler.add_job(
            self._send_evening_stats,
            trigger=CronTrigger(hour=21, minute=0)
        )
        
        # Очистка старых сообщений
        self.scheduler.add_job(
            lambda: ChatHistory.cleanup_old_messages(self.db_pool), 
            trigger=CronTrigger(hour=0, minute=0)
        )
        
        # Проверка состояния базы данных
        self.scheduler.add_job(
            self.command_handlers.check_database_health,
            trigger='interval',
            minutes=30
        )
        
        # Резервное копирование БД
        if BACKUP_ENABLED:
            self.scheduler.add_job(
                backup_database, 
                args=[DATABASE_URL],
                trigger=CronTrigger(day_of_week='mon-sun', hour=3, minute=0)  # Каждый день в 3:00
            )
            
        # Логирование использования памяти
        self.scheduler.add_job(
            monitoring.log_memory_usage,
            trigger='interval',
            hours=2
        )
        
        # Запуск планировщика
        self.scheduler.start()
        logger.info("Планировщик запущен")
        
        # Запуск задачи поддержания активности
        self.keep_alive_task = asyncio.create_task(self.keep_alive())
        
        # Уведомление о запуске
        if MONITORING_ENABLED:
            await monitoring.notify_admin(f"🚀 Бот запущен, версия {CODE_VERSION}")
            
    async def on_shutdown(self):
        """Выполняется при остановке бота"""
        logger.info("Остановка бота")
        
        # Остановка задачи keep_alive
        if self.keep_alive_task and not self.keep_alive_task.done():
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
                
        # Остановка планировщика
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Планировщик остановлен")
            
        # Закрытие соединения с базой данных
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Соединение с PostgreSQL закрыто")
            
        # Закрытие сессии бота
        await self.bot.session.close()
        logger.info("Бот остановлен")

    def setup_handlers(self):
        """Регистрация обработчиков сообщений и команд"""
        # Команды
        self.dp.message.register(self.command_handlers.command_start, Command("start"))
        self.dp.message.register(self.command_handlers.command_version, Command("version"))
        self.dp.message.register(self.command_handlers.command_reset, Command("reset"))
        self.dp.message.register(self.command_handlers.command_stats, Command("stats"))
        self.dp.message.register(self.command_handlers.command_test, Command("test"))
        self.dp.message.register(self.command_handlers.command_pogoda, Command("pogoda"))
        self.dp.message.register(self.command_handlers.command_wld, Command("wld"))
        self.dp.message.register(self.command_handlers.command_rub, Command("rub"))
        self.dp.message.register(self.command_handlers.command_byn, Command("byn"))
        self.dp.message.register(self.command_handlers.command_chatstats, Command("chatstats"))
        self.dp.message.register(self.command_handlers.command_reaction, Command("reaction"))
        self.dp.message.register(self.command_handlers.command_users_stat, Command("users_stat"))
        
        # Команды для футбольных матчей
        self.dp.message.register(
            partial(self.command_handlers.command_team_matches, team_name="real"), 
            Command("real")
        )
        self.dp.message.register(
            partial(self.command_handlers.command_team_matches, team_name="lfc"), 
            Command("lfc")
        )
        self.dp.message.register(
            partial(self.command_handlers.command_team_matches, team_name="arsenal"), 
            Command("arsenal")
        )
        
        # Обработчик всех сообщений
        self.dp.message.register(self.message_handlers.handle_message)

    async def start(self):
        """Запуск бота"""
        await self.on_startup()  # Сначала инициализируем все компоненты
        self.setup_handlers()    # Затем регистрируем обработчики
        try:
            await self.dp.start_polling(self.bot, allowed_updates=["message"])
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            if MONITORING_ENABLED:
                monitoring.log_error(e, {"context": "bot_polling"})
        finally:
            await self.on_shutdown()

    async def _send_evening_stats(self):
        """Отправляет вечернюю статистику в чат"""
        try:
            logger.info("Отправка вечерней статистики")
            
            # Получаем общую статистику
            stats = monitoring.get_stats()
            
            # Формируем сообщение со статистикой
            message = (
                f"📊 Статистика за день:\n\n"
                f"⏱️ Время работы бота: {stats['uptime']}\n"
                f"💬 Обработано сообщений: {stats['message_count']}\n"
                f"⌨️ Команд выполнено: {stats['command_count']}\n"
                f"🧠 AI-запросов: {stats['ai_request_count']}\n"
                f"❌ Ошибок: {stats['error_count']}"
            )
            
            # Отправляем в основной чат
            await self.bot.send_message(
                chat_id=CHAT_ID,
                text=message
            )
            
            logger.info("Вечерняя статистика отправлена")
        except Exception as e:
            logger.error(f"Ошибка при отправке вечерней статистики: {e}")
            if MONITORING_ENABLED:
                monitoring.log_error(e, {"context": "evening_stats"})
