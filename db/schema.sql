-- =====================================================================
-- Dental Home · Esquema de base de datos (PostgreSQL 16)
-- SaaS multiclínica: una sola base compartida, aislamiento con clinica_id + RLS.
--
-- Criterios de modelado
--   · Tercera forma normal (3FN) en todas las tablas.
--   · Única denormalización deliberada: clinica_id se repite en cada tabla de
--     clínica (necesario para RLS). Las claves foráneas COMPUESTAS
--     (clinica_id, x_id) garantizan que nunca se mezclen datos de dos clínicas.
--   · Sin valores derivados almacenados: edad, estado de suscripción vencida,
--     historial de una consulta, doctor de una receta, etc. se obtienen por consulta.
--   · Los conflictos de agenda se impiden en la base (restricción de exclusión).
--
-- Orden: 1 tipos · 2 plataforma · 3 clínica · 4 clínico · 5 operación
--        6 vistas y triggers · 7 RLS y roles · 8 datos base
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;   -- restricción de exclusión de citas

-- ---------------------------------------------------------------------
-- 1. TIPOS (dominios cerrados y estables)
-- ---------------------------------------------------------------------
CREATE TYPE rol_usuario          AS ENUM ('administrador', 'doctor', 'secretaria');
CREATE TYPE turno_trabajo        AS ENUM ('manana', 'tarde', 'tiempo_completo');
CREATE TYPE sexo_paciente        AS ENUM ('M', 'F');
CREATE TYPE tipo_documento       AS ENUM ('DNI', 'CE', 'PASAPORTE');
CREATE TYPE estado_cita          AS ENUM ('pendiente', 'completada', 'cancelada');
CREATE TYPE superficie_dental    AS ENUM ('vestibular', 'lingual', 'mesial', 'distal', 'oclusal');
CREATE TYPE estado_suscripcion   AS ENUM ('prueba', 'activa', 'cancelada');
CREATE TYPE estado_pago          AS ENUM ('pendiente', 'pagado', 'fallido', 'reembolsado');
CREATE TYPE tipo_reporte         AS ENUM ('citas', 'pacientes', 'ingresos', 'actividad');
CREATE TYPE formato_reporte      AS ENUM ('pdf', 'excel');
CREATE TYPE tipo_copia           AS ENUM ('manual', 'automatica');
CREATE TYPE estado_copia         AS ENUM ('pendiente', 'exitoso', 'fallido');
CREATE TYPE canal_notificacion   AS ENUM ('correo', 'whatsapp');
CREATE TYPE tipo_notificacion    AS ENUM ('recordatorio_cita', 'aviso_suscripcion');
CREATE TYPE estado_notificacion  AS ENUM ('pendiente', 'enviada', 'fallida');

-- ---------------------------------------------------------------------
-- 2. PLATAFORMA (tablas globales, sin clinica_id)
-- ---------------------------------------------------------------------
CREATE TABLE planes (
    id                 smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo             text         NOT NULL UNIQUE CHECK (codigo ~ '^[a-z]+$'),
    nombre             text         NOT NULL,
    precio_mensual     numeric(8,2) NOT NULL CHECK (precio_mensual >= 0),
    max_usuarios       integer      CHECK (max_usuarios > 0),    -- NULL = sin límite
    max_pacientes      integer      CHECK (max_pacientes > 0),   -- NULL = sin límite
    permite_excel      boolean      NOT NULL DEFAULT false,
    permite_respaldos  boolean      NOT NULL DEFAULT false,
    activo             boolean      NOT NULL DEFAULT true
);

CREATE TABLE clinicas (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo     text        NOT NULL UNIQUE
               CHECK (codigo ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(codigo) <= 32),
    nombre     text        NOT NULL,
    correo     text        NOT NULL CHECK (correo = lower(correo)),
    activa     boolean     NOT NULL DEFAULT true,
    creada_en  timestamptz NOT NULL DEFAULT now()
);

-- Una fila por periodo contratado; solo una vigente (prueba o activa) por clínica.
-- "Vencida" no se guarda: se calcula con vence_en (ver v_suscripcion_actual).
CREATE TABLE suscripciones (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id  bigint             NOT NULL REFERENCES clinicas(id),
    plan_id     smallint           NOT NULL REFERENCES planes(id),
    estado      estado_suscripcion NOT NULL DEFAULT 'prueba',
    inicia_en   date               NOT NULL DEFAULT current_date,
    vence_en    date               NOT NULL,
    creada_en   timestamptz        NOT NULL DEFAULT now(),
    CHECK (vence_en >= inicia_en),
    UNIQUE (clinica_id, id)
);
CREATE UNIQUE INDEX ux_suscripcion_vigente
    ON suscripciones (clinica_id) WHERE estado IN ('prueba', 'activa');

