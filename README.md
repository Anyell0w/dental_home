# Dental Home — Sistema de Gestión Odontológica

**Dental Home** es un sistema de gestión para consultorios odontológicos. Permite administrar pacientes, citas, historiales clínicos, recetas médicas, reportes y usuarios según sus roles.

El proyecto cuenta con dos versiones:
- **Aplicación de escritorio:** desarrollada con Python, Tkinter y SQLite.
- **Aplicación web (SaaS):** desarrollada con Flask, PostgreSQL y Alpine.js, diseñada para ofrecer el servicio a diferentes clínicas mediante suscripciones.

## Integrantes

- Angello Marcelo Zamora Valencia
- Lizbeth Estefany Cáceres Tacora
- Tania Karin Butrón Maquera

---

# 1. Aplicación web

La versión web permite que diferentes clínicas utilicen el sistema de manera independiente, compartiendo una misma base de datos.

### Tecnologías utilizadas

- **Backend:** Python y Flask.
- **Base de datos:** PostgreSQL 16.
- **Frontend:** HTML, CSS, JavaScript y Alpine.js.
- **Arquitectura de datos:** modelo relacional en tercera forma normal (3FN).
- **Seguridad:** aislamiento de información por clínica mediante `clinica_id` y Row Level Security (RLS).

La aplicación de escritorio continúa funcionando de manera independiente, utilizando SQLite.

## 1.1. Instalación y configuración

Primero, instala las dependencias:

```bash
pip install -r requirements.txt
```

Después, configura PostgreSQL y ejecuta los siguientes pasos.

**Paso 1. Crear la base de datos y aplicar el esquema:**

```bash
DATABASE_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres python -m web.db init
```

**Paso 2. Crear un administrador de la plataforma (opcional):**

```bash
python -m web.db admin-plataforma admin@dentalhome.pe
```

**Paso 3. Iniciar el servidor web:**

```bash
python -m web.app
```

La aplicación estará disponible en:

- Aplicación web: http://localhost:5000
- Consola de administración: http://localhost:5000/#/plataforma

**Alternativa: ejecutar con Docker**

```bash
docker compose up
```

## 1.2. Variables de entorno

La aplicación utiliza las siguientes variables para configurar sus servicios:

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Conexión de la API con PostgreSQL. |
| `DATABASE_ADMIN_URL` | Conexión de administrador para inicializar la base de datos. |
| `DENTAL_API_PASSWORD` | Contraseña del usuario de conexión de la API. |
| `DENTAL_TZ` | Zona horaria de la clínica. Por defecto: `America/Lima`. |
| `DENTAL_SECRET_KEY` | Clave para firmar las cookies de sesión. |
| `DENTAL_HTTPS` | Activa las cookies seguras cuando se utiliza HTTPS. |
| `DENTAL_PASARELA` | Configuración de la pasarela de pagos. |
| `DENTAL_WEBHOOK_SECRET` | Clave para verificar los webhooks de pago. |
| `DENTAL_SMTP_*` | Configuración del servicio de correo electrónico. |
| `DENTAL_BASE_URL` | Dirección principal de la aplicación web. |
| `DENTAL_DATA_DIR` | Directorio para copias de seguridad y mensajes pendientes. |

---

# 2. Funcionamiento de la versión web

### 2.1. Base de datos y seguridad

La aplicación utiliza diferentes roles de PostgreSQL para controlar el acceso a la información:

- `dental_api`: usuario con el que se conecta la API.
- `dental_app`: rol utilizado para las operaciones de cada clínica.
- `dental_plataforma`: rol encargado de las operaciones administrativas de la plataforma.

Cada petición establece el identificador de la clínica mediante `app.clinica_id`. PostgreSQL utiliza Row Level Security (RLS) para impedir que una clínica acceda a los datos de otra.

### 2.2. Gestión de citas

El sistema permite registrar, modificar y administrar citas odontológicas. Además, la base de datos cuenta con una restricción que impide que un mismo doctor tenga dos citas en horarios superpuestos.

### 2.3. Odontograma

Los cambios realizados en el odontograma se almacenan como registros históricos en `odontograma_hallazgos`.

La vista `v_odontograma_actual` permite consultar el estado actual de los dientes, tanto de la dentición permanente como temporal.

### 2.4. Historial clínico

Cada cita tiene asociado un registro clínico. También es posible registrar una atención sin cita previa, creando automáticamente la cita correspondiente.

### 2.5. Recetas médicas

El sistema cuenta con un catálogo de medicamentos independiente para cada clínica. Las recetas se generan en formato PDF cuando el usuario solicita descargarlas.

### 2.6. Seguridad de usuarios

Se implementan las siguientes medidas:

- Protección de contraseñas mediante Argon2id.
- Bloqueo de acceso durante 15 minutos después de 5 intentos fallidos.
- Control de sesiones mediante tokens almacenados como hashes.
- Expiración de sesiones por inactividad.
- Recuperación de contraseñas mediante tokens de un solo uso.
- Registro de actividades mediante una auditoría que no permite modificar ni eliminar los registros.

