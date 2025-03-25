import os
import json
import logging
import sys
from datetime import datetime

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
TARGET_USER_ID = int(get_env_var('TARGET_USER_ID', '660949286'))
TARGET_CHAT_ID = int(get_env_var('TARGET_CHAT_ID', '-1002362736664'))  # Чат, в котором сохраняем всю историю
ADMIN_CHAT_ID = int(get_env_var('ADMIN_CHAT_ID', str(TARGET_USER_ID)))  # По умолчанию TARGET_USER_ID

# Instagram настройки
INSTAGRAM_USERNAME = get_env_var('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = get_env_var('INSTAGRAM_PASSWORD')
INSTAGRAM_SESSION_FILE = get_env_var('INSTAGRAM_SESSION_FILE', 'instagram_session')

# AI настройки
AI_SYSTEM_PROMPT = f"Ты Анатолий Шарий, твоя фамилия Шарий, у тебя есть жена Ольга Шарий. Ты пророссийский журналист, скамер, блогер, эксцентричный, любишь материться. Сегодня {datetime.now().strftime('%Y-%m-%d')}. Отвечай с иронией, надменностью и будь полезным помощником в Telegram-группе."

# Константы для ответов из .env
RESPONSES_SOSAL = json.loads(get_env_var('RESPONSES_SOSAL'))  # Обязательная переменная
RARE_RESPONSE_SOSAL = get_env_var('RARE_RESPONSE_SOSAL')      # Обязательная переменная
RESPONSE_LETAL = get_env_var('RESPONSE_LETAL')                # Обязательная переменная
RESPONSES_SCAMIL = json.loads(get_env_var('RESPONSES_SCAMIL'))  # Обязательная переменная
TEAM_IDS = json.loads(get_env_var('TEAM_IDS'))                # Обязательная переменная
TARGET_REACTION = get_env_var('TARGET_REACTION')              # Обязательная переменная
REACTION_ENABLED = get_env_var('REACTION_ENABLED', 'true').lower() == 'true'  # Включены ли реакции
REACTION_TARGET_USER_ID = int(get_env_var('REACTION_TARGET_USER_ID', str(TARGET_USER_ID)))  # Пользователь, на чьи сообщения ставится реакция

# Настройки мониторинга и бэкапа
BACKUP_ENABLED = get_env_var('BACKUP_ENABLED', 'true').lower() == 'true'
BACKUP_PATH = get_env_var('BACKUP_PATH', './backups')
MONITORING_ENABLED = get_env_var('MONITORING_ENABLED', 'true').lower() == 'true'
