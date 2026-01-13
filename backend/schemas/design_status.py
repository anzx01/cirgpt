from pydantic import BaseModel
from typing import Optional


class DesignStatus(BaseModel):
    """Schema for design generation status"""
    id: int
    status: str  # pending, processing, completed, failed
    current_step: Optional[str] = None  # e.g., "Parsing natural language", "Generating schematic"
    progress: Optional[int] = None  # 0-100
    error_message: Optional[str] = None
    completed_steps: list[str] = []
