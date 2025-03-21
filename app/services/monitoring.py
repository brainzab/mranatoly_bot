import time
import logging
import asyncio
import traceback
import os
import psutil
from functools import wraps
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

class BotMonitoring:
    def __init__(self, bot=None, admin_chat_id=None):
        self.bot = bot
        self.admin_chat_id = admin_chat_id
        self.error_count = 0
        self.last_errors = []  # Хранить последние N ошибок
        self.start_time = time.time()
        self.message_count = 0
        self.command_count = 0
        self.api_request_count = 0
        self.ai_request_count = 0
        self.db_operation_count = 0
        
        # Статистика по чатам
        self.chat_stats = defaultdict(lambda: {
            'message_count': 0,
            'command_count': 0,
            'api_request_count': 0,
            'ai_request_count': 0,
            'db_operation_count': 0
        })
        
    def set_bot(self, bot):
        """Устанавливает бота для отправки уведомлений"""
        self.bot = bot
        
    async def notify_admin(self, message):
        """Отправляет оповещение администратору"""
        if self.bot and self.admin_chat_id:
            try:
                await self.bot.send_message(self.admin_chat_id, message)
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление админу: {e}")
    
    def log_error(self, error, context=None):
        """Логирует ошибку и уведомляет админа если нужно"""
        self.error_count += 1
        error_msg = f"❌ Ошибка: {type(error).__name__}: {error}"
        if context:
            error_msg += f"\nКонтекст: {context}"
        
        # Добавляем трассировку
        error_trace = traceback.format_exc()
        error_msg += f"\n\nТрассировка:\n{error_trace}"
        
        # Логируем
        logger.error(error_msg)
        
        # Храним в списке последних ошибок
        self.last_errors.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': str(error),
            'trace': error_trace,
            'context': context
        })
        
        # Ограничиваем размер списка ошибок
        if len(self.last_errors) > 10:
            self.last_errors = self.last_errors[-10:]
        
        # Асинхронно уведомляем админа
        if self.bot and self.admin_chat_id:
            asyncio.create_task(self.notify_admin(error_msg[:4000]))  # Ограничиваем размер сообщения
    
    def log_memory_usage(self):
        """Логирует использование памяти процессом"""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        logger.info(f"Использование памяти: {mem_info.rss / 1024 / 1024:.2f} МБ")
    
    def get_stats(self):
        """Возвращает статистику работы бота"""
        uptime_seconds = time.time() - self.start_time
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = ""
        if days > 0:
            uptime_str += f"{int(days)}д "
        if hours > 0 or days > 0:
            uptime_str += f"{int(hours)}ч "
        if minutes > 0 or hours > 0 or days > 0:
            uptime_str += f"{int(minutes)}м "
        uptime_str += f"{int(seconds)}с"
        
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        
        return {
            "uptime": uptime_str,
            "memory_mb": f"{mem_info.rss / 1024 / 1024:.2f}",
            "message_count": self.message_count,
            "command_count": self.command_count,
            "api_request_count": self.api_request_count,
            "ai_request_count": self.ai_request_count,
            "db_operation_count": self.db_operation_count,
            "error_count": self.error_count,
            "last_errors": self.last_errors
        }
    
    def get_all_chats_stats(self):
        """Возвращает статистику по всем чатам"""
        total_stats = {
            "total_chats": len(self.chat_stats),
            "chats": {},
            "total_ai_requests": sum(stats['ai_request_count'] for stats in self.chat_stats.values()),
            "total_api_requests": sum(stats['api_request_count'] for stats in self.chat_stats.values())
        }
        
        # Добавляем статистику по каждому чату
        for chat_id, stats in self.chat_stats.items():
            total_stats["chats"][chat_id] = stats.copy()
        
        return total_stats
        
    def increment_message(self, chat_id=None):
        """Увеличивает счетчик обработанных сообщений"""
        self.message_count += 1
        if chat_id:
            self.chat_stats[chat_id]['message_count'] += 1
        
    def increment_command(self, chat_id=None):
        """Увеличивает счетчик выполненных команд"""
        self.command_count += 1
        if chat_id:
            self.chat_stats[chat_id]['command_count'] += 1
        
    def increment_api_request(self, chat_id=None):
        """Увеличивает счетчик API-запросов"""
        self.api_request_count += 1
        if chat_id:
            self.chat_stats[chat_id]['api_request_count'] += 1
        
    def increment_ai_request(self, chat_id=None):
        """Увеличивает счетчик запросов к AI"""
        self.ai_request_count += 1
        if chat_id:
            self.chat_stats[chat_id]['ai_request_count'] += 1
        
    def increment_db_operation(self, chat_id=None):
        """Увеличивает счетчик операций с базой данных"""
        self.db_operation_count += 1
        if chat_id:
            self.chat_stats[chat_id]['db_operation_count'] += 1

# Создаем глобальный экземпляр мониторинга
monitoring = BotMonitoring()

def monitor_function(func):
    """Декоратор для мониторинга выполнения функций"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        function_name = func.__name__
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            # Если выполнение слишком долгое, можно логировать
            if execution_time > 5:  # больше 5 секунд
                logger.warning(f"Функция {function_name} выполнялась долго: {execution_time:.2f}с")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            context = {
                "function": function_name,
                "args": str(args),
                "kwargs": str(kwargs),
                "execution_time": f"{execution_time:.2f}s"
            }
            monitoring.log_error(e, context)
            raise  # Перебрасываем исключение дальше
    return wrapper

class RateLimiter:
    """Ограничитель частоты запросов"""
    def __init__(self, rate_limit=5, period=60):
        # rate_limit - число запросов
        # period - период в секундах
        self.rate_limit = rate_limit
        self.period = period
        self.user_timestamps = {}  # user_id -> [timestamps]
    
    def can_process(self, user_id):
        now = time.time()
        period_ago = now - self.period
        
        if user_id not in self.user_timestamps:
            self.user_timestamps[user_id] = []
        
        # Удаление старых временных меток
        self.user_timestamps[user_id] = [ts for ts in self.user_timestamps[user_id] if ts > period_ago]
        
        # Проверка лимита
        if len(self.user_timestamps[user_id]) >= self.rate_limit:
            return False
        
        # Добавление новой метки
        self.user_timestamps[user_id].append(now)
        return True
