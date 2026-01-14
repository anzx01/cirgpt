"""
Database utilities for EDA Tools
"""
import logging

logger = logging.getLogger(__name__)


async def get_db():
    """Get database session (optional for EDA tools)"""
    logger.info("Database not configured for EDA tools")
    yield None