### 2.7. Suscripciones y pagos

Cada clínica cuenta con una suscripción que determina qué operaciones puede realizar.

- El sistema verifica el estado de la suscripción antes de permitir operaciones de escritura.
- Cuando una suscripción vence, la API responde con el código HTTP 402.
- Los pagos se registran inicialmente como pendientes.
- La suscripción se actualiza cuando se recibe y verifica el webhook de la pasarela de pago.

En desarrollo se utiliza una pasarela de prueba que permite simular el proceso de pago.

### 2.8. Tareas automáticas

El sistema permite ejecutar tareas programadas para facilitar la administración de las clínicas:

- Envío de recordatorios de citas 24 horas antes.
- Avisos sobre el vencimiento de suscripciones.
- Generación automática de copias de seguridad.

Para ejecutar estas tareas:

```bash
python -m web.tareas recordatorios
python -m web.tareas avisos
python -m web.tareas copias
```

También se pueden ejecutar todas las tareas:

```bash
python -m web.tareas todo
```

---

# 3. Arquitectura del sistema

## 3.1. Aplicación de escritorio

La versión de escritorio utiliza una arquitectura en capas, donde cada componente tiene una responsabilidad específica.

```text
        VISTAS (Tkinter)
               |
               v
     CONTROLADORES
       (Lógica de negocio)
               |
               v
          DAO
    (Acceso a datos)
               |
               v
        BASE DE DATOS
           (SQLite)
```

### Organización de carpetas

| Carpeta / Archivo | Responsabilidad |
|---|---|
| `models/` | Contiene las entidades del sistema, como Paciente, Cita, Receta y Usuario. |
| `dao/` | Gestiona las operaciones de acceso y almacenamiento de datos. |
| `controllers/` | Contiene la lógica del sistema, reglas de negocio y validaciones. |
| `views/` | Contiene las interfaces gráficas de cada módulo. |
| `utils/` | Incluye herramientas para generar PDF, Excel, respaldos y administrar el diseño visual. |
| `config.py` | Define las rutas, parámetros de configuración y seguridad. |
| `database.py` | Administra la conexión con SQLite y la creación o migración de tablas. |
| `main.py` | Punto de entrada de la aplicación de escritorio. |

## 3.2. Arquitectura de la versión web

La versión web utiliza Flask como backend y PostgreSQL como sistema de almacenamiento.

```text
       USUARIO
          |
          v
   INTERFAZ WEB (SPA)
      Alpine.js
          |
          v
      API REST
        Flask
          |
          v
    LÓGICA DE NEGOCIO
          |
          v
      POSTGRESQL
    (Base de datos)
```

La arquitectura permite gestionar varias clínicas manteniendo separada la información de cada una.

---

# 4. Requisitos del sistema

Para ejecutar la aplicación de escritorio se necesita:

- Python 3.10 o superior.
- Tkinter.
- SQLite.
- Las dependencias especificadas en `requirements.txt`.

Para ejecutar la versión web también se necesita:

- PostgreSQL 16.
- Flask y las dependencias del proyecto.
- Configuración de las variables de entorno.

---

# 5. Instalación de la aplicación de escritorio

**Paso 1. Instalar las dependencias:**

```bash
pip install -r requirements.txt
```

**Paso 2. Ejecutar el sistema:**

Desde la carpeta principal del proyecto:

```bash
python main.py
```

**Paso 3. Inicialización automática:**

En el primer inicio, el sistema crea automáticamente:

- La base de datos `dental_home.db`.
- La carpeta `backups/` para almacenar copias de seguridad.
- La carpeta `exports/` para guardar los documentos generados.

---

# 6. Usuarios de prueba

La aplicación de escritorio cuenta con usuarios de prueba que se generan automáticamente.

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `admin123` | Administrador |
| `doctor1` | `doctor123` | Doctor |
| `secret1` | `secret123` | Secretaria |

**Importante:** Estas credenciales son únicamente para pruebas. Se recomienda cambiarlas antes de utilizar el sistema en un entorno real.

---

# 7. Módulos según el tipo de usuario

El acceso a las funcionalidades depende del rol asignado a cada usuario.

| Módulo | Administrador | Doctor | Secretaria |
|---|:---:|:---:|:---:|
| Inicio | ✓ | ✓ | ✓ |
| Pacientes | ✓ | ✓ | ✓ |
| Citas | ✓ | ✓ | ✓ |
| Historial clínico | — | ✓ | — |
| Reportes | ✓ | — | — |
| Copias de seguridad | ✓ | — | — |
| Gestión de usuarios | ✓ | — | — |

### Responsabilidades de cada rol

- **Administrador:** administra los usuarios, pacientes, citas, reportes y copias de seguridad.
- **Doctor:** consulta los pacientes, administra sus citas y registra la información de los historiales clínicos.
- **Secretaria:** registra pacientes y gestiona la programación de citas.

