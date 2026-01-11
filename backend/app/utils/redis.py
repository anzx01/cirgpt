import redis.asyncio as redis
from app.config import settings

redis_client = None

async def init_redis():
    """初始化Redis连接"""
    global redis_client
    redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

async def close_redis():
    """关闭Redis连接"""
    if redis_client:
        await redis_client.close()

def get_redis_client():
    """获取Redis客户端"""
    if not redis_client:
        raise Exception("Redis client not initialized")
    return redis_client