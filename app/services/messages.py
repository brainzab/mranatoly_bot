import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from app.services.api import ApiClient
from app.config import CHAT_ID, TARGET_CHAT_ID
from app.services.ai import AiHandler

logger = logging.getLogger(__name__)

def split_long_message(text, max_length=4096):
    """Разделяет длинное сообщение на части для отправки в Telegram."""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    for i in range(0, len(text), max_length):
        parts.append(text[i:i + max_length])
    return parts

async def send_long_message(bot, chat_id, text, **kwargs):
    """Отправляет длинное сообщение по частям."""
    parts = split_long_message(text)
    sent_messages = []
    for part in parts:
        sent = await bot.send_message(chat_id=chat_id, text=part, **kwargs)
        sent_messages.append(sent)
    return sent_messages

class MorningMessageSender:
    def __init__(self, bot):
        self.bot = bot

    async def get_ai_wish_by_day(self):
        """Получает уникальное пожелание от ИИ в зависимости от дня недели"""
        try:
            # Получаем текущий день недели (0 - понедельник, 6 - воскресенье)
            current_day = datetime.now().weekday()
            day_names = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
            day_name = day_names[current_day]
            
            # Определяем тип дня (рабочий или выходной)
            is_weekend = current_day >= 5  # 5 - суббота, 6 - воскресенье
            is_friday = current_day == 4   # 4 - пятница
            
            # Формируем запрос к ИИ в зависимости от дня недели
            if is_weekend:
                prompt = f"Сегодня {day_name}. Сгенерируй уникальное и креативное пожелание хороших выходных для утреннего приветствия в групповом чате друзей. Пожелание должно быть позитивным, с юмором, и учитывать, что сегодня выходной. Длина - 2-3 предложения. Добавь эмодзи. Не используй обращения."
            elif is_friday:
                prompt = f"Сегодня {day_name}. Сгенерируй уникальное и креативное пожелание отличной пятницы и предстоящих выходных для утреннего приветствия в групповом чате друзей. Пожелание должно быть позитивным, с юмором. Длина - 2-3 предложения. Добавь эмодзи. Не используй обращения."
            else:
                prompt = f"Сегодня {day_name}. Сгенерируй уникальное и креативное пожелание продуктивного дня для утреннего приветствия в групповом чате друзей. Пожелание должно быть позитивным, с юмором, и учитывать день недели. Длина - 2-3 предложения. Добавь эмодзи. Не используй обращения."
            
            # Получаем ответ от ИИ
            wish = await AiHandler.get_ai_response([], prompt)
            logger.info(f"Сгенерировано пожелание для дня недели {day_name}: {wish[:50]}...")
            
            return wish
            
        except Exception as e:
            logger.error(f"Ошибка при генерации пожелания от ИИ: {e}")
            # Возвращаем базовое пожелание в случае ошибки
            return "❤️ Желаю всем хорошего и продуктивного дня! Пусть всё задуманное получится!"

    async def send_morning_message(self):
        logger.info("Подготовка утреннего сообщения")
        try:
            cities = {
                "Минск": "Minsk,BY", "Жлобин": "Zhlobin,BY", "Гомель": "Gomel,BY",
                "Житковичи": "Zhitkovichi,BY", "Шри-Ланка": "Colombo,LK", "Ноябрьск": "Noyabrsk,RU"
            }
            
            # Параллельно выполняем все запросы к API и получаем пожелание
            weather_tasks = [ApiClient.get_weather(code, TARGET_CHAT_ID) for code in cities.values()]
            currency_task = ApiClient.get_currency_rates(TARGET_CHAT_ID)
            crypto_task = ApiClient.get_crypto_prices(TARGET_CHAT_ID)
            wish_task = self.get_ai_wish_by_day()
            
            # Добавляем логирование для диагностики
            logger.info(f"Запущены задачи: погода ({len(weather_tasks)}), валюты, крипта, пожелание")
            
            # Собираем результаты с таймаутом для каждой задачи
            weather_results = []
            for i, task in enumerate(weather_tasks):
                try:
                    result = await asyncio.wait_for(task, timeout=10)  # 10 секунд таймаут
                    weather_results.append(result)
                    logger.info(f"Получена погода {i+1}/{len(weather_tasks)}")
                except asyncio.TimeoutError:
                    logger.error(f"Таймаут при получении погоды {i+1}/{len(weather_tasks)}")
                    weather_results.append("Нет данных (таймаут)")
                except Exception as e:
                    logger.error(f"Ошибка при получении погоды {i+1}/{len(weather_tasks)}: {e}")
                    weather_results.append(f"Нет данных ({str(e)[:20]})")
            
            # Получаем курсы валют
            try:
                usd_byn_rate, usd_rub_rate = await asyncio.wait_for(currency_task, timeout=10)
                logger.info("Получены курсы валют")
            except asyncio.TimeoutError:
                logger.error("Таймаут при получении курсов валют")
                usd_byn_rate, usd_rub_rate = "?", "?"
            except Exception as e:
                logger.error(f"Ошибка при получении курсов валют: {e}")
                usd_byn_rate, usd_rub_rate = "?", "?"
            
            # Получаем криптовалюты
            try:
                btc_price_usd, wld_price_usd = await asyncio.wait_for(crypto_task, timeout=10)
                logger.info("Получены цены криптовалют")
            except asyncio.TimeoutError:
                logger.error("Таймаут при получении цен криптовалют")
                btc_price_usd, wld_price_usd = "?", "?"
            except Exception as e:
                logger.error(f"Ошибка при получении цен криптовалют: {e}")
                btc_price_usd, wld_price_usd = "?", "?"
            
            # Получаем пожелание
            try:
                ai_wish = await asyncio.wait_for(wish_task, timeout=20)  # AI может дольше отвечать
                logger.info(f"Получено пожелание: {ai_wish[:30]}...")
            except asyncio.TimeoutError:
                logger.error("Таймаут при получении пожелания от AI")
                ai_wish = "❤️ Хорошего всем дня! Извините, у меня проблемы со связью."
            except Exception as e:
                logger.error(f"Ошибка при получении пожелания: {e}")
                ai_wish = f"❤️ Хорошего всем дня! Что-то пошло не так: {str(e)[:30]}"
            
            weather_data = dict(zip(cities.keys(), weather_results))
            
            # Рассчитываем цены в BYN
            try:
                btc_price_byn = float(btc_price_usd) * float(usd_byn_rate) if btc_price_usd not in ("?", None) and usd_byn_rate not in ("?", None) else "?"
                wld_price_byn = float(wld_price_usd) * float(usd_byn_rate) if wld_price_usd not in ("?", None) and usd_byn_rate not in ("?", None) else "?"
            except (ValueError, TypeError) as e:
                logger.error(f"Ошибка при расчете цен в BYN: {e}")
                btc_price_byn, wld_price_byn = "?", "?"
            
            # Форматируем строки для вывода
            def format_price(price):
                if price == "?":
                    return "?"
                try:
                    if isinstance(price, (int, float)) and price > 1000:
                        return f"{price:,.2f}"
                    elif isinstance(price, (int, float)):
                        return f"{price:.4f}" if price < 1 else f"{price:.2f}"
                    return price
                except Exception:
                    return str(price)
            
            # Формируем сообщение
            message = (
                "Родные мои, всем доброе утро и хорошего дня! ❤️\n\n"
                "*Положняк по погоде:*\n"
                + "\n".join(f"🌥 *{city}*: {data}" 
                          for city, data in weather_data.items()) + "\n\n"
                "*Положняк по курсам:*\n"
            )
            
            # Добавляем данные по курсам в зависимости от их наличия
            if usd_byn_rate != "?":
                message += f"💵 *USD/BYN*: {format_price(usd_byn_rate)} BYN\n"
            else:
                message += "💵 *USD/BYN*: Нет данных\n"
                
            if usd_rub_rate != "?":
                message += f"💵 *USD/RUB*: {format_price(usd_rub_rate)} RUB\n"
            else:
                message += "💵 *USD/RUB*: Нет данных\n"
                
            if btc_price_usd != "?":
                if btc_price_byn != "?":
                    message += f"₿ *BTC*: ${format_price(btc_price_usd)} USD | {format_price(btc_price_byn)} BYN\n"
                else:
                    message += f"₿ *BTC*: ${format_price(btc_price_usd)} USD\n"
            else:
                message += "₿ *BTC*: Нет данных\n"
                
            if wld_price_usd != "?":
                if wld_price_byn != "?":
                    message += f"🌍 *WLD*: ${format_price(wld_price_usd)} USD | {format_price(wld_price_byn)} BYN\n\n"
                else:
                    message += f"🌍 *WLD*: ${format_price(wld_price_usd)} USD\n\n"
            else:
                message += "🌍 *WLD*: Нет данных\n\n"
            
            # Добавляем пожелание
            message += f"{ai_wish}"
            
            # Отправляем сообщение
            sent_message = await self.bot.send_message(
                chat_id=CHAT_ID, 
                text=message, 
                parse_mode="MARKDOWN"
            )
            
            logger.info("Утреннее сообщение отправлено успешно")
            
            # Также отправляем сообщение в канал мониторинга
            from app.config import MONITORING_ENABLED, ADMIN_CHAT_ID
            if MONITORING_ENABLED and ADMIN_CHAT_ID != CHAT_ID:
                await self.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text="✅ Утреннее сообщение успешно отправлено в чат"
                )
            
            return sent_message
            
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего сообщения: {e}")
            # Отправляем информацию об ошибке администратору
            from app.config import MONITORING_ENABLED, ADMIN_CHAT_ID
            if MONITORING_ENABLED:
                from app.services.monitoring import monitoring
                monitoring.log_error(e, {"context": "morning_message"})
                try:
                    await self.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"❌ Ошибка при отправке утреннего сообщения: {e}"
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить уведомление об ошибке: {send_error}")
            return None