CREATE TABLE pagos (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id         bigint       NOT NULL,
    suscripcion_id     bigint       NOT NULL,
    plan_id            smallint     NOT NULL REFERENCES planes(id),  -- plan vigente al pagar
    monto              numeric(10,2) NOT NULL CHECK (monto > 0),
    moneda             char(3)      NOT NULL DEFAULT 'PEN',
    estado             estado_pago  NOT NULL DEFAULT 'pendiente',
    pasarela           text         NOT NULL,
    referencia_externa text         NOT NULL,
    periodo_inicio     date,
    periodo_fin        date,
    pagado_en          timestamptz,
    creado_en          timestamptz  NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, suscripcion_id) REFERENCES suscripciones (clinica_id, id),
    UNIQUE (pasarela, referencia_externa),
    CHECK (estado <> 'pagado' OR (pagado_en IS NOT NULL AND periodo_inicio IS NOT NULL AND periodo_fin >= periodo_inicio))
);

-- Idempotencia del webhook: un evento externo se procesa una sola vez.
CREATE TABLE eventos_webhook (
    pasarela      text        NOT NULL,
    evento_id     text        NOT NULL,
    tipo          text        NOT NULL,
    payload       jsonb       NOT NULL,
    recibido_en   timestamptz NOT NULL DEFAULT now(),
    procesado_en  timestamptz,
    PRIMARY KEY (pasarela, evento_id)
);

-- Personal de la consola de plataforma (no pertenece a ninguna clínica).
CREATE TABLE usuarios_plataforma (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    correo           text        NOT NULL UNIQUE CHECK (correo = lower(correo)),
    contrasena_hash  text        NOT NULL,
    activo           boolean     NOT NULL DEFAULT true,
    creado_en        timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 3. IDENTIDAD Y ACCESO DE CADA CLÍNICA
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id        bigint      NOT NULL REFERENCES clinicas(id),
    nombre_usuario    text        NOT NULL CHECK (nombre_usuario ~ '^[a-z0-9._-]{3,32}$'),
    correo            text        NOT NULL CHECK (correo = lower(correo)),
    contrasena_hash   text        NOT NULL,                      -- argon2id
    rol               rol_usuario NOT NULL,
    activo            boolean     NOT NULL DEFAULT true,
    intentos_fallidos smallint    NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
    bloqueado_hasta   timestamptz,
    creado_en         timestamptz NOT NULL DEFAULT now(),
    actualizado_en    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (clinica_id, id),
    UNIQUE (clinica_id, nombre_usuario),
    UNIQUE (clinica_id, correo)
);

-- Datos propios del profesional (evita columnas NULL en usuarios).
CREATE TABLE doctores (
    usuario_id          bigint PRIMARY KEY,
    clinica_id          bigint     NOT NULL,
    numero_colegiatura  text       NOT NULL,
    turno               turno_trabajo NOT NULL DEFAULT 'tiempo_completo',
    FOREIGN KEY (clinica_id, usuario_id) REFERENCES usuarios (clinica_id, id),
    UNIQUE (clinica_id, usuario_id),
    UNIQUE (clinica_id, numero_colegiatura)
);

-- Refresh tokens rotativos (solo se guarda el hash).
CREATE TABLE sesiones (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinica_id  bigint      NOT NULL,
    usuario_id  bigint      NOT NULL,
    token_hash  text        NOT NULL UNIQUE,
    creada_en   timestamptz NOT NULL DEFAULT now(),
    expira_en   timestamptz NOT NULL,
    revocada_en timestamptz,
    ip          inet,
    agente      text,
    FOREIGN KEY (clinica_id, usuario_id) REFERENCES usuarios (clinica_id, id),
    CHECK (expira_en > creada_en)
);

-- Enlaces de recuperación de contraseña: de un solo uso y con caducidad.
CREATE TABLE tokens_recuperacion (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id  bigint      NOT NULL,
    usuario_id  bigint      NOT NULL,
    token_hash  text        NOT NULL UNIQUE,
    creado_en   timestamptz NOT NULL DEFAULT now(),
    expira_en   timestamptz NOT NULL,
    usado_en    timestamptz,
    FOREIGN KEY (clinica_id, usuario_id) REFERENCES usuarios (clinica_id, id),
    CHECK (expira_en > creado_en)
);

