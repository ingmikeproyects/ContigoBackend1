from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/notas", tags=["notas"])

def check_specialist_vinculation(paciente_id: int, especialista_id: int, supabase: Client):
    """Verifica si el especialista tiene una vinculación activa con el paciente."""
    vinculacion = supabase.table("vinculaciones")\
        .select("*")\
        .eq("paciente_id", paciente_id)\
        .eq("especialista_id", especialista_id)\
        .eq("activa", True)\
        .execute()

    if not vinculacion.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para acceder a los datos de este paciente. No existe una vinculación activa."
        )

@router.post("")
def create_note(data: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    # 1. Verificar Rol
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo los especialistas pueden crear notas clínicas.")

    # 2. Verificar Propiedad/Vinculación (Anti-IDOR)
    paciente_id = data.get("paciente_id")
    if not paciente_id:
        raise HTTPException(status_code=400, detail="Falta paciente_id")

    check_specialist_vinculation(paciente_id, current_user["id"], supabase)

    note = {
        "especialista_id": current_user["id"],
        "paciente_id": paciente_id,
        "texto": data["texto"],
        "visible_para_paciente": data.get("visible_para_paciente", False)
    }
    response = supabase.table("notas_especialista").insert(note).execute()
    return response.data[0]

@router.get("/patient/{patient_id}")
def get_notes(patient_id: int, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    # 1. Verificar Rol
    if current_user["rol"] not in ["especialista", "paciente"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para ver notas.")

    if current_user["rol"] == "especialista":
        # Verificar Propiedad/Vinculación (Anti-IDOR)
        check_specialist_vinculation(patient_id, current_user["id"], supabase)

        response = supabase.table("notas_especialista")\
            .select("*")\
            .eq("paciente_id", patient_id)\
            .eq("especialista_id", current_user["id"])\
            .order("created_at", desc=True)\
            .execute()
    else: # Paciente
        if current_user["id"] != patient_id:
            raise HTTPException(status_code=403, detail="Solo puedes ver tus propias notas.")

        response = supabase.table("notas_especialista")\
            .select("*")\
            .eq("paciente_id", patient_id)\
            .eq("visible_para_paciente", True)\
            .order("created_at", desc=True)\
            .execute()

    return response.data
