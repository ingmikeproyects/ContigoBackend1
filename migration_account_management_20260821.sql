-- Gestión de cuenta Contigo: baja temporal, reactivación verificada y
-- eliminación definitiva. Ejecutar una vez en Supabase SQL Editor antes de
-- desplegar el backend y la aplicación actualizados. Es idempotente.

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS reactivated_at TIMESTAMP WITH TIME ZONE;

-- Permite distinguir una vinculación finalizada por decisión del paciente de
-- una vinculación suspendida únicamente mientras la cuenta está inactiva.
ALTER TABLE public.vinculaciones
  ADD COLUMN IF NOT EXISTS suspendida_por_cuenta BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS vinculaciones_suspension_cuenta_idx
  ON public.vinculaciones(suspendida_por_cuenta, paciente_id, especialista_id);

CREATE TABLE IF NOT EXISTS public.account_reactivation_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  token VARCHAR(6) NOT NULL CHECK (token ~ '^[0-9]{6}$'),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  used BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE public.account_reactivation_tokens ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS account_reactivation_tokens_active_idx
  ON public.account_reactivation_tokens(user_id, used, expires_at DESC);

-- El backend usa SUPABASE_SERVICE_KEY y es el único encargado de emitir y
-- validar estos códigos. No se crea una política pública de lectura/escritura.
COMMENT ON TABLE public.account_reactivation_tokens IS
  'Códigos de un solo uso para reactivar cuentas temporalmente desactivadas';

