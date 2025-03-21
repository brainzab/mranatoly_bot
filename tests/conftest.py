import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, AsyncGenerator

from app.services.api import ApiClient, ApiGateway
from app.services.ai import OpenAIClient
from app.services.monitoring import BotMonitoring
from app.services.bot import ActionManager
from app.services.messages import MessageService
from app.database.client import DatabaseClient
from app.database.models import ChatHistory
from app.services.drive import GoogleDriveService
from app.services.export import ChatExportService

@pytest.fixture
def event_loop():
    """Создаем новый event loop для каждого теста."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def database_mock():
    """Мок для базы данных."""
    mock = AsyncMock(spec=DatabaseClient)
    mock.execute = AsyncMock(return_value=None)
    mock.fetchall = AsyncMock(return_value=[])
    mock.fetchone = AsyncMock(return_value=None)
    mock.close = AsyncMock()
    
    # Добавляем моки для методов, которые могут использоваться в тестах
    mock.get_chat_history = AsyncMock(return_value=[])
    mock.add_message = AsyncMock(return_value=1)
    mock.get_chat_stats = AsyncMock(return_value={"total_messages": 0, "users": {}})
    
    return mock

@pytest.fixture
def api_mock():
    """Мок для API клиента."""
    mock = AsyncMock(spec=ApiClient)
    mock.get_weather = AsyncMock(return_value={"temp": 20, "description": "ясно"})
    mock.get_currency = AsyncMock(return_value={"USD": 2.5, "EUR": 3.0, "RUB": 0.03})
    mock.get_crypto = AsyncMock(return_value={"BTC": 30000, "ETH": 2000, "WLD": 5.0})
    mock.get_team_matches = AsyncMock(return_value=[{"date": "2023-01-01", "team1": "Team A", "team2": "Team B", "score": "1-0"}])
    return mock

@pytest.fixture
def gateway_mock(api_mock):
    """Мок для API шлюза."""
    mock = MagicMock(spec=ApiGateway)
    mock.client = api_mock
    mock.get_weather_for_cities = AsyncMock(return_value="Погода: Минск 20°C, ясно")
    mock.get_currency_rates = AsyncMock(return_value="Курсы валют: USD: 2.5, EUR: 3.0, RUB: 0.03")
    mock.get_crypto_prices = AsyncMock(return_value="Криптовалюты: BTC: $30000, ETH: $2000, WLD: $5.0")
    mock.get_team_info = AsyncMock(return_value="Матчи команды: 01.01.2023 Team A - Team B 1-0")
    return mock

@pytest.fixture
def ai_mock():
    """Мок для OpenAI клиента."""
    mock = AsyncMock(spec=OpenAIClient)
    mock.generate_response = AsyncMock(return_value=("Это ответ от ИИ", 10))
    mock.generate_ai_wish = AsyncMock(return_value="Хорошего дня!")
    return mock

@pytest.fixture
def monitoring_mock():
    """Мок для системы мониторинга."""
    mock = MagicMock(spec=BotMonitoring)
    mock.increment_message = MagicMock()
    mock.increment_command = MagicMock()
    mock.increment_api_request = MagicMock()
    mock.increment_ai_request = MagicMock()
    mock.get_stats = MagicMock(return_value={
        "total_messages": 100,
        "total_commands": 50,
        "total_api_requests": 30,
        "total_ai_requests": 20,
        "chats": {
            "123456789": {
                "messages": 10,
                "commands": 5,
                "api_requests": 3,
                "ai_requests": 2
            }
        }
    })
    return mock

@pytest.fixture
def message_service_mock(gateway_mock, ai_mock):
    """Мок для сервиса сообщений."""
    mock = MagicMock(spec=MessageService)
    mock.api = gateway_mock
    mock.ai = ai_mock
    mock.get_morning_message = AsyncMock(return_value="Доброе утро! Погода: 20°C, ясно. Курсы валют: USD: 2.5")
    mock.get_ai_wish_by_day = MagicMock(return_value="Хорошего дня!")
    return mock

@pytest.fixture
def action_manager_mock():
    """Мок для менеджера действий."""
    mock = MagicMock(spec=ActionManager)
    mock.process_message = AsyncMock(return_value="Ответ на сообщение")
    return mock

@pytest.fixture
def chat_history_mock():
    """Мок для истории чата."""
    mock = MagicMock(spec=ChatHistory)
    mock.get_chat_messages = AsyncMock(return_value=[])
    mock.add_message = AsyncMock(return_value=1)
    mock.get_chat_stats = AsyncMock(return_value={"total_messages": 0, "users": {}})
    mock.get_all_chats_stats = AsyncMock(return_value={})
    return mock

@pytest.fixture
def google_drive_mock():
    """Мок для Google Drive сервиса."""
    mock = MagicMock(spec=GoogleDriveService)
    mock.initialize = AsyncMock()
    mock.upload_file = AsyncMock(return_value="https://drive.google.com/file/d/123456")
    mock.is_enabled = MagicMock(return_value=True)
    return mock

@pytest.fixture
def chat_export_mock(database_mock, google_drive_mock):
    """Мок для сервиса экспорта чатов."""
    mock = MagicMock(spec=ChatExportService)
    mock.db = database_mock
    mock.drive = google_drive_mock
    mock.export_chats = AsyncMock(return_value="https://drive.google.com/file/d/123456")
    mock.generate_export_data = AsyncMock(return_value={
        "export_timestamp": "2023-01-01T00:00:00",
        "total_chats": 1,
        "chats": {
            "123456789": {
                "total_messages": 10,
                "users": {"user1": {"message_count": 5}},
                "messages": []
            }
        }
    })
    return mock 