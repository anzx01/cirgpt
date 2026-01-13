from fastapi import FastAPI
from app.routers import health, eda
from app.config import settings

app = FastAPI(title="EDA Circuit Design Tools", version="1.0.0")

# 注册路由
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(eda.router, tags=["eda"])

@app.get("/")
async def root():
    return {"message": "EDA Circuit Design Tools", "version": "1.0.0"}