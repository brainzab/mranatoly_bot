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
            
            # Собираем результаты
            results = await asyncio.gather(
                *weather_tasks,
                currency_task,
                crypto_task,
                wish_task,
                return_exceptions=True
            )
            
            # Обрабатываем результаты
            weather_results = results[:len(cities)]
            usd_byn_rate, usd_rub_rate = results[len(cities)]
            btc_price_usd, wld_price_usd = results[len(cities) + 1]
            ai_wish = results[len(cities) + 2] if not isinstance(results[len(cities) + 2], Exception) else "❤️ Хорошего всем дня!"
            
            weather_data = dict(zip(cities.keys(), weather_results))
            
            # Рассчитываем цены в BYN
            btc_price_byn = float(btc_price_usd) * float(usd_byn_rate) if btc_price_usd and usd_byn_rate else 0
            wld_price_byn = float(wld_price_usd) * float(usd_byn_rate) if wld_price_usd and usd_byn_rate else 0
            
            # Формируем сообщение
            message = (
                "Родные мои, всем доброе утро и хорошего дня! ❤️\n\n"
                "*Положняк по погоде:*\n"
                + "\n".join(f"🌥 *{city}*: {data if not isinstance(data, Exception) else 'Нет данных'}" 
                          for city, data in weather_data.items()) + "\n\n"
                "*Положняк по курсам:*\n"
                f"💵 *USD/BYN*: {usd_byn_rate:.2f} BYN\n"
                f"💵 *USD/RUB*: {usd_rub_rate:.2f} RUB\n"
                f"₿ *BTC*: ${btc_price_usd:,.2f} USD | {btc_price_byn:,.2f} BYN\n"
                f"🌍 *WLD*: ${wld_price_usd:.4f} USD | {wld_price_byn:.4f} BYN\n\n"
                f"{ai_wish}"
            )
            
            # Отправляем сообщение
            sent_message = await self.bot.send_message(
                chat_id=CHAT_ID, 
                text=message, 
                parse_mode="MARKDOWN"
            )
            
            logger.info("Утреннее сообщение отправлено")
            return sent_message
            
        except Exception as e:
            logger.error(f"Ошибка при отправке утреннего сообщения: {e}")
            # Можно добавить оповещение администратора
            return None