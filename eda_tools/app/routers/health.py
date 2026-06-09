from fastapi import APIRouter, Depends

from app.services.health import HealthService


router = APIRouter()


@router.get("/", summary="Health check")
async def health_check(health_service: HealthService = Depends()):
    return await health_service.check()


@router.get("/detailed", summary="Detailed health check")
async def detailed_health_check(health_service: HealthService = Depends()):
    return await health_service.detailed_check()
