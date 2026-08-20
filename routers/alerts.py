from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
from schemas.alert import AlertCreate

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.post("")
def create_alert(data: AlertCreate, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    alert = {
        "user_id": current_user["id"],
        "risk_level": data.risk_level
    }
    response = supabase.table("alerts").insert(alert).execute()

    # Notificación en caso de riesgo SEVERE
    if data.risk_level == "SEVERE":
        try:
            # Buscar especialista vinculado
            vinculacion = supabase.table("vinculaciones")\
                .select("especialista_id")\
                .eq("paciente_id", current_user["id"])\
                .eq("activa", True)\
                .execute()

            if vinculacion.data:
                esp_id = vinculacion.data[0]["especialista_id"]
                especialista = supabase.table("users").select("correo", "nombre").eq("id", esp_id).execute()

                if especialista.data:
                    esp_email = especialista.data[0]["correo"]
                    esp_nombre = especialista.data[0]["nombre"]

                    from routers.auth import send_reset_email # Reusar lógica de envío si es genérica o crear una nueva
                    # En este caso, crearé una función de notificación específica en auth.py o similar
                    # Por ahora, usemos un log potente
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"CRITICAL ALERT: Patient {current_user['nombre']} (ID: {current_user['id']}) is in SEVERE risk. Notifying specialist {esp_nombre} ({esp_email})")

                    # Opcional: Enviar correo real si send_reset_email se adapta o se crea send_alert_email
        except Exception as e:
            print(f"Error notifying alert: {e}")

    return response.data[0]

@router.get("/me")
def get_my_alerts(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    response = supabase.table("alerts")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .order("generated_at", desc=True)\
        .execute()
    return response.data

@router.get("/patient/{patient_id}")
def get_patient_alerts(patient_id: int, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] not in ["especialista", "administrador"]:
        raise HTTPException(status_code=403, detail="Sin permisos")

    if current_user["rol"] == "especialista":
        # Verificar vinculación
        vinculacion = supabase.table("vinculaciones")\
            .select("*")\
            .eq("paciente_id", patient_id)\
            .eq("especialista_id", current_user["id"])\
            .eq("activa", True)\
            .execute()
        if not vinculacion.data:
            raise HTTPException(status_code=403, detail="Paciente no vinculado")

    response = supabase.table("alerts")\
        .select("*")\
        .eq("user_id", patient_id)\
        .order("generated_at", desc=True)\
        .execute()
    return response.data

@router.get("/specialist")
def get_specialist_alerts(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")

    # Obtener IDs de pacientes vinculados
    links = supabase.table("vinculaciones")\
        .select("paciente_id")\
        .eq("especialista_id", current_user["id"])\
        .eq("activa", True)\
        .execute()

    patient_ids = [link["paciente_id"] for link in (links.data or [])]
    if not patient_ids:
        return []

    response = supabase.table("alerts")\
        .select("*")\
        .in_("user_id", patient_ids)\
        .order("generated_at", desc=True)\
        .execute()

    return response.data
