-- Ejecutar una vez en Supabase antes de desplegar el backend Feedback 3.
ALTER TABLE vinculaciones
  ADD COLUMN IF NOT EXISTS codigo VARCHAR(6),
  ADD COLUMN IF NOT EXISTS estado VARCHAR(20) DEFAULT 'aceptada',
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE notas_especialista
  ADD COLUMN IF NOT EXISTS visible_para_paciente BOOLEAN DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS vinculaciones_codigo_unique
  ON vinculaciones(codigo)
  WHERE codigo IS NOT NULL;

ALTER TABLE vinculaciones DROP CONSTRAINT IF EXISTS vinculaciones_estado_check;
ALTER TABLE vinculaciones ADD CONSTRAINT vinculaciones_estado_check
  CHECK (estado IN ('pendiente', 'aceptada', 'expirada', 'finalizada'));

UPDATE vinculaciones
SET estado = CASE WHEN activa THEN 'aceptada' ELSE 'finalizada' END
WHERE estado IS NULL;

CREATE TABLE IF NOT EXISTS specialist_tasks (
  id SERIAL PRIMARY KEY,
  especialista_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  paciente_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
  titulo VARCHAR(160) NOT NULL,
  descripcion TEXT,
  minutos_estimados INTEGER DEFAULT 15 CHECK (minutos_estimados BETWEEN 1 AND 180),
  completada BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS specialist_tasks_patient_idx
  ON specialist_tasks(paciente_id, completada, created_at DESC);
