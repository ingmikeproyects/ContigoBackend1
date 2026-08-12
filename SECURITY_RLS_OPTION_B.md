# RLS — estado real y diseño Opción B

Contigo mantiene autenticación propia: JWT emitido por FastAPI, `password_hash`
en `users` y `SUPABASE_SERVICE_KEY` para acceder a PostgREST. No se crean
usuarios en Supabase Auth; por tanto, `auth.uid()` no representa al usuario de
Contigo y la service key omite RLS.

El archivo `rls_option_b.sql` documenta la defensa en profundidad diseñada para
la tesis (`self / linked-specialist / admin`) sobre las tablas sensibles. No se
debe afirmar que esas políticas protegen hoy las llamadas del backend: para que
se apliquen hará falta migrar a una conexión Postgres directa y ejecutar
`SET LOCAL app.current_user_id` y `SET LOCAL app.current_role` en cada
transacción autenticada. Esa migración queda expresamente como trabajo futuro.

La autorización efectiva actual sigue estando en los routers FastAPI. El panel
Supabase Authentication → Users permanecerá vacío por diseño; la tabla `users`
de la aplicación es la única fuente de verdad.
