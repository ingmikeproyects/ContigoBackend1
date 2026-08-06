from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from supabase import Client
from database import get_supabase
from schemas.user import UserCreate, Token, UserResponse, LoginRequest, ResetPasswordRequest, ForgotPasswordRequest
from utils.password_handler import get_password_hash, verify_password
from utils.jwt_handler import create_access_token, create_refresh_token, decode_token
import uuid
from datetime import datetime, timedelta
import smtplib
import os
import random
import string
import logging
import re
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

def send_reset_email(email: str, name: str, token: str):
    try:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")

        if not smtp_user or not smtp_password:
            logger.error("CRITICAL: SMTP credentials missing in environment variables.")
            return

        msg = MIMEText(
            f"Hola {name},\n\n"
            f"Tu código de verificación para Contigo es: {token}\n\n"
            f"Este código es válido por 1 hora.\n"
            f"Si no solicitaste este código, puedes ignorar este mensaje con seguridad."
        )
        msg['From'] = f"Contigo App <{smtp_user}>"
        msg['To'] = email
        msg["Subject"] = "Código de Verificación - Contigo"

        logger.info(f"Connecting to SMTP server {smtp_host}:{smtp_port}...")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.starttls()

        logger.info(f"Logging in as {smtp_user}...")
        server.login(smtp_user, smtp_password)

        logger.info(f"Sending message to {email}...")
        server.send_message(msg)
        server.quit()
        logger.info(f"SUCCESS: Email sent successfully to {email}")
    except smtplib.SMTPAuthenticationError:
        logger.error(f"AUTH ERROR: Google rejected credentials for {smtp_user}. "
                     "Make sure you are using an 'App Password' and not your regular password.")
    except Exception as e:
        logger.error(f"SMTP FAILURE to {email}: {type(e).__name__} - {str(e)}", exc_info=True)

@router.post("/register", response_model=Token)
def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    user_agent: str = Depends(lambda: ""), # Placeholder for device info if needed
    x_device_info: str = Depends(lambda: ""), # Custom header for device validation
    supabase: Client = Depends(get_supabase)
):
    # 1. Validaciones de Seguridad y Negocio

    # Validar Edad (Mínimo 18 años)
    if user_data.edad and user_data.edad < 18:
        raise HTTPException(status_code=400, detail="Debes ser mayor de 18 años para registrarte.")

    # Validar Formato de Cédula (si es especialista)
    if user_data.rol == "especialista":
        if not user_data.cedula_profesional:
            raise HTTPException(status_code=400, detail="La cédula profesional es obligatoria para especialistas.")
        # Regex flexible: 7 a 10 dígitos (México usa 8 estándar, pero variaciones existen)
        if not re.match(r"^\d{7,10}$", user_data.cedula_profesional):
            raise HTTPException(status_code=400, detail="Formato de cédula profesional inválido (7-10 dígitos).")

    # Validar Correo Electrónico (Regex estándar más estricto)
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(email_regex, user_data.correo):
        raise HTTPException(status_code=400, detail="Formato de correo electrónico inválido.")

    # Validar Compatibilidad de Dispositivo (Vía Header X-Device-Info)
    # Ejemplo esperado: "Android:30;Sensors:accel,hr"
    if x_device_info:
        try:
            parts = x_device_info.split(";")
            api_version = int(parts[0].split(":")[1])
            sensors = parts[1].split(":")[1].split(",")

            if api_version < 29:
                raise HTTPException(status_code=400, detail="Dispositivo no compatible. Se requiere Android 10 (API 29) o superior.")

            required_sensors = ["accel", "hr"]
            for s in required_sensors:
                if s not in sensors:
                    raise HTTPException(status_code=400, detail=f"El dispositivo carece del sensor requerido: {s}")
        except (IndexError, ValueError):
            # Si el header está mal formado pero existe, podemos loguear o ser estrictos
            pass

    # Check if email exists
    existing = supabase.table("users").select("id").eq("correo", user_data.correo).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_data.password)
    uid = str(uuid.uuid4())
    
    # Mapeo exacto de campos según supabase_schema.sql
    new_user = {
        "uid": uid,
        "nombre": user_data.nombre,
        "correo": user_data.correo,
        "password_hash": hashed_password,
        "rol": user_data.rol,
        "edad": user_data.edad,
        "sexo": user_data.sexo,
        "contacto_emergencia_nombre": user_data.emergencia_nombre,
        "contacto_emergencia_telefono": user_data.emergencia_tel,
        "lista_medicamentos": user_data.medicamentos,
        "alergias": user_data.alergias,
        "plan_tratamiento": user_data.plan_tratamiento,
        "cedula_profesional": user_data.cedula_profesional,
        "licenciatura_psicologia": user_data.institucion_licenciatura,
        "cedula_especialidad": user_data.cedula_especialidad,
        "especialidad": user_data.tipo_especialidad,
        "anios_experiencia": user_data.anios_experiencia,
        "institucion_actual": user_data.institucion,
        "enfoque_terapeutico": user_data.enfoque_terapeutico,
        "telefono": user_data.telefono,
        "historial_medico": user_data.historial_medico,
        "activo": True
    }
    
    try:
        response = supabase.table("users").insert(new_user).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Error creating user in Database")

        db_user = response.data[0]

        # Enviar correo de bienvenida/verificación (opcional pero solicitado)
        token = ''.join(random.choices(string.digits, k=6))
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        supabase.table("password_reset_tokens").insert({
            "user_id": db_user["id"],
            "token": token,
            "expires_at": expires_at
        }).execute()

        background_tasks.add_task(send_reset_email, user_data.correo, db_user['nombre'], token)

    except Exception as e:
        print(f"DEBUG: Supabase error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    access_token = create_access_token(data={"user_id": db_user["id"], "uid": uid, "rol": db_user["rol"]})
    refresh_token = create_refresh_token(data={"user_id": db_user["id"]})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": db_user
    }

