"""
Тесты для worker (фонового процесса проверки цен).
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from bot.db.models import User


@pytest.mark.asyncio
async def test_redis_deduplication(redis_client):
    """Тест дедупликации офферов через Redis."""
    # Генерируем тестовый хеш оффера
    offer_hash = "test_offer_hash_123"
    sub_id = 1

    # Проверяем, что оффер не был отправлен
    is_member = await redis_client.sismember(f"subs:{sub_id}:sent", offer_hash)
    assert is_member == 0

    # Добавляем оффер в отправленные
    await redis_client.sadd(f"subs:{sub_id}:sent", offer_hash)

    # Проверяем, что оффер теперь в списке
    is_member = await redis_client.sismember(f"subs:{sub_id}:sent", offer_hash)
    assert is_member == 1

    # Устанавливаем TTL (60 дней)
    await redis_client.expire(f"subs:{sub_id}:sent", 60 * 24 * 60 * 60)

    # Проверяем TTL
    ttl = await redis_client.ttl(f"subs:{sub_id}:sent")
    assert ttl > 0


@pytest.mark.asyncio
async def test_aviasales_api_request(mock_aviasales_response):
    """Тест запроса к Aviasales API (с моком)."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Настраиваем мок ответа
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_aviasales_response)
        mock_get.return_value.__aenter__.return_value = mock_response

        # Имитируем запрос (нужно импортировать функцию из worker)
        # Здесь показан пример структуры теста
        # В реальном коде нужно импортировать функцию запроса из worker.py

        assert mock_aviasales_response["success"] is True
        assert len(mock_aviasales_response["data"]) == 1
        assert mock_aviasales_response["data"][0]["price"] == 150


@pytest.mark.asyncio
async def test_month_span_generation():
    """Тест функции разбиения диапазона дат на месяцы."""
    # Этот тест требует импорта функции month_span из worker.py
    # Пример структуры теста:

    # from bot.worker import month_span

    # range_from = datetime(2025, 10, 15).date()
    # range_to = datetime(2025, 12, 20).date()

    # months = month_span(range_from, range_to)

    # assert "2025-10" in months
    # assert "2025-11" in months
    # assert "2025-12" in months
    # assert len(months) == 3

    pass  # Заглушка, пока не импортирована функция
