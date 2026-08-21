-- Tabla de usuarios
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    uid UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    correo VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) CHECK (rol IN (
        'paciente', 'especialista', 'administrador'
    )) NOT NULL,
    -- Campos paciente
    edad INTEGER,
    fecha_nacimiento DATE,
    genero VARCHAR(50),
    tiempo_diagnostico VARCHAR(100),
    medicacion_activa BOOLEAN DEFAULT FALSE,
    frecuencia_consultas VARCHAR(100),
    -- Campos clínicos paciente
    nombre_completo VARCHAR(255),
    sexo VARCHAR(20),
    fecha_nacimiento_completa DATE,
    contacto_emergencia_nombre VARCHAR(255),
    contacto_emergencia_telefono VARCHAR(20),
    lista_medicamentos TEXT,
    alergias TEXT,
    plan_tratamiento TEXT,
    dosis_medicamentos TEXT,
    -- Campos especialista
    cedula_profesional VARCHAR(50),
    especialidad VARCHAR(255),
    institucion VARCHAR(255),
    anios_experiencia INTEGER,
    -- Campos profesionales del especialista (extendidos)
    licenciatura_psicologia VARCHAR(255),
    especialidades TEXT,
    cedula_especialidad VARCHAR(20),
    institucion_actual VARCHAR(255),
    enfoque_terapeutico TEXT,
    telefono VARCHAR(20),
    historial_medico TEXT,
    -- Estado de cuenta
    activo BOOLEAN DEFAULT TRUE,
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ultimo_acceso TIMESTAMP WITH TIME ZONE
);

-- Tabla de vinculaciones
CREATE TABLE vinculaciones (
    id SERIAL PRIMARY KEY,
    paciente_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    especialista_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    fecha_vinculacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    activa BOOLEAN DEFAULT TRUE,
    consentimiento_dado BOOLEAN DEFAULT FALSE,
    codigo VARCHAR(6) UNIQUE,
    estado VARCHAR(20) DEFAULT 'aceptada' CHECK (estado IN (
        'pendiente', 'aceptada', 'expirada', 'finalizada'
    )),
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Tabla de lecturas biométricas
CREATE TABLE biometric_readings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    heart_rate FLOAT,
    hrv FLOAT,
    spo2 FLOAT,
    stress_level FLOAT,
    sleep_hours FLOAT,
    activity_level FLOAT,
    steps INTEGER,
    screen_unlocks INTEGER,
    app_usage_minutes INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla de estados emocionales
CREATE TABLE emotional_states (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    emotional_state VARCHAR(50) NOT NULL,
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla de actividades completadas
CREATE TABLE activity_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(100) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duration_seconds INTEGER NOT NULL
);

-- Tabla de alertas
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    risk_level VARCHAR(10) CHECK (risk_level IN (
        'NORMAL', 'MILD', 'MODERATE', 'SEVERE'
    )) NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE
);

-- Tabla de notas del especialista
CREATE TABLE notas_especialista (
    id SERIAL PRIMARY KEY,
    especialista_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    paciente_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    texto TEXT NOT NULL,
    visible_para_paciente BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tareas terapéuticas asignadas por el especialista
CREATE TABLE specialist_tasks (
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

-- Tabla de calibración
CREATE TABLE calibration_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    avg_heart_rate FLOAT,
    avg_hrv FLOAT,
    avg_sleep_hours FLOAT,
    avg_activity_level FLOAT,
    avg_screen_unlocks FLOAT,
    avg_app_usage_minutes FLOAT,
    std_heart_rate FLOAT,
    std_hrv FLOAT,
    std_sleep_hours FLOAT,
    std_activity_level FLOAT,
    std_screen_unlocks FLOAT,
    std_app_usage_minutes FLOAT,
    calibration_completed BOOLEAN DEFAULT FALSE,
    calibration_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    calibration_end TIMESTAMP WITH TIME ZONE
);

-- Tabla de tokens de reset de contraseña
CREATE TABLE password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla de resultados GAD-7
CREATE TABLE gad7_results (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    q1 INTEGER CHECK (q1 BETWEEN 0 AND 3),
    q2 INTEGER CHECK (q2 BETWEEN 0 AND 3),
    q3 INTEGER CHECK (q3 BETWEEN 0 AND 3),
    q4 INTEGER CHECK (q4 BETWEEN 0 AND 3),
    q5 INTEGER CHECK (q5 BETWEEN 0 AND 3),
    q6 INTEGER CHECK (q6 BETWEEN 0 AND 3),
    q7 INTEGER CHECK (q7 BETWEEN 0 AND 3),
    total_score INTEGER NOT NULL,
    severity_level VARCHAR(20) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Habilitar Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE vinculaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE biometric_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE emotional_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE notas_especialista ENABLE ROW LEVEL SECURITY;
ALTER TABLE specialist_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE calibration_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE gad7_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    plan_id VARCHAR(20) NOT NULL,
    plan_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    mp_preapproval_id VARCHAR(100),
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_date TIMESTAMP WITH TIME ZONE,
    amount INTEGER NOT NULL,
    currency VARCHAR(3) DEFAULT 'mxn',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Si tu tabla subscriptions ya existía con la columna vieja de Stripe,
-- corre esto una sola vez para migrarla:
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS
    mp_preapproval_id VARCHAR(100);
ALTER TABLE subscriptions DROP COLUMN IF EXISTS payment_intent_id;

ALTER TABLE users DROP COLUMN IF EXISTS stripe_customer_id;
ALTER TABLE users ADD COLUMN IF NOT EXISTS
    subscription_plan VARCHAR(20);

-- No usar auth.uid(): Contigo emplea JWT propio, no Supabase Auth.
-- Aplicar el diseño completo e idempotente de rls_option_b.sql. Mientras el
-- backend use SUPABASE_SERVICE_KEY, la autorización efectiva vive en FastAPI.
