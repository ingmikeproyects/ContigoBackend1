import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# En local admite ejecutar uvicorn desde la carpeta del backend o desde la
# raíz del proyecto. En producción nunca sobrescribe las variables del host.
backend_dir = Path(__file__).resolve().parent
for candidate in (backend_dir / ".env", backend_dir.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Faltan llaves de Supabase")
    supabase = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Cliente de Supabase conectado")
    except Exception as e:
        print(f"❌ Error al conectar: {e}")
        supabase = None

def get_supabase() -> Client:
    return supabase
