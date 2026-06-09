from pydantic import BaseModel, Field
from typing import Optional


class DesignStatus(BaseModel):
    """Schema for design generation status"""
    id: int
    status: str  # pending, processing, completed, failed
    current_step: Optional[str] = None  # e.g., "Parsing natural language", "Generating schematic"
    progress: Optional[int] = None  # 0-100
    job_id: Optional[str] = None
    error_message: Optional[str] = None
    completed_steps: list[str] = Field(default_factory=list)
