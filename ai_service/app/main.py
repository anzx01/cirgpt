from fastapi import FastAPI
from app.routers import health, parse
from app.config import settings

app = FastAPI(title="AI Circuit Design Service", version="1.0.0")

# 注册路由
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(parse.router, prefix="/api/ai", tags=["ai"])

@app.get("/")
async def root():
    return {"message": "AI Circuit Design Service", "version": "1.0.0"}