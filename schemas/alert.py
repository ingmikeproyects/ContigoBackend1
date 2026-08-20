from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from models.alert import RiskLevel

class AlertBase(BaseModel):
    risk_level: RiskLevel

class AlertCreate(AlertBase):
    trigger_summary: Optional[str] = Field(default=None, max_length=600)
    heart_rate: Optional[float] = None
    hrv: Optional[float] = None
    spo2: Optional[float] = None
    stress_level: Optional[float] = None
    source: Optional[str] = Field(default=None, max_length=40)

class AlertResponse(AlertBase):
    id: int
    user_id: int
    generated_at: datetime
    acknowledged: bool
    trigger_summary: Optional[str] = None
    heart_rate: Optional[float] = None
    hrv: Optional[float] = None
    spo2: Optional[float] = None
    stress_level: Optional[float] = None
    source: Optional[str] = None

    class Config:
        from_attributes = True
