-- Contigo: diseño RLS de defensa en profundidad (Opción B)
--
-- IMPORTANTE: el backend actual usa SUPABASE_SERVICE_KEY y esa llave omite RLS.
-- Estas políticas empezarán a proteger tráfico de aplicación solo cuando una
-- conexión Postgres directa establezca, por transacción:
--   SET LOCAL app.current_user_id = '<users.id>';
--   SET LOCAL app.current_role = '<paciente|especialista|administrador>';

CREATE OR REPLACE FUNCTION public.contigo_user_id()
RETURNS integer LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::integer
$$;

CREATE OR REPLACE FUNCTION public.contigo_role()
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('app.current_role', true), '')
$$;

CREATE OR REPLACE FUNCTION public.contigo_is_linked(patient integer)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM vinculaciones v
    WHERE v.paciente_id = patient
      AND v.especialista_id = public.contigo_user_id()
      AND v.activa = true
  )
$$;

CREATE OR REPLACE FUNCTION public.contigo_history_is_shared(patient integer)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM vinculaciones v
    WHERE v.paciente_id = patient
      AND v.especialista_id = public.contigo_user_id()
      AND v.activa = true
      AND v.consentimiento_dado = true
  )
$$;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE vinculaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE biometric_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE emotional_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE notas_especialista ENABLE ROW LEVEL SECURITY;
ALTER TABLE calibration_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE gad7_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE specialist_tasks ENABLE ROW LEVEL SECURITY;

-- Idempotencia para instalaciones que ya tenían políticas de prototipo.
DROP POLICY IF EXISTS "Usuarios ven solo su propia suscripción" ON subscriptions;
DROP POLICY IF EXISTS "Solo el backend (service role) puede insertar" ON subscriptions;
DROP POLICY IF EXISTS "Solo el backend (service role) puede actualizar" ON subscriptions;

CREATE POLICY users_self ON users FOR SELECT
  USING (id = public.contigo_user_id());
CREATE POLICY users_self_update ON users FOR UPDATE
  USING (id = public.contigo_user_id())
  WITH CHECK (id = public.contigo_user_id());
CREATE POLICY users_linked_specialist ON users FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_is_linked(id));
CREATE POLICY users_admin ON users FOR ALL
  USING (public.contigo_role() = 'administrador')
  WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY links_participants ON vinculaciones FOR SELECT
  USING (paciente_id = public.contigo_user_id() OR especialista_id = public.contigo_user_id());
CREATE POLICY links_patient_consent ON vinculaciones FOR UPDATE
  USING (paciente_id = public.contigo_user_id())
  WITH CHECK (paciente_id = public.contigo_user_id());
CREATE POLICY links_admin ON vinculaciones FOR ALL
  USING (public.contigo_role() = 'administrador')
  WITH CHECK (public.contigo_role() = 'administrador');

-- Tablas cuyo propietario lógico es user_id.
CREATE POLICY biometric_self ON biometric_readings FOR ALL
  USING (user_id = public.contigo_user_id()) WITH CHECK (user_id = public.contigo_user_id());
CREATE POLICY biometric_specialist ON biometric_readings FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_history_is_shared(user_id));
CREATE POLICY biometric_admin ON biometric_readings FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY emotional_self ON emotional_states FOR ALL
  USING (user_id = public.contigo_user_id()) WITH CHECK (user_id = public.contigo_user_id());
CREATE POLICY emotional_specialist ON emotional_states FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_history_is_shared(user_id));
CREATE POLICY emotional_admin ON emotional_states FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY activities_self ON activity_logs FOR ALL
  USING (user_id = public.contigo_user_id()) WITH CHECK (user_id = public.contigo_user_id());
CREATE POLICY activities_specialist ON activity_logs FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_history_is_shared(user_id));
CREATE POLICY activities_admin ON activity_logs FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY alerts_self ON alerts FOR SELECT
  USING (user_id = public.contigo_user_id());
CREATE POLICY alerts_specialist ON alerts FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_is_linked(user_id));
CREATE POLICY alerts_admin ON alerts FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY calibration_self ON calibration_data FOR ALL
  USING (user_id = public.contigo_user_id()) WITH CHECK (user_id = public.contigo_user_id());
CREATE POLICY calibration_specialist ON calibration_data FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_is_linked(user_id));
CREATE POLICY calibration_admin ON calibration_data FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY gad7_self ON gad7_results FOR ALL
  USING (user_id = public.contigo_user_id()) WITH CHECK (user_id = public.contigo_user_id());
CREATE POLICY gad7_specialist ON gad7_results FOR SELECT
  USING (public.contigo_role() = 'especialista' AND public.contigo_history_is_shared(user_id));
CREATE POLICY gad7_admin ON gad7_results FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY notes_patient_read ON notas_especialista FOR SELECT
  USING (
    paciente_id = public.contigo_user_id()
    AND visible_para_paciente = true
  );
CREATE POLICY notes_specialist ON notas_especialista FOR ALL
  USING (especialista_id = public.contigo_user_id())
  WITH CHECK (especialista_id = public.contigo_user_id() AND public.contigo_is_linked(paciente_id));
CREATE POLICY notes_admin ON notas_especialista FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY subscriptions_self ON subscriptions FOR SELECT
  USING (user_id = public.contigo_user_id());
CREATE POLICY subscriptions_admin ON subscriptions FOR ALL
  USING (public.contigo_role() = 'administrador') WITH CHECK (public.contigo_role() = 'administrador');

CREATE POLICY tasks_patient ON specialist_tasks FOR SELECT
  USING (paciente_id = public.contigo_user_id());
CREATE POLICY tasks_patient_complete ON specialist_tasks FOR UPDATE
  USING (paciente_id = public.contigo_user_id())
  WITH CHECK (paciente_id = public.contigo_user_id());
CREATE POLICY tasks_specialist ON specialist_tasks FOR ALL
  USING (
    especialista_id = public.contigo_user_id()
    AND public.contigo_is_linked(paciente_id)
  )
  WITH CHECK (
    especialista_id = public.contigo_user_id()
    AND public.contigo_is_linked(paciente_id)
  );
CREATE POLICY tasks_admin ON specialist_tasks FOR ALL
  USING (public.contigo_role() = 'administrador')
  WITH CHECK (public.contigo_role() = 'administrador');

-- password_reset_tokens no tiene políticas de cliente intencionalmente:
-- únicamente el backend de autenticación debe acceder a esta tabla.
