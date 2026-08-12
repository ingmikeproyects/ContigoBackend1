# MercadoPago — configuración real del flujo por redirección

El checkout actual no usa Bricks ni Wallet embebida. Solo necesita:

- `MP_ACCESS_TOKEN`: secreto privado del backend.
- `MP_PLAN_PREMIUM_ID`: identificador del plan creado en MercadoPago; debe
  pertenecer al mismo ambiente que el access token.

`MP_PUBLIC_KEY` no participa en este flujo y puede retirarse de Railway para
evitar confusión. El backend construye el checkout de suscripción a partir del
`MP_PLAN_PREMIUM_ID`; no extrae el ID de otra URL ni mantiene un valor
hardcodeado.

Antes de la demo, consultar el recurso `preapproval_plan/{id}` con el access
token y confirmar `status=active`, moneda MXN, frecuencia mensual y monto 10.
