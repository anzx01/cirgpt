from datetime import datetime
from typing import Dict, Any
import os
from app.config import settings
from app.utils.redis import get_redis_client

class HealthService:
    async def check(self) -> Dict[str, Any]:
        """基本健康检查"""
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "eda-service"
        }
    
    async def detailed_check(self) -> Dict[str, Any]:
        """详细健康检查"""
        checks = {
            "eda-service": {"status": "ok"},
            "redis": await self._check_redis(),
            "storage": await self._check_storage()
        }
        
        overall_status = "ok" if all(check["status"] == "ok" for check in checks.values()) else "error"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "service": "eda-service"
        }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """检查Redis连接"""
        try:
            redis_client = get_redis_client()
            await redis_client.ping()
            return {"status": "ok", "message": "Redis connection successful"}
        except Exception as e:
            return {"status": "error", "message": f"Redis connection failed: {str(e)}"}
    
    async def _check_storage(self) -> Dict[str, Any]:
        """检查存储目录是否可用"""
        try:
            if os.path.exists(settings.STORAGE_PATH):
                if os.access(settings.STORAGE_PATH, os.W_OK):
                    return {"status": "ok", "message": "Storage directory is writable", "storage_path": settings.STORAGE_PATH}
                else:
                    return {"status": "error", "message": "Storage directory is not writable", "storage_path": settings.STORAGE_PATH}
            else:
                return {"status": "warning", "message": "Storage directory not found, will be created when needed", "storage_path": settings.STORAGE_PATH}
        except Exception as e:
            return {"status": "error", "message": f"Storage check failed: {str(e)}"}