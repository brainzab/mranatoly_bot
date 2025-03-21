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