-- ---------------------------------------------------------------------
-- 4. NÚCLEO CLÍNICO
-- ---------------------------------------------------------------------
CREATE TABLE pacientes (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id        bigint         NOT NULL REFERENCES clinicas(id),
    tipo_documento    tipo_documento NOT NULL DEFAULT 'DNI',
    numero_documento  text           NOT NULL,
    nombres           text           NOT NULL,
    apellidos         text           NOT NULL,
    sexo              sexo_paciente,
    fecha_nacimiento  date           CHECK (fecha_nacimiento <= current_date),
    telefono          text,
    correo            text           CHECK (correo = lower(correo)),
    direccion         text,
    activo            boolean        NOT NULL DEFAULT true,           -- baja lógica
    registrado_por    bigint,
    creado_en         timestamptz    NOT NULL DEFAULT now(),
    actualizado_en    timestamptz    NOT NULL DEFAULT now(),
    UNIQUE (clinica_id, id),
    UNIQUE (clinica_id, tipo_documento, numero_documento),
    FOREIGN KEY (clinica_id, registrado_por) REFERENCES usuarios (clinica_id, id),
    CHECK (tipo_documento <> 'DNI' OR numero_documento ~ '^[0-9]{8}$')
);

CREATE TABLE historiales_clinicos (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id      bigint      NOT NULL,
    paciente_id     bigint      NOT NULL,
    observaciones   text        NOT NULL DEFAULT '',
    creado_en       timestamptz NOT NULL DEFAULT now(),
    actualizado_en  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, paciente_id) REFERENCES pacientes (clinica_id, id),
    UNIQUE (clinica_id, id),
    UNIQUE (clinica_id, paciente_id)                                  -- un historial por paciente
);

CREATE TABLE citas (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id          bigint      NOT NULL,
    paciente_id         bigint      NOT NULL,
    doctor_id           bigint      NOT NULL,
    inicia_en           timestamptz NOT NULL,
    termina_en          timestamptz NOT NULL,
    estado              estado_cita NOT NULL DEFAULT 'pendiente',
    motivo_cancelacion  text,
    creada_en           timestamptz NOT NULL DEFAULT now(),
    actualizada_en      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, paciente_id) REFERENCES pacientes (clinica_id, id),
    FOREIGN KEY (clinica_id, doctor_id)   REFERENCES doctores (clinica_id, usuario_id),
    UNIQUE (clinica_id, id),
    CHECK (termina_en > inicia_en),
    CHECK (motivo_cancelacion IS NULL OR estado = 'cancelada'),
    -- Un doctor no puede tener dos citas que se crucen (las canceladas no cuentan).
    EXCLUDE USING gist (
        clinica_id WITH =,
        doctor_id  WITH =,
        tstzrange(inicia_en, termina_en) WITH &&
    ) WHERE (estado <> 'cancelada')
);

-- Una consulta por cita atendida. El paciente y el doctor se obtienen de la cita.
CREATE TABLE registros_clinicos (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id      bigint      NOT NULL,
    cita_id         bigint      NOT NULL,
    diagnostico     text        NOT NULL,
    tratamiento     text        NOT NULL,
    observaciones   text        NOT NULL DEFAULT '',
    atendido_en     timestamptz NOT NULL DEFAULT now(),
    actualizado_en  timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, cita_id) REFERENCES citas (clinica_id, id),
    UNIQUE (clinica_id, id),
    UNIQUE (clinica_id, cita_id)
);

-- Catálogos globales del odontograma (numeración FDI).
CREATE TABLE piezas_dentales (
    codigo     smallint PRIMARY KEY,
    cuadrante  smallint NOT NULL CHECK (cuadrante BETWEEN 1 AND 8),
    posicion   smallint NOT NULL CHECK (posicion BETWEEN 1 AND 8),
    dentadura  text GENERATED ALWAYS AS (CASE WHEN cuadrante <= 4 THEN 'permanente' ELSE 'temporal' END) STORED,
    CHECK (codigo = cuadrante * 10 + posicion),
    CHECK (cuadrante <= 4 OR posicion <= 5)
);

CREATE TABLE condiciones_dentales (
    id      smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo  text NOT NULL UNIQUE CHECK (codigo ~ '^[a-z_]+$'),
    nombre  text NOT NULL
);

