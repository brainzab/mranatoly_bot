import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from app.handlers.commands import CommandHandlers

@pytest.fixture
def message_mock():
    message = AsyncMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = -1001234567890
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456789
    message.text = "Test message"
    return message

@pytest.fixture
def bot_mock():
    bot = AsyncMock()
    bot.id = 987654321
    return bot

@pytest.fixture
def db_pool_mock():
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    conn.fetchval.return_value = 1
    return pool

@pytest.mark.asyncio
async def test_command_start(message_mock, bot_mock, db_pool_mock):
    # Подготовка
    message_mock.reply = AsyncMock(return_value=MagicMock(message_id=1))
    command_handlers = CommandHandlers(bot_mock, db_pool_mock)
    
    # Действие
    await command_handlers.command_start(message_mock)
    
    # Проверка
    message_mock.reply.assert_called_once()
    assert "Привет, я бот версии" in message_mock.reply.call_args[0][0]

@pytest.mark.asyncio
async def test_command_version(message_mock, bot_mock, db_pool_mock):
    # Подготовка
    message_mock.reply = AsyncMock(return_value=MagicMock(message_id=1))
    command_handlers = CommandHandlers(bot_mock, db_pool_mock)
    
    # Действие
    await command_handlers.command_version(message_mock)
    
    # Проверка
    message_mock.reply.assert_called_once()
    assert "Версия бота:" in message_mock.reply.call_args[0][0]

@pytest.mark.asyncio
async def test_check_database_health(bot_mock, db_pool_mock):
    # Подготовка
    command_handlers = CommandHandlers(bot_mock, db_pool_mock)
    
    # Действие
    result = await command_handlers.check_database_health()
    
    # Проверка
    assert result is True
    db_pool_mock.acquire.assert_called_once()

@pytest.mark.asyncio
async def test_check_database_health_unexpected_result(bot_mock, db_pool_mock):
    # Подготовка
    conn = AsyncMock()
    db_pool_mock.acquire.return_value.__aenter__.return_value = conn
    conn.fetchval.return_value = None  # Возвращаем None вместо 1
    command_handlers = CommandHandlers(bot_mock, db_pool_mock)
    
    # Действие
    result = await command_handlers.check_database_health()
    
    # Проверка
    assert result is False
    db_pool_mock.acquire.assert_called_once()

@pytest.mark.asyncio
async def test_check_database_health_db_error(bot_mock, db_pool_mock):
    # Подготовка
    conn = AsyncMock()
    db_pool_mock.acquire.return_value.__aenter__.return_value = conn
    conn.fetchval.side_effect = Exception("Тестовая ошибка БД")
    command_handlers = CommandHandlers(bot_mock, db_pool_mock)
    
    # Действие
    result = await command_handlers.check_database_health()
    
    # Проверка
    assert result is False
    db_pool_mock.acquire.assert_called_once()

@pytest.mark.asyncio
async def test_command_chatstats(message_mock, bot_mock, db_pool_mock):
    # Подготовка
    message_mock.reply = AsyncMock(return_value=MagicMock(message_id=1))
    message_mock.chat.type = "supergroup"
    bot_mock.get_chat = AsyncMock(return_value=MagicMock(title="Test Group"))
    bot_mock.get_chat_member = AsyncMock(return_value=MagicMock(
        user=MagicMock(username="testuser", full_name="Test User")
    ))
    bot_mock.delete_message = AsyncMock()
    
    conn = AsyncMock()
    db_pool_mock.acquire.return_value.__aenter__.return_value = conn
    
    # Имитируем результаты для разных периодов
    conn.fetchval.return_value = 10  # Общее количество сообщений
    conn.fetch.side_effect = [
        # Статистика за день
        [{"user_id": 123456, "message_count": 5}],
        # Статистика за месяц
        [{"user_id": 123456, "message_count": 8}],
        # Статистика за все время
        [{"user_id": 123456, "message_count": 10}]
    ]
    
    command_handlers = CommandHandlers(bot_mock, db_pool_mock)
    
    # Действие
    await command_handlers.command_chatstats(message_mock)
    
    # Проверка
    # Проверяем, что было отправлено два сообщения (ожидание и результат)
    assert message_mock.reply.call_count == 2
    # Проверяем, что сообщение об ожидании было удалено
    bot_mock.delete_message.assert_called_once()
    # Проверяем, что во втором сообщении есть статистика
    assert "Статистика сообщений" in message_mock.reply.call_args_list[1][0][0]
    assert "За последние 24 часа" in message_mock.reply.call_args_list[1][0][0]
    assert "За последние 30 дней" in message_mock.reply.call_args_list[1][0][0]
    assert "За все время" in message_mock.reply.call_args_list[1][0][0]

