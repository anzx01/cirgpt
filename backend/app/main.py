from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ai, eda, health, circuit
from app.config import settings

app = FastAPI(title="Circuit Design API Gateway", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(eda.router, prefix="/api/eda", tags=["eda"])
app.include_router(circuit.router, prefix="/api/circuit", tags=["circuit"])

@app.get("/")
async def root():
    return {"message": "Circuit Design API Gateway", "version": "1.0.0"}