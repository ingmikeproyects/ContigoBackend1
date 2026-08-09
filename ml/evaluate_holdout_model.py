"""Evaluate the deployed Random Forest on records held out by database offset.

The training script uses the first 100,000 TAG_MULTIMODAL_REAL records.  This
script evaluates a later, non-overlapping block and produces thesis-ready
metrics.  It is still a row-level holdout: it is not a clinical validation and
must not be described as one.
"""

import csv
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from supabase import create_client

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env")

FEATURE_COLUMNS = [
    "heart_rate", "hrv", "stress_level", "sleep_hours", "activity_level",
    "screen_unlocks", "app_usage_minutes",
]
LABELS = [0, 1, 3]
LABEL_NAMES = ["NORMAL", "MODERATE", "SEVERE"]
SOURCE_DATASET = "TAG_MULTIMODAL_REAL"
TRAINING_RECORDS = 100_000
HOLDOUT_SIZE = 10_000


def load_holdout() -> pd.DataFrame:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL y SUPABASE_SERVICE_KEY deben estar configuradas.")

    client = create_client(url, key)
    records = []
    batch_size = 1_000
    for start in range(TRAINING_RECORDS, TRAINING_RECORDS + HOLDOUT_SIZE, batch_size):
        response = (
            client.table("public_reference_dataset")
            .select("id,heart_rate,hrv,stress_level,sleep_hours,activity_level,screen_unlocks,app_usage_minutes,risk_level")
            .eq("source_dataset", SOURCE_DATASET)
            .order("id")
            .range(start, start + batch_size - 1)
            .execute()
        )
        if not response.data:
            break
        records.extend(response.data)

    if not records:
        raise RuntimeError("No se encontraron registros reservados para evaluar.")

    df = pd.DataFrame(records)
    label_map = {"NORMAL": 0, "MODERATE": 1, "SEVERE": 3}
    df["risk_level_num"] = df["risk_level"].map(label_map)
    return df.dropna(subset=FEATURE_COLUMNS + ["risk_level_num"])


def write_report(y_true: np.ndarray, y_pred: np.ndarray, sample_count: int) -> None:
    matrix = confusion_matrix(y_true, y_pred, labels=LABELS)
    report = classification_report(
        y_true, y_pred, labels=LABELS, target_names=LABEL_NAMES,
        output_dict=True, zero_division=0,
    )
    accuracy = accuracy_score(y_true, y_pred)
    severe = report["SEVERE"]

    csv_path = SCRIPT_DIR / "matriz_confusion_holdout.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Real / Predicho", *LABEL_NAMES])
        for name, row in zip(LABEL_NAMES, matrix):
            writer.writerow([name, *row])

    report_path = SCRIPT_DIR / "REPORTE_EVALUACION_HOLDOUT.md"
    with report_path.open("w", encoding="utf-8") as report_file:
        report_file.write("# Evaluación del modelo Random Forest\n\n")
        report_file.write(f"**Accuracy global:** {accuracy:.4f} ({accuracy * 100:.2f}%)\n\n")
        report_file.write("## Diseño de evaluación\n\n")
        report_file.write(
            f"Se evaluaron {sample_count:,} registros de `TAG_MULTIMODAL_REAL` "
            f"a partir del offset {TRAINING_RECORDS:,}, posterior al bloque de "
            "entrenamiento configurado. No se reutilizaron las primeras 100,000 filas.\n\n"
        )
        report_file.write(
            "> Limitación: esta es una separación por filas. La tabla actual no conserva "
            "un identificador real de participante/sesión, por lo que no equivale a una "
            "validación externa o clínica por paciente.\n\n"
        )
        report_file.write("## Matriz de confusión\n\n| Real / Predicho | NORMAL | MODERATE | SEVERE |\n|---|---:|---:|---:|\n")
        for name, row in zip(LABEL_NAMES, matrix):
            report_file.write(f"| {name} | {row[0]} | {row[1]} | {row[2]} |\n")

        report_file.write("\n## Métricas por clase\n\n| Clase | Precision | Recall / Sensibilidad | F1-score | Soporte |\n|---|---:|---:|---:|---:|\n")
        for name in LABEL_NAMES:
            values = report[name]
            report_file.write(
                f"| {name} | {values['precision']:.4f} | {values['recall']:.4f} | "
                f"{values['f1-score']:.4f} | {int(values['support'])} |\n"
            )

        report_file.write("\n## Caso crítico: SEVERE\n\n")
        report_file.write(f"- Precision: **{severe['precision']:.4f}**\n")
        report_file.write(f"- Recall / sensibilidad: **{severe['recall']:.4f}**\n")
        report_file.write(f"- F1-score: **{severe['f1-score']:.4f}**\n")
        report_file.write(
            "\nLa sensibilidad de SEVERE mide la proporción de casos severos reales "
            "detectados por el modelo; debe interpretarse junto con los falsos positivos "
            "de la matriz de confusión.\n"
        )

    print(f"Reporte: {report_path}")
    print(f"Matriz CSV: {csv_path}")
    print(f"Accuracy: {accuracy:.4f}")
    print("SEVERE:", severe)


def main() -> None:
    model_path = SCRIPT_DIR / "models" / "contigo_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"No se encontró el modelo: {model_path}")

    bundle = joblib.load(model_path)
    df = load_holdout()
    x_scaled = bundle["scaler"].transform(df[FEATURE_COLUMNS])
    predictions = bundle["model"].predict(x_scaled)
    write_report(df["risk_level_num"].to_numpy(), predictions, len(df))


if __name__ == "__main__":
    main()
