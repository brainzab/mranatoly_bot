import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.messages import MorningMessageSender, split_long_message, send_long_message

@pytest.mark.asyncio
async def test_split_long_message():
    # Проверяем разделение короткого сообщения
    short_message = "Короткое сообщение"
    parts = split_long_message(short_message, max_length=100)
    assert len(parts) == 1
    assert parts[0] == short_message
    
    # Проверяем разделение длинного сообщения
    long_message = "x" * 150
    parts = split_long_message(long_message, max_length=100)
    assert len(parts) == 2
    assert parts[0] == "x" * 100
    assert parts[1] == "x" * 50

@pytest.mark.asyncio
async def test_send_long_message():
    # Подготовка
    bot = AsyncMock()
    bot.send_message.return_value = MagicMock()
    
    # Отправка короткого сообщения
    await send_long_message(bot, chat_id=123, text="Короткое сообщение")
    assert bot.send_message.call_count == 1
    
    # Сброс счетчика вызовов
    bot.send_message.reset_mock()
    
    # Отправка длинного сообщения
    await send_long_message(bot, chat_id=123, text="x" * 5000, max_length=2000)
    assert bot.send_message.call_count == 3

@pytest.mark.asyncio
async def test_morning_message_sender():
    # Подготовка
    bot = AsyncMock()
    sender = MorningMessageSender(bot)
    
    # Мокаем все вызовы к API
    with patch('app.services.api.ApiClient.get_weather', return_value="10°C, солнечно"), \
         patch('app.services.api.ApiClient.get_currency_rates', return_value=(2.5, 90.0)), \
         patch('app.services.api.ApiClient.get_crypto_prices', return_value=(50000, 0.5)):
        
        # Отправка утреннего сообщения
        await sender.send_morning_message()
        
        # Проверяем, что сообщение было отправлено
        bot.send_message.assert_called_once()
        
        # Проверяем, что в тексте сообщения есть ключевые фразы
        text = bot.send_message.call_args[1]['text']
        assert "доброе утро" in text.lower()
        assert "погоде" in text
        assert "usd/byn" in text.lower()
        assert "btc" in text.lower()

@pytest.mark.asyncio
async def test_get_ai_wish_by_day():
    # Подготовка
    bot = AsyncMock()
    sender = MorningMessageSender(bot)
    
    # Мокаем вызов к AI
    expected_wish = "🌟 Пусть этот день будет наполнен успехами и радостью!"
    with patch('app.services.ai.AiHandler.get_ai_response', return_value=expected_wish):
        # Получаем пожелание
        wish = await sender.get_ai_wish_by_day()
        
        # Проверяем, что пожелание соответствует ожидаемому
        assert wish == expected_wish
        
        # Проверяем, что AiHandler.get_ai_response был вызван
        from app.services.ai import AiHandler
        AiHandler.get_ai_response.assert_called_once() 