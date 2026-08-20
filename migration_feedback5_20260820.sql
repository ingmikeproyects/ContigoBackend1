-- Feedback 5 (20-08-2026). Ejecutar una vez en Supabase SQL Editor
-- antes de desplegar el backend actualizado. El script es idempotente.

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(20) DEFAULT 'basico';

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS privacy_version VARCHAR(30);

UPDATE public.users
SET subscription_plan = 'basico'
WHERE subscription_plan IS NULL;

ALTER TABLE public.specialist_tasks
  ADD COLUMN IF NOT EXISTS instrucciones_html TEXT,
  ADD COLUMN IF NOT EXISTS enlace_recurso TEXT,
  ADD COLUMN IF NOT EXISTS fecha_vencimiento TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS adjunto_path TEXT,
  ADD COLUMN IF NOT EXISTS adjunto_nombre VARCHAR(180),
  ADD COLUMN IF NOT EXISTS adjunto_tipo VARCHAR(120),
  ADD COLUMN IF NOT EXISTS estado_entrega VARCHAR(20) DEFAULT 'pendiente';

ALTER TABLE public.specialist_tasks DROP CONSTRAINT IF EXISTS specialist_tasks_estado_entrega_check;
ALTER TABLE public.specialist_tasks ADD CONSTRAINT specialist_tasks_estado_entrega_check
  CHECK (estado_entrega IN ('pendiente', 'entregada'));

UPDATE public.specialist_tasks
SET estado_entrega = CASE WHEN completada THEN 'entregada' ELSE 'pendiente' END
WHERE estado_entrega IS NULL;

CREATE TABLE IF NOT EXISTS public.task_notifications (
  id BIGSERIAL PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES public.specialist_tasks(id) ON DELETE CASCADE,
  paciente_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  titulo VARCHAR(160) NOT NULL,
  mensaje TEXT NOT NULL,
  leida BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE (task_id, paciente_id)
);

CREATE INDEX IF NOT EXISTS task_notifications_patient_idx
  ON public.task_notifications(paciente_id, leida, created_at DESC);

-- Bucket privado: los pacientes reciben una URL firmada temporal desde FastAPI.
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('task-attachments', 'task-attachments', FALSE, 10485760)
ON CONFLICT (id) DO UPDATE
SET public = FALSE,
    file_size_limit = 10485760;

-- Los intentos pendientes aún no cobrados deben reflejar el precio vigente.
UPDATE public.subscriptions
SET amount = 349
WHERE plan_id = 'premium' AND status = 'pending';

CREATE INDEX IF NOT EXISTS specialist_tasks_patient_status_idx
  ON public.specialist_tasks(paciente_id, completada, created_at DESC);

-- Explicación y captura asociada a las alertas de riesgo.
ALTER TABLE public.alerts
  ADD COLUMN IF NOT EXISTS trigger_summary TEXT,
  ADD COLUMN IF NOT EXISTS heart_rate NUMERIC,
  ADD COLUMN IF NOT EXISTS hrv NUMERIC,
  ADD COLUMN IF NOT EXISTS spo2 NUMERIC,
  ADD COLUMN IF NOT EXISTS stress_level NUMERIC,
  ADD COLUMN IF NOT EXISTS source VARCHAR(40);

CREATE INDEX IF NOT EXISTS alerts_user_generated_idx
  ON public.alerts(user_id, generated_at DESC);

CREATE INDEX IF NOT EXISTS password_reset_tokens_user_active_idx
  ON public.password_reset_tokens(user_id, used, expires_at DESC);

-- Respuestas de la calibración clínica inicial. Una fila vigente por paciente.
CREATE TABLE IF NOT EXISTS public.calibration_extended (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  peso NUMERIC CHECK (peso IS NULL OR peso BETWEEN 20 AND 350),
  tiene_diabetes BOOLEAN NOT NULL DEFAULT FALSE,
  tipo_diabetes VARCHAR(80),
  realiza_actividad_fisica BOOLEAN NOT NULL DEFAULT FALSE,
  frecuencia_actividad_fisica VARCHAR(120),
  actividad_fisica_trabajo TEXT,
  actividad_sexual TEXT,
  inicio_ataque_ansiedad JSONB NOT NULL DEFAULT '[]'::jsonb,
  inicio_ataque_ansiedad_otro TEXT,
  historial_medico_general TEXT,
  factores_riesgo TEXT,
  habito_sueno TEXT,
  alimentacion_general TEXT,
  consumo_cafeina TEXT,
  consumo_alcohol TEXT,
  consumo_tabaco TEXT,
  applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE public.calibration_extended ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS calibration_extended_user_idx
  ON public.calibration_extended(user_id);
