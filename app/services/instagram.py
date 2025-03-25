import logging
import re
import os
import tempfile
import time
import json
import requests
import urllib.parse
from instaloader import Instaloader, Post, LoginRequiredException, ConnectionException, TwoFactorAuthRequiredException
import pyotp
from app.services.api import retry_async
from app.config import (
    INSTAGRAM_USERNAME, 
    INSTAGRAM_PASSWORD, 
    INSTAGRAM_SESSION_FILE,
    INSTAGRAM_2FA_ENABLED,
    INSTAGRAM_2FA_SECRET
)

logger = logging.getLogger(__name__)

class InstagramHandler:
    def __init__(self):
        self.loader = Instaloader()
        self.temp_dir = tempfile.gettempdir()
        self.session_file = INSTAGRAM_SESSION_FILE
        self.is_logged_in = False
        self._login()
    
    def _generate_2fa_code(self):
        """Генерирует код для двухфакторной аутентификации"""
        if not INSTAGRAM_2FA_SECRET:
            logger.error("Отсутствует секрет для 2FA")
            return None
        
        try:
            secret = INSTAGRAM_2FA_SECRET
            
            # Если передан URL TOTP (otpauth://...), извлекаем секрет из него
            if secret.startswith("otpauth://"):
                try:
                    import urllib.parse
                    url_parts = urllib.parse.urlparse(secret)
                    query_params = dict(urllib.parse.parse_qsl(url_parts.query))
                    if "secret" in query_params:
                        secret = query_params["secret"]
                        logger.info("Извлечен секрет из TOTP URL")
                except Exception as e:
                    logger.error(f"Ошибка при извлечении секрета из URL: {e}")
            
            # Очищаем секрет от лишних символов и приводим к base32
            secret = secret.replace(' ', '').replace('-', '').upper()
            
            # Удаляем все символы, не входящие в алфавит Base32
            base32_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
            secret = ''.join(c for c in secret if c in base32_alphabet)
            
            # Проверяем валидность очищенного секрета
            if not secret or len(secret) < 16:
                logger.error(f"Секретный ключ 2FA недействителен или слишком короткий после очистки: {len(secret)} символов")
                return None
                
            # Дополняем строку символами = если длина не кратна 8
            if len(secret) % 8 != 0:
                secret += '=' * (8 - len(secret) % 8)
                
            logger.info(f"Длина очищенного секретного ключа 2FA: {len(secret)} символов")
            
            # Создаем TOTP с использованием стандартных параметров Instagram
            totp = pyotp.TOTP(secret, digits=6, digest='sha1', interval=30)
            
            # Получаем текущий код
            return totp.now()
        except Exception as e:
            logger.error(f"Ошибка при генерации 2FA кода: {e}")
            return None
    
    def _login(self):
        """Авторизация в Instagram с поддержкой сессии и 2FA"""
        try:
            if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
                logger.warning("Учетные данные Instagram не указаны")
                return

            # Пробуем загрузить существующую сессию
            try:
                self.loader.load_session_from_file(INSTAGRAM_USERNAME, self.session_file)
                logger.info("Сессия Instagram успешно загружена")
                self.is_logged_in = True
                return
            except FileNotFoundError:
                logger.info("Сессия не найдена, выполняем новую авторизацию")
            except Exception as e:
                logger.warning(f"Ошибка при загрузке сессии: {e}")
            
            # Если сессия не найдена или недействительна, выполняем новую авторизацию
            try:
                if INSTAGRAM_2FA_ENABLED:
                    logger.info("Используем 2FA для авторизации в Instagram")
                    self._login_with_2fa()
                else:
                    self.loader.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                
                # Сохраняем сессию
                self.loader.save_session_to_file(self.session_file)
                logger.info("Новая сессия Instagram успешно создана и сохранена")
                self.is_logged_in = True
            except TwoFactorAuthRequiredException:
                if INSTAGRAM_2FA_ENABLED:
                    logger.error("Не удалось авторизоваться с 2FA. Проверьте секретный ключ.")
                else:
                    logger.error("Для этого аккаунта требуется 2FA. Включите поддержку 2FA в настройках.")
                return
            except LoginRequiredException as e:
                if "checkpoint" in str(e).lower():
                    logger.error("Требуется подтверждение безопасности в Instagram. Пожалуйста, войдите в аккаунт через браузер и подтвердите безопасность.")
                    # Не прерываем работу бота, просто логируем ошибку
                    return
                raise
            except ConnectionException as e:
                logger.error(f"Ошибка подключения к Instagram: {e}")
                # Не прерываем работу бота, просто логируем ошибку
                return
            except Exception as e:
                logger.error(f"Ошибка при авторизации в Instagram: {e}")
                # Не прерываем работу бота, просто логируем ошибку
                return
            
        except Exception as e:
            logger.error(f"Критическая ошибка при авторизации в Instagram: {e}")
            # Не прерываем работу бота, просто логируем ошибку
            return
    
    def _login_with_2fa(self):
        """Выполняет вход с двухфакторной аутентификацией"""
        try:
            # Пробуем авторизоваться
            self.loader.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        except TwoFactorAuthRequiredException:
            # Получаем код 2FA
            code = self._generate_2fa_code()
            if not code:
                raise ValueError("Не удалось сгенерировать код 2FA")
                
            logger.info(f"Сгенерирован код 2FA: {code}")
            
            # В некоторых случаях может потребоваться подождать несколько секунд,
            # чтобы код стал действительным на серверах Instagram
            time.sleep(3)
            
            # Пробуем несколько кодов с разным временем
            try:
                # Пробуем текущий код
                self.loader.two_factor_login(code)
                logger.info("Успешная 2FA авторизация в Instagram")
                return
            except Exception as e:
                logger.warning(f"Ошибка при первой попытке 2FA: {e}")
                
            # Если первая попытка не удалась, ждем 30 секунд и пробуем снова
            # (коды TOTP обновляются каждые 30 секунд)
            logger.info("Ожидаем нового кода 2FA...")
            time.sleep(30)
            
            # Генерируем новый код
            new_code = self._generate_2fa_code()
            if new_code != code:
                logger.info(f"Сгенерирован новый код 2FA: {new_code}")
                try:
                    self.loader.two_factor_login(new_code)
                    logger.info("Успешная 2FA авторизация с новым кодом")
                    return
                except Exception as e:
                    logger.error(f"Ошибка при второй попытке 2FA: {e}")
                    raise ValueError("Не удалось авторизоваться с 2FA кодом")
            else:
                logger.error("Новый код 2FA совпадает с предыдущим, возможно неверная настройка TOTP")
                raise ValueError("Проблема с генерацией 2FA кодов")
    
    async def download_reel(self, url: str) -> str:
        """Скачивает видео из Instagram Reel"""
        try:
            # Проверяем авторизацию
            if not self.is_logged_in:
                logger.warning("Не авторизован в Instagram, пробуем альтернативный метод")
                return await self._download_reel_alternative(url)
            
            # Извлекаем shortcode из URL
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                raise ValueError("Неверный формат URL Instagram Reel")
            
            # Создаем временную директорию для сохранения
            temp_path = os.path.join(self.temp_dir, f"reel_{shortcode}")
            os.makedirs(temp_path, exist_ok=True)
            
            try:
                # Пробуем скачать через instaloader
                post = await retry_async(
                    self._download_post,
                    shortcode=shortcode,
                    target=temp_path,
                    max_retries=3,
                    retry_delay=1
                )
                
                # Находим видео файл
                video_path = self._find_video_file(temp_path)
                if not video_path:
                    raise ValueError("Видео не найдено в скачанном посте")
                
                return video_path
            except Exception as e:
                logger.error(f"Ошибка при скачивании через Instaloader: {e}")
                # Если не удалось скачать через instaloader, пробуем альтернативный метод
                return await self._download_reel_alternative(url)
            
        except Exception as e:
            logger.error(f"Ошибка при скачивании Reel: {e}")
            raise
    
    async def _download_reel_alternative(self, url: str) -> str:
        """Альтернативный метод скачивания через публичный API без авторизации"""
        try:
            # Извлекаем shortcode из URL
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                raise ValueError("Неверный формат URL Instagram Reel")
            
            logger.info(f"Пробуем скачать рил с shortcode {shortcode} альтернативным методом")
            
            # Создаем временную директорию для сохранения
            temp_path = os.path.join(self.temp_dir, f"reel_{shortcode}_alt")
            os.makedirs(temp_path, exist_ok=True)
            
            try:
                # Формируем URL для получения информации о посте без авторизации
                json_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"
                
                # Задаем заголовки для имитации браузера
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                }
                
                # Получаем информацию о посте
                session = requests.Session()
                response = session.get(json_url, headers=headers)
                
                if response.status_code != 200:
                    raise ValueError(f"Ошибка при получении информации о посте: {response.status_code}")
                
                # Парсим JSON
                data = response.json()
                
                # Ищем URL видео
                video_url = None
                if 'items' in data and len(data['items']) > 0:
                    item = data['items'][0]
                    if 'video_versions' in item:
                        video_url = item['video_versions'][0]['url']
                    elif 'carousel_media' in item:
                        for media in item['carousel_media']:
                            if 'video_versions' in media:
                                video_url = media['video_versions'][0]['url']
                                break
                
                # Проверяем другие пути в JSON
                if not video_url and 'graphql' in data:
                    if 'shortcode_media' in data['graphql']:
                        media = data['graphql']['shortcode_media']
                        if media.get('is_video') and 'video_url' in media:
                            video_url = media['video_url']
                
                if not video_url:
                    raise ValueError("Не удалось найти URL видео в JSON")
                    
                # Скачиваем видео
                video_path = os.path.join(temp_path, f"{shortcode}.mp4")
                self._download_file(video_url, video_path)
                
                return video_path
            except Exception as e:
                logger.error(f"Ошибка метода 1: {e}")
                # Если не удалось скачать через API, пробуем другие методы
                try:
                    # Пробуем скачать через веб-парсинг
                    return await self._download_reel_web(url, temp_path)
                except Exception as e2:
                    logger.error(f"Ошибка метода 2: {e2}")
                    # Если и через веб-парсинг не удалось, пробуем через сторонние сервисы
                    return await self._download_reel_via_service(url, temp_path)
            
        except Exception as e:
            logger.error(f"Ошибка при альтернативном скачивании: {e}")
            # Финальная попытка - через сторонний сервис
            return await self._download_reel_via_service(url, temp_path if 'temp_path' in locals() else None)
    
    async def _download_reel_via_service(self, url: str, temp_path: str = None) -> str:
        """Скачивает рил через сторонние сервисы"""
        try:
            logger.info("Пробуем скачать рил через сторонний сервис")
            
            shortcode = self._extract_shortcode(url)
            if not temp_path:
                temp_path = os.path.join(self.temp_dir, f"reel_{shortcode}_service")
                os.makedirs(temp_path, exist_ok=True)
            
            # Список сервисов для скачивания
            services = [
                self._download_via_ssinsta,   # Добавляем SSInsta как самый первый приоритетный сервис
                self._download_via_savefrom,  # SaveFrom.net вторым
                self._download_via_rapidapi,
                self._download_via_snapinsta,
                self._download_via_saveinsta
            ]
            
            # Пробуем каждый сервис по очереди
            last_error = None
            for service_func in services:
                try:
                    return await service_func(url, shortcode, temp_path)
                except Exception as e:
                    logger.warning(f"Сервис {service_func.__name__} не сработал: {e}")
                    last_error = e
            
            raise last_error or ValueError("Не удалось скачать видео через сторонние сервисы")
            
        except Exception as e:
            logger.error(f"Ошибка при скачивании через сторонние сервисы: {e}")
            raise
    
    async def _download_via_ssinsta(self, url: str, shortcode: str, temp_path: str) -> str:
        """Скачивает видео через SSInsta (ssyoutube)"""
        try:
            logger.info(f"Скачиваем видео через SSInsta: {shortcode}")
            
            # Преобразуем URL в формат ssyoutube
            ss_url = url.replace("instagram.com", "sssinstagram.com")
            
            # Настройки запроса
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://sssinstagram.com',
            }
            
            # Отправляем запрос
            session = requests.Session()
            response = session.get(ss_url, headers=headers)
            
            if response.status_code != 200:
                raise ValueError(f"Ошибка доступа к SSInsta: {response.status_code}")
            
            # Ищем URL видео в HTML
            html = response.text
            
            # Различные шаблоны для поиска URL видео
            video_patterns = [
                r'<a[^>]*href="([^"]+\.mp4[^"]*)"[^>]*download',
                r'"contentUrl"\s*:\s*"(https://[^"]+\.mp4[^"]*)"',
                r'<source[^>]*src="([^"]+\.mp4[^"]*)"',
                r'<video[^>]*src="([^"]+\.mp4[^"]*)"',
            ]
            
            video_url = None
            for pattern in video_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    for match in matches:
                        if ".mp4" in match:
                            video_url = match
                            break
                    if video_url:
                        break
            
            if not video_url:
                # Ищем по JSON данным, которые могут быть встроены в страницу
                json_pattern = r'<script[^>]*type="application/json"[^>]*>(.*?)</script>'
                json_matches = re.findall(json_pattern, html, re.DOTALL)
                
                for json_data in json_matches:
                    try:
                        data = json.loads(json_data)
                        if isinstance(data, dict) and "url" in data:
                            possible_url = data.get("url")
                            if isinstance(possible_url, str) and ".mp4" in possible_url:
                                video_url = possible_url
                                break
                    except Exception:
                        continue
            
            if not video_url:
                # Если все еще не найдено, сохраняем HTML для дебага
                debug_path = os.path.join(temp_path, "debug_ssinsta.html")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)
                raise ValueError(f"Не удалось найти URL видео в ответе SSInsta. HTML сохранен в {debug_path}")
            
            # Исправляем URL если необходимо
            if not video_url.startswith("http"):
                video_url = "https:" + video_url if video_url.startswith("//") else "https://" + video_url
            
            # Скачиваем видео
            video_path = os.path.join(temp_path, f"{shortcode}_ssinsta.mp4")
            self._download_file(video_url, video_path)
            
            return video_path
            
        except Exception as e:
            logger.error(f"Ошибка при скачивании через SSInsta: {e}")
            raise
    
    async def _download_via_savefrom(self, url: str, shortcode: str, temp_path: str) -> str:
        """Скачивает видео через SaveFrom.net"""
        try:
            logger.info(f"Скачиваем видео через SaveFrom.net: {shortcode}")
            
            # Настройки запроса для получения данных с SaveFrom
            api_url = "https://ru.savefrom.net/api/convert"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/json',
                'Origin': 'https://ru.savefrom.net',
                'Referer': 'https://ru.savefrom.net/25-instagram-reels-download.html',
            }
            
            # Формируем данные для запроса
            data = {
                "url": url,
                "lang": "ru",
            }
            
            # Отправляем запрос
            session = requests.Session()
            response = session.post(api_url, headers=headers, json=data)
            
            if response.status_code != 200:
                raise ValueError(f"Ошибка API SaveFrom: {response.status_code}")
            
            # Парсим JSON ответ
            result = response.json()
            
            # Проверяем наличие ошибок
            if result.get("error"):
                raise ValueError(f"Ошибка SaveFrom API: {result.get('error')}")
            
            # Находим URL видео в ответе
            media_data = result.get("url") or []
            if not media_data:
                raise ValueError("Пустой ответ от SaveFrom.net")
            
            # Ищем видео с наилучшим качеством
            video_url = None
            max_quality = 0
            
            for item in media_data:
                if item.get("url") and item.get("type") == "mp4":
                    quality = item.get("quality", 0)
                    if quality > max_quality:
                        max_quality = quality
                        video_url = item["url"]
            
            if not video_url:
                raise ValueError("Не удалось найти URL видео в ответе SaveFrom.net")
            
            # Скачиваем видео
            video_path = os.path.join(temp_path, f"{shortcode}_savefrom.mp4")
            self._download_file(video_url, video_path)
            
            return video_path
            
        except Exception as e:
            logger.error(f"Ошибка при скачивании через SaveFrom.net: {e}")
            raise
    
    async def _download_via_rapidapi(self, url: str, shortcode: str, temp_path: str) -> str:
        """Скачивает видео через RapidAPI Instagram Downloader"""
        try:
            # Настройки запроса
            api_url = "https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index"
            headers = {
                'X-RapidAPI-Host': 'instagram-downloader-download-instagram-videos-stories.p.rapidapi.com',
                'X-RapidAPI-Key': '87fc744925msh6a94fe5a6a95178p1af631jsna48e1f87db4c'  # Демо-ключ
            }
            params = {"url": url}
            
            # Отправляем запрос
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code != 200:
                raise ValueError(f"Ошибка API: {response.status_code}")
            
            data = response.json()
            if not data.get('media'):
                raise ValueError("Ответ API не содержит медиа-данных")
            
            video_url = None
            for media in data['media']:
                if media.get('type') == 'video':
                    video_url = media.get('url')
                    break
            
            if not video_url:
                raise ValueError("В ответе API нет URL видео")
            
            # Скачиваем видео
            video_path = os.path.join(temp_path, f"{shortcode}_rapidapi.mp4")
            self._download_file(video_url, video_path)
            
            return video_path
        except Exception as e:
            logger.error(f"Ошибка при скачивании через RapidAPI: {e}")
            raise
    
    async def _download_via_snapinsta(self, url: str, shortcode: str, temp_path: str) -> str:
        """Скачивает видео через snapinsta.app"""
        try:
            # Первый запрос для получения токена
            session = requests.Session()
            main_url = "https://snapinsta.app/"
            main_response = session.get(main_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            })
            
            if main_response.status_code != 200:
                raise ValueError(f"Ошибка при доступе к сервису: {main_response.status_code}")
            
            # Извлекаем токен из HTML
            token_match = re.search(r'name="token" value="([^"]+)"', main_response.text)
            if not token_match:
                raise ValueError("Не удалось найти токен")
            
            token = token_match.group(1)
            
            # Отправляем запрос на скачивание
            download_url = "https://snapinsta.app/action.php"
            data = {
                "url": url,
                "token": token,
                "lang": "en"
            }
            
            download_response = session.post(download_url, data=data, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://snapinsta.app',
                'Referer': 'https://snapinsta.app/',
            })
            
            if download_response.status_code != 200:
                raise ValueError(f"Ошибка при запросе на скачивание: {download_response.status_code}")
            
            # Ищем URL видео
            html_content = download_response.text
            video_match = re.search(r'<a\s+href="([^"]+)"\s+.*?download', html_content)
            if not video_match:
                raise ValueError("Не удалось найти ссылку на скачивание")
            
            video_url = video_match.group(1)
            
            # Скачиваем видео
            video_path = os.path.join(temp_path, f"{shortcode}_snapinsta.mp4")
            self._download_file(video_url, video_path)
            
            return video_path
        except Exception as e:
            logger.error(f"Ошибка при скачивании через SnapInsta: {e}")
            raise
    
    async def _download_via_saveinsta(self, url: str, shortcode: str, temp_path: str) -> str:
        """Скачивает видео через saveinsta.app"""
        try:
            # Настройки запроса
            api_url = "https://saveinsta.app/api/ajaxSearch"
            data = {"q": url, "t": "media", "lang": "en"}
            
            # Отправляем запрос
            response = requests.post(api_url, data=data, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://saveinsta.app',
                'Referer': 'https://saveinsta.app/',
            })
            
            if response.status_code != 200:
                raise ValueError(f"Ошибка при запросе: {response.status_code}")
            
            # Парсим JSON
            data = response.json()
            if not data.get('data'):
                raise ValueError("Ответ не содержит данных")
            
            # Ищем URL видео
            html_content = data['data']
            video_match = re.search(r'<a\s+href="([^"]+)"\s+.*?download', html_content)
            if not video_match:
                raise ValueError("Не удалось найти ссылку на скачивание")
            
            video_url = video_match.group(1)
            
            # Скачиваем видео
            video_path = os.path.join(temp_path, f"{shortcode}_saveinsta.mp4")
            self._download_file(video_url, video_path)
            
            return video_path
        except Exception as e:
            logger.error(f"Ошибка при скачивании через SaveInsta: {e}")
            raise
    
    def _download_file(self, url: str, path: str):
        """Скачивает файл по URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
            
            with requests.get(url, headers=headers, stream=True) as r:
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            logger.info(f"Файл успешно скачан: {path}")
            return path
        except Exception as e:
            logger.error(f"Ошибка при скачивании файла: {e}")
            raise
    
    def _extract_shortcode(self, url: str) -> str:
        """Извлекает shortcode из URL Instagram"""
        patterns = [
            r"instagram\.com/reel/([A-Za-z0-9_-]+)",
            r"instagram\.com/p/([A-Za-z0-9_-]+)",
            r"instagram\.com/tv/([A-Za-z0-9_-]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def _download_post(self, shortcode: str, target: str) -> Post:
        """Скачивает пост из Instagram"""
        try:
            post = Post.from_shortcode(self.loader.context, shortcode)
            self.loader.download_post(post, target=target)
            return post
        except Exception as e:
            logger.error(f"Ошибка при скачивании поста: {e}")
            raise
    
    def _find_video_file(self, directory: str) -> str:
        """Находит видео файл в директории"""
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.mp4'):
                    return os.path.join(root, file)
        return None
    
    def cleanup(self, video_path: str):
        """Удаляет временные файлы"""
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            temp_dir = os.path.dirname(video_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"Ошибка при очистке временных файлов: {e}")
    
    async def _download_reel_web(self, url: str, temp_path: str) -> str:
        """Скачивает рил через web-запрос, извлекая URL видео из HTML"""
        try:
            shortcode = self._extract_shortcode(url)
            logger.info(f"Пробуем скачать рил с shortcode {shortcode} через парсинг HTML")
            
            # Пробуем разные URL форматы
            urls_to_try = [
                f"https://www.instagram.com/reel/{shortcode}/",
                f"https://www.instagram.com/p/{shortcode}/",
                f"https://www.instagram.com/tv/{shortcode}/"
            ]
            
            html = None
            for page_url in urls_to_try:
                try:
                    # Задаем заголовки для имитации браузера
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Cookie': 'ig_cb=1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0',
                    }
                    
                    # Получаем HTML страницы
                    session = requests.Session()
                    response = session.get(page_url, headers=headers)
                    
                    if response.status_code == 200:
                        html = response.text
                        logger.info(f"Успешно получен HTML с URL: {page_url}")
                        break
                    else:
                        logger.warning(f"Ошибка при получении {page_url}: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Ошибка при доступе к {page_url}: {e}")
            
            if not html:
                raise ValueError("Не удалось получить HTML страницы Instagram")
            
            # Ищем URL видео в HTML
            video_url = None
            
            # Регулярное выражение для поиска URL видео
            video_patterns = [
                r'\"video_url\":\"(https:\\\/\\\/.*?\.mp4.*?)\"',
                r'"video_url":"(https:\/\/.*?\.mp4.*?)"',
                r'"contentUrl":"(https:\/\/.*?\.mp4.*?)"',
                r'<meta property="og:video" content="([^"]+)"',
                r'<meta property="og:video:secure_url" content="([^"]+)"',
                r'videoUrl&quot;:&quot;(https:\/\/.*?\.mp4.*?)&quot;'
            ]
            
            for pattern in video_patterns:
                match = re.search(pattern, html)
                if match:
                    video_url = match.group(1).replace('\\/', '/').replace('&amp;', '&')
                    logger.info(f"Найден URL видео по шаблону: {pattern[:20]}...")
                    break
            
            if not video_url:
                # Сохраняем HTML для отладки
                debug_html_path = os.path.join(temp_path, "debug_page.html")
                with open(debug_html_path, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.error(f"Не удалось найти URL видео. HTML сохранен в: {debug_html_path}")
                raise ValueError("Не удалось найти URL видео на странице")
                
            # Скачиваем видео
            video_path = os.path.join(temp_path, f"{shortcode}_web.mp4")
            self._download_file(video_url, video_path)
            
            return video_path
            
        except Exception as e:
            logger.error(f"Ошибка при скачивании через web: {e}")
            raise 