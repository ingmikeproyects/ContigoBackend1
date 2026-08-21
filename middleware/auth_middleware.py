from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from utils.jwt_handler import decode_token
from supabase import Client
from database import get_supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), supabase: Client = Depends(get_supabase)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    # Query Supabase instead of SQLAlchemy
    response = supabase.table("users").select("*").eq("id", user_id).execute()

    if not response.data:
        raise credentials_exception

    user = response.data[0]
    if not user.get("activo", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada temporalmente")

    return user
