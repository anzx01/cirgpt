from pydantic import BaseSettings
from typing import List

class Settings(BaseSettings):
    # 基本配置
    PROJECT_NAME: str = "Circuit Design API Gateway"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 数据库配置
    DB_URL: str = "sqlite:///./app.db"
    
    # Redis配置
    REDIS_URL: str = "redis://redis:6379"
    
    # 服务配置
    AI_SERVICE_URL: str = "http://ai-service:8001"
    EDA_SERVICE_URL: str = "http://eda-service:8002"
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()