@router.post("/login", response_model=Token)
def login(user_data: LoginRequest, supabase: Client = Depends(get_supabase)):
    try:
        # Búsqueda insensible a mayúsculas/minúsculas para el correo
        response = supabase.table("users").select("*").ilike("correo", user_data.correo).execute()
        if not response.data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

        user = response.data[0]

        # Depuración de hash malformado
        db_hash = user.get("password_hash", "")
        if not verify_password(user_data.password, db_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

        if not user.get("activo", True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada. Contacta al administrador.")

        access_token = create_access_token(data={"user_id": user["id"], "uid": user["uid"], "rol": user["rol"]})
        refresh_token = create_refresh_token(data={"user_id": user["id"]})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.post("/refresh", response_model=dict)
def refresh(refresh_token: str, supabase: Client = Depends(get_supabase)):
    payload = decode_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    user_id = payload.get("user_id")
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    user = response.data[0]
    new_access_token = create_access_token(data={"user_id": user["id"], "uid": user["uid"], "rol": user["rol"]})
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase)
):
    response = supabase.table("users").select("*").eq("correo", request.correo).execute()
    if not response.data:
        # Por seguridad, no revelamos si el correo existe
        return {"message": "Si el correo existe recibirás instrucciones"}
    
    user = response.data[0]
    token = ''.join(random.choices(string.digits, k=6))
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    
    supabase.table("password_reset_tokens").insert({
        "user_id": user["id"],
        "token": token,
        "expires_at": expires_at
    }).execute()
    
    background_tasks.add_task(send_reset_email, request.correo, user['nombre'], token)
            
    return {"message": "Si el correo existe recibirás instrucciones"}

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, supabase: Client = Depends(get_supabase)):
    now = datetime.utcnow().isoformat()
    response = supabase.table("password_reset_tokens")\
        .select("*")\
        .eq("token", request.token)\
        .eq("used", False)\
        .gt("expires_at", now)\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=400, detail="Código inválido o expirado")
    
    reset_token = response.data[0]
    hashed_password = get_password_hash(request.new_password)
    
    supabase.table("users").update({"password_hash": hashed_password}).eq("id", reset_token["user_id"]).execute()
    supabase.table("password_reset_tokens").update({"used": True}).eq("id", reset_token["id"]).execute()
    
    return {"message": "Tu contraseña fue actualizada correctamente"}
