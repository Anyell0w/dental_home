# Dental Home — Sistema de Gestión Odontológica

Aplicación de escritorio (Tkinter) para la gestión integral de un consultorio dental:
pacientes, agenda de citas, historial clínico, recetas en PDF, reportes (PDF/Excel),
copias de seguridad y administración de usuarios por roles.

# INTEGRANTES
- Angello Marcelo Zamora Valencia
- Ronaldo Carlos Mamani Mena
- Lizbeth Estefany Cáceres Tacora
- Tania Karin Butrón Maquera

## Versión web (SaaS por suscripción)

API Flask sobre **PostgreSQL 16** con el esquema de `db/schema.sql` (modelo ER en 3FN, una base compartida,
aislamiento por clínica con `clinica_id` + Row Level Security) y una SPA ligera (Alpine.js) en `web/static`.
La aplicación de escritorio (Tkinter + SQLite) sigue funcionando de forma independiente.

```bash
pip install -r requirements.txt
# 1) crear la base, aplicar el esquema y el rol de login de la API (como superusuario)
DATABASE_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres python -m web.db init
# 2) (opcional) administrador de la consola de plataforma
python -m web.db admin-plataforma admin@dentalhome.pe
# 3) servidor
python -m web.app                    # http://localhost:5000   ·  consola: /#/plataforma
# todo junto con Docker:  docker compose up
```

En **Windows (PowerShell)** las variables se definen así (la contraseña de `postgres` solo va en `DATABASE_ADMIN_URL`):

```powershell
$env:DATABASE_ADMIN_URL = "postgresql://postgres:TU_CLAVE@localhost:5432/postgres"
python -m web.db init        # crea el rol dental_api; la API usa DATABASE_URL (por defecto dental_api/dental_api)
python -m web.app
```

| Variable | Uso |
|---|---|
| `DATABASE_URL` | Conexión de la API (por defecto `postgresql://dental_api:dental_api@localhost:5432/dental_home`) |
| `DATABASE_ADMIN_URL`, `DENTAL_API_PASSWORD` | Solo para `python -m web.db init` |
| `DENTAL_TZ` | Zona horaria de la clínica (por defecto `America/Lima`) |
| `DENTAL_SECRET_KEY`, `DENTAL_HTTPS=1` | Firma de cookies de la consola y cookie segura |
| `DENTAL_PASARELA`, `DENTAL_WEBHOOK_SECRET` | Pasarela de pago (`simulada` en desarrollo) y secreto HMAC del webhook |
| `DENTAL_SMTP_*`, `DENTAL_BASE_URL` | Correo saliente (sin SMTP los mensajes van a `data/outbox.log`) |
| `DENTAL_DATA_DIR` | Copias de seguridad y bandeja de salida |

**Cómo usa la API el esquema**
- **Roles de PostgreSQL:** la API entra con `dental_api` (sin privilegios propios). Cada petición abre una transacción con
  `SET LOCAL ROLE dental_app` + `app.clinica_id` (RLS); el registro de clínicas, los pagos, el webhook y la consola usan
  `dental_plataforma`. Ninguna consulta de la app filtra por clínica a mano: lo garantiza la base.
- **Agenda:** la restricción de exclusión de `citas` impide cruces por doctor; la API traduce el error a un mensaje.
- **Odontograma:** cada cambio es un hallazgo fechado en `odontograma_hallazgos`; el estado vigente sale de
  `v_odontograma_actual` (dentición permanente y temporal).
- **Consultas:** un `registro_clinico` por cita. La "atención sin cita" crea la cita en el momento.
- **Recetas:** catálogo propio de `medicamentos` por clínica; el PDF se genera al descargarlo.
- **Seguridad:** argon2id, bloqueo de 15 min tras 5 intentos, sesiones en `sesiones` (solo hash del token, expiración por inactividad),
  recuperación de contraseña con `tokens_recuperacion` de un solo uso y `auditoria` de solo inserción (vista *Auditoría*).
- **Suscripción y pagos:** `v_suscripcion_actual` decide si la clínica puede escribir (HTTP 402 si venció). Pagar crea un `pago`
  pendiente; el plan solo cambia cuando llega el webhook firmado (`POST /api/webhooks/<pasarela>`, idempotente con `eventos_webhook`).
  En desarrollo, la pasarela de prueba (`/#/pago/<ref>`) envía ese mismo webhook.
