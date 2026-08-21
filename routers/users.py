from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
from schemas.user import DeleteAccountRequest
from utils.password_handler import verify_password
from datetime import datetime

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    return current_user

@router.put("/me")
def update_me(updates: dict, current_user: dict = Depends(get_current_user), supabase: Client = Depends(get_supabase)):
    # Mapeo de campos del frontend/schema a columnas de base de datos
    mapping = {
        "emergencia_nombre": "contacto_emergencia_nombre",
        "emergencia_tel": "contacto_emergencia_telefono",
        "medicamentos": "lista_medicamentos",
        "institucion_licenciatura": "licenciatura_psicologia",
        "tipo_especialidad": "especialidad",
        "institucion": "institucion_actual",
        "genero": "sexo"
    }

    db_updates = {}
    for k, v in updates.items():
        if v is not None:
            db_key = mapping.get(k, k)
            db_updates[db_key] = v

    if not db_updates:
        return current_user

    response = supabase.table("users").update(db_updates).eq("id", current_user["id"]).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail="Error updating user")
    return response.data[0]

@router.get("/all")
def get_all_users(
    rol: str = None,
    search: str = None,
    page: int = 1,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Only admins can view all users")

    query = supabase.table("users").select("*")

    if rol:
        query = query.eq("rol", rol)
    if search:
        query = query.ilike("nombre", f"%{search}%")

    # Paginación
    start = (page - 1) * limit
    end = start + limit - 1

    response = query.range(start, end).order("fecha_registro", desc=True).execute()
    return response.data

@router.put("/{uid}/admin-update")
def admin_update_user(
    uid: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403,
                           detail="Solo administradores")

    # Mapeo exhaustivo de campos para admin
    mapping = {
        "emergencia_nombre": "contacto_emergencia_nombre",
        "emergencia_tel": "contacto_emergencia_telefono",
        "medicamentos": "lista_medicamentos",
        "institucion_licenciatura": "licenciatura_psicologia",
        "tipo_especialidad": "especialidad",
        "institucion": "institucion_actual",
        "genero": "genero"
    }

    db_updates = {}
    for k, v in body.items():
        if v is not None:
            db_key = mapping.get(k, k)
            db_updates[db_key] = v

    # Log para auditoría y debugging
    import logging
    logging.getLogger(__name__).info(f"Admin {current_user['id']} updating user {uid}: {db_updates}")

    response = supabase.table("users").update(db_updates).eq("uid", uid).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o sin cambios realizados")

    return {"message": "Usuario actualizado exitosamente", "user": response.data[0]}

@router.get("/patients")
def get_my_patients(
    activa: bool = True,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    if current_user["rol"] != "especialista":
        raise HTTPException(status_code=403, detail="Only specialists can view patients")
    
    # Get vinculaciones
    vinculaciones = supabase.table("vinculaciones")\
        .select("paciente_id")\
        .eq("especialista_id", current_user["id"])\
        .eq("activa", activa).execute()
    
    patient_ids = [v["paciente_id"] for v in vinculaciones.data]
    if not patient_ids:
        return []
    
    patients = supabase.table("users").select("*").in_("id", patient_ids).execute()
    return patients.data

@router.get("/by-uid/{uid}")
def get_user_by_uid(
    uid: str,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    # Permiso: especialista puede ver sus pacientes, o admin, o el propio usuario
    response = supabase.table("users").select("*").eq("uid", uid).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")

    user = response.data[0]

    if current_user["rol"] == "administrador":
        return user

    if current_user["uid"] == uid:
        return user

    if current_user["rol"] == "especialista":
        # Verificar vinculación activa
        vinculacion = supabase.table("vinculaciones")\
            .select("*")\
            .eq("paciente_id", user["id"])\
            .eq("especialista_id", current_user["id"])\
            .eq("activa", True)\
            .execute()

        if vinculacion.data:
            return user
        else:
            # Log para debugging si la vinculación no aparece
            import logging
            logging.getLogger(__name__).warning(
                f"Specialist {current_user['id']} denied access to patient {user['id']}. "
                f"No active vinculacion found."
            )

    raise HTTPException(status_code=403, detail="Not authorized to view this user")


@router.post("/me/deactivate")
def deactivate_my_account(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Baja temporal: conserva los datos y suspende el acceso de vinculaciones."""
    linkage_column = (
        "paciente_id" if current_user["rol"] == "paciente" else "especialista_id"
    )
    try:
        supabase.table("vinculaciones")\
            .update({"activa": False, "suspendida_por_cuenta": True})\
            .eq(linkage_column, current_user["id"])\
            .eq("activa", True)\
            .eq("estado", "aceptada")\
            .execute()

        response = supabase.table("users").update({
            "activo": False,
            "deactivated_at": datetime.utcnow().isoformat(),
        }).eq("id", current_user["id"]).execute()
    except Exception:
        # El error más frecuente aquí es no haber ejecutado la migración que
        # agrega las columnas de baja temporal. No se desactiva parcialmente.
        raise HTTPException(
            status_code=503,
            detail="La base de datos aún no tiene instalada la migración de gestión de cuenta.",
        )

    if not response.data:
        raise HTTPException(status_code=500, detail="No fue posible desactivar la cuenta")

    return {
        "message": (
            "Cuenta desactivada temporalmente. Conservamos tus datos y podrás "
            "reactivarla verificando tu correo."
        )
    }


@router.post("/me/delete-permanently")
def delete_my_account_permanently(
    request: DeleteAccountRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Eliminación irreversible del usuario autenticado y sus datos en cascada."""
    if not verify_password(request.password, current_user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="La contraseña es incorrecta")

    try:
        response = (
            supabase.table("users")
            .delete()
            .eq("id", current_user["id"])
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No fue posible eliminar todos los datos de la cuenta",
        )

    if not response.data:
        raise HTTPException(status_code=500, detail="No fue posible eliminar la cuenta")

    return {"message": "Cuenta y datos asociados eliminados definitivamente"}

@router.delete("/{userId}")
def delete_user(
    userId: int,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    if current_user["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    # La autenticación de Contigo es propia; Supabase Auth no es una segunda
    # fuente de verdad (decisión arquitectónica Opción B).
    user_to_delete = supabase.table("users").select("id").eq("id", userId).execute()
    if not user_to_delete.data:
        raise HTTPException(status_code=404, detail="User not found")

    # Borrar de la tabla users dispara las cascadas definidas en DB.
    supabase.table("users").delete().eq("id", userId).execute()

    return {"message": "Usuario eliminado correctamente"}
