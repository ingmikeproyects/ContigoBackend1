import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pydantic import model_validator
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/gad7", tags=["GAD-7"])
logger = logging.getLogger(__name__)


class Gad7ResultCreate(BaseModel):
    q1: int = Field(ge=0, le=3)
    q2: int = Field(ge=0, le=3)
    q3: int = Field(ge=0, le=3)
    q4: int = Field(ge=0, le=3)
    q5: int = Field(ge=0, le=3)
    q6: int = Field(ge=0, le=3)
    q7: int = Field(ge=0, le=3)
    total_score: int = Field(ge=0, le=21)
    severity_level: str = Field(min_length=1, max_length=50)
    applied_at: datetime

    @model_validator(mode="after")
    def score_matches_answers(self):
        expected = sum((self.q1, self.q2, self.q3, self.q4, self.q5, self.q6, self.q7))
        if self.total_score != expected:
            raise ValueError("total_score must equal the sum of q1..q7")
        return self

@router.post("")
def save_gad7_result(
    result: Gad7ResultCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        data = {**result.model_dump(mode="json"), "user_id": current_user["id"]}
        response = supabase.table("gad7_results").insert(data).execute()
        if not response.data:
            logger.error("GAD-7 insert returned no data for user_id=%s", current_user["id"])
            raise HTTPException(status_code=500, detail="Error saving GAD-7 result")
        return response.data[0]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to save GAD-7 for user_id=%s", current_user["id"])
        raise HTTPException(status_code=500, detail="Error saving GAD-7 result")

@router.get("/me")
def get_my_gad7_results(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    response = supabase.table("gad7_results")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .order("applied_at", desc=True)\
        .execute()
    return response.data

@router.get("/patient/{patient_id}")
def get_patient_gad7(
    patient_id: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    if current_user["rol"] not in ["especialista", "administrador"]:
        raise HTTPException(status_code=403, detail="Sin permisos")
    
    response = supabase.table("gad7_results")\
        .select("*")\
        .eq("user_id", patient_id)\
        .order("applied_at", desc=True)\
        .execute()
    return response.data
