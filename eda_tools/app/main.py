from fastapi import FastAPI
from app.routers import health, netlist, schematic, simulation, pcb
from app.config import settings

app = FastAPI(title="EDA Circuit Design Tools", version="1.0.0")

# 注册路由
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(netlist.router, prefix="/api/eda", tags=["eda"])
app.include_router(schematic.router, prefix="/api/eda", tags=["eda"])
app.include_router(simulation.router, prefix="/api/eda", tags=["eda"])
app.include_router(pcb.router, prefix="/api/eda", tags=["eda"])

@app.get("/")
async def root():
    return {"message": "EDA Circuit Design Tools", "version": "1.0.0"}