-- Hallazgos del odontograma: cada fila es un hecho fechado (pieza, superficie, condición).
-- superficie NULL = afecta a la pieza completa (ausente, corona, implante...).
-- El estado vigente se obtiene con la vista v_odontograma_actual.
CREATE TABLE odontograma_hallazgos (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id          bigint            NOT NULL,
    historial_id        bigint            NOT NULL,
    pieza_codigo        smallint          NOT NULL REFERENCES piezas_dentales(codigo),
    superficie          superficie_dental,
    condicion_id        smallint          NOT NULL REFERENCES condiciones_dentales(id),
    registro_clinico_id bigint,                                       -- consulta que lo registró
    notas               text,
    registrado_en       timestamptz       NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, historial_id)        REFERENCES historiales_clinicos (clinica_id, id),
    FOREIGN KEY (clinica_id, registro_clinico_id) REFERENCES registros_clinicos (clinica_id, id)
);

CREATE TABLE medicamentos (            -- catálogo propio de cada clínica
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id    bigint  NOT NULL REFERENCES clinicas(id),
    nombre        text    NOT NULL,
    presentacion  text,
    activo        boolean NOT NULL DEFAULT true,
    UNIQUE (clinica_id, id),
    UNIQUE (clinica_id, nombre)
);

CREATE TABLE recetas (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id              bigint      NOT NULL,
    registro_clinico_id     bigint      NOT NULL,
    indicaciones_generales  text        NOT NULL DEFAULT '',
    emitida_en              timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, registro_clinico_id) REFERENCES registros_clinicos (clinica_id, id),
    UNIQUE (clinica_id, id),
    UNIQUE (clinica_id, registro_clinico_id)                          -- una receta por consulta
);

CREATE TABLE receta_detalles (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id     bigint        NOT NULL,
    receta_id      bigint        NOT NULL,
    medicamento_id bigint        NOT NULL,
    cantidad       numeric(8,2)  NOT NULL CHECK (cantidad > 0),
    indicaciones   text          NOT NULL,
    FOREIGN KEY (clinica_id, receta_id)      REFERENCES recetas (clinica_id, id) ON DELETE CASCADE,
    FOREIGN KEY (clinica_id, medicamento_id) REFERENCES medicamentos (clinica_id, id),
    UNIQUE (receta_id, medicamento_id)
);

-- ---------------------------------------------------------------------
-- 5. OPERACIÓN Y TRAZABILIDAD
-- ---------------------------------------------------------------------
CREATE TABLE reportes (                -- registro de reportes solicitados (el archivo se genera al pedirlo)
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id     bigint          NOT NULL,
    generado_por   bigint          NOT NULL,
    tipo           tipo_reporte    NOT NULL,
    formato        formato_reporte NOT NULL,
    fecha_inicio   date            NOT NULL,
    fecha_fin      date            NOT NULL,
    generado_en    timestamptz     NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, generado_por) REFERENCES usuarios (clinica_id, id),
    CHECK (fecha_fin >= fecha_inicio)
);

CREATE TABLE copias_seguridad (        -- bitácora de exportaciones y copias de la clínica
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id      bigint       NOT NULL REFERENCES clinicas(id),
    solicitada_por  bigint,                                           -- NULL = copia automática
    tipo            tipo_copia   NOT NULL,
    estado          estado_copia NOT NULL DEFAULT 'pendiente',
    iniciada_en     timestamptz  NOT NULL DEFAULT now(),
    finalizada_en   timestamptz,
    FOREIGN KEY (clinica_id, solicitada_por) REFERENCES usuarios (clinica_id, id),
    CHECK (finalizada_en IS NULL OR finalizada_en >= iniciada_en),
    CHECK ((tipo = 'manual') = (solicitada_por IS NOT NULL))
);

-- Cola ligera de avisos. El destinatario se obtiene de la cita (paciente) o del usuario.
CREATE TABLE notificaciones (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id      bigint              NOT NULL REFERENCES clinicas(id),
    tipo            tipo_notificacion   NOT NULL,
    canal           canal_notificacion  NOT NULL,
    cita_id         bigint,
    usuario_id      bigint,
    estado          estado_notificacion NOT NULL DEFAULT 'pendiente',
    programada_para timestamptz         NOT NULL,
    enviada_en      timestamptz,
    intentos        smallint            NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    FOREIGN KEY (clinica_id, cita_id)    REFERENCES citas (clinica_id, id) ON DELETE CASCADE,
    FOREIGN KEY (clinica_id, usuario_id) REFERENCES usuarios (clinica_id, id),
    CHECK ((cita_id IS NOT NULL) <> (usuario_id IS NOT NULL)),        -- exactamente un destinatario
    CHECK (estado <> 'enviada' OR enviada_en IS NOT NULL)
);
CREATE UNIQUE INDEX ux_recordatorio_unico
    ON notificaciones (cita_id, canal, tipo) WHERE cita_id IS NOT NULL;