---

# 8. Funcionalidades principales

### 8.1. Gestión de pacientes
- Registrar nuevos pacientes.
- Editar información personal.
- Crear automáticamente el historial clínico del paciente.

### 8.2. Gestión de citas
- Visualizar la agenda por día, semana o mes.
- Filtrar citas por doctor.
- Registrar y reprogramar citas.
- Completar o cancelar citas.
- Evitar cruces de horarios para un mismo doctor.

### 8.3. Historial clínico
- Registrar información de cada consulta.
- Guardar observaciones y antecedentes.
- Consultar las citas anteriores del paciente.
- Emitir recetas médicas.

### 8.4. Recetas médicas
- Registrar medicamentos y sus indicaciones.
- Generar recetas en formato PDF.
- Guardar los documentos generados.

### 8.5. Reportes
El sistema permite generar reportes de:

- Citas.
- Pacientes.
- Actividad del sistema.

Los reportes pueden filtrarse por fechas y exportarse en PDF o Excel.

### 8.6. Copias de seguridad
- Generar respaldos manuales.
- Ejecutar respaldos automáticos cada 24 horas.
- Almacenar las copias en archivos comprimidos `.zip`.
- Registrar las operaciones de respaldo.

### 8.7. Gestión de usuarios
- Crear usuarios.
- Activar o desactivar cuentas.
- Restablecer contraseñas.
- Asignar roles y permisos.

---

# 9. Seguridad

La aplicación de escritorio incorpora las siguientes medidas:

- Almacenamiento de contraseñas mediante hash SHA-256.
- Longitud mínima de contraseña de 8 caracteres.
- Expiración de sesión después de 30 minutos de inactividad.
- Control de acceso según el rol del usuario.

La versión web implementa mecanismos adicionales, como Argon2id, bloqueo por intentos fallidos, sesiones protegidas y aislamiento de datos mediante RLS.

---

# 10. Ubicación de los archivos generados

Los documentos y archivos creados por la aplicación de escritorio se almacenan en las siguientes ubicaciones:

| Archivo o carpeta | Contenido |
|---|---|
| `dental_home.db` | Base de datos principal. |
| `backups/` | Copias de seguridad comprimidas en ZIP. |
| `exports/reportes/` | Reportes generados en PDF y Excel. |
| `exports/recetas/` | Recetas médicas en PDF. |
| `log.txt` | Registro de errores y eventos del sistema. |

---

# 11. Pruebas del sistema

Para ejecutar las pruebas automatizadas de la versión web:

```bash
python -m pytest tests/
```

Las pruebas requieren que la base de datos esté inicializada.

Se comprueban aspectos como:

- Aislamiento de datos entre clínicas mediante RLS.
- Prevención de cruces de citas.
- Bloqueo de usuarios por intentos fallidos.
- Recuperación de contraseñas.
- Validación de pagos y webhooks.
- Generación de reportes.
- Copias de seguridad.
- Ejecución de tareas programadas.

---

# 12. Diseño de la interfaz

El diseño visual de Dental Home utiliza:

- **Manrope y Montserrat:** tipografías principales.
- Paleta de colores propia.
- Logotipo institucional del sistema.
- Animaciones y elementos visuales para mejorar la experiencia del usuario.

Las fuentes se encuentran en `web/static/vendor/fonts`.

La guía de diseño está documentada en:

```text
.claude/skills/dental-ui/SKILL.md
```

---

# 13. Documentación corporativa

El proyecto también cuenta con un documento que describe la propuesta empresarial de Dental Home.

Incluye:

- Descripción de la empresa.
- Objetivos del proyecto.
- Análisis de la competencia.
- Presupuesto.
- Plazos de desarrollo.

Documento: [`docs/brief-corporativo-dental-home.pdf`](docs/brief-corporativo-dental-home.pdf)

Para volver a generarlo:

```bash
python docs/brief_corporativo.py
```

---

# 14. Pendientes para producción

Antes de ofrecer el servicio comercialmente y recibir pagos reales, es necesario completar los siguientes puntos:

1. **Integración de una pasarela de pago real:** implementar `crear_cobro()` en `web/pasarela.py`, utilizando un proveedor como Culqi, Niubiz o Mercado Pago.
2. **Integración de WhatsApp:** configurar un proveedor real en `web/notificador.py`.
3. **Configuración de correo electrónico:** establecer un servidor SMTP real para el envío de notificaciones.
4. **Seguridad del servidor:** configurar HTTPS y cookies seguras.
5. **Copias de seguridad externas:** implementar respaldos de PostgreSQL mediante `pg_dump`.
6. **Monitoreo:** incorporar mecanismos para supervisar el funcionamiento del servidor y detectar errores.

---

**Dental Home** busca facilitar la administración de consultorios odontológicos mediante herramientas que permitan organizar la información de los pacientes, optimizar la gestión de citas y mejorar el seguimiento de la atención clínica.