from app.config import settings


redis_client = None


def _load_redis_module():
    try:
        import redis.asyncio as redis
        return redis
    except ImportError as exc:
        raise RuntimeError("redis package is not installed; install backend requirements to enable Redis") from exc


async def init_redis():
    """Initialize Redis connection."""
    global redis_client
    redis = _load_redis_module()
    redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def close_redis():
    """Close Redis connection."""
    if redis_client:
        await redis_client.close()


def get_redis_client():
    """Get Redis client, lazily creating one for health checks and workers."""
    global redis_client
    if redis_client is None:
        redis = _load_redis_module()
        redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    return redis_client
