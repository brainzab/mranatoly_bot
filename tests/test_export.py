import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.export import ChatExportService
from app.services.drive import GoogleDriveService

@pytest.fixture
def drive_service_mock():
    drive_service = MagicMock(spec=GoogleDriveService)
    drive_service.authenticate.return_value = True
    drive_service.upload_json.return_value = "https://drive.google.com/file/d/example_id"
    return drive_service

@pytest.fixture
def db_pool_mock():
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    
    # Мокаем данные для _get_all_chat_ids
    conn.fetch.side_effect = [
        # Список chat_id
        [{"chat_id": -1001234567890}, {"chat_id": -1001987654321}],
        # Статистика пользователей для первого чата
        [{"user_id": 123456789, "message_count": 10}, {"user_id": 987654321, "message_count": 5}],
        # Сообщения для первого чата
        [
            {
                "id": 1, "user_id": 123456789, "message_id": 100, "role": "user", 
                "content": "Привет, бот!", "timestamp": 1672531200.0, "reset_id": 0, "tokens": 0
            },
            {
                "id": 2, "user_id": 987654321, "message_id": 101, "role": "assistant", 
                "content": "Привет!", "timestamp": 1672531260.0, "reset_id": 0, "tokens": 0
            }
        ],
        # Статистика пользователей для второго чата
        [{"user_id": 555555555, "message_count": 3}],
        # Сообщения для второго чата
        [
            {
                "id": 3, "user_id": 555555555, "message_id": 200, "role": "user", 
                "content": "Как дела?", "timestamp": 1672617600.0, "reset_id": 0, "tokens": 0
            }
        ]
    ]
    
    # Мокаем данные для общего количества сообщений
    conn.fetchval.side_effect = [10, 3]
    
    return pool

@pytest.mark.asyncio
async def test_export_all_chats_history(db_pool_mock, drive_service_mock):
    # Подготовка
    with patch('app.services.export.GoogleDriveService', return_value=drive_service_mock), \
         patch('app.services.export.DRIVE_ENABLED', True):
        
        export_service = ChatExportService(db_pool_mock)
        
        # Действие
        result = await export_service.export_all_chats_history()
        
        # Проверка
        assert result == "https://drive.google.com/file/d/example_id"
        
        # Проверяем, что методы были вызваны правильное число раз
        assert db_pool_mock.acquire.call_count >= 3  # Минимум для получения списка чатов и данных для 2 чатов
        assert drive_service_mock.upload_json.call_count == 1
        
        # Проверяем аргументы вызова upload_json
        args, kwargs = drive_service_mock.upload_json.call_args
        uploaded_data, filename = args
        
        # Проверка структуры выгруженных данных
        assert "export_timestamp" in uploaded_data
        assert uploaded_data["total_chats"] == 2
        assert "-1001234567890" in uploaded_data["chats"]
        assert "-1001987654321" in uploaded_data["chats"]
        assert uploaded_data["chats"]["-1001234567890"]["total_messages"] == 10
        assert uploaded_data["chats"]["-1001987654321"]["total_messages"] == 3
        assert "123456789" in uploaded_data["chats"]["-1001234567890"]["users"]

@pytest.mark.asyncio
async def test_get_chat_data(db_pool_mock):
    # Подготовка
    export_service = ChatExportService(db_pool_mock)
    
    # Действие
    chat_data = await export_service._get_chat_data(-1001234567890)
    
    # Проверка
    assert chat_data["total_messages"] == 10
    assert len(chat_data["users"]) == 2
    assert "123456789" in chat_data["users"]
    assert "987654321" in chat_data["users"]
    assert chat_data["users"]["123456789"]["message_count"] == 10
    assert len(chat_data["messages"]) == 2

@pytest.mark.asyncio
async def test_export_without_drive(db_pool_mock):
    # Подготовка
    with patch('app.services.export.DRIVE_ENABLED', False):
        export_service = ChatExportService(db_pool_mock)
        
        # Действие
        result = await export_service.export_all_chats_history()
        
        # Проверка - должны получить данные без загрузки на Google Drive
        assert result is not None
        assert "total_chats" in result
        assert result["total_chats"] == 2 