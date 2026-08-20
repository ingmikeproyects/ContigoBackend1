-- Feedback 5 (20-08-2026). Ejecutar una vez en Supabase SQL Editor
-- antes de desplegar el backend actualizado. El script es idempotente.

ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(20) DEFAULT 'basico';

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
