from fastapi import HTTPException

from schemas.eda import NetlistRequest, NetlistResponse, SchematicRequest, SchematicResponse
from app.config import settings
from app.utils.http_client import get_http_client


class EDAService:
    def __init__(self):
        self.http_client = get_http_client()
        self.base_url = settings.EDA_SERVICE_URL.rstrip("/")

    async def generate_netlist(self, netlist_request: NetlistRequest) -> NetlistResponse:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/eda/netlist",
                json=netlist_request.model_dump(),
            )
            response.raise_for_status()
            return NetlistResponse(**response.json())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")

    async def generate_schematic(self, schematic_request: SchematicRequest) -> SchematicResponse:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/eda/schematic",
                json=schematic_request.model_dump(),
            )
            response.raise_for_status()
            return SchematicResponse(**response.json())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")

    async def run_simulation(self, simulation_request: dict) -> dict:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/eda/simulation",
                json=simulation_request,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")

    async def generate_pcb(self, pcb_request: dict) -> dict:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/eda/pcb",
                json=pcb_request,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")

    async def generate_bom(self, bom_request: dict) -> dict:
        try:
            response = await self.http_client.post(
                f"{self.base_url}/eda/bom",
                json=bom_request,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA service error: {str(e)}")
