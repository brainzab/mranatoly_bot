import os
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Версия кода
CODE_VERSION = "3.0"

# Константы
MAX_TOKENS = 999
AI_TEMPERATURE = 1.5
CHAT_HISTORY_LIMIT = 30

# Получение переменных окружения
def get_env_var(var_name, default=None):
    value = os.getenv(var_name)
    if value is None and default is None:
        logger.error(f"Отсутствует обязательная переменная окружения: {var_name}")
        sys.exit(1)
    return value if value is not None else default

# Токены и ключи
TELEGRAM_TOKEN = get_env_var('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = get_env_var('DEEPSEEK_API_KEY')
OPENWEATHER_API_KEY = get_env_var('OPENWEATHER_API_KEY')
RAPIDAPI_KEY = get_env_var('RAPIDAPI_KEY')
CHAT_ID = int(get_env_var('CHAT_ID'))
DATABASE_URL = get_env_var('DATABASE_URL')
TARGET_USER_ID = int(get_env_var('TARGET_USER_ID', '948182089'))
TARGET_CHAT_ID = int(get_env_var('TARGET_CHAT_ID', '-1002520045054'))  # Чат, в котором сохраняем всю историю
ADMIN_CHAT_ID = int(get_env_var('ADMIN_CHAT_ID', str(TARGET_USER_ID)))  # По умолчанию TARGET_USER_ID

# AI настройки
AI_SYSTEM_PROMPT = f"Ты Анатолий Шарий, твоя фамилия Шарий, у тебя есть жена Ольга Шарий. Ты пророссийский журналист, скамер, блогер, эксцентричный пиздец, любишь материться. Сегодня {datetime.now().strftime('%Y-%m-%d')}. Отвечай с иронией, надменностью и будь полезным помощником в Telegram-группе."

# Константы для ответов из .env
RESPONSES_SOSAL = json.loads(get_env_var('RESPONSES_SOSAL'))  # Обязательная переменная
RARE_RESPONSE_SOSAL = get_env_var('RARE_RESPONSE_SOSAL')      # Обязательная переменная
RESPONSE_LETAL = get_env_var('RESPONSE_LETAL')                # Обязательная переменная
RESPONSES_SCAMIL = json.loads(get_env_var('RESPONSES_SCAMIL'))  # Обязательная переменная
TEAM_IDS = json.loads(get_env_var('TEAM_IDS'))                # Обязательная переменная
TARGET_REACTION = get_env_var('TARGET_REACTION')              # Обязательная переменная

# Настройки мониторинга и бэкапа
BACKUP_ENABLED = get_env_var('BACKUP_ENABLED', 'true').lower() == 'true'
BACKUP_PATH = get_env_var('BACKUP_PATH', './backups')
MONITORING_ENABLED = get_env_var('MONITORING_ENABLED', 'true').lower() == 'true'

# Google Drive API настройки
DRIVE_ENABLED = bool(os.environ.get('DRIVE_ENABLED', 'False') == 'True')
GDRIVE_CREDENTIALS_FILE = os.environ.get('GDRIVE_CREDENTIALS_FILE', 'credentials.json')
GDRIVE_FOLDER_ID = os.environ.get('GDRIVE_FOLDER_ID', '')  # ID папки на Google Drive для сохранения файлов
CHAT_EXPORT_INTERVAL_HOURS = int(os.environ.get('CHAT_EXPORT_INTERVAL_HOURS', '24'))  # Интервал экспорта в часах

class Config:
    """Класс конфигурации бота"""
    
    @staticmethod
    def get_logging_config() -> Dict[str, Any]:
        """Получить конфигурацию логирования"""
        return {
            "level": getattr(logging, get_env_var('LOG_LEVEL', 'INFO')),
            "format": get_env_var('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
        }
    
    @staticmethod
    def get_database_config() -> Dict[str, Any]:
        """Получить конфигурацию базы данных"""
        return {
            "url": DATABASE_URL,
            "pool_size": int(get_env_var('DATABASE_POOL_SIZE', '10')),
        }
    
    @staticmethod
    def get_api_config() -> Dict[str, Any]:
        """Получить конфигурацию API"""
        return {
            "timeout": int(get_env_var('API_TIMEOUT', '10')),
            "openai_key": get_env_var('OPENAI_API_KEY', ''),
            "weather_key": get_env_var('WEATHER_API_KEY', ''),
            "rapidapi_key": RAPIDAPI_KEY,
        }
    
    @staticmethod
    def get_team_ids() -> Dict[str, int]:
        """Получить ID футбольных команд"""
        return TEAM_IDS
    
    @staticmethod
    def get_drive_config() -> Dict[str, Any]:
        """Получить конфигурацию Google Drive"""
        return {
            "enabled": DRIVE_ENABLED,
            "credentials_file": GDRIVE_CREDENTIALS_FILE,
            "folder_id": GDRIVE_FOLDER_ID,
            "export_interval_hours": CHAT_EXPORT_INTERVAL_HOURS,
        }