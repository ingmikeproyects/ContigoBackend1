import os
import datetime
import mercadopago
import logging
import hmac
import hashlib
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel

sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

def get_plan_id_from_env():
    """Extrae el ID del plan de la URL configurada en el .env."""
    back_url = os.getenv("MP_BACK_URL", "")
    if "preapproval_plan_id=" in back_url:
        try:
            parsed = urllib.parse.urlparse(back_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            return query_params.get("preapproval_plan_id", [None])[0]
        except Exception:
            pass
    return "cce2f641fb2b4519bf35b8f8d2fe2521"

PLANS = {
    "premium": {
            "name": "Premium",
            "mp_plan_id": get_plan_id_from_env(),
            "amount": 10,
            "description": "Acceso Premium Contigo"
        }
}

class CreateSubscriptionRequest(BaseModel):
    plan_id: str

@router.get("/plans")
def get_plans():
    return [
        {
            "id": plan_id,
            "name": plan["name"],
            "amount": plan["amount"],
            "currency": "mxn",
            "description": plan["description"],
            "interval": "month"
        }
        for plan_id, plan in PLANS.items()
    ]

@router.post("/create-subscription")
async def create_subscription(
    body: CreateSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Redirige directamente al checkout de Mercado Pago.
    Eliminamos la creación vía SDK para evitar el error de card_token_id.
    """
    plan = PLANS.get(body.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan no válido")

    # Usamos la URL que ya configuraste en el .env que contiene el preapproval_plan_id
    init_point = os.getenv("MP_BACK_URL")

    if not init_point:
        raise HTTPException(status_code=500, detail="URL de cobro no configurada")

    # Registramos el intento en la base de datos
    # Como no estamos usando el SDK para crear, usaremos el mp_plan_id como referencia temporal
    supabase.table("subscriptions").insert({
        "user_id": current_user["id"],
        "plan_id": body.plan_id,
        "plan_name": plan["name"],
        "status": "pending",
        "mp_preapproval_id": plan["mp_plan_id"],
        "amount": plan["amount"],
        "currency": "mxn",
        "start_date": datetime.datetime.utcnow().isoformat()
    }).execute()

    return {
        "init_point": init_point,
        "preapproval_id": plan["mp_plan_id"]
    }

@router.get("/return", response_class=HTMLResponse)
async def payment_return():
    return """
    <html>
        <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>¡Pago Procesado!</h1>
            <p>Ya puedes cerrar esta ventana y volver a la app Contigo.</p>
        </body>
    </html>
    """

@router.get("/my-subscription")
async def get_my_subscription(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    result = supabase.table("subscriptions")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .in_("status", ["authorized", "pending"])\
        .order("start_date", desc=True)\
        .limit(1)\
        .execute()
    return {"subscription": result.data[0] if result.data else None}

@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    supabase: Client = Depends(get_supabase)
):
    # Webhook para procesar la suscripción una vez pagada
    body = await request.json()
    data_id = (body.get("data") or {}).get("id") or request.query_params.get("data.id")

    if not data_id: return {"status": "ok"}

    info_result = sdk.preapproval().get(data_id)
    if info_result["status"] == 200:
        info = info_result["response"]
        mp_status = info.get("status")

        # El external_reference nos ayuda a saber qué usuario es,
        # pero si el checkout directo no lo envía, lo buscamos por email
        payer_email = info.get("payer_email")

        if mp_status == "authorized":
            # Actualizar suscripción por email o por ID si existe
            user_res = supabase.table("users").select("id").eq("correo", payer_email).execute()
            if user_res.data:
                user_id = user_res.data[0]["id"]
                supabase.table("users").update({"subscription_plan": "premium"}).eq("id", user_id).execute()

                # Actualizar tabla de suscripciones
                supabase.table("subscriptions")\
                    .update({"status": "authorized", "mp_preapproval_id": info.get("id")})\
                    .eq("user_id", user_id)\
                    .eq("status", "pending")\
                    .execute()

    return {"status": "ok"}
