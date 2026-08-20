from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from supabase import Client
from pathlib import Path
import re
import uuid

from database import get_supabase
from middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/tasks", tags=["tasks"])
TASK_ATTACHMENTS_BUCKET = "task-attachments"
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


class TaskCreate(BaseModel):
    paciente_id: int
    titulo: str = Field(min_length=1, max_length=160)
    descripcion: str | None = Field(default=None, max_length=1000)
    instrucciones_html: str | None = Field(default=None)
    enlace_recurso: str | None = Field(default=None)
    adjunto_path: str | None = Field(default=None, max_length=500)
    adjunto_nombre: str | None = Field(default=None, max_length=180)
    adjunto_tipo: str | None = Field(default=None, max_length=120)
    fecha_vencimiento: datetime | None = Field(default=None)
    minutos_estimados: int = Field(default=15, ge=1, le=180)


class TaskCompletion(BaseModel):
    completada: bool


def task_with_signed_attachment(task: dict, supabase: Client) -> dict:
    result = dict(task)
    result["adjunto_url"] = None
    storage_path = result.get("adjunto_path")
    if not storage_path:
        return result
    try:
        signed = (
            supabase.storage.from_(TASK_ATTACHMENTS_BUCKET)
            .create_signed_url(storage_path, 3600)
        )
        result["adjunto_url"] = signed.get("signedURL") or signed.get("signedUrl")
    except Exception:
        # La tarea sigue siendo utilizable aunque Supabase Storage esté temporalmente caído.
        result["adjunto_url"] = None
    return result


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


@router.post("/attachment")
async def upload_task_attachment(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")

    content = await file.read(MAX_ATTACHMENT_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="El archivo no puede superar 10 MB")

    original_name = (file.filename or "archivo_adjunto").strip()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(original_name).stem)[:100]
    safe_suffix = re.sub(r"[^A-Za-z0-9.]", "", Path(original_name).suffix)[:12]
    stored_name = f"{uuid.uuid4().hex}_{safe_stem}{safe_suffix}"
    storage_path = f"{current_user['id']}/{stored_name}"
    mime_type = file.content_type or "application/octet-stream"

    try:
        supabase.storage.from_(TASK_ATTACHMENTS_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": mime_type, "upsert": "false"},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No se pudo guardar el archivo") from exc

    return {"path": storage_path, "name": original_name[:180], "mime_type": mime_type}


@router.post("")
def create_task(
    data: TaskCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    require_link(data.paciente_id, current_user["id"], supabase)
    if data.adjunto_path and not data.adjunto_path.startswith(f"{current_user['id']}/"):
        raise HTTPException(status_code=403, detail="El archivo adjunto no pertenece al especialista")
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
                "adjunto_path": data.adjunto_path,
                "adjunto_nombre": data.adjunto_nombre,
                "adjunto_tipo": data.adjunto_tipo,
                "fecha_vencimiento": data.fecha_vencimiento.isoformat() if data.fecha_vencimiento else None,
                "minutos_estimados": data.minutos_estimados,
            }
        )
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=500, detail="No se pudo crear la tarea")
    created = response.data[0]
    try:
        supabase.table("task_notifications").insert(
            {
                "task_id": created["id"],
                "paciente_id": data.paciente_id,
                "titulo": "Nueva tarea de tu especialista",
                "mensaje": data.titulo.strip(),
            }
        ).execute()
    except Exception:
        # Compatibilidad durante el despliegue escalonado de la migración SQL.
        pass
    return task_with_signed_attachment(created, supabase)


@router.get("/me")
def get_my_tasks(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "paciente":
        raise HTTPException(status_code=403, detail="Solo pacientes")
    rows = (
        supabase.table("specialist_tasks")
        .select("*")
        .eq("paciente_id", current_user["id"])
        .order("completada")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return [task_with_signed_attachment(row, supabase) for row in rows]


@router.get("/patient/{patient_id}")
def get_patient_tasks(
    patient_id: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    require_link(patient_id, current_user["id"], supabase)
    rows = (
        supabase.table("specialist_tasks")
        .select("*")
        .eq("paciente_id", patient_id)
        .eq("especialista_id", current_user["id"])
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    return [task_with_signed_attachment(row, supabase) for row in rows]


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
    return task_with_signed_attachment(response.data[0], supabase)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    existing = (
        supabase.table("specialist_tasks")
        .select("id,adjunto_path")
        .eq("id", task_id)
        .eq("especialista_id", current_user["id"])
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    response = (
        supabase.table("specialist_tasks")
        .delete()
        .eq("id", task_id)
        .eq("especialista_id", current_user["id"])
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    attachment_path = existing.data[0].get("adjunto_path")
    if attachment_path:
        try:
            supabase.storage.from_(TASK_ATTACHMENTS_BUCKET).remove([attachment_path])
        except Exception:
            pass
    return {"message": "Tarea eliminada"}
