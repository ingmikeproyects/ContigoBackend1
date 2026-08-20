import os
import jwt
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path


# Forzar la carga del archivo .env buscando en el directorio raíz del backend
backend_dir = Path(__file__).resolve().parent.parent
dotenv_path = backend_dir / ".env"
for candidate in (dotenv_path, backend_dir.parent / ".env"):
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=False)

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    # Fallback por si la carga falla, pero avisando
    print(f"⚠️  ERROR: No se pudo cargar SECRET_KEY desde {dotenv_path}")
    SECRET_KEY = "clave-secreta-temporal-de-emergencia"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
