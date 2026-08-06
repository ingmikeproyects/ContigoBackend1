"""
Destilación de conocimiento: Random Forest -> Red neuronal pequeña -> TFLite.
Actualizado para usar los datos reales de WESAD desde Supabase.
"""

import os
import json
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
from sklearn.metrics import accuracy_score, classification_report
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

RANDOM_STATE = 42
FEATURE_COLUMNS = [
    "heart_rate", "hrv", "stress_level", "activity_level"
]

MODEL_PATH = os.path.join("ml", "models", "contigo_model.joblib")
TFLITE_PATH = os.path.join("ml", "models", "contigo_model.tflite")
SCALER_JSON_PATH = os.path.join("ml", "models", "scaler_params.json")

def load_data_from_supabase() -> np.ndarray:
    """Carga los datos de WESAD desde Supabase para la destilación."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
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

    df = pd.DataFrame(all_data)
    return df[FEATURE_COLUMNS].values.astype(np.float32)

def main():
    print(f"Cargando modelo entrenado desde {MODEL_PATH}...")
    bundle = joblib.load(MODEL_PATH)
    rf_model = bundle["model"]
    scaler = bundle["scaler"]

    print("Cargando datos reales para destilación...")
    X_raw = load_data_from_supabase()
    X_scaled = scaler.transform(X_raw).astype(np.float32)

    # Etiquetas "blandas" (probabilidades) del Random Forest real
    rf_probs = rf_model.predict_proba(X_scaled)
    rf_hard_labels = rf_model.predict(X_scaled)

    split = int(len(X_scaled) * 0.85)
    X_train, X_val = X_scaled[:split], X_scaled[split:]
    y_train, y_val = rf_probs[:split], rf_probs[split:]
    y_val_hard = rf_hard_labels[split:]

    student = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(len(FEATURE_COLUMNS),)),
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(2, activation='softmax'), # 2 clases: NORMAL y SEVERE
    ])
    student.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

    print("Entrenando red pequeña para imitar al Random Forest (destilación)...")
    student.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0, validation_split=0.1)

    # Validar acuerdo real
    student_probs = student.predict(X_val, verbose=0)
    student_preds_idx = np.argmax(student_probs, axis=1)

    # Mapear de vuelta a los valores originales [0, 3]
    class_map = rf_model.classes_
    student_preds = np.array([class_map[idx] for idx in student_preds_idx])

    agreement = accuracy_score(y_val_hard, student_preds)
    print(f"\nAcuerdo red destilada vs Random Forest en validación: {agreement:.3f}")

    # Convertir a TFLite
    converter = tf.lite.TFLiteConverter.from_keras_model(student)
    tflite_model = converter.convert()

    os.makedirs(os.path.dirname(TFLITE_PATH), exist_ok=True)
    with open(TFLITE_PATH, "wb") as f:
        f.write(tflite_model)
    print(f"Modelo TFLite guardado en {TFLITE_PATH}")

    # Exportar parámetros del scaler
    scaler_params = {
        "features": FEATURE_COLUMNS,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
    }
    with open(SCALER_JSON_PATH, "w") as f:
        json.dump(scaler_params, f, indent=2)
    print(f"Parámetros del scaler guardados en {SCALER_JSON_PATH}")

if __name__ == "__main__":
    main()
