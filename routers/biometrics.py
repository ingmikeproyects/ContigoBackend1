from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
from typing import List

router = APIRouter(prefix="/biometrics", tags=["biometrics"])

@router.post("")
def save_biometric(reading: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    data = {**reading, "user_id": current_user["id"]}
    response = supabase.table("biometric_readings").insert(data).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Error saving reading")
    return response.data[0]

@router.get("/me")
def get_my_biometrics(days: int = 7, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    response = supabase.table("biometric_readings")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .order("timestamp", desc=True)\
        .limit(days * 24)\
        .execute()
    return response.data

@router.get("/patient/{patient_id}/stats")
def get_patient_stats(
    patient_id: int,
    range_days: int = 7,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Devuelve series temporales agregadas de un paciente para el dashboard del especialista.
    """
    if current_user["rol"] not in ["especialista", "administrador"]:
        raise HTTPException(status_code=403, detail="No autorizado")

    if current_user["rol"] == "especialista":
        # Verificar vinculación
        vinculacion = supabase.table("vinculaciones")\
            .select("id, consentimiento_dado")\
            .eq("paciente_id", patient_id)\
            .eq("especialista_id", current_user["id"])\
            .eq("activa", True)\
            .execute()
        if not vinculacion.data:
            raise HTTPException(status_code=403, detail="Paciente no vinculado")
        if not vinculacion.data[0].get("consentimiento_dado", False):
            raise HTTPException(
                status_code=403,
                detail="El paciente pausó el acceso a su historial"
            )

    # Obtener lecturas
    from datetime import datetime, timedelta
    start_date = (datetime.utcnow() - timedelta(days=range_days)).isoformat()

    response = supabase.table("biometric_readings")\
        .select("heart_rate, hrv, stress_level, activity_level, steps, timestamp")\
        .eq("user_id", patient_id)\
        .gte("timestamp", start_date)\
        .order("timestamp", desc=False)\
        .execute()

    # Formatear para el dashboard (gráficos de series temporales)
    data = response.data
    return {
        "labels": [d["timestamp"] for d in data],
        "heart_rate": [d["heart_rate"] for d in data],
        "hrv": [d["hrv"] for d in data],
        "stress": [d["stress_level"] for d in data],
        "activity": [d["activity_level"] for d in data],
        "steps": [d.get("steps") for d in data]
    }
