from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime
from models.user import UserRole

class UserBase(BaseModel):
    nombre: str
    correo: EmailStr
    rol: UserRole

class LoginRequest(BaseModel):
    correo: EmailStr
    password: str

class UserCreate(UserBase):
    password: str
    edad: Optional[int] = None
    sexo: Optional[str] = None
    emergencia_nombre: Optional[str] = None
    emergencia_tel: Optional[str] = None
    medicamentos: Optional[str] = None
    alergias: Optional[str] = None
    plan_tratamiento: Optional[str] = None
    cedula_profesional: Optional[str] = None
    institucion_licenciatura: Optional[str] = None
    cedula_especialidad: Optional[str] = None
    tipo_especialidad: Optional[str] = None
    anios_experiencia: Optional[int] = None
    institucion: Optional[str] = None
    enfoque_terapeutico: Optional[str] = None
    telefono: Optional[str] = None
    historial_medico: Optional[str] = None

class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    edad: Optional[int] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    genero: Optional[str] = None
    tiempo_diagnostico: Optional[str] = None
    medicacion_activa: Optional[bool] = None
    frecuencia_consultas: Optional[str] = None
    emergencia_nombre: Optional[str] = None
    emergencia_tel: Optional[str] = None
    medicamentos: Optional[str] = None
    alergias: Optional[str] = None
    plan_tratamiento: Optional[str] = None
    dosis_medicamentos: Optional[str] = None
    cedula_profesional: Optional[str] = None
    institucion_licenciatura: Optional[str] = None
    cedula_especialidad: Optional[str] = None
    tipo_especialidad: Optional[str] = None
    anios_experiencia: Optional[int] = None
    institucion: Optional[str] = None
    enfoque_terapeutico: Optional[str] = None
    telefono: Optional[str] = None
    historial_medico: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    correo: EmailStr

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserResponse(UserBase):
    id: int
    uid: str
    activo: bool
    fecha_registro: datetime
    ultimo_acceso: Optional[datetime] = None

    # Campos paciente
    edad: Optional[int] = None
    sexo: Optional[str] = None
    genero: Optional[str] = None
    contacto_emergencia_nombre: Optional[str] = None
    contacto_emergencia_telefono: Optional[str] = None
    lista_medicamentos: Optional[str] = None
    alergias: Optional[str] = None
    plan_tratamiento: Optional[str] = None
    historial_medico: Optional[str] = None

    # Campos especialista
    cedula_profesional: Optional[str] = None
    especialidad: Optional[str] = None
    institucion: Optional[str] = None
    anios_experiencia: Optional[int] = None
    licenciatura_psicologia: Optional[str] = None
    cedula_especialidad: Optional[str] = None
    institucion_actual: Optional[str] = None
    enfoque_terapeutico: Optional[str] = None
    telefono: Optional[str] = None

    subscription_plan: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: int
    uid: str
    rol: str
