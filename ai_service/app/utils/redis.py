"""
Redis client for AI Service
"""
import logging

logger = logging.getLogger(__name__)


async def get_redis_client():
    """Get Redis client (optional for MVP)"""
    logger.info("Redis not configured for AI service")
    return None
