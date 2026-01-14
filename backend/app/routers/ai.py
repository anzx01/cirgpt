from fastapi import APIRouter, Depends, HTTPException
from schemas.ai import AIRequest, AIResponse
from app.services.ai import AIService
from app.utils.http_client import get_http_client

router = APIRouter()

@router.post("/parse", response_model=AIResponse, summary="解析电路描述")
async def parse_circuit(ai_request: AIRequest, ai_service: AIService = Depends()):
    return await ai_service.parse_circuit(ai_request)

@router.get("/models", summary="获取可用模型列表")
async def get_models(ai_service: AIService = Depends()):
    return await ai_service.get_models()