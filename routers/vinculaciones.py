from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/vinculaciones", tags=["vinculaciones"])

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
    response = supabase.table("vinculaciones")\
        .select("*, paciente:paciente_id(nombre), especialista:especialista_id(nombre)")\
        .execute()
    return response.data

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

@router.put("/consent")
def update_consent(data: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    response = supabase.table("vinculaciones")\
        .update({"consentimiento_dado": data["enabled"]})\
        .eq("paciente_id", current_user["id"])\
        .execute()
    return response.data
