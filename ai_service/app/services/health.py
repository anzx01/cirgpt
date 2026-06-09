from datetime import datetime
from typing import Dict, Any
from app.config import settings
from app.utils.redis import get_redis_client

class HealthService:
    async def check(self) -> Dict[str, Any]:
        """基本健康检查"""
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "ai-service"
        }
    
    async def detailed_check(self) -> Dict[str, Any]:
        """详细健康检查"""
        checks = {
            "ai-service": {"status": "ok"},
            "redis": await self._check_redis(),
            "model": await self._check_model()
        }
        
        statuses = {check["status"] for check in checks.values()}
        overall_status = "error" if "error" in statuses else ("degraded" if "warning" in statuses or "degraded" in statuses else "ok")
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "service": "ai-service"
        }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """检查Redis连接"""
        try:
            redis_client = get_redis_client()
            await redis_client.ping()
            return {"status": "ok", "message": "Redis connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"Redis connection failed: {str(e)}"}
    
    async def _check_model(self) -> Dict[str, Any]:
        """检查模型是否可用"""
        try:
            # 简单检查模型文件是否存在
            import os
            if os.path.exists(settings.MODEL_PATH):
                return {"status": "ok", "message": "Model files found", "model_path": settings.MODEL_PATH}
            else:
                return {"status": "degraded", "message": "Model files not found; rule-based CircuitIR parser is active", "model_path": settings.MODEL_PATH}
        except Exception as e:
            return {"status": "error", "message": f"Model check failed: {str(e)}"}
