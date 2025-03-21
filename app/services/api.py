import logging
import asyncio
import aiohttp
import time
from app.config import (
    OPENWEATHER_API_KEY, 
    RAPIDAPI_KEY
)

logger = logging.getLogger(__name__)

async def retry_async(func, *args, max_retries=3, retry_delay=1, **kwargs):
    """
    Выполняет асинхронную функцию с повторными попытками при неудаче
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            if attempt < max_retries - 1:
                delay = retry_delay * (2 ** attempt)  # Экспоненциальная задержка
                logger.info(f"Повторная попытка через {delay} секунд")
                await asyncio.sleep(delay)
    
    logger.error(f"Все {max_retries} попытки не удались. Последняя ошибка: {last_error}")
    raise last_error

class ApiGateway:
    """
    Централизованный шлюз для всех API-запросов с поддержкой кэширования и мониторинга
    """
    def __init__(self):
        self.cache = {}
        self.request_count = 0
        self.error_count = 0
        
    def clear_cache(self, cache_key=None):
        """
        Очищает весь кэш или только указанный ключ
        """
        if cache_key:
            if cache_key in self.cache:
                del self.cache[cache_key]
                logger.info(f"Кэш очищен для ключа {cache_key}")
        else:
            self.cache.clear()
            logger.info("Весь кэш очищен")
            
    async def request(self, method, url, headers=None, params=None, data=None, 
                     cache_key=None, cache_ttl=300, chat_id=None, force_fresh=False):
        """
        Выполняет HTTP-запрос с поддержкой кэширования и повторных попыток
        
        :param force_fresh: Если True, запрос будет выполнен в обход кэша
        """
        self.request_count += 1
        
        # Увеличиваем глобальный счетчик API-запросов
        from app.services.monitoring import monitoring
        monitoring.increment_api_request(chat_id)
        
        # Если требуется свежий запрос, очищаем кэш для данного ключа
        if force_fresh and cache_key and cache_key in self.cache:
            del self.cache[cache_key]
            logger.debug(f"Кэш очищен для {cache_key} перед новым запросом")
        
        # Проверяем кэш если нужно
        if cache_key and cache_key in self.cache and not force_fresh:
            cache_time, cache_data = self.cache[cache_key]
            if time.time() - cache_time < cache_ttl:
                logger.debug(f"Возврат кэшированного ответа для {cache_key}")
                return cache_data
        
        # Выполняем запрос с повторными попытками
        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(3):
                    try:
                        async with session.request(
                            method=method, 
                            url=url, 
                            headers=headers, 
                            params=params, 
                            json=data,
                            timeout=10
                        ) as response:
                            response.raise_for_status()
                            result = await response.json()
                            
                            # Сохраняем в кэш если нужно
                            if cache_key:
                                self.cache[cache_key] = (time.time(), result)
                            
                            return result
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        if attempt == 2:  # последняя попытка
                            raise
                        logger.warning(f"Попытка запроса {attempt+1}/3 не удалась: {e}. Повторная попытка...")
                        await asyncio.sleep(1 * (attempt + 1))
        
        except Exception as e:
            self.error_count += 1
            logger.error(f"Ошибка API запроса к {url}: {e}")
            raise

# Глобальный экземпляр API шлюза
api_gateway = ApiGateway()

class ApiClient:
    @staticmethod
    async def get_weather(city, chat_id=None):
        cache_key = f"weather_{city}"
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "ru"
        }
        
        try:
            data = await api_gateway.request(
                method="GET", 
                url=url, 
                params=params,
                cache_key=cache_key,
                cache_ttl=1800,  # 30 минут
                chat_id=chat_id
            )
            temp = data['main']['temp']
            desc = data['weather'][0]['description']
            return f"{temp}°C, {desc}"
        except Exception as e:
            logger.error(f"Ошибка получения погоды для {city}: {e}")
            return "Нет данных"

    @staticmethod
    async def get_currency_rates(chat_id=None):
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        cache_key = "currency_rates"
        
        try:
            data = await api_gateway.request(
                method="GET", 
                url=url,
                cache_key=cache_key,
                cache_ttl=3600,  # 1 час
                chat_id=chat_id
            )
            usd_byn = data['usd'].get('byn', 0)
            usd_rub = data['usd'].get('rub', 0)
            return usd_byn, usd_rub
        except Exception as e:
            logger.error(f"Ошибка получения курсов валют: {e}")
            return 0, 0

    @staticmethod
    async def get_crypto_prices(chat_id=None):
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,worldcoin-wld&vs_currencies=usd"
        cache_key = "crypto_prices"
        
        try:
            # Для крипто-цен всегда запрашиваем свежие данные, игнорируя кэш
            data = await api_gateway.request(
                method="GET", 
                url=url,
                cache_key=cache_key,
                cache_ttl=3600,  # 1 час
                chat_id=chat_id,
                force_fresh=True  # Обходим кэш для получения актуальных данных
            )
            btc_price = data.get('bitcoin', {}).get('usd', 0)
            wld_price = data.get('worldcoin-wld', {}).get('usd', 0)
            
            logger.info(f"Получены цены криптовалют: BTC=${btc_price}, WLD=${wld_price}")
            
            # Если данные по WLD отсутствуют, пробуем альтернативный ID
            if wld_price == 0:
                logger.warning("WLD цена не найдена с ID 'worldcoin-wld', пробуем запрос с ID 'world-coin'")
                api_gateway.clear_cache(cache_key)
                
                alt_url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,world-coin&vs_currencies=usd"
                alt_data = await api_gateway.request(
                    method="GET", 
                    url=alt_url,
                    cache_key=cache_key,
                    cache_ttl=3600,
                    chat_id=chat_id
                )
                wld_price = alt_data.get('world-coin', {}).get('usd', 0)
                logger.info(f"Альтернативная WLD цена: ${wld_price}")
            
            return btc_price, wld_price
        except Exception as e:
            logger.error(f"Ошибка получения цен криптовалют: {e}")
            return 0, 0

    @staticmethod
    async def get_team_matches(team_id, chat_id=None):
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
        params = {"team": team_id, "last": "5"}
        cache_key = f"team_matches_{team_id}"
        
        try:
            return await api_gateway.request(
                method="GET", 
                url=url, 
                headers=headers,
                params=params,
                cache_key=cache_key,
                cache_ttl=7200,  # 2 часа
                chat_id=chat_id
            )
        except Exception as e:
            logger.error(f"Ошибка API-Football для команды {team_id}: {e}")
            return None

    @staticmethod
    async def get_match_events(fixture_id, chat_id=None):
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/events"
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
        params = {"fixture": fixture_id}
        cache_key = f"match_events_{fixture_id}"
        
        try:
            data = await api_gateway.request(
                method="GET", 
                url=url, 
                headers=headers,
                params=params,
                cache_key=cache_key,
                cache_ttl=3600,  # 1 час
                chat_id=chat_id
            )
            logger.info(f"События для матча {fixture_id}: получено")
            return data
        except Exception as e:
            logger.error(f"Ошибка API-Football для событий матча {fixture_id}: {e}")
            return None