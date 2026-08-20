from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client

from database import get_supabase
from middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    paciente_id: int
    titulo: str = Field(min_length=1, max_length=160)
    descripcion: str | None = Field(default=None, max_length=1000)
    instrucciones_html: str | None = Field(default=None)
    enlace_recurso: str | None = Field(default=None)
    fecha_vencimiento: datetime | None = Field(default=None)
    minutos_estimados: int = Field(default=15, ge=1, le=180)


class TaskCompletion(BaseModel):
    completada: bool
    adjunto_url: str | None = None


def require_link(patient_id: int, specialist_id: int, supabase: Client):
    result = (
        supabase.table("vinculaciones")
        .select("id")
        .eq("paciente_id", patient_id)
        .eq("especialista_id", specialist_id)
        .eq("activa", True)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=403, detail="No existe una vinculación activa")


@router.post("")
def create_task(
    data: TaskCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    require_link(data.paciente_id, current_user["id"], supabase)
    response = (
        supabase.table("specialist_tasks")
        .insert(
            {
                "especialista_id": current_user["id"],
                "paciente_id": data.paciente_id,
                "titulo": data.titulo.strip(),
                "descripcion": data.descripcion.strip() if data.descripcion else None,
                "instrucciones_html": data.instrucciones_html,
                "enlace_recurso": data.enlace_recurso,
                "fecha_vencimiento": data.fecha_vencimiento.isoformat() if data.fecha_vencimiento else None,
                "minutos_estimados": data.minutos_estimados,
            }
        )
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=500, detail="No se pudo crear la tarea")
    return response.data[0]


@router.get("/me")
def get_my_tasks(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "paciente":
        raise HTTPException(status_code=403, detail="Solo pacientes")
    return (
        supabase.table("specialist_tasks")
        .select("*")
        .eq("paciente_id", current_user["id"])
        .order("completada")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


@router.get("/patient/{patient_id}")
def get_patient_tasks(
    patient_id: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    require_link(patient_id, current_user["id"], supabase)
    return (
        supabase.table("specialist_tasks")
        .select("*")
        .eq("paciente_id", patient_id)
        .eq("especialista_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )


@router.put("/{task_id}/complete")
def complete_task(
    task_id: int,
    data: TaskCompletion,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "paciente":
        raise HTTPException(status_code=403, detail="Solo pacientes")
    update_data = {
        "completada": data.completada,
        "completed_at": datetime.now(timezone.utc).isoformat()
        if data.completada
        else None,
        "adjunto_url": data.adjunto_url if data.completada else None,
        "estado_entrega": "entregada" if data.completada else "pendiente"
    }

    response = (
        supabase.table("specialist_tasks")
        .update(update_data)
        .eq("id", task_id)
        .eq("paciente_id", current_user["id"])
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return response.data[0]


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    response = (
        supabase.table("specialist_tasks")
        .delete()
        .eq("id", task_id)
        .eq("especialista_id", current_user["id"])
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return {"message": "Tarea eliminada"}
