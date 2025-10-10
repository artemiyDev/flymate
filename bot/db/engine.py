# db/engine.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from bot.settings import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

def init_db_engine() -> None:
    global _engine, _sessionmaker
    _engine = create_async_engine(settings.DB_DSN, pool_pre_ping=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)

def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        init_db_engine()
    return _sessionmaker



async def close_db_engine() -> None:
    """
    Аккуратно закрыть engine (например при shutdown).
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None