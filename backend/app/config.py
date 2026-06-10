from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
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
    SECRET_KEY: str = Field(
        ...,  # 必填字段，没有默认值
        description="JWT signing key. MUST be set in .env file or environment variable.",
    )
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

    @field_validator("SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, value):
        """验证SECRET_KEY的安全性"""
        if not value:
            raise ValueError(
                "SECRET_KEY is required! Set it in .env file or environment variable."
            )

        # 检查是否使用了不安全的默认值
        insecure_defaults = [
            "change-me",
            "change-me-in-local-env",
            "secret",
            "secretkey",
            "mysecret",
            "password",
            "admin"
        ]

        if value.lower() in insecure_defaults or len(value) < 32:
            raise ValueError(
                f"SECRET_KEY is insecure! It must be:\n"
                f"  - At least 32 characters long\n"
                f"  - Not a common/default value\n"
                f"  - Randomly generated\n"
                f"Current length: {len(value)} characters\n"
                f"Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        return value

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes"}:
                return True
        return value

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        """Convert CORS_ORIGINS string to list"""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return self.CORS_ORIGINS

# 实例化配置
try:
    settings = Settings()
except Exception as e:
    print(f"\n{'='*70}")
    print(f"配置错误: {str(e)}")
    print(f"{'='*70}\n")
    raise
