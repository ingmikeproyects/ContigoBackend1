# Despliegue final del backend Contigo en Railway

Configurar el servicio con **Root Directory** `acompanname-backend` cuando el
repositorio contenga también la aplicación Android. `railway.json` inicia
FastAPI escuchando el puerto que Railway asigna y comprueba `/health`.

## Variables obligatorias

- `SECRET_KEY`: cadena aleatoria larga para firmar JWT.
- `SUPABASE_URL`: URL HTTPS del proyecto Supabase.
- `SUPABASE_SERVICE_KEY`: clave `service_role`, nunca la `anon`.

## Correo: elegir un solo proveedor

### Gmail SMTP

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USER`: correo completo.
- `SMTP_PASSWORD`: contraseña de aplicación de 16 caracteres; no usar la
  contraseña normal de Google.

Si se va a usar Gmail, elimina cualquier `RESEND_API_KEY` antiguo que tenga
contenido. El backend da prioridad a Resend cuando esa variable existe.

### Resend, recomendado si Railway no alcanza Gmail

- `RESEND_API_KEY`: secreto generado en Resend.
- `RESEND_FROM`: remitente de un dominio verificado.

Si `RESEND_API_KEY` existe, el backend utiliza Resend e ignora SMTP.

## Mercado Pago

- `MP_ACCESS_TOKEN`
- `MP_PLAN_PREMIUM_ID`
- `MP_BACK_URL=https://contigobackend1-production.up.railway.app/payments/return`

En Mercado Pago configura la URL de notificaciones como
`https://contigobackend1-production.up.railway.app/payments/webhook`. El
`MP_BACK_URL` lo usa el script de creación del plan; el backend en ejecución
necesita principalmente `MP_ACCESS_TOKEN` y `MP_PLAN_PREMIUM_ID`.

Después de cambiar variables hay que desplegar los cambios pendientes. Verificar:

1. `https://contigobackend1-production.up.railway.app/health` devuelve `status: ok`.
2. `/openapi.json` contiene `/vinculaciones/invitation`,
   `/calibration/extended` y `/auth/forgot-password`.
3. Ejecutar `migration_feedback5_20260820.sql` en Supabase antes de probar.
4. Solicitar un código con una cuenta real y revisar los logs del deployment
   para `SUCCESS: Email sent successfully` o el error SMTP clasificado.
5. Solicitar recuperación de contraseña y comprobar que el correo llega; el
   código vence en una hora y solo puede usarse una vez.
