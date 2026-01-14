"""
AI Service Configuration
"""
class Settings:
    """Application settings"""
    PROJECT_NAME = "AI Circuit Design Service"
    VERSION = "1.0.0"
    DEBUG = True

    # AI Model settings
    MODEL_NAME = "microsoft/circuit-bert"
    MODEL_PATH = "./models"


settings = Settings()
