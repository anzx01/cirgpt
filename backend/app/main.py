from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ai, eda, health, circuit
from app.config import settings
from app.websocket.socket_manager import socket_manager

api_app = FastAPI(title="Circuit Design API Gateway", version="1.0.0")

# 配置CORS
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
api_app.include_router(health.router, prefix="/api/health", tags=["health"])
api_app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
api_app.include_router(eda.router, prefix="/api/eda", tags=["eda"])
api_app.include_router(circuit.router, prefix="/api/circuit", tags=["circuit"])

# Mount Socket.io server when the optional dependency is installed.
try:
    from socketio import ASGIApp
except ImportError:
    ASGIApp = None

app = api_app
if ASGIApp is not None and socket_manager.get_app() is not None:
    app = ASGIApp(
        socket_manager.get_app(),
        other_asgi_app=api_app,
        socketio_path="socket.io",
    )

@api_app.get("/")
async def root():
    return {
        "message": "Circuit Design API Gateway",
        "version": "1.0.0",
        "websocket": "Socket.io available at /socket.io"
    }
