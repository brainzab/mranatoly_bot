import logging
import re
import os
import tempfile
from instaloader import Instaloader, Post
from app.services.api import retry_async

logger = logging.getLogger(__name__)

class InstagramHandler:
    def __init__(self):
        self.loader = Instaloader()
        self.temp_dir = tempfile.gettempdir()
    
    async def download_reel(self, url: str) -> str:
        """Скачивает видео из Instagram Reel"""
        try:
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