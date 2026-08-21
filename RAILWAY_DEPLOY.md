# Despliegue final del backend Contigo en Railway

Configurar el servicio con **Root Directory** `acompanname-backend` cuando el
repositorio contenga también la aplicación Android. `railway.json` inicia
FastAPI escuchando el puerto que Railway asigna y comprueba `/health`.

## Variables obligatorias

- `SECRET_KEY`: cadena aleatoria larga para firmar JWT.
- `SUPABASE_URL`: URL HTTPS del proyecto Supabase.
- `SUPABASE_SERVICE_KEY`: clave `service_role`, nunca la `anon`.

## Correo

El backend usa el primer proveedor configurado en este orden: **Brevo**,
**Resend** y, por último, SMTP.

### Brevo, recomendado para este despliegue

- `BREVO_API_KEY`: clave API que comienza normalmente con `xkeysib-`.
- `BREVO_SENDER_EMAIL`: dirección que aparece como verificada en Brevo.
- `BREVO_SENDER_NAME=Contigo`

No publiques la clave ni la incluyas en el repositorio. Brevo se conecta por
HTTPS, por lo que funciona aunque el plan de Railway bloquee SMTP saliente.

### Gmail SMTP

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USER`: correo completo.
- `SMTP_PASSWORD`: contraseña de aplicación de 16 caracteres; no usar la
  contraseña normal de Google.

Para forzar SMTP deben estar vacías o eliminadas tanto `BREVO_API_KEY` como
`RESEND_API_KEY`.

### Resend, recomendado si Railway no alcanza Gmail

- `RESEND_API_KEY`: secreto generado en Resend.
- `RESEND_FROM`: remitente de un dominio verificado.

Resend se usa solamente cuando `BREVO_API_KEY` no está configurada.

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
   Después ejecutar `migration_account_management_20260821.sql` para habilitar
   baja temporal, reactivación por correo y eliminación definitiva.
4. Solicitar un código con una cuenta real y revisar los logs del deployment
   para `SUCCESS: Reset email sent through Brevo` o el error clasificado.
5. Solicitar recuperación de contraseña y comprobar que el correo llega; el
   código vence en una hora y solo puede usarse una vez.
6. Desactivar una cuenta de prueba, iniciar sesión de nuevo, introducir el
   código recibido y confirmar que conserva su perfil y su vinculación.
7. Para probar la eliminación definitiva usa una cuenta desechable: requiere
   la contraseña actual y elimina en cascada los datos asociados.
