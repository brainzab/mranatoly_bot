import logging
from aiogram import types
from aiogram.filters import Command
from functools import partial
from app.services.api import ApiClient
from app.database.models import ChatHistory
from app.config import CODE_VERSION, TARGET_CHAT_ID, TEAM_IDS
from app.services.monitoring import monitoring, monitor_function

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self, bot, db_pool):
        self.bot = bot
        self.db_pool = db_pool

    @monitor_function
    async def command_start(self, message: types.Message):
        """Обработчик команды /start"""
        monitoring.increment_command()
        sent_message = await message.reply(f"Привет, я бот версии {CODE_VERSION}")
        if message.chat.id == TARGET_CHAT_ID:
            await ChatHistory.save_message(
                self.db_pool, 
                message.chat.id, 
                self.bot.id, 
                sent_message.message_id, 
                "assistant", 
                f"Привет, я бот версии {CODE_VERSION}"
            )

    @monitor_function
    async def command_version(self, message: types.Message):
        """Обработчик команды /version"""
        monitoring.increment_command()
        sent_message = await message.reply(f"Версия бота: {CODE_VERSION}")
        if message.chat.id == TARGET_CHAT_ID:
            await ChatHistory.save_message(
                self.db_pool, 
                message.chat.id, 
                self.bot.id, 
                sent_message.message_id, 
                "assistant", 
                f"Версия бота: {CODE_VERSION}"
            )

    @monitor_function
    async def command_reset(self, message: types.Message):
        """Обработчик команды /reset для сброса контекста AI"""
        monitoring.increment_command()
        chat_id = message.chat.id
        await ChatHistory.increment_reset_id(self.db_pool, chat_id)
        sent_message = await message.reply("Контекст для AI сброшен, мудила. Начинаем с чистого листа!")
        if chat_id == TARGET_CHAT_ID:
            await ChatHistory.save_message(
                self.db_pool, 
                chat_id, 
                self.bot.id, 
                sent_message.message_id, 
                "assistant", 
                "Контекст для AI сброшен, мудила. Начинаем с чистого листа!"
            )

    @monitor_function
    async def command_stats(self, message: types.Message):
        """Обработчик команды /stats для получения статистики"""
        monitoring.increment_command()
        stats = monitoring.get_stats()
        response = (
            f"📊 Статистика бота:\n\n"
            f"⏱️ Время работы: {stats['uptime']}\n"
            f"💾 Использование памяти: {stats['memory_mb']} МБ\n"
            f"💬 Обработано сообщений: {stats['message_count']}\n"
            f"⌨️ Выполнено команд: {stats['command_count']}\n"
            f"🌐 API-запросов: {stats['api_request_count']}\n"
            f"🧠 AI-запросов: {stats['ai_request_count']}\n"
            f"🗄️ Операций с БД: {stats['db_operation_count']}\n"
            f"❌ Ошибок: {stats['error_count']}\n\n"
            f"🤖 Версия бота: {CODE_VERSION}"
        )
        await message.reply(response)

    @monitor_function
    async def command_test(self, message: types.Message):
        """Тестовая команда для проверки работоспособности бота"""
        monitoring.increment_command()
        try:
            # Тестируем базу данных
            db_ok = await self.check_database_health()
            
            # Тестируем API-клиенты
            weather_test = await ApiClient.get_weather("Minsk,BY")
            currency_test = await ApiClient.get_currency_rates()
            
            response = (
                f"🧪 Тест системы:\n\n"
                f"🤖 Бот: Онлайн ✅\n"
                f"🗃️ База данных: {'Работает ✅' if db_ok else 'Ошибка ❌'}\n"
                f"🌤️ API погоды: {'Работает ✅' if 'Нет данных' not in weather_test else 'Ошибка ❌'}\n"
                f"💱 API валют: {'Работает ✅' if all(currency_test) else 'Ошибка ❌'}\n\n"
                f"📋 Версия: {CODE_VERSION}"
            )
            
            await message.reply(response)
        except Exception as e:
            logger.error(f"Ошибка в команде /test: {e}")
            await message.reply(f"❌ Произошла ошибка: {e}")

    async def check_database_health(self):
        """Проверяет доступность базы данных и логирует результат"""
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result == 1:
                    logger.info("Проверка базы данных: ОК")
                    return True
                else:
                    logger.error(f"Проверка базы данных вернула неожиданный результат: {result}")
                    return False
        except Exception as e:
            logger.error(f"Ошибка при проверке базы данных: {e}")
            return False

    @monitor_function
    async def command_team_matches(self, message: types.Message, team_name):
        """Обработчик команд для показа матчей команды"""
        monitoring.increment_command()
        team_id = TEAM_IDS.get(team_name)
        if not team_id:
            sent_message = await message.reply("Команда не найдена, мудила!")
            if message.chat.id == TARGET_CHAT_ID:
                await ChatHistory.save_message(
                    self.db_pool, 
                    message.chat.id, 
                    self.bot.id, 
                    sent_message.message_id, 
                    "assistant", 
                    "Команда не найдена, мудила!"
                )
            return
        
        data = await ApiClient.get_team_matches(team_id)
        if not data or not data.get("response"):
            sent_message = await message.reply("Не удалось получить данные о матчах. Пиздец какой-то!")
            if message.chat.id == TARGET_CHAT_ID:
                await ChatHistory.save_message(
                    self.db_pool, 
                    message.chat.id, 
                    self.bot.id, 
                    sent_message.message_id, 
                    "assistant", 
                    "Не удалось получить данные о матчах. Пиздец какой-то!"
                )
            return
        
        response = f"Последние 5 матчей {team_name.upper()}:\n\n"
        for fixture in data["response"]:
            fixture_id = fixture["fixture"]["id"]
            home_team = fixture["teams"]["home"]["name"]
            away_team = fixture["teams"]["away"]["name"]
            home_goals = fixture["goals"]["home"] if fixture["goals"]["home"] is not None else 0
            away_goals = fixture["goals"]["away"] if fixture["goals"]["away"] is not None else 0
            date = fixture["fixture"]["date"].split("T")[0]
            result_icon = ("🟢" if home_goals > away_goals else "🔴" if home_goals < away_goals else "🟡") \
                if fixture["teams"]["home"]["id"] == team_id else \
                ("🟢" if away_goals > home_goals else "🔴" if away_goals < home_goals else "🟡")
            
            events_data = await ApiClient.get_match_events(fixture_id)
            goals_str = "Голы: "
            if events_data and events_data.get("response"):
                goal_events = [e for e in events_data["response"] if e["type"] == "Goal"]
                goals_str += ", ".join([f"{e['player']['name']} ({e['time']['elapsed']}')" for e in goal_events]) \
                    if goal_events else "Нет данных о голах"
            else:
                goals_str += "Ошибка получения событий"
                
            response += f"{result_icon} {date}: {home_team} {home_goals} - {away_goals} {away_team}\n{goals_str}\n\n"
        
        sent_message = await message.reply(response)
        if message.chat.id == TARGET_CHAT_ID:
            await ChatHistory.save_message(
                self.db_pool, 
                message.chat.id, 
                self.bot.id, 
                sent_message.message_id, 
                "assistant", 
                response
            )