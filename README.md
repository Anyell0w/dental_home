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

La lógica (modelos, DAO, controladores) es la misma del escritorio; `web/` la expone como
API Flask y agrega una interfaz moderna en el navegador.

```bash
pip install -r requirements.txt
python -m web.app                    # http://localhost:5000
# producción: gunicorn -w 2 -k gthread --threads 4 web.app:app   (o `docker build .`)
```

- **Multi-clínica:** cada consultorio tiene su propio SQLite en `data/clinicas/<código>/` (aislamiento total);
  `data/plataforma.db` guarda clínicas, plan y estado de suscripción. Variables: `DENTAL_DATA_DIR`,
  `DENTAL_SECRET_KEY`, `DENTAL_HTTPS=1` (cookie segura), `PORT`.
- **Planes** (`web/platform.py`): Esencial / Profesional / Clínica, con límites de usuarios y pacientes,
  Excel solo desde Profesional, 14 días de prueba. Vencida la prueba o cancelado el plan, la clínica queda
  en solo lectura (HTTP 402 al escribir).
- **Roles:** Administrador (todo), Doctor (agenda propia, historial, odontograma, recetas), Secretaria (pacientes y citas).
  El Administrador también accede al historial clínico (en un consultorio pequeño suele ser el propio odontólogo).
- **Frontend sin build:** Alpine.js + three.js vendorizados en `web/static/vendor` (landing con diente 3D).
  Guía de diseño en `.claude/skills/dental-ui/SKILL.md`.

### Pendiente antes de cobrar de verdad
1. **Pasarela de pago:** `POST /api/suscripcion/plan` activa el plan *sin cobrar* (modo demo). Integrar Stripe/Culqi/MercadoPago
   y activar el plan desde su webhook.
2. **Contraseñas:** el modelo original usa SHA-256 sin sal (`Usuario.hashear_contrasena`); migrar a bcrypt/argon2 antes de producción.
3. HTTPS, correo de recuperación de contraseña y respaldos externos de `data/`.

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