-- Auditoría de solo inserción.
CREATE TABLE auditoria (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clinica_id    bigint      REFERENCES clinicas(id),                -- NULL = evento de plataforma
    usuario_id    bigint,
    accion        text        NOT NULL,
    recurso       text        NOT NULL,
    recurso_id    bigint,
    ip            inet,
    detalle       jsonb,
    ocurrido_en   timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (clinica_id, usuario_id) REFERENCES usuarios (clinica_id, id)
);

-- ---------------------------------------------------------------------
-- Índices de consulta frecuente (las claves únicas ya generan los suyos)
-- ---------------------------------------------------------------------
CREATE INDEX ix_pacientes_busqueda   ON pacientes (clinica_id, apellidos, nombres);
CREATE INDEX ix_citas_agenda         ON citas (clinica_id, inicia_en);
CREATE INDEX ix_citas_paciente       ON citas (clinica_id, paciente_id, inicia_en DESC);
CREATE INDEX ix_hallazgos_pieza      ON odontograma_hallazgos (historial_id, pieza_codigo, superficie, registrado_en DESC);
CREATE INDEX ix_detalles_medicamento ON receta_detalles (clinica_id, medicamento_id);
CREATE INDEX ix_sesiones_usuario     ON sesiones (usuario_id) WHERE revocada_en IS NULL;
CREATE INDEX ix_notif_pendientes     ON notificaciones (programada_para) WHERE estado = 'pendiente';
CREATE INDEX ix_auditoria_clinica    ON auditoria (clinica_id, ocurrido_en DESC);
CREATE INDEX ix_pagos_suscripcion    ON pagos (clinica_id, suscripcion_id);
CREATE INDEX ix_reportes_clinica     ON reportes (clinica_id, generado_en DESC);

-- ---------------------------------------------------------------------
-- 6. VISTAS Y TRIGGERS
-- ---------------------------------------------------------------------
-- Estado vigente del odontograma: el último hallazgo por pieza y superficie.
CREATE VIEW v_odontograma_actual WITH (security_invoker = true) AS
SELECT DISTINCT ON (h.historial_id, h.pieza_codigo, h.superficie)
       h.historial_id, h.clinica_id, h.pieza_codigo, h.superficie,
       h.condicion_id, h.notas, h.registrado_en
FROM odontograma_hallazgos h
ORDER BY h.historial_id, h.pieza_codigo, h.superficie, h.registrado_en DESC, h.id DESC;

-- Suscripción vigente con su estado efectivo (vencida se calcula, no se guarda).
CREATE VIEW v_suscripcion_actual WITH (security_invoker = true) AS
SELECT s.clinica_id, s.id AS suscripcion_id, s.plan_id, s.inicia_en, s.vence_en,
       CASE WHEN s.vence_en < current_date THEN 'vencida' ELSE s.estado::text END AS estado_efectivo,
       (s.vence_en >= current_date) AS vigente
FROM suscripciones s
WHERE s.estado IN ('prueba', 'activa');

CREATE FUNCTION tg_actualizado_en() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'citas' THEN NEW.actualizada_en := now();
    ELSE NEW.actualizado_en := now();
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER t_usuarios_act   BEFORE UPDATE ON usuarios             FOR EACH ROW EXECUTE FUNCTION tg_actualizado_en();
CREATE TRIGGER t_pacientes_act  BEFORE UPDATE ON pacientes            FOR EACH ROW EXECUTE FUNCTION tg_actualizado_en();
CREATE TRIGGER t_historial_act  BEFORE UPDATE ON historiales_clinicos FOR EACH ROW EXECUTE FUNCTION tg_actualizado_en();
CREATE TRIGGER t_citas_act      BEFORE UPDATE ON citas                FOR EACH ROW EXECUTE FUNCTION tg_actualizado_en();
CREATE TRIGGER t_registros_act  BEFORE UPDATE ON registros_clinicos   FOR EACH ROW EXECUTE FUNCTION tg_actualizado_en();

