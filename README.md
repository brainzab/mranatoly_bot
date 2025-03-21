# Mr. Anatoly Bot

Телеграм-бот с функциями погоды, курсов валют и разговорного ИИ.

## Основные команды

- `/start` - начать диалог с ботом
- `/help` - получить справку по командам
- `/pogoda` - погода в Минске, Гомеле и Жлобине
- `/stats` - статистика использования бота
- `/chatstats` - статистика сообщений в чате
- `/byn` - курс белорусского рубля
- `/rub` - курс российского рубля
- `/wld` - курс WorldCoin (WLD)
- `/exportchats` - экспортировать историю чатов (только для админа)

## Функции

- **Утреннее сообщение**: каждое утро в 8:00 бот отправляет приветствие с погодой, курсами валют и пожеланием, сгенерированным ИИ
- **Обработка сообщений**: бот отвечает на сообщения пользователей с помощью ИИ
- **Мониторинг**: отслеживает использование API и ИИ по чатам
- **Экспорт данных**: автоматический ежедневный экспорт истории чатов на Google Drive

## Установка

1. Клонировать репозиторий
2. Установить зависимости: `pip install -r requirements.txt`
3. Создать файл `.env` с необходимыми переменными окружения
4. Запустить бота: `python main.py`

## Настройка Google Drive

Для использования функции экспорта на Google Drive следуйте инструкции в [docs/google_drive_setup.md](docs/google_drive_setup.md).

## Переменные окружения

```
# Обязательные
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Опциональные
LOG_LEVEL=INFO
ADMIN_CHAT_ID=your_telegram_user_id
TARGET_CHAT_ID=target_chat_for_morning_message
WEATHER_API_KEY=your_openweathermap_api_key

# Настройки Google Drive (опционально)
DRIVE_ENABLED=True
GDRIVE_CREDENTIALS_FILE=credentials.json
GDRIVE_FOLDER_ID=your_google_drive_folder_id
CHAT_EXPORT_INTERVAL_HOURS=24
```

## Тестирование

Запуск тестов: `pytest tests/`

## Лицензия

MIT
