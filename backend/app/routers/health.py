from fastapi import APIRouter, Depends
from app.services.health import HealthService

router = APIRouter()

@router.get("/", summary="健康检查")
async def health_check(health_service: HealthService = Depends()):
    return await health_service.check()

@router.get("/detailed", summary="详细健康检查")
async def detailed_health_check(health_service: HealthService = Depends()):
    return await health_service.detailed_check()