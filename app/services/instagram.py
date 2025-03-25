import logging
import re
import os
import tempfile
import time
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
        self._login()
    
    def _generate_2fa_code(self):
        """Генерирует код для двухфакторной аутентификации"""
        if not INSTAGRAM_2FA_SECRET:
            logger.error("Отсутствует секрет для 2FA")
            return None
        
        try:
            totp = pyotp.TOTP(INSTAGRAM_2FA_SECRET)
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
            
            # Вводим код 2FA
            self.loader.two_factor_login(code)
            logger.info("Успешная 2FA авторизация в Instagram")
    
    async def download_reel(self, url: str) -> str:
        """Скачивает видео из Instagram Reel"""
        try:
            # Проверяем авторизацию
            if not self.loader.context.is_logged_in:
                logger.warning("Не авторизован в Instagram, пробуем скачать без авторизации")
            
            # Извлекаем shortcode из URL
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                raise ValueError("Неверный формат URL Instagram Reel")
            
            # Создаем временную директорию для сохранения
            temp_path = os.path.join(self.temp_dir, f"reel_{shortcode}")
            os.makedirs(temp_path, exist_ok=True)
            
            # Скачиваем пост
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
            logger.error(f"Ошибка при скачивании Reel: {e}")
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