from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
import numpy as np

router = APIRouter(prefix="/risk", tags=["risk"])

# Métricas disponibles en WESAD
WESAD_METRICS = {
    "heart_rate": {"mean": 70.5, "std": 6.2},
    "hrv": {"mean": 62.0, "std": 15.0},
    "stress_level": {"mean": 1.8, "std": 0.9},
    "activity_level": {"mean": 0.12, "std": 0.05}
}

@router.post("/population-compare")
def compare_to_population(
    current_metrics: dict,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Compara los biométricos actuales del usuario contra la población de referencia WESAD.
    """
    results = {}
    out_of_range_count = 0

    for metric, ref in WESAD_METRICS.items():
        val = current_metrics.get(metric)
        if val is not None:
            # Calcular z-score: (valor - media) / desviación_estándar
            z_score = (val - ref["mean"]) / ref["std"]

            # Se considera fuera de rango si está a más de 2 desviaciones estándar (percentil ~95)
            is_out = abs(z_score) > 2.0
            if is_out:
                out_of_range_count += 1

            results[metric] = {
                "z_score": round(float(z_score), 2),
                "status": "ABNORMAL" if is_out else "NORMAL"
            }

    # Lógica de mensaje clínico pre-redactado
    if out_of_range_count >= 2:
        message = "Tus indicadores muestran una variación significativa respecto a la media poblacional. Te recomendamos realizar una actividad de calma."
        risk_level = "MODERATE"
    elif out_of_range_count == 1:
        message = "Uno de tus indicadores está ligeramente fuera del rango normal poblacional. Mantén el monitoreo."
        risk_level = "MILD"
    else:
        message = "Tus indicadores se encuentran dentro de los rangos normales de la población de referencia."
        risk_level = "NORMAL"

    return {
        "risk_level": risk_level,
        "message": message,
        "comparison_details": results
    }
