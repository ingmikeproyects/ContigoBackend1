from datetime import datetime, timedelta, timezone
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from database import get_supabase
from middleware.auth_middleware import get_current_user


router = APIRouter(prefix="/vinculaciones", tags=["vinculaciones"])
logger = logging.getLogger(__name__)


class ConsentUpdate(BaseModel):
    consentimiento_dado: bool


class InvitationCreate(BaseModel):
    email: str


class InvitationAccept(BaseModel):
    code: str


@router.get("/my-patients")
def get_my_patients(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    links = (
        supabase.table("vinculaciones")
        .select("paciente_id")
        .eq("especialista_id", current_user["id"])
        .eq("activa", True)
        .execute()
    )
    patient_ids = [link["paciente_id"] for link in (links.data or [])]
    if not patient_ids:
        return []
    return (
        supabase.table("users")
        .select("id,uid,nombre")
        .in_("id", patient_ids)
        .execute()
        .data
        or []
    )


@router.get("/my-specialist")
def get_my_specialist(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "paciente":
        raise HTTPException(status_code=403, detail="Solo pacientes")
    link = (
        supabase.table("vinculaciones")
        .select("id,especialista_id,consentimiento_dado")
        .eq("paciente_id", current_user["id"])
        .eq("activa", True)
        .limit(1)
        .execute()
    )
    if not link.data:
        return None
    specialist_result = (
        supabase.table("users")
        .select("id,uid,nombre,especialidad")
        .eq("id", link.data[0]["especialista_id"])
        .limit(1)
        .execute()
    )
    specialist = (specialist_result.data or [None])[0]
    if specialist:
        specialist["vinculacion_id"] = link.data[0]["id"]
        specialist["consentimiento_dado"] = link.data[0].get(
            "consentimiento_dado", False
        )
    return specialist


@router.post("/invitation")
def create_invitation(
    data: InvitationCreate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")

    patient_result = (
        supabase.table("users")
        .select("id,uid,nombre,correo,rol")
        .ilike("correo", data.email.strip())
        .limit(1)
        .execute()
    )
    if not patient_result.data:
        raise HTTPException(
            status_code=404, detail="No se encontró un paciente con ese correo"
        )
    patient = patient_result.data[0]
    if patient.get("rol") != "paciente":
        raise HTTPException(
            status_code=400, detail="El correo no pertenece a un paciente"
        )

    active = (
        supabase.table("vinculaciones")
        .select("id")
        .eq("paciente_id", patient["id"])
        .eq("activa", True)
        .execute()
    )
    if active.data:
        raise HTTPException(
            status_code=409, detail="El paciente ya tiene un especialista activo"
        )

    # Reemplaza una invitación anterior del mismo par para que solo exista un
    # código válido y fácil de explicar al paciente.
    (
        supabase.table("vinculaciones")
        .delete()
        .eq("especialista_id", current_user["id"])
        .eq("paciente_id", patient["id"])
        .eq("estado", "pendiente")
        .execute()
    )

    code = None
    for _ in range(5):  # Reintento en caso de colisión
        potential_code = f"{secrets.randbelow(1_000_000):06d}"
        exists = supabase.table("vinculaciones").select("id").eq("codigo", potential_code).eq("activa", True).execute()
        if not exists.data:
            code = potential_code
            break

    if not code:
        raise HTTPException(status_code=500, detail="No se pudo generar un código único. Intenta más tarde.")

    now = datetime.now(timezone.utc)
    invitation = {
        "especialista_id": current_user["id"],
        "paciente_id": patient["id"],
        "activa": False,
        "consentimiento_dado": True,
        "codigo": code,
        "estado": "pendiente",
        "expires_at": (now + timedelta(hours=24)).isoformat(),
    }
    response = supabase.table("vinculaciones").insert(invitation).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="No se pudo crear la invitación")
    created = response.data[0]
    return {
        "id": created["id"],
        "codigo": code,
        "especialista_uid": current_user["uid"],
        "especialista_nombre": current_user["nombre"],
        "paciente_email": patient["correo"],
        "fecha_creacion": created.get("fecha_vinculacion", now.isoformat()),
        "estado": "pendiente",
    }


@router.get("/invitations")
def get_invitations(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    links = (
        supabase.table("vinculaciones")
        .select("*")
        .eq("especialista_id", current_user["id"])
        .order("fecha_vinculacion", desc=True)
        .execute()
    )
    invitation_rows = [row for row in (links.data or []) if row.get("codigo")]
    patient_ids = {row["paciente_id"] for row in invitation_rows}
    patients = {}
    if patient_ids:
        rows = (
            supabase.table("users")
            .select("id,correo")
            .in_("id", list(patient_ids))
            .execute()
            .data
            or []
        )
        patients = {row["id"]: row["correo"] for row in rows}
    return [
        {
            "id": row["id"],
            "codigo": row.get("codigo", ""),
            "especialista_uid": current_user["uid"],
            "especialista_nombre": current_user["nombre"],
            "paciente_email": patients.get(row["paciente_id"], ""),
            "fecha_creacion": row.get("fecha_vinculacion"),
            "estado": row.get("estado")
            or ("aceptada" if row.get("activa") else "pendiente"),
        }
        for row in invitation_rows
    ]


@router.post("/accept-invitation")
def accept_invitation(
    data: InvitationAccept,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "paciente":
        raise HTTPException(status_code=403, detail="Solo pacientes")
    code = data.code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="El código debe tener 6 dígitos")
    result = (
        supabase.table("vinculaciones")
        .select("*")
        .eq("paciente_id", current_user["id"])
        .eq("codigo", code)
        .eq("estado", "pendiente")
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Código inválido o ya utilizado")
    invitation = result.data[0]
    expires_at = invitation.get("expires_at")
    if expires_at and datetime.fromisoformat(
        expires_at.replace("Z", "+00:00")
    ) < datetime.now(timezone.utc):
        (
            supabase.table("vinculaciones")
            .update({"estado": "expirada"})
            .eq("id", invitation["id"])
            .execute()
        )
        raise HTTPException(
            status_code=410, detail="El código expiró; solicita uno nuevo"
        )
    (
        supabase.table("vinculaciones")
        .update(
            {
                "activa": True,
                "consentimiento_dado": True,
                "estado": "aceptada",
            }
        )
        .eq("id", invitation["id"])
        .execute()
    )
    return {"message": "Vinculación creada correctamente"}


@router.get("/me")
def get_my_linkages(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    response = (
        supabase.table("vinculaciones")
        .select("*, paciente:paciente_id(nombre, uid)")
        .eq("especialista_id", current_user["id"])
        .eq("activa", True)
        .execute()
    )
    return response.data or []


@router.put("/me/consent")
def update_consent(
    data: ConsentUpdate,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "paciente":
        raise HTTPException(
            status_code=403, detail="Solo el paciente puede cambiar este acceso"
        )
    response = (
        supabase.table("vinculaciones")
        .update({"consentimiento_dado": data.consentimiento_dado})
        .eq("paciente_id", current_user["id"])
        .eq("activa", True)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="No hay una vinculación activa")
    return {"message": "Acceso al historial actualizado"}


@router.get("/all")
def get_all_vinculaciones(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "administrador":
        raise HTTPException(
            status_code=403, detail="Solo administradores pueden ver vinculaciones"
        )
    response = supabase.table("vinculaciones").select("*").execute()
    linkages = response.data or []
    user_ids = {
        value
        for item in linkages
        for value in (item.get("paciente_id"), item.get("especialista_id"))
        if value is not None
    }
    users_by_id = {}
    if user_ids:
        rows = (
            supabase.table("users")
            .select("id,nombre,uid")
            .in_("id", list(user_ids))
            .execute()
            .data
            or []
        )
        users_by_id = {row["id"]: row for row in rows}
    for linkage in linkages:
        linkage["paciente"] = users_by_id.get(linkage.get("paciente_id"))
        linkage["especialista"] = users_by_id.get(
            linkage.get("especialista_id")
        )
    return linkages


@router.post("/vincular")
def admin_vincular(
    data: dict,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    patient = (
        supabase.table("users")
        .select("id")
        .eq("uid", data["paciente_uid"])
        .execute()
    )
    specialist = (
        supabase.table("users")
        .select("id")
        .eq("uid", data["especialista_uid"])
        .execute()
    )
    if not patient.data or not specialist.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    response = (
        supabase.table("vinculaciones")
        .insert(
            {
                "especialista_id": specialist.data[0]["id"],
                "paciente_id": patient.data[0]["id"],
                "activa": True,
                "consentimiento_dado": True,
                "estado": "aceptada",
            }
        )
        .execute()
    )
    return response.data[0]


@router.delete("/{vinculacion_id}")
def delete_vinculacion(
    vinculacion_id: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    # "Dar de baja" conserva trazabilidad y permite mostrar la pestaña Baja.
    query = (
        supabase.table("vinculaciones")
        .update({"activa": False, "estado": "finalizada"})
        .eq("id", vinculacion_id)
    )
    if current_user["rol"] == "especialista":
        query = query.eq("especialista_id", current_user["id"])
    elif current_user["rol"] == "paciente":
        query = query.eq("paciente_id", current_user["id"])
    elif current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="No autorizado")
    response = query.execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Vinculación no encontrada")
    return {"message": "Vinculación finalizada"}


@router.put("/{vinculacion_id}")
def update_vinculacion(
    vinculacion_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    allowed = {
        key: value
        for key, value in data.items()
        if key in {"activa", "consentimiento_dado"}
    }
    if not allowed:
        raise HTTPException(status_code=400, detail="No hay campos válidos")
    response = (
        supabase.table("vinculaciones")
        .update(allowed)
        .eq("id", vinculacion_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Vinculación no encontrada")
    return response.data[0]
