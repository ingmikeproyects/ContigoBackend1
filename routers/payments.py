import os
import datetime
import mercadopago
import logging
import hmac
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from supabase import Client
from database import get_supabase
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel

sdk = mercadopago.SDK(os.getenv("MP_ACCESS_TOKEN"))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

PLANS = {
    "premium": {
            "name": "Premium",
            "mp_plan_id": os.getenv("MP_PLAN_PREMIUM_ID"),
            "amount": 10,  # PRUEBA REAL - normalmente sería 599
            "description": "Personalización de umbrales de alerta, reportes "
                           "exportables en PDF, capacitación, soporte técnico "
                           "prioritario y actualizaciones prioritarias"
        }
}

# Estados de Mercado Pago que cuentan como "activo" para dar acceso
ACTIVE_STATUSES = {"authorized"}


class CreateSubscriptionRequest(BaseModel):
    plan_id: str


@router.get("/plans")
def get_plans():
    """Retorna los planes disponibles con precios."""
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
    Crea una suscripción (preapproval) en Mercado Pago y devuelve
    el init_point al que la app debe redirigir al usuario para que
    autorice el cobro recurrente.
    """
    if not os.getenv("MP_ACCESS_TOKEN"):
        raise HTTPException(status_code=503, detail="El servicio de pagos aún no está configurado. Intenta más tarde.")
    plan = PLANS.get(body.plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan no válido")

    if not plan["mp_plan_id"]:
        raise HTTPException(
            status_code=500,
            detail=f"Falta configurar MP_PLAN_{body.plan_id.upper()}_ID "
                   "en el backend"
        )

    # Verificar si ya tiene suscripción activa (solo bloquea si ya es Premium)
    existing = supabase.table("subscriptions")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .eq("status", "authorized")\
        .neq("plan_id", "basico")\
        .execute()

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail=f"Ya tienes una suscripción activa. Cancélala antes de cambiar de plan."
        )

    preapproval_data = {
        "preapproval_plan_id": plan["mp_plan_id"],
        "reason": f"Suscripción {plan['name']} - Contigo",
        "external_reference": (
            f"user_{current_user['id']}_plan_{body.plan_id}"
        ),
        "payer_email": current_user["correo"],
        "back_url": os.getenv(
            "MP_BACK_URL",
            "https://your-api-url.railway.app/payments/return"
        ),
        "status": "pending"
    }

    result = sdk.preapproval().create(preapproval_data)

    if result["status"] not in (200, 201):
        logger.error(f"Mercado Pago subscription creation failed: {result['response']}")
        raise HTTPException(
            status_code=400,
            detail=result["response"].get(
                "message", "No se pudo crear la suscripción en Mercado Pago"
            )
        )

    response = result["response"]

    # Guardamos la suscripción como "pending" -- el webhook la
    # actualizará a "authorized" cuando el usuario complete el pago.
    supabase.table("subscriptions").insert({
        "user_id": current_user["id"],
        "plan_id": body.plan_id,
        "plan_name": plan["name"],
        "status": "pending",
        "mp_preapproval_id": response["id"],
        "amount": plan["amount"],
        "currency": "mxn",
        "start_date": datetime.datetime.utcnow().isoformat()
    }).execute()

    return {
        "init_point": response["init_point"],
        "preapproval_id": response["id"]
    }


@router.get("/return", response_class=HTMLResponse)
async def payment_return():
    """
    Pagina a la que Mercado Pago redirige al usuario despues de
    autorizar (o cancelar) el pago desde la Custom Tab. Solo le
    indica que puede volver a la app; el estado real se confirma
    por el webhook.
    """
    return """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Contigo</title>
            <style>
                body {
                    font-family: -apple-system, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: #F5F5F5;
                    text-align: center;
                    padding: 24px;
                    box-sizing: border-box;
                }
                h1 { color: #2D2D2D; font-size: 20px; }
                p { color: #757575; font-size: 15px; }
            </style>
        </head>
        <body>
            <h1>Listo</h1>
            <p>Ya puedes cerrar esta ventana y volver a la app Contigo.</p>
            <p>Tu suscripción se activará en unos segundos.</p>
        </body>
    </html>
    """


@router.get("/my-subscription")
async def get_my_subscription(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Retorna la suscripción activa (o pendiente) más reciente del usuario."""
    result = supabase.table("subscriptions")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .in_("status", ["authorized", "pending"])\
        .order("start_date", desc=True)\
        .limit(1)\
        .execute()

    if not result.data:
        return {"subscription": None}

    return {"subscription": result.data[0]}


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Cancela la suscripción activa del usuario en Mercado Pago y en la BD."""
    # Check ownership: only cancel my own subscription
    existing = supabase.table("subscriptions")\
        .select("*")\
        .eq("user_id", current_user["id"])\
        .eq("status", "authorized")\
        .execute()

    if not existing.data:
        raise HTTPException(
            status_code=400,
            detail="No tienes una suscripción activa"
        )

    preapproval_id = existing.data[0]["mp_preapproval_id"]

    try:
        sdk.preapproval().update(preapproval_id, {"status": "cancelled"})
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo cancelar en Mercado Pago: {e}"
        )

    supabase.table("subscriptions")\
        .update({"status": "cancelled"})\
        .eq("user_id", current_user["id"])\
        .eq("status", "authorized")\
        .execute()

    supabase.table("users")\
        .update({"subscription_plan": None})\
        .eq("id", current_user["id"])\
        .execute()

    return {"message": "Suscripción cancelada exitosamente"}


def validate_mp_signature(x_signature: str, x_request_id: str, data_id: str):
    secret = os.getenv("MP_WEBHOOK_SECRET")
    if not secret:
        logger.error(
            "MP_WEBHOOK_SECRET no está configurada. "
            "Rechazando el webhook por seguridad."
        )
        return False

    if not x_signature or not x_request_id or not data_id:
        return False

    try:
        # x-signature format: ts=123,v1=abc
        parts = dict(item.split('=') for item in x_signature.split(','))
        ts = parts.get('ts')
        v1_received = parts.get('v1')

        if not ts or not v1_received:
            return False

        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
        hmac_obj = hmac.new(secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256)
        v1_calculated = hmac_obj.hexdigest()

        return hmac.compare_digest(v1_calculated, v1_received)
    except Exception as e:
        logger.error(f"Error validating MP signature: {e}")
        return False

@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    supabase: Client = Depends(get_supabase)
):
    # Validate signature
    x_signature = request.headers.get("x-signature")
    x_request_id = request.headers.get("x-request-id")
    data_id = request.query_params.get("data.id")

    # Also check body for data_id if not in query params
    body = await request.json()
    if not data_id:
        data_id = (body.get("data") or {}).get("id")

    if not validate_mp_signature(x_signature, x_request_id, str(data_id)):
        logger.warning(f"Unauthorized webhook attempt. Signature validation failed for ID {data_id}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    topic = request.query_params.get("type") or body.get("type")

    if not data_id:
        return {"status": "ignored"}

    if topic == "subscription_preapproval":
        info_result = sdk.preapproval().get(data_id)
        if info_result["status"] != 200:
            return {"status": "error_fetching_preapproval"}

        info = info_result["response"]
        mp_status = info.get("status")  # authorized | paused | cancelled | pending
        preapproval_id = info.get("id")

        supabase.table("subscriptions")\
            .update({"status": mp_status})\
            .eq("mp_preapproval_id", preapproval_id)\
            .execute()

        if mp_status == "authorized":
            ext_ref = info.get("external_reference", "")
            # external_reference tiene forma "user_<id>_plan_<plan_id>"
            try:
                user_id = int(ext_ref.split("_")[1])
                plan_id = ext_ref.split("plan_")[1]
            except (IndexError, ValueError):
                user_id, plan_id = None, None

            if user_id:
                now = datetime.datetime.utcnow()
                end_date = now + datetime.timedelta(days=30)
                supabase.table("subscriptions")\
                    .update({"end_date": end_date.isoformat()})\
                    .eq("mp_preapproval_id", preapproval_id)\
                    .execute()
                supabase.table("users")\
                    .update({"subscription_plan": plan_id})\
                    .eq("id", user_id)\
                    .execute()

        elif mp_status in ("cancelled", "paused"):
            ext_ref = info.get("external_reference", "")
            try:
                user_id = int(ext_ref.split("_")[1])
            except (IndexError, ValueError):
                user_id = None
            if user_id:
                supabase.table("users")\
                    .update({"subscription_plan": None})\
                    .eq("id", user_id)\
                    .execute()

    elif topic == "subscription_authorized_payment":
        # Cada cobro mensual recurrente exitoso/fallido. Útil para
        # extender end_date en cada renovación si quieres llevar
        # registro de pagos individuales.
        pass

    return {"status": "ok"}
