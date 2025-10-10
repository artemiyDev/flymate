# db/redis_client.py
from redis.asyncio import Redis
from bot.settings import settings

_redis_client: Redis | None = None


def init_redis_client() -> None:
    """Initialize global async Redis client."""
    global _redis_client
    _redis_client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        db=0,
        decode_responses=True,
    )


def get_redis_client() -> Redis:
    """Get global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        init_redis_client()
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis client gracefully (on shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


async def get_airport_name(iata_code: str) -> str:
    """
    Get airport name from Redis cache by IATA code.
    Falls back to IATA code if not found.
    """
    if not iata_code:
        return "Unknown"

    rds = get_redis_client()

    # Try airport first
    airport_name = await rds.get(f"airport:{iata_code.upper()}")
    if airport_name:
        return airport_name

    # Try city as fallback
    city_name = await rds.get(f"city:{iata_code.upper()}")
    if city_name:
        return city_name

    # Fallback to IATA code
    return iata_code.upper()


async def get_airline_name(iata_code: str) -> str:
    """
    Get airline name from Redis cache by IATA code.
    Falls back to IATA code if not found.
    """
    if not iata_code:
        return "Unknown airline"

    rds = get_redis_client()

    airline_name = await rds.get(f"airline:{iata_code.upper()}")
    if airline_name:
        return airline_name

    # Fallback to IATA code
    return iata_code.upper()
