import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# En local solo carga el .env que pertenece al backend. Railway obtiene los
# secretos de sus Variables; no debemos recorrer carpetas padre ni intentar
# interpretar archivos .env de otros proyectos.
backend_dir = Path(__file__).resolve().parent
local_env = backend_dir / ".env"
if local_env.exists():
    load_dotenv(local_env, override=False, encoding="utf-8-sig")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Faltan llaves de Supabase")
    supabase = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Cliente de Supabase configurado")
    except Exception as e:
        print(f"Error al configurar Supabase: {e}")
        supabase = None

def get_supabase() -> Client:
    return supabase
