# Evaluación del modelo Random Forest

**Accuracy global:** 1.0000 (100.00%)

## Diseño de evaluación

Se evaluaron 10,000 registros de `TAG_MULTIMODAL_REAL` a partir del offset 100,000, posterior al bloque de entrenamiento configurado. No se reutilizaron las primeras 100,000 filas.

> Limitación: esta es una separación por filas. La tabla actual no conserva un identificador real de participante/sesión, por lo que no equivale a una validación externa o clínica por paciente.

## Matriz de confusión

| Real / Predicho | NORMAL | MODERATE | SEVERE |
|---|---:|---:|---:|
| NORMAL | 5424 | 0 | 0 |
| MODERATE | 0 | 2846 | 0 |
| SEVERE | 0 | 0 | 1730 |

## Métricas por clase

| Clase | Precision | Recall / Sensibilidad | F1-score | Soporte |
|---|---:|---:|---:|---:|
| NORMAL | 1.0000 | 1.0000 | 1.0000 | 5424 |
| MODERATE | 1.0000 | 1.0000 | 1.0000 | 2846 |
| SEVERE | 1.0000 | 1.0000 | 1.0000 | 1730 |

## Caso crítico: SEVERE

- Precision: **1.0000**
- Recall / sensibilidad: **1.0000**
- F1-score: **1.0000**

La sensibilidad de SEVERE mide la proporción de casos severos reales detectados por el modelo; debe interpretarse junto con los falsos positivos de la matriz de confusión.
