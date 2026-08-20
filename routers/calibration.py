from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
from schemas.calibration import ExtendedCalibrationCreate

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.post("/extended", status_code=status.HTTP_204_NO_CONTENT)
def save_extended_calibration(
    data: ExtendedCalibrationCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user.get("rol") != "paciente":
        raise HTTPException(status_code=403, detail="Solo los pacientes pueden guardar esta calibración")

    item = data.model_dump(mode="json", exclude={"applied_at"})
    item.update({
        "user_id": current_user["id"],
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    supabase.table("calibration_extended").upsert(item, on_conflict="user_id").execute()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/status")
def get_calibration_status(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    status = supabase.table("calibration_data").select("*").eq("user_id", current_user["id"]).execute()

    # Buscar la fecha del primer biométrico como inicio de referencia
    first_reading = supabase.table("biometric_readings")\
        .select("timestamp")\
        .eq("user_id", current_user["id"])\
        .order("timestamp", desc=False)\
        .limit(1).execute()

    start_date = first_reading.data[0]["timestamp"] if first_reading.data else current_user.get("fecha_registro")

    if not status.data:
        return {"calibration_completed": False, "baseline": None, "start_date": start_date}

    return {**status.data[0], "start_date": start_date}

@router.post("/data")
def save_calibration_data(data: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    # Upsert logic for Supabase
    item = {**data, "user_id": current_user["id"]}
    response = supabase.table("calibration_data").upsert(item).execute()
    return response.data[0]

@router.put("/complete")
def complete_calibration(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    response = supabase.table("calibration_data")\
        .update({"calibration_completed": True})\
        .eq("user_id", current_user["id"])\
        .execute()
    return response.data[0]
