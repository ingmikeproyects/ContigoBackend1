import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
import time
import numpy as np

# 1. Cargar configuración desde el .env del backend
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def upload_in_batches():
    start_time = time.time()
    print(f"--- INICIANDO SUBIDA DE DATASET MAESTRO ---")

    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"❌ Error: Credenciales faltantes en .env")
        return

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Conexión con Supabase establecida.")
    except Exception as e:
        print(f"❌ Error al conectar con Supabase: {e}")
        return

    CSV_PATH = r'D:\Tesis\Datasets\tag_final_master.csv'
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: El archivo no existe en {CSV_PATH}")
        return

    print(f"📖 Cargando archivo CSV en memoria...")
    try:
        df = pd.read_csv(CSV_PATH)
        print(f"✅ CSV cargado. Total registros: {len(df)}")
    except Exception as e:
        print(f"❌ Error al leer el CSV: {e}")
        return

    # 2. LIMPIEZA Y MAPEO DE COLUMNAS
    # Eliminamos 'label' porque no existe en la tabla de Supabase
    if 'label' in df.columns:
        df = df.drop(columns=['label'])

    # Lista de columnas que la tabla public_reference_dataset SÍ acepta
    db_columns = [
        'heart_rate', 'hrv', 'spo2', 'stress_level',
        'sleep_hours', 'activity_level', 'screen_unlocks', 'app_usage_minutes', 'risk_level'
    ]

    # Aseguramos que existan todas, llenando con None si faltan
    for col in db_columns:
        if col not in df.columns:
            df[col] = None

    df['source_dataset'] = 'TAG_MULTIMODAL_REAL'

    # Filtramos para enviar SOLO lo que la base de datos permite
    final_df = df[db_columns + ['source_dataset']]

    # Convertimos NaN a None para SQL
    final_df = final_df.replace({np.nan: None})

    records = final_df.to_dict(orient="records")
    total_records = len(records)
    batch_size = 1000

    print(f"🚀 Subiendo {total_records} registros en lotes de {batch_size}...")

    for i in range(0, total_records, batch_size):
        batch = records[i : i + batch_size]
        try:
            supabase.table("public_reference_dataset").insert(batch).execute()
            if i % 5000 == 0 or i + batch_size >= total_records:
                elapsed = time.time() - start_time
                percent = (i / total_records) * 100
                print(f"⏳ PROGRESO: {i}/{total_records} ({percent:.1f}%) | {elapsed:.1f}s")
        except Exception as e:
            print(f"❌ ERROR LOTE {i}: {str(e)}")
            time.sleep(3)
            try:
                supabase.table("public_reference_dataset").insert(batch).execute()
                print(f"✅ Reintento exitoso.")
            except Exception as e2:
                print(f"❌ FALLO DEFINITIVO LOTE {i}. Abortando.")
                break

    end_time = time.time()
    print(f"\n✅ ¡PROCESO FINALIZADO!")
    print(f"Registros procesados: {total_records}")
    print(f"Tiempo total: {(end_time - start_time)/60:.2f} minutos.")

if __name__ == "__main__":
    upload_in_batches()
