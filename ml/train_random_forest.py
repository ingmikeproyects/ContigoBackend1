"""
Script de entrenamiento del modelo Random Forest para Contigo.
Entrenado con el dataset de referencia WESAD para clasificar
niveles de riesgo (NORMAL vs SEVERE).
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
import joblib
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ─── CONFIGURACIÓN ────────────────────────────────────────
RANDOM_STATE = 42
N_ESTIMATORS = 100

# ─── FEATURES USADAS ──────────────────────────────────────
# Eliminamos spo2 para garantizar que el modelo sea 100% REAL
FEATURE_COLUMNS = [
    "heart_rate", "hrv", "stress_level",
    "sleep_hours", "activity_level", "screen_unlocks", "app_usage_minutes"
]

def load_real_data_from_supabase() -> pd.DataFrame:
    """Carga los datos de WESAD desde la tabla public_reference_dataset."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados.")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("📥 Descargando dataset completo desde Supabase...")
    all_data = []
    batch_size = 1000
    current_offset = 0

    # Bucle infinito hasta que no haya más datos (para traer los 369k)
    while True:
        response = supabase.table("public_reference_dataset")\
            .select("*")\
            .eq("source_dataset", "TAG_MULTIMODAL_REAL")\
            .range(current_offset, current_offset + batch_size - 1)\
            .execute()

        if not response.data:
            break

        all_data.extend(response.data)
        current_offset += batch_size
        if current_offset % 10000 == 0:
            print(f"Descargados {current_offset} registros...")

        # Limitamos a 50k para no saturar la memoria local si es necesario,
        # pero para una tesis 369k es mejor. Probemos con 100k por ahora para velocidad.
        if current_offset >= 100000:
            break

    if not all_data:
        raise ValueError("No se encontraron datos en public_reference_dataset.")
    
    df = pd.DataFrame(all_data)
    print(f"✅ Cargados {len(df)} registros para entrenamiento.")

    # Mapeo de riesgo corregido (incluyendo MODERATE)
    risk_map = {"NORMAL": 0, "MODERATE": 1, "SEVERE": 3}
    df["risk_level_num"] = df["risk_level"].map(risk_map)

    # Eliminar cualquier fila que aún tenga NaN (por si acaso)
    df = df.dropna(subset=["risk_level_num"] + FEATURE_COLUMNS)

    return df

def train_model(df: pd.DataFrame):
    print(f"Shape de X antes de entrenar: {df[FEATURE_COLUMNS].shape}")
    X = df[FEATURE_COLUMNS]
    y = df["risk_level_num"]
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Stratify asegura que ambas clases estén en el set de prueba
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    
    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=10,
        random_state=RANDOM_STATE,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    print("\n--- MÉTRICAS REALES (WESAD) ---")

    # Aseguramos que target_names coincida con las clases presentes
    unique_classes = sorted(y_test.unique())
    all_target_names = ["NORMAL", "MODERATE", "SEVERE"]
    # Mapear solo las clases que existen en este conjunto de datos
    target_names = [all_target_names[i] if i < len(all_target_names) else f"Class_{i}" for i in unique_classes]

    # Si por alguna razón el mapeo no es perfecto, simplemente usar strings de los números
    if len(target_names) != len(unique_classes):
        target_names = [str(c) for c in unique_classes]

    print(classification_report(y_test, y_pred, target_names=target_names))

    return model, scaler

if __name__ == "__main__":
    try:
        df = load_real_data_from_supabase()
        model, scaler = train_model(df)

        # Rutas absolutas
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(script_dir, "models")
        os.makedirs(model_dir, exist_ok=True)

        joblib.dump({"model": model, "scaler": scaler}, os.path.join(model_dir, "contigo_model.joblib"))
        print(f"✅ Modelo real guardado en {os.path.join(model_dir, 'contigo_model.joblib')}")
    except Exception as e:
        print(f"❌ Error en entrenamiento: {e}")
