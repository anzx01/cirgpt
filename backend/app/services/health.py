from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException
from sqlalchemy import text
from app.config import settings
from app.utils.redis import get_redis_client
from app.utils.database import get_db

class HealthService:
    async def check(self) -> Dict[str, Any]:
        """基本健康检查"""
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "api-gateway"
        }
    
    async def detailed_check(self) -> Dict[str, Any]:
        """详细健康检查，检查所有依赖服务"""
        checks = {
            "api-gateway": {"status": "ok"},
            "redis": await self._check_redis(),
            "database": await self._check_database(),
            "ai-service": await self._check_ai_service(),
            "eda-service": await self._check_eda_service()
        }
        
        statuses = {check["status"] for check in checks.values()}
        overall_status = "error" if "error" in statuses else ("degraded" if "warning" in statuses or "degraded" in statuses else "ok")
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "service": "api-gateway"
        }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """检查Redis连接"""
        try:
            redis_client = get_redis_client()
            await redis_client.ping()
            return {"status": "ok", "message": "Redis connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"Redis connection failed: {str(e)}"}
    
    async def _check_database(self) -> Dict[str, Any]:
        """检查数据库连接"""
        try:
            db = next(get_db())
            db.execute(text("SELECT 1"))
            return {"status": "ok", "message": "Database connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"Database connection failed: {str(e)}"}
    
    async def _check_ai_service(self) -> Dict[str, Any]:
        """检查AI服务连接"""
        try:
            import httpx
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(f"{settings.AI_SERVICE_URL}/api/health/")
                response.raise_for_status()
                return {"status": "ok", "message": "AI service connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"AI service connection failed: {str(e)}"}
    
    async def _check_eda_service(self) -> Dict[str, Any]:
        """检查EDA服务连接"""
        try:
            import httpx
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(f"{settings.EDA_SERVICE_URL}/api/health/")
                response.raise_for_status()
                return {"status": "ok", "message": "EDA service connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"EDA service connection failed: {str(e)}"}
