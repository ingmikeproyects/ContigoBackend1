from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExtendedCalibrationCreate(BaseModel):
    peso: Optional[float] = Field(default=None, ge=20, le=350)
    tiene_diabetes: bool = False
    tipo_diabetes: Optional[str] = Field(default=None, max_length=80)
    realiza_actividad_fisica: bool = False
    frecuencia_actividad_fisica: Optional[str] = Field(default=None, max_length=120)
    actividad_fisica_trabajo: Optional[str] = Field(default=None, max_length=500)
    actividad_sexual: Optional[str] = Field(default=None, max_length=500)
    inicio_ataque_ansiedad: list[str] = Field(default_factory=list, max_length=20)
    inicio_ataque_ansiedad_otro: Optional[str] = Field(default=None, max_length=500)
    historial_medico_general: Optional[str] = Field(default=None, max_length=4000)
    factores_riesgo: Optional[str] = Field(default=None, max_length=2000)
    habito_sueno: Optional[str] = Field(default=None, max_length=1000)
    alimentacion_general: Optional[str] = Field(default=None, max_length=1000)
    consumo_cafeina: Optional[str] = Field(default=None, max_length=500)
    consumo_alcohol: Optional[str] = Field(default=None, max_length=500)
    consumo_tabaco: Optional[str] = Field(default=None, max_length=500)
    applied_at: Optional[datetime] = None
