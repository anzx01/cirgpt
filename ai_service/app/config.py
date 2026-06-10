"""
AI Service Configuration
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    """Application settings"""

    PROJECT_NAME = "AI Circuit Design Service"
    VERSION = "1.0.0"
    DEBUG = True

    # AI Model settings
    MODEL_NAME = os.getenv("MODEL_NAME", "microsoft/circuit-bert")
    MODEL_PATH = os.getenv("MODEL_PATH", "./models")

    # Optional DeepSeek parser. The key must come from the environment; never
    # hard-code it in source.
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "30"))


settings = Settings()
