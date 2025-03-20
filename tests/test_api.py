import pytest
import asyncio
from app.services.api import ApiClient

@pytest.mark.asyncio
async def test_get_weather():
    result = await ApiClient.get_weather("Minsk,BY")
    assert isinstance(result, str)
    assert "°C" in result or "Нет данных" in result

@pytest.mark.asyncio
async def test_get_currency_rates():
    usd_byn, usd_rub = await ApiClient.get_currency_rates()
    assert isinstance(usd_byn, (float, int))
    assert isinstance(usd_rub, (float, int))

@pytest.mark.asyncio
async def test_get_crypto_prices():
    btc_price, wld_price = await ApiClient.get_crypto_prices()
    assert isinstance(btc_price, (float, int))
    assert isinstance(wld_price, (float, int))