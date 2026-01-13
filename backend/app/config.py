from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        env_ignore_empty=True,
        extra="ignore"  # 忽略 .env 文件中的额外字段
    )

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

    # CORS配置 - 使用默认值，避免解析问题
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        """Convert CORS_ORIGINS string to list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

settings = Settings()