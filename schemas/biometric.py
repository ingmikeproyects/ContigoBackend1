from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class BiometricBase(BaseModel):
    heart_rate: Optional[float] = None
    hrv: Optional[float] = None
    spo2: Optional[float] = None
    stress_level: Optional[float] = None
    sleep_hours: Optional[float] = None
    activity_level: Optional[float] = None
    steps: Optional[int] = None
    screen_unlocks: Optional[int] = None
    app_usage_minutes: Optional[int] = None

class BiometricCreate(BiometricBase):
    pass

class BiometricResponse(BiometricBase):
    id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True
