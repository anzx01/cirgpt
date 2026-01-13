from pydantic import BaseModel, Field


class DesignRequest(BaseModel):
    """Schema for submitting a circuit design request"""
    description: str = Field(
        ...,
        description="Natural language description of the circuit to design",
        example="Design a 555 timer LED blinker circuit with 1 Hz frequency"
    )