-- Solo un usuario con rol doctor o administrador puede tener perfil de doctor.
CREATE FUNCTION tg_validar_perfil_doctor() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM usuarios u
                   WHERE u.id = NEW.usuario_id AND u.clinica_id = NEW.clinica_id
                     AND u.rol IN ('doctor', 'administrador')) THEN
        RAISE EXCEPTION 'El usuario % no puede tener perfil de doctor por su rol', NEW.usuario_id;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER t_doctores_rol BEFORE INSERT OR UPDATE ON doctores
    FOR EACH ROW EXECUTE FUNCTION tg_validar_perfil_doctor();

-- La auditoría no se modifica ni se borra.
CREATE FUNCTION tg_auditoria_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla auditoria es de solo inserción';
END $$;
CREATE TRIGGER t_auditoria_solo_insercion BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION tg_auditoria_inmutable();
CREATE TRIGGER t_auditoria_sin_truncate BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION tg_auditoria_inmutable();

-- ---------------------------------------------------------------------
-- 7. SEGURIDAD: RLS Y ROLES
--    La API fija la clínica en cada transacción:  SET LOCAL app.clinica_id = '<id>';
-- ---------------------------------------------------------------------
CREATE FUNCTION app_clinica_id() RETURNS bigint
LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.clinica_id', true), '')::bigint
$$;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'suscripciones','pagos','usuarios','doctores','sesiones','tokens_recuperacion',
        'pacientes','historiales_clinicos','citas','registros_clinicos','odontograma_hallazgos',
        'medicamentos','recetas','receta_detalles','reportes','copias_seguridad',
        'notificaciones','auditoria']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY aislamiento_clinica ON %I USING (clinica_id = app_clinica_id()) WITH CHECK (clinica_id = app_clinica_id())',
            t);
    END LOOP;
END $$;

-- Rol de la API: sin BYPASSRLS. Rol de plataforma: consola y webhook de pagos (omite RLS).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dental_app') THEN
        CREATE ROLE dental_app NOLOGIN NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dental_plataforma') THEN
        CREATE ROLE dental_plataforma NOLOGIN BYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO dental_app, dental_plataforma;

-- API de clínica: datos de la clínica activa; catálogos y planes solo lectura.
GRANT SELECT, INSERT, UPDATE, DELETE ON
    usuarios, doctores, sesiones, tokens_recuperacion, pacientes, historiales_clinicos,
    citas, registros_clinicos, odontograma_hallazgos, medicamentos, recetas, receta_detalles,
    reportes, copias_seguridad, notificaciones TO dental_app;
GRANT SELECT ON suscripciones, pagos, planes, piezas_dentales, condiciones_dentales,
    v_odontograma_actual, v_suscripcion_actual TO dental_app;
GRANT SELECT, INSERT ON auditoria TO dental_app;
GRANT SELECT (id, codigo, nombre, activa) ON clinicas TO dental_app;   -- para el inicio de sesión
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO dental_app;

-- Plataforma: altas de clínicas, suscripciones, pagos y webhook.
GRANT SELECT, INSERT, UPDATE ON clinicas, suscripciones, pagos, eventos_webhook TO dental_plataforma;
GRANT SELECT, INSERT, UPDATE ON planes TO dental_plataforma;
GRANT SELECT, INSERT, UPDATE ON usuarios_plataforma TO dental_plataforma;
GRANT SELECT, INSERT ON auditoria TO dental_plataforma;
GRANT SELECT ON usuarios TO dental_plataforma;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO dental_plataforma;

-- ---------------------------------------------------------------------
-- 8. DATOS BASE
-- ---------------------------------------------------------------------
INSERT INTO planes (codigo, nombre, precio_mensual, max_usuarios, max_pacientes, permite_excel, permite_respaldos) VALUES
    ('esencial',    'Esencial',     49.00,    3,  150, false, false),
    ('profesional', 'Profesional',  99.00,   10, 1500, true,  true),
    ('clinica',     'Clínica',     189.00, NULL, NULL, true,  true);

INSERT INTO piezas_dentales (codigo, cuadrante, posicion)
SELECT c * 10 + p, c, p
FROM generate_series(1, 8) AS c, generate_series(1, 8) AS p
WHERE c <= 4 OR p <= 5;

INSERT INTO condiciones_dentales (codigo, nombre) VALUES
    ('sano',               'Sano'),
    ('caries',             'Caries'),
    ('obturacion',         'Obturación'),
    ('sellante',           'Sellante'),
    ('endodoncia',         'Tratamiento de conductos'),
    ('corona',             'Corona'),
    ('implante',           'Implante'),
    ('puente',             'Puente'),
    ('fractura',           'Fractura'),
    ('ausente',            'Ausente'),
    ('extraccion_indicada','Extracción indicada');

COMMIT;
