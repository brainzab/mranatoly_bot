import logging
import os
import json
from datetime import datetime
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from app.config import GDRIVE_CREDENTIALS_FILE, GDRIVE_FOLDER_ID

logger = logging.getLogger(__name__)

class GoogleDriveService:
    """Сервис для работы с Google Drive API"""
    
    def __init__(self):
        self.drive = None
        self.credentials_file = GDRIVE_CREDENTIALS_FILE
        self.folder_id = GDRIVE_FOLDER_ID
    
    def authenticate(self):
        """Авторизация в Google Drive с использованием сервисного аккаунта"""
        try:
            logger.info(f"Выполняется аутентификация в Google Drive с файлом {self.credentials_file}")
            
            # Проверяем, существует ли файл с учетными данными
            if not os.path.exists(self.credentials_file):
                logger.error(f"Файл с учетными данными не найден: {self.credentials_file}")
                return False
            
            # Используем сервисный аккаунт для авторизации
            credentials = Credentials.from_service_account_file(
                self.credentials_file, 
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            # Инициализируем сервис
            service = build('drive', 'v3', credentials=credentials)
            
            # Инициализируем клиент PyDrive (оболочка для удобной работы с Google Drive API)
            gauth = GoogleAuth()
            gauth.credentials = credentials
            self.drive = GoogleDrive(gauth)
            
            logger.info("Аутентификация в Google Drive успешно выполнена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка аутентификации в Google Drive: {e}")
            return False
    
    def upload_json(self, data, filename):
        """
        Загружает данные в формате JSON на Google Drive
        
        :param data: Словарь или список для сохранения в JSON
        :param filename: Имя файла (без расширения)
        :return: URL файла или None в случае ошибки
        """
        if not self.drive:
            if not self.authenticate():
                logger.error("Не удалось авторизоваться в Google Drive")
                return None
        
        try:
            # Добавляем временную метку к имени файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            full_filename = f"{filename}_{timestamp}.json"
            
            # Создаем временный файл
            temp_file_path = f"/tmp/{full_filename}"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Создаем файл на Google Drive
            file_metadata = {
                'title': full_filename,
                'parents': [{'id': self.folder_id}] if self.folder_id else [],
                'mimeType': 'application/json'
            }
            
            gfile = self.drive.CreateFile(file_metadata)
            gfile.SetContentFile(temp_file_path)
            gfile.Upload()
            
            # Удаляем временный файл
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            
            logger.info(f"Файл {full_filename} успешно загружен на Google Drive")
            return gfile.get('alternateLink')  # URL для доступа к файлу
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла на Google Drive: {e}")
            return None
    
    def list_files(self, query=None):
        """
        Получает список файлов из указанной папки на Google Drive
        
        :param query: Запрос для поиска файлов (по умолчанию - все файлы в указанной папке)
        :return: Список файлов или пустой список в случае ошибки
        """
        if not self.drive:
            if not self.authenticate():
                logger.error("Не удалось авторизоваться в Google Drive")
                return []
        
        try:
            if query is None and self.folder_id:
                query = f"'{self.folder_id}' in parents"
            
            file_list = self.drive.ListFile({'q': query}).GetList()
            return file_list
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка файлов из Google Drive: {e}")
            return []
    
    def delete_file(self, file_id):
        """
        Удаляет файл с указанным ID из Google Drive
        
        :param file_id: ID файла для удаления
        :return: True в случае успеха, False в случае ошибки
        """
        if not self.drive:
            if not self.authenticate():
                logger.error("Не удалось авторизоваться в Google Drive")
                return False
        
        try:
            file = self.drive.CreateFile({'id': file_id})
            file.Delete()
            logger.info(f"Файл с ID {file_id} успешно удален из Google Drive")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении файла из Google Drive: {e}")
            return False 