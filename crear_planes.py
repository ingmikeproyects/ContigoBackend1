"""
Script de un solo uso para crear los dos planes de suscripcion
(Basico y Comercial) en Mercado Pago.

Usa peticiones HTTP directas (requests) contra la API de Mercado
Pago en vez del metodo sdk.preapproval_plan(), porque las versiones
recientes del SDK de Python (3.x) ya no exponen ese recurso.

Uso:
1. Asegurate de tener MP_ACCESS_TOKEN en tu .env (en esta misma carpeta).
2. Ejecuta: python crear_planes.py
3. Copia los IDs que imprima y ponlos en tu .env como
   MP_PLAN_BASICO_ID y MP_PLAN_COMERCIAL_ID
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # lee tu archivo .env si corres esto desde acompanname-backend/

ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")

if not ACCESS_TOKEN:
    raise SystemExit(
        "No encontre MP_ACCESS_TOKEN en tu .env. "
        "Ponlo ahi primero o pegalo directo en este script."
    )

URL = "https://api.mercadopago.com/preapproval_plan"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

BACK_URL = os.getenv(
    "MP_BACK_URL",
    "https://contigobackend1-production.up.railway.app/payments/return"
)

print(f"[DEBUG] MP_BACK_URL leido: '{BACK_URL}'")
print(f"[DEBUG] MP_ACCESS_TOKEN leido (primeros 15 chars): "
      f"'{ACCESS_TOKEN[:15]}...'")

planes = [
    {
        "reason": "Plan Premium Contigo",
        "back_url": BACK_URL,
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": 349,
            "currency_id": "MXN"
        }
    }
]

for plan_data in planes:
    response = requests.post(URL, json=plan_data, headers=HEADERS)
    if response.status_code in (200, 201):
        plan_id = response.json()["id"]
        print(f"OK - {plan_data['reason']} creado. ID: {plan_id}")
    else:
        print(f"ERROR creando {plan_data['reason']}:")
        print(f"  Status: {response.status_code}")
        print(f"  Respuesta: {response.text}")
