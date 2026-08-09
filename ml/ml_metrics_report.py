import os
import joblib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import StandardScaler
from dotenv import load_dotenv
from supabase import create_client

# Configuración
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

FEATURE_COLUMNS = [
    "heart_rate", "hrv", "stress_level",
    "sleep_hours", "activity_level", "screen_unlocks", "app_usage_minutes"
]

def generate_report():
    print("📊 Generando Reporte de Métricas para la Tesis...")

    # 1. Cargar el modelo
    model_path = os.path.join(os.path.dirname(__file__), "models", "contigo_model.joblib")
    if not os.path.exists(model_path):
        print("❌ Error: No se encontró contigo_model.joblib")
        return

    bundle = joblib.load(model_path)
    model = bundle["model"]
    scaler = bundle["scaler"]

    # 2. Obtener datos de prueba desde Supabase (usamos un set de validación de 5000 registros)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    response = supabase.table("public_reference_dataset")\
        .select("*")\
        .eq("source_dataset", "TAG_MULTIMODAL_REAL")\
        .limit(5000)\
        .execute()

    df = pd.DataFrame(response.data)
    risk_map = {"NORMAL": 0, "MODERATE": 1, "SEVERE": 3}
    df["risk_level_num"] = df["risk_level"].map(risk_map)
    df = df.dropna(subset=["risk_level_num"] + FEATURE_COLUMNS)

    X = df[FEATURE_COLUMNS]
    y_true = df["risk_level_num"]
    X_scaled = scaler.transform(X)

    # 3. Predicciones
    y_pred = model.predict(X_scaled)

    # 4. Generar Métricas
    acc = accuracy_score(y_true, y_pred)
    target_names = ["NORMAL", "MODERATE", "SEVERE"]
    unique_y = sorted(y_true.unique())
    present_names = [target_names[i] if i < len(target_names) else f"Clase_{i}" for i in range(len(unique_y))]

    report_dict = classification_report(y_true, y_pred, target_names=present_names, output_dict=True)

    # 5. Guardar en un archivo Markdown legible (Usando UTF-8 para evitar errores de codec)
    report_path = os.path.join(os.path.dirname(__file__), "REPORTE_METRICAS_TESIS.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 📝 Reporte de Desempeño del Modelo de IA (TAG Multimodal)\n\n")
        f.write(f"**Precisión Global (Accuracy):** {acc:.4f}\n\n")
        f.write("## 📈 Tabla de Métricas por Clase\n")
        f.write("| Clase | Precision | Recall | F1-Score | Soporte |\n")
        f.write("|-------|-----------|--------|----------|---------|\n")
        for label, metrics in report_dict.items():
            if label in ['accuracy', 'macro avg', 'weighted avg']: continue
            f.write(f"| {label} | {metrics['precision']:.3f} | {metrics['recall']:.3f} | {metrics['f1-score']:.3f} | {metrics['support']} |\n")

        f.write("\n## 🧠 Importancia de las Características (Feature Importance)\n")
        importances = model.feature_importances_
        feat_imp = sorted(zip(FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
        f.write("| Característica | Importancia (%) |\n")
        f.write("|----------------|-----------------|\n")
        for feat, imp in feat_imp:
            f.write(f"| {feat} | {imp*100:.2f}% |\n")

    print(f"✅ Reporte generado en: {report_path}")

if __name__ == "__main__":
    generate_report()
