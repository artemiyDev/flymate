"""
Pytest конфигурация и фикстуры для тестов Flymate бота.
"""
import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Создаёт event loop для всей сессии тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Создаёт тестовый движок БД."""
    database_url = (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'test_user')}:"
        f"{os.getenv('POSTGRES_PASSWORD', 'test_password')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'flymate_test')}"
    )

    engine = create_async_engine(database_url, echo=False)

    # Создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Очистка после тестов
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Создаёт тестовую сессию БД."""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Создаёт тестовый клиент Redis."""
    redis = Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )

    yield redis

    # Очистка после теста
    await redis.flushdb()
    await redis.aclose()


@pytest.fixture
def mock_aviasales_response():
    """Мок ответа от Aviasales API."""
    return {
        "success": True,
        "data": [
            {
                "origin": "IST",
                "destination": "AMS",
                "origin_airport": "SAW",
                "destination_airport": "AMS",
                "price": 150,
                "airline": "PC",
                "flight_number": "1234",
                "departure_at": "2025-11-15T10:30:00+03:00",
                "return_at": "2025-11-20T18:45:00+01:00",
                "transfers": 0,
                "link": "https://www.aviasales.com/search/IST1511AMS2011PC1234",
            }
        ],
    }