@pytest.mark.asyncio
async def test_command_export_chats(message_mock, bot_mock, db_pool_mock):
    # Подготовка
    message_mock.reply = AsyncMock(return_value=MagicMock(message_id=1))
    message_mock.from_user.id = 123456789  # ID пользователя, совпадающий с ADMIN_CHAT_ID
    bot_mock.delete_message = AsyncMock()
    
    # Мокаем ChatExportService
    mock_export_service = AsyncMock()
    mock_export_service.export_all_chats_history.return_value = "https://drive.google.com/file/d/example_id"
    
    with patch('app.handlers.commands.ADMIN_CHAT_ID', '123456789'), \
         patch('app.handlers.commands.DRIVE_ENABLED', True), \
         patch('app.handlers.commands.ChatExportService', return_value=mock_export_service):
        
        command_handlers = CommandHandlers(bot_mock, db_pool_mock)
        
        # Действие
        await command_handlers.command_export_chats(message_mock)
        
        # Проверка
        assert message_mock.reply.call_count == 2  # Ожидание и результат
        assert "успешно экспортирована" in message_mock.reply.call_args_list[1][0][0]
        assert mock_export_service.export_all_chats_history.call_count == 1
        assert bot_mock.delete_message.call_count == 1  # Удаление сообщения об ожидании

@pytest.mark.asyncio
async def test_command_export_chats_unauthorized(message_mock, bot_mock, db_pool_mock):
    # Подготовка
    message_mock.reply = AsyncMock(return_value=MagicMock(message_id=1))
    message_mock.from_user.id = 987654321  # ID пользователя, НЕ совпадающий с ADMIN_CHAT_ID
    
    with patch('app.handlers.commands.ADMIN_CHAT_ID', '123456789'), \
         patch('app.handlers.commands.DRIVE_ENABLED', True):
        
        command_handlers = CommandHandlers(bot_mock, db_pool_mock)
        
        # Действие
        await command_handlers.command_export_chats(message_mock)
        
        # Проверка
        message_mock.reply.assert_called_once_with("У вас нет доступа к этой команде.")

@pytest.mark.asyncio
async def test_command_export_chats_drive_disabled(message_mock, bot_mock, db_pool_mock):
    # Подготовка
    message_mock.reply = AsyncMock(return_value=MagicMock(message_id=1))
    message_mock.from_user.id = 123456789  # ID пользователя, совпадающий с ADMIN_CHAT_ID
    
    with patch('app.handlers.commands.ADMIN_CHAT_ID', '123456789'), \
         patch('app.handlers.commands.DRIVE_ENABLED', False):
        
        command_handlers = CommandHandlers(bot_mock, db_pool_mock)
        
        # Действие
        await command_handlers.command_export_chats(message_mock)
        
        # Проверка
        message_mock.reply.assert_called_once_with("Экспорт в Google Drive отключен. Включите его в настройках.")

@pytest.mark.asyncio
async def test_command_help():
    # Подготовка
    bot_mock = AsyncMock()
    db_pool_mock = AsyncMock()
    message_mock = MagicMock(spec=Message)
    message_mock.chat.id = 123456
    message_mock.from_user.id = 123456  # Не админ
    message_mock.reply = AsyncMock()
    
    # Мок для сохранения сообщения
    with patch('app.database.models.ChatHistory.save_message', AsyncMock()) as save_message_mock:
        # Создаем обработчик команд
        handlers = CommandHandlers(bot_mock, db_pool_mock)
        
        # Вызываем команду /help
        await handlers.command_help(message_mock)
        
        # Проверяем, что метод reply был вызван
        message_mock.reply.assert_called_once()
        
        # Проверяем, что ответ содержит список команд
        args, kwargs = message_mock.reply.call_args
        assert "Доступные команды" in args[0]
        assert "/start" in args[0]
        assert "/help" in args[0]
        assert "/version" in args[0]
        assert "/pogoda" in args[0]
        assert "/stats" in args[0]
        assert "Команды администратора" not in args[0]  # Не для админа
        
        # Проверяем parse_mode
        assert kwargs.get("parse_mode") == "Markdown"

@pytest.mark.asyncio
async def test_command_help_admin():
    # Подготовка
    bot_mock = AsyncMock()
    db_pool_mock = AsyncMock()
    message_mock = MagicMock(spec=Message)
    message_mock.chat.id = 123456
    message_mock.reply = AsyncMock()
    
    # Устанавливаем ID пользователя как ID админа
    with patch('app.handlers.commands.ADMIN_CHAT_ID', 123456):
        message_mock.from_user.id = 123456  # ID админа
        
        # Мок для сохранения сообщения
        with patch('app.database.models.ChatHistory.save_message', AsyncMock()) as save_message_mock:
            # Создаем обработчик команд
            handlers = CommandHandlers(bot_mock, db_pool_mock)
            
            # Вызываем команду /help
            await handlers.command_help(message_mock)
            
            # Проверяем, что метод reply был вызван
            message_mock.reply.assert_called_once()
            
            # Проверяем, что ответ содержит список команд, включая команды админа
            args, kwargs = message_mock.reply.call_args
            assert "Доступные команды" in args[0]
            assert "/start" in args[0]
            assert "/help" in args[0]
            assert "/version" in args[0]
            assert "/pogoda" in args[0]
            assert "/stats" in args[0]
            assert "Команды администратора" in args[0]  # Для админа
            assert "/test" in args[0]
            assert "/exportchats" in args[0]