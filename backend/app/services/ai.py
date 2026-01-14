from fastapi import HTTPException
from schemas.ai import AIRequest, AIResponse
from app.utils.http_client import get_http_client
from app.config import settings

class AIService:
    def __init__(self):
        self.http_client = get_http_client()
    
    async def parse_circuit(self, ai_request: AIRequest) -> AIResponse:
        """解析电路描述"""
        try:
            response = await self.http_client.post(
                f"{settings.AI_SERVICE_URL}/api/ai/parse",
                json=ai_request.dict()
            )
            response.raise_for_status()
            return AIResponse(**response.json())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    
    async def get_models(self) -> dict:
        """获取可用模型列表"""
        try:
            response = await self.http_client.get(f"{settings.AI_SERVICE_URL}/api/ai/models")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")