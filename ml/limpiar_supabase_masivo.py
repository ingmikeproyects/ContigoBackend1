import os
from dotenv import load_dotenv
from supabase import create_client
import time

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def limpiar():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("🧹 Limpiando tabla por lotes para evitar timeouts...")

    # Eliminamos por lotes de 10k basándonos en el source_dataset
    while True:
        try:
            # Seleccionar los primeros 10k ids para borrar
            res = supabase.table("public_reference_dataset") \
                .select("id") \
                .eq("source_dataset", "TAG_MULTIMODAL_REAL") \
                .limit(10000) \
                .execute()

            ids = [r['id'] for r in res.data]
            if not ids:
                break

            supabase.table("public_reference_dataset") \
                .delete() \
                .in_("id", ids) \
                .execute()

            print(f"🗑️ Borrados {len(ids)} registros...")
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ Error: {e}")
            break

    print("✅ Limpieza completada.")

if __name__ == "__main__":
    limpiar()
