# Dental Home — Sistema de Gestión Odontológica

Aplicación de escritorio (Tkinter) para la gestión integral de un consultorio dental:
pacientes, agenda de citas, historial clínico, recetas en PDF, reportes (PDF/Excel),
copias de seguridad y administración de usuarios por roles.

# INTEGRANTES
- Angello Marcelo Zamora Valencia
- Ronaldo Carlos Mamani Mena
- Lizbeth Estefany Cáceres Tacora
- Tania Karin Butrón Maquera

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
