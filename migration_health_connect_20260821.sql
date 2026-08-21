-- Integración OHealth -> Health Connect -> Contigo.
-- Almacena pasos reales de la ventana sincronizada; las métricas que OHealth
-- no publique continúan como NULL y nunca se sintetizan.
ALTER TABLE public.biometric_readings
    ADD COLUMN IF NOT EXISTS steps INTEGER;

COMMENT ON COLUMN public.biometric_readings.steps IS
    'Pasos reales obtenidos del reloj o Health Connect durante la ventana de lectura.';
