# МистерТоля Telegram Бот

Версия: 3.0

## Описание
Этот бот предоставляет функционал на базе AI для работы в Telegram-группах, имитируя характер Анатолия Шария. Бот умеет отвечать на сообщения, реагировать на упоминания, предоставлять информацию о футбольных матчах и многое другое.

## Функциональность
- Интеграция с DeepSeek AI для генерации ответов
- Автоматические утренние сообщения
- Команды для просмотра статистики футбольных команд
- Система мониторинга состояния бота
- Автоматическое резервное копирование базы данных
- История сообщений и контекстные ответы

## Технологический стек
- Python 3.10+
- aiogram 3.4.1+ для работы с Telegram API
- PostgreSQL для хранения данных
- OpenAI API (DeepSeek) для генерации текста
- APScheduler для запланированных задач

## Установка

### Предварительные требования
- Python 3.10+
- PostgreSQL
- Токен Telegram бота (получите у [@BotFather](https://t.me/BotFather))
- API ключи для DeepSeek, OpenWeather и RapidAPI

### Установка зависимостей
```bash
pip install -r requirements.txt
```

### Переменные окружения
Перед запуском необходимо настроить следующие переменные окружения:

```
# Обязательные переменные
TELEGRAM_TOKEN=ваш_токен_бота
DEEPSEEK_API_KEY=ваш_api_ключ
DATABASE_URL=postgresql://username:password@localhost:5432/db_name
CHAT_ID=-1001234567890
TARGET_USER_ID=123456789
TARGET_CHAT_ID=-1002520045054
ADMIN_CHAT_ID=948182089
OPENWEATHER_API_KEY=ваш_ключ
RAPIDAPI_KEY=ваш_ключ

# Дополнительные параметры
BACKUP_ENABLED=true
MONITORING_ENABLED=true
BACKUP_PATH=./backups

# Шаблоны ответов
RESPONSES_SOSAL=["Ответ 1", "Ответ 2"]
RARE_RESPONSE_SOSAL="Редкий ответ"
RESPONSE_LETAL="Ответ на 'летал?'"
RESPONSES_SCAMIL=["Ответ 1", "Ответ 2"]
TEAM_IDS={"real": 541, "lfc": 40, "arsenal": 42}
TARGET_REACTION="👍"
```

## Запуск бота локально
```bash
python -m app.main
```

## Деплой в Railway

### Подготовка к деплою
1. Создайте аккаунт на [Railway](https://railway.app/)
2. Создайте новый проект и подключите репозиторий
3. Добавьте сервис PostgreSQL к проекту
4. Настройте все переменные окружения в разделе Variables
5. Убедитесь, что в Railway указан правильный путь в Procfile

### Настройка Railway
- Настройте автоматические деплои при изменении в репозитории
- Включите мониторинг для отслеживания состояния бота
- Проверьте логи после деплоя для выявления возможных проблем

## Тестирование
Для запуска тестов используйте:
```bash
pytest
```

## Обслуживание
- Периодически проверяйте потребление ресурсов в Railway
- Следите за логами бота для выявления ошибок
- Периодически обновляйте зависимости

## Разработка

### Структура проекта
- `app/` - основной код бота
  - `handlers/` - обработчики сообщений и команд
  - `services/` - внешние сервисы (API, AI, мониторинг)
  - `database/` - модели и операции с базой данных
  - `config.py` - настройки бота
  - `bot.py` - основная логика работы бота
  - `main.py` - точка входа в приложение
- `tests/` - тесты для всех компонентов

## Лицензия
Все права защищены. Несанкционированное использование запрещено.
