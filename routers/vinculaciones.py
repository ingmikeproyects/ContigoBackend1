from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/vinculaciones", tags=["vinculaciones"])

class ConsentUpdate(BaseModel):
    consentimiento_dado: bool

@router.get("/my-patients")
def get_my_patients(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Solo especialistas")
    links = supabase.table("vinculaciones").select("paciente_id").eq("especialista_id", current_user["id"]).eq("activa", True).execute()
    patient_ids = [link["paciente_id"] for link in (links.data or [])]
    if not patient_ids:
        return []
    return supabase.table("users").select("id,uid,nombre").in_("id", patient_ids).execute().data or []

@router.get("/my-specialist")
def get_my_specialist(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "paciente":
        raise HTTPException(status_code=403, detail="Solo pacientes")
    link = supabase.table("vinculaciones").select("especialista_id").eq("paciente_id", current_user["id"]).eq("activa", True).limit(1).execute()
    if not link.data:
        return None
    users = supabase.table("users").select("id,uid,nombre,especialidad").eq("id", link.data[0]["especialista_id"]).limit(1).execute()
    return (users.data or [None])[0]

@router.post("/invitation")
def create_invitation(data: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Only specialists can invite")
    
    # Get patient by email
    patient = supabase.table("users").select("*").eq("correo", data["email"]).execute()
    if not patient.data:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    invitation = {
        "especialista_id": current_user["id"],
        "paciente_id": patient.data[0]["id"],
        "activa": True
    }
    response = supabase.table("vinculaciones").insert(invitation).execute()
    return response.data[0]

@router.get("/me")
def get_my_linkages(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Only specialists can view their linkages")

    response = supabase.table("vinculaciones")\
        .select("*, paciente:paciente_id(nombre, uid)")\
        .eq("especialista_id", current_user["id"])\
        .eq("activa", True)\
        .execute()
    return response.data

@router.get("/all")
def get_all_vinculaciones(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Only admins can view all linkages")

    # Simplificar el join usando nombres de columna como alias de relación
    # Consultas separadas: no dependen del nombre de una relación PostgREST.
    response = supabase.table("vinculaciones").select("*").execute()
    linkages = response.data or []
    user_ids = {
        item.get("paciente_id") for item in linkages
    } | {
        item.get("especialista_id") for item in linkages
    }
    user_ids.discard(None)
    users_by_id = {}
    if user_ids:
        users = supabase.table("users").select("id,nombre,uid").in_("id", list(user_ids)).execute()
        users_by_id = {
            user["id"]: {"nombre": user.get("nombre", ""), "uid": user.get("uid")}
            for user in (users.data or [])
        }
    for linkage in linkages:
        linkage["paciente"] = users_by_id.get(linkage.get("paciente_id"))
        linkage["especialista"] = users_by_id.get(linkage.get("especialista_id"))
    return linkages

@router.post("/vincular")
def admin_vincular(data: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Only admins can link")

    try:
        # Get IDs from UIDs
        p = supabase.table("users").select("id").eq("uid", data["paciente_uid"]).execute()
        e = supabase.table("users").select("id").eq("uid", data["especialista_uid"]).execute()

        if not p.data or not e.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        vinculation = {
            "especialista_id": e.data[0]["id"],
            "paciente_id": p.data[0]["id"],
            "activa": True,
            "consentimiento_dado": True  # Consentimiento automático por política de registro
        }
        response = supabase.table("vinculaciones").insert(vinculation).execute()
        return response.data[0]
    except Exception as ex:
        import logging
        logging.getLogger(__name__).error(f"Error creating vinculation: {ex}")
        raise HTTPException(status_code=500, detail=f"Error en base de datos: {str(ex)}")

@router.delete("/{vinculacionId}")
def delete_vinculacion(vinculacionId: int, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] == "administrador":
        supabase.table("vinculaciones").delete().eq("id", vinculacionId).execute()
    elif current_user["rol"] == "especialista":
        # Asegurar que solo borra sus propios vínculos
        supabase.table("vinculaciones")\
            .delete()\
            .eq("id", vinculacionId)\
            .eq("especialista_id", current_user["id"])\
            .execute()
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return {"message": "Vinculación eliminada"}

@router.put("/{vinculacionId}")
def update_vinculacion(vinculacionId: int, data: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    allowed = {key: value for key, value in data.items() if key in {"activa", "consentimiento_dado"}}
    if not allowed:
        raise HTTPException(status_code=400, detail="No hay campos válidos para actualizar")
    response = supabase.table("vinculaciones").update(allowed).eq("id", vinculacionId).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Vinculación no encontrada")
    return response.data[0]

@router.put("/consent")
def update_consent(data: ConsentUpdate, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    response = supabase.table("vinculaciones")\
        .update({"consentimiento_dado": data.consentimiento_dado})\
        .eq("paciente_id", current_user["id"])\
        .execute()
    return response.data
