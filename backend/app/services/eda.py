from fastapi import HTTPException
from schemas.eda import NetlistRequest, NetlistResponse, SchematicRequest, SchematicResponse
from app.utils.http_client import get_http_client
from app.config import settings

class EDAService:
    def __init__(self):
        self.http_client = get_http_client()
    
    async def generate_netlist(self, netlist_request: NetlistRequest) -> NetlistResponse:
        """生成网表"""
        try:
            response = await self.http_client.post(
                f"{settings.EDA_SERVICE_URL}/api/eda/netlist",
                json=netlist_request.dict()
            )
            response.raise_for_status()
            return NetlistResponse(**response.json())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")
    
    async def generate_schematic(self, schematic_request: SchematicRequest) -> SchematicResponse:
        """生成原理图"""
        try:
            response = await self.http_client.post(
                f"{settings.EDA_SERVICE_URL}/api/eda/schematic",
                json=schematic_request.dict()
            )
            response.raise_for_status()
            return SchematicResponse(**response.json())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")
    
    async def run_simulation(self, simulation_request: dict) -> dict:
        """运行仿真"""
        try:
            response = await self.http_client.post(
                f"{settings.EDA_SERVICE_URL}/api/eda/simulation",
                json=simulation_request
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")
    
    async def generate_pcb(self, pcb_request: dict) -> dict:
        """生成PCB布局"""
        try:
            response = await self.http_client.post(
                f"{settings.EDA_SERVICE_URL}/api/eda/pcb",
                json=pcb_request
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")