- **Tareas programadas** (`python -m web.tareas recordatorios|avisos|copias|todo`): recordatorios de cita 24 h antes por
  correo/WhatsApp (`notificaciones`), avisos de vencimiento y copias automáticas (`copias_seguridad`). Ejemplo de cron:
  `*/5 * * * * python -m web.tareas recordatorios` y `0 3 * * * python -m web.tareas avisos && python -m web.tareas copias`.

**Pruebas:** `python -m pytest tests/` (requiere la base inicializada) cubre aislamiento RLS, cruces de citas, bloqueo,
recuperación de contraseña, webhook idempotente, reportes, copias y tareas.

**Diseño:** paleta, tipografías (Manrope y Montserrat, incluidas en `web/static/vendor/fonts`), logo y animaciones del landing;
guía en `.claude/skills/dental-ui/SKILL.md`.

**Brief corporativo** (empresa, objetivos, competencia, presupuesto y plazos): [`docs/brief-corporativo-dental-home.pdf`](docs/brief-corporativo-dental-home.pdf). Se regenera con `python docs/brief_corporativo.py` (los supuestos financieros están en ese archivo).

### Pendiente antes de cobrar de verdad
1. **Pasarela real:** implementar `crear_cobro()` en `web/pasarela.py` (Culqi, Niubiz, Mercado Pago…) y apuntar su webhook a la API.
2. **Proveedor de WhatsApp** en `web/notificador.py` y SMTP real para los correos.
3. HTTPS, copias externas de la base (`pg_dump`) y monitoreo.

## Arquitectura

Arquitectura en capas con inyección de dependencias desde `main.py`:

```
Vistas (Tkinter)  →  Controladores (lógica)  →  DAO (acceso a datos)  →  SQLite
```

- `models/` — entidades del dominio (Paciente, Cita, Receta, Usuario, etc.).
- `dao/` — gestores de persistencia (una tabla por gestor).
- `controllers/` — reglas de negocio y validaciones.
- `views/` — interfaz gráfica por módulo.
- `utils/` — tema visual, generadores de PDF/Excel y respaldos.
- `config.py` — rutas, logging y parámetros de seguridad.
- `database.py` — conexión Singleton y creación/migración de esquema.

## Requisitos

- Python 3.10 o superior (probado en 3.14).
- Tkinter (incluido en la instalación estándar de Python en Windows).

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

Desde la carpeta `dental_home_alpha`:

```bash
python main.py
```

La base de datos `dental_home.db` y las carpetas `backups/` y `exports/` se crean
automáticamente en el primer arranque.

## Usuarios de prueba (seeding automático)

| Usuario   | Contraseña  | Rol           |
|-----------|-------------|---------------|
| `admin`   | `admin123`  | Administrador |
| `doctor1` | `doctor123` | Doctor        |
| `secret1` | `secret123` | Secretaria    |

## Módulos por rol

- **Administrador:** Inicio, Pacientes, Citas, Reportes, Copias de Seguridad, Usuarios.
- **Doctor:** Inicio, Pacientes, Citas, Historial Clínico.
- **Secretaria:** Inicio, Pacientes, Citas.

## Funcionalidades principales

- **Pacientes:** alta/edición con creación automática del historial clínico.
- **Citas:** agenda por día/semana/mes, filtro por doctor, completar/reprogramar/cancelar.
- **Historial clínico:** registros por consulta, observaciones con bitácora, citas del
  paciente y emisión de recetas.
- **Recetas:** formulario de medicamentos y generación de PDF con ReportLab.
- **Reportes:** tipos Citas, Pacientes y Actividad; filtro por rango de fechas;
  exportación a PDF o Excel.
- **Copias de seguridad:** respaldo manual y daemon automático cada 24 h, ambos
  auditados en la base de datos.
- **Usuarios:** creación, activación/desactivación y restablecimiento de contraseña.

## Seguridad

- Contraseñas con hash SHA-256 (definido en `config.MIN_PASSWORD_LENGTH`, mínimo 8).
- Expiración de sesión por inactividad (`config.SESSION_TIMEOUT_MINUTES`, 30 min).

## Notas

- Los reportes se guardan en `exports/reportes/` y las recetas en `exports/recetas/`.
- Los respaldos se generan comprimidos (`.zip`) en `backups/`.
- Los errores se registran en `log.txt`.
