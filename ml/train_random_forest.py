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
# Solo usamos las que WESAD provee para el entrenamiento del modelo base
FEATURE_COLUMNS = [
    "heart_rate", "hrv", "stress_level", "activity_level"
]

def load_real_data_from_supabase() -> pd.DataFrame:
    """Carga los datos de WESAD desde la tabla public_reference_dataset."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados.")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Supabase tiene un límite de 1000 por defecto. Obtenemos los 5000 registros usando range.
    all_data = []
    batch_size = 1000
    for i in range(0, 5001, batch_size):
        response = supabase.table("public_reference_dataset")\
            .select("*")\
            .range(i, i + batch_size - 1)\
            .execute()
        if response.data:
            all_data.extend(response.data)
        else:
            break

    if not all_data:
        raise ValueError("No se encontraron datos en public_reference_dataset. ¿Corriste load_wesad_dataset.py?")
    
    df = pd.DataFrame(all_data)
    print(f"Cargados {len(df)} registros de WESAD desde Supabase.")

    # Mapeo de riesgo a numérico para sklearn
    risk_map = {"NORMAL": 0, "SEVERE": 3}
    df["risk_level_num"] = df["risk_level"].map(risk_map)

    return df

def train_model(df: pd.DataFrame):
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
    target_names = ["NORMAL", "SEVERE"]
    if len(unique_classes) == 1:
        target_names = [target_names[0]] if unique_classes[0] == 0 else [target_names[1]]

    print(classification_report(y_test, y_pred, target_names=target_names))

    return model, scaler

if __name__ == "__main__":
    try:
        df = load_real_data_from_supabase()
        model, scaler = train_model(df)

        # Guardar modelo
        os.makedirs("ml/models", exist_ok=True)
        joblib.dump({"model": model, "scaler": scaler}, "ml/models/contigo_model.joblib")
        print("✅ Modelo real guardado como joblib.")
    except Exception as e:
        print(f"❌ Error en entrenamiento: {e}")
