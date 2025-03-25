import logging
from aiogram import types
from aiogram.filters import Command
from functools import partial
from app.services.api import ApiClient
from app.database.models import ChatHistory
from app.config import CODE_VERSION, TARGET_CHAT_ID, TEAM_IDS, MONITORING_ENABLED, REACTION_ENABLED, REACTION_TARGET_USER_ID, TARGET_REACTION
from app.services.monitoring import monitoring, monitor_function
import asyncpg
import asyncio
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class CommandHandlers:
    def __init__(self, bot, db_pool):
        self.bot = bot
        self.db_pool = db_pool

    @monitor_function
    async def command_start(self, message: types.Message, **kwargs):
        """Обработчик команды /start"""
        monitoring.increment_command(message.chat.id)
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
    async def command_version(self, message: types.Message, **kwargs):
        """Обработчик команды /version"""
        monitoring.increment_command(message.chat.id)
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
    async def command_reset(self, message: types.Message, **kwargs):
        """Обработчик команды /reset для сброса контекста AI"""
        monitoring.increment_command(message.chat.id)
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
    async def command_stats(self, message: types.Message, **kwargs):
        """Обработчик команды /stats для получения статистики"""
        monitoring.increment_command(message.chat.id)
        
        # Получаем общую статистику
        stats = monitoring.get_stats()
        
        # Получаем статистику по всем чатам
        chats_stats = monitoring.get_all_chats_stats()
        
        # Базовый ответ со статистикой бота
        response = (
            f"📊 Статистика бота:\n\n"
            f"⏱️ Время работы: {stats['uptime']}\n"
            f"💾 Использование памяти: {stats['memory_mb']} МБ\n"
            f"💬 Обработано сообщений: {stats['message_count']}\n"
            f"⌨️ Выполнено команд: {stats['command_count']}\n"
            f"🧠 AI-запросов (всего): {stats['ai_request_count']}\n"
            f"🌐 API-запросов (всего): {stats['api_request_count']}\n"
            f"🗄️ Операций с БД: {stats['db_operation_count']}\n"
            f"❌ Ошибок: {stats['error_count']}\n\n"
        )
        
        # Добавляем статистику по всем чатам
        if chats_stats["total_chats"] > 0:
            response += f"📋 Статистика по всем чатам:\n"
            response += f"🏢 Всего чатов: {chats_stats['total_chats']}\n"
            response += f"🧠 AI-запросов по всем чатам: {chats_stats['total_ai_requests']}\n"
            response += f"🌐 API-запросов по всем чатам: {chats_stats['total_api_requests']}\n\n"
            
            # Добавляем детальную статистику по каждому чату, если их не слишком много
            max_chats_to_display = 10
            if len(chats_stats["chats"]) <= max_chats_to_display:
                response += f"📋 Детальная статистика по чатам:\n\n"
                for chat_id, chat_stats in chats_stats["chats"].items():
                    response += (
                        f"Чат {chat_id}:\n"
                        f"- 🧠 AI-запросов: {chat_stats['ai_request_count']}\n"
                        f"- 🌐 API-запросов: {chat_stats['api_request_count']}\n"
                        f"- 💬 Сообщений: {chat_stats['message_count']}\n"
                        f"- ⌨️ Команд: {chat_stats['command_count']}\n\n"
                    )
        
        response += f"🤖 Версия бота: {CODE_VERSION}"
        await message.reply(response)

    @monitor_function
    async def command_test(self, message: types.Message, **kwargs):
        """Тестовая команда для проверки работоспособности бота"""
        monitoring.increment_command(message.chat.id)
        try:
            # Тестируем базу данных
            db_ok = await self.check_database_health()
            
            # Тестируем API-клиенты
            weather_test = await ApiClient.get_weather("Minsk,BY", message.chat.id)
            currency_test = await ApiClient.get_currency_rates(message.chat.id)
            
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
        except asyncpg.exceptions.PostgresConnectionError as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            if MONITORING_ENABLED:
                monitoring.log_error(e, {"context": "db_health_check", "type": "connection_error"})
            return False
        except asyncpg.exceptions.PostgresError as e:
            logger.error(f"Ошибка PostgreSQL при проверке базы данных: {e}")
            if MONITORING_ENABLED:
                monitoring.log_error(e, {"context": "db_health_check", "type": "postgres_error"})
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке базы данных: {e}")
            if MONITORING_ENABLED:
                monitoring.log_error(e, {"context": "db_health_check", "type": "unexpected_error"})
            return False

    @monitor_function
    async def command_team_matches(self, message: types.Message, team_name, **kwargs):
        """Обработчик команд для показа матчей команды"""
        monitoring.increment_command(message.chat.id)
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
        
        data = await ApiClient.get_team_matches(team_id, message.chat.id)
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
            
            events_data = await ApiClient.get_match_events(fixture_id, message.chat.id)
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

    @monitor_function
    async def command_pogoda(self, message: types.Message, **kwargs):
        """Обработчик команды /pogoda для отображения погоды в указанных городах"""
        monitoring.increment_command(message.chat.id)
        
        cities = {
            "Минск": "Minsk,BY",
            "Гомель": "Gomel,BY",
            "Жлобин": "Zhlobin,BY"
        }
        
        # Параллельно получаем данные о погоде для всех городов
        weather_tasks = [ApiClient.get_weather(code, message.chat.id) for code in cities.values()]
        weather_results = await asyncio.gather(*weather_tasks, return_exceptions=True)
        
        # Формируем сообщение с результатами
        weather_data = dict(zip(cities.keys(), weather_results))
        
        response = "🌤 *Погода сейчас:*\n\n"
        for city, data in weather_data.items():
            if isinstance(data, Exception):
                response += f"🏙 *{city}*: Нет данных\n"
            else:
                response += f"🏙 *{city}*: {data}\n"
        
        sent_message = await message.reply(response, parse_mode="Markdown")
        
        # Сохраняем сообщение в историю чата если нужно
        if message.chat.id == TARGET_CHAT_ID:
            await ChatHistory.save_message(
                self.db_pool, 
                message.chat.id, 
                self.bot.id, 
                sent_message.message_id, 
                "assistant", 
                response
            )

    @monitor_function
    async def command_wld(self, message: types.Message, **kwargs):
        """Обработчик команды /wld для отображения курса WLD"""
        monitoring.increment_command(message.chat.id)
        
        try:
            # Получаем курсы криптовалют
            btc_price_usd, wld_price_usd = await ApiClient.get_crypto_prices(message.chat.id)
            
            # Получаем курсы валют для конвертации
            usd_byn_rate, usd_rub_rate = await ApiClient.get_currency_rates(message.chat.id)
            
            # Проверяем наличие данных
            if not wld_price_usd or not usd_byn_rate or not usd_rub_rate:
                sent_message = await message.reply("Не удалось получить актуальные данные. Попробуйте позже.")
                if message.chat.id == TARGET_CHAT_ID:
                    await ChatHistory.save_message(
                        self.db_pool, 
                        message.chat.id, 
                        self.bot.id, 
                        sent_message.message_id, 
                        "assistant", 
                        "Не удалось получить актуальные данные. Попробуйте позже."
                    )
                return
            
            # Рассчитываем цены в BYN и RUB
            wld_price_byn = float(wld_price_usd) * float(usd_byn_rate)
            wld_price_rub = float(wld_price_usd) * float(usd_rub_rate)
            
            # Формируем ответное сообщение
            response = (
                f"💰 *Курс WorldCoin (WLD):*\n\n"
                f"📈 USD: ${wld_price_usd:.4f}\n"
                f"📈 BYN: {wld_price_byn:.4f} BYN\n"
                f"📈 RUB: {wld_price_rub:.4f} RUB\n\n"
                f"⏱ Данные на {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            sent_message = await message.reply(response, parse_mode="Markdown")
            
            # Сохраняем сообщение в историю чата если нужно
            if message.chat.id == TARGET_CHAT_ID:
                await ChatHistory.save_message(
                    self.db_pool, 
                    message.chat.id, 
                    self.bot.id, 
                    sent_message.message_id, 
                    "assistant", 
                    response
                )
        except Exception as e:
            logger.error(f"Ошибка при получении курса WLD: {e}")
            error_message = f"Произошла ошибка при получении курса: {e}"
            await message.reply(error_message)

    @monitor_function
    async def command_rub(self, message: types.Message, **kwargs):
        """Обработчик команды /rub для отображения курса USD/RUB"""
        monitoring.increment_command(message.chat.id)
        
        try:
            # Получаем курсы валют
            usd_byn_rate, usd_rub_rate = await ApiClient.get_currency_rates(message.chat.id)
            
            if not usd_rub_rate:
                sent_message = await message.reply("Не удалось получить актуальные данные о курсе USD/RUB. Попробуйте позже.")
                if message.chat.id == TARGET_CHAT_ID:
                    await ChatHistory.save_message(
                        self.db_pool, 
                        message.chat.id, 
                        self.bot.id, 
                        sent_message.message_id, 
                        "assistant", 
                        "Не удалось получить актуальные данные о курсе USD/RUB. Попробуйте позже."
                    )
                return
            
            # Создаем обратный курс (RUB/USD)
            rub_usd_rate = 1 / float(usd_rub_rate) if float(usd_rub_rate) > 0 else 0
            
            # Формируем ответное сообщение
            response = (
                f"💵 *Курс USD/RUB:*\n\n"
                f"1 USD = {float(usd_rub_rate):.4f} RUB\n"
                f"1 RUB = {rub_usd_rate:.6f} USD\n\n"
                f"⏱ Данные на {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            sent_message = await message.reply(response, parse_mode="Markdown")
            
            # Сохраняем сообщение в историю чата если нужно
            if message.chat.id == TARGET_CHAT_ID:
                await ChatHistory.save_message(
                    self.db_pool, 
                    message.chat.id, 
                    self.bot.id, 
                    sent_message.message_id, 
                    "assistant", 
                    response
                )
                
        except Exception as e:
            logger.error(f"Ошибка при получении курса USD/RUB: {e}")
            error_message = f"Произошла ошибка при получении курса: {e}"
            await message.reply(error_message)

    @monitor_function
    async def command_byn(self, message: types.Message, **kwargs):
        """Обработчик команды /byn для отображения курса USD/BYN"""
        monitoring.increment_command(message.chat.id)
        
        try:
            # Получаем курсы валют
            usd_byn_rate, usd_rub_rate = await ApiClient.get_currency_rates(message.chat.id)
            
            if not usd_byn_rate:
                sent_message = await message.reply("Не удалось получить актуальные данные о курсе USD/BYN. Попробуйте позже.")
                if message.chat.id == TARGET_CHAT_ID:
                    await ChatHistory.save_message(
                        self.db_pool, 
                        message.chat.id, 
                        self.bot.id, 
                        sent_message.message_id, 
                        "assistant", 
                        "Не удалось получить актуальные данные о курсе USD/BYN. Попробуйте позже."
                    )
                return
            
            # Создаем обратный курс (BYN/USD)
            byn_usd_rate = 1 / float(usd_byn_rate) if float(usd_byn_rate) > 0 else 0
            
            # Формируем ответное сообщение
            response = (
                f"💵 *Курс USD/BYN:*\n\n"
                f"1 USD = {float(usd_byn_rate):.4f} BYN\n"
                f"1 BYN = {byn_usd_rate:.6f} USD\n\n"
                f"⏱ Данные на {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            sent_message = await message.reply(response, parse_mode="Markdown")
            
            # Сохраняем сообщение в историю чата если нужно
            if message.chat.id == TARGET_CHAT_ID:
                await ChatHistory.save_message(
                    self.db_pool, 
                    message.chat.id, 
                    self.bot.id, 
                    sent_message.message_id, 
                    "assistant", 
                    response
                )
                
        except Exception as e:
            logger.error(f"Ошибка при получении курса USD/BYN: {e}")
            error_message = f"Произошла ошибка при получении курса: {e}"
            await message.reply(error_message)

    @monitor_function
    async def command_chatstats(self, message: types.Message, **kwargs):
        """Обработчик команды /chatstats для получения статистики сообщений в чате"""
        monitoring.increment_command(message.chat.id)
        
        # Проверяем, что команда вызвана в групповом чате
        if message.chat.type not in ['group', 'supergroup']:
            await message.reply("Эта команда доступна только в групповых чатах.")
            return
        
        try:
            chat_id = message.chat.id
            
            # Отправляем сообщение о начале обработки, чтобы пользователь знал, что бот работает
            wait_message = await message.reply("⏳ Собираю статистику сообщений чата...")
            
            # Получаем статистику за разные периоды
            day_stats = await ChatHistory.get_chat_messages_stats(self.db_pool, chat_id, "day")
            month_stats = await ChatHistory.get_chat_messages_stats(self.db_pool, chat_id, "month")
            all_stats = await ChatHistory.get_chat_messages_stats(self.db_pool, chat_id, None)
            
            # Если нет сообщений в базе
            if all_stats["total_messages"] == 0:
                await message.reply("Статистика недоступна: в базе нет сообщений для этого чата.")
                await self.bot.delete_message(chat_id=chat_id, message_id=wait_message.message_id)
                return
            
            # Получаем информацию о чате
            chat_info = await self.bot.get_chat(chat_id)
            chat_name = chat_info.title or f"Chat {chat_id}"
            
            # Получаем имена пользователей
            all_user_ids = [user_stat["user_id"] for user_stat in all_stats["users"]]
            usernames = {}
            
            for user_id in all_user_ids:
                try:
                    chat_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                    user = chat_member.user
                    
                    # Формируем имя пользователя
                    if user.username:
                        name = f"@{user.username}"
                    else:
                        name = user.full_name or f"User {user_id}"
                    
                    usernames[user_id] = name
                except Exception as e:
                    logger.warning(f"Не удалось получить имя пользователя {user_id}: {e}")
                    usernames[user_id] = f"User {user_id}"
            
            # Формируем ответное сообщение
            response = f"📊 *Статистика сообщений в чате {chat_name}*\n\n"
            
            # Статистика за день
            response += f"*За последние 24 часа:*\n"
            response += f"Всего сообщений: {day_stats['total_messages']}\n"
            if day_stats['users']:
                response += "Топ отправителей:\n"
                for i, user in enumerate(day_stats['users'][:5], 1):  # Показываем только топ-5
                    user_id = user['user_id']
                    username = usernames.get(user_id, f"User {user_id}")
                    response += f"{i}. {username}: {user['message_count']} сообщений\n"
            else:
                response += "Нет данных о сообщениях за этот период\n"
            
            response += "\n"
            
            # Статистика за месяц
            response += f"*За последние 30 дней:*\n"
            response += f"Всего сообщений: {month_stats['total_messages']}\n"
            if month_stats['users']:
                response += "Топ отправителей:\n"
                for i, user in enumerate(month_stats['users'][:5], 1):  # Показываем только топ-5
                    user_id = user['user_id']
                    username = usernames.get(user_id, f"User {user_id}")
                    response += f"{i}. {username}: {user['message_count']} сообщений\n"
            else:
                response += "Нет данных о сообщениях за этот период\n"
            
            response += "\n"
            
            # Статистика за все время
            response += f"*За все время:*\n"
            response += f"Всего сообщений: {all_stats['total_messages']}\n"
            if all_stats['users']:
                response += "Топ отправителей:\n"
                for i, user in enumerate(all_stats['users'][:10], 1):  # Показываем топ-10 за все время
                    user_id = user['user_id']
                    username = usernames.get(user_id, f"User {user_id}")
                    response += f"{i}. {username}: {user['message_count']} сообщений\n"
            
            # Удаляем сообщение о ожидании
            await self.bot.delete_message(chat_id=chat_id, message_id=wait_message.message_id)
            
            # Отправляем ответ
            await message.reply(response, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики чата: {e}")
            await message.reply(f"Произошла ошибка при получении статистики: {e}")

    @monitor_function
    async def command_reaction(self, message: types.Message, **kwargs):
        """Обработчик команды /reaction для настройки реакций на сообщения"""
        monitoring.increment_command(message.chat.id)
        
        # Проверка прав администратора
        is_admin = False
        try:
            chat_member = await self.bot.get_chat_member(message.chat.id, message.from_user.id)
            is_admin = chat_member.status in ["administrator", "creator"]
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора: {e}")
        
        # Если это не администратор, не разрешаем использовать команду
        if not is_admin:
            sent_message = await message.reply("Только админы могут управлять реакциями, петушок!")
            return
            
        # Разбираем аргументы команды
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        
        # Если аргументов нет, выводим текущие настройки и инструкцию
        if not args:
            status = "включены" if REACTION_ENABLED else "выключены"
            target_user = REACTION_TARGET_USER_ID if REACTION_ENABLED else "не задан"
            reaction = TARGET_REACTION if REACTION_ENABLED and TARGET_REACTION else "не задана"
            
            response = (
                f"🔹 Текущие настройки реакций:\n"
                f"▫️ Статус: {status}\n"
                f"▫️ ID пользователя: {target_user}\n"
                f"▫️ Реакция: {reaction}\n\n"
                f"🔸 Использование команды:\n"
                f"▫️ /reaction on|off - включить/выключить реакции\n"
                f"▫️ /reaction set_user ID - установить ID пользователя для реакций\n"
                f"▫️ /reaction set_emoji EMOJI - установить эмодзи для реакции\n"
                f"▫️ /reaction clear - отключить реакции"
            )
            
            sent_message = await message.reply(response)
            return
            
        # Обрабатываем команды
        action = args[0].lower()
        
        if action == "on":
            # Сохраняем в переменную окружения
            os.environ['REACTION_ENABLED'] = 'true'
            # Обновляем переменную в памяти
            import app.config
            app.config.REACTION_ENABLED = True
            sent_message = await message.reply("✅ Реакции включены")
            
        elif action == "off":
            # Сохраняем в переменную окружения
            os.environ['REACTION_ENABLED'] = 'false'
            # Обновляем переменную в памяти
            import app.config
            app.config.REACTION_ENABLED = False
            sent_message = await message.reply("✅ Реакции выключены")
            
        elif action == "set_user" and len(args) > 1:
            try:
                # Проверка валидности ID
                user_id = int(args[1])
                # Сохраняем в переменную окружения
                os.environ['REACTION_TARGET_USER_ID'] = str(user_id)
                # Обновляем переменную в памяти
                import app.config
                app.config.REACTION_TARGET_USER_ID = user_id
                sent_message = await message.reply(f"✅ ID пользователя для реакций установлен: {user_id}")
            except ValueError:
                sent_message = await message.reply("❌ Ошибка: ID пользователя должен быть числом")
                
        elif action == "set_emoji" and len(args) > 1:
            emoji = args[1]
            # Проверка, что это действительно эмодзи или поддерживаемая реакция
            # Это простая проверка, можно реализовать более сложную валидацию
            if len(emoji) <= 2:
                sent_message = await message.reply("❌ Ошибка: это не похоже на эмодзи")
                return
                
            # Сохраняем в переменную окружения
            os.environ['TARGET_REACTION'] = emoji
            # Обновляем переменную в памяти
            import app.config
            app.config.TARGET_REACTION = emoji
            sent_message = await message.reply(f"✅ Эмодзи для реакций установлено: {emoji}")
            
        elif action == "clear":
            # Отключаем реакции и сбрасываем настройки
            os.environ['REACTION_ENABLED'] = 'false'
            os.environ['TARGET_REACTION'] = ''
            # Обновляем переменные в памяти
            import app.config
            app.config.REACTION_ENABLED = False
            app.config.TARGET_REACTION = ''
            sent_message = await message.reply("✅ Реакции отключены и настройки сброшены")
            
        else:
            sent_message = await message.reply("❌ Неизвестная команда. Используйте /reaction без параметров для справки.")