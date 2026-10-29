"""
Dental Home Web — API Flask sobre PostgreSQL (db/schema.sql) + SPA estática.

Ejecutar:  python -m web.app             (desarrollo)
           gunicorn web.app:app           (producción)
Antes:     python -m web.db init          (crea la base, aplica el esquema y el rol de la API)
"""
import logging
import os
import secrets

from flask import Flask, jsonify, request, send_from_directory
from psycopg import errors

from web import api_clinica, api_cuenta, api_gestion, api_plataforma
from web.notificador import DATA_DIR

logging.getLogger("werkzeug").setLevel(logging.WARNING)
AQUI = os.path.dirname(os.path.abspath(__file__))


def _secret_key() -> str:
    if os.environ.get("DENTAL_SECRET_KEY"):
        return os.environ["DENTAL_SECRET_KEY"]
    os.makedirs(DATA_DIR, exist_ok=True)
    ruta = os.path.join(DATA_DIR, "secret.key")
    if not os.path.exists(ruta):
        with open(os.open(ruta, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
            f.write(secrets.token_urlsafe(48))
    with open(ruta) as f:
        return f.read().strip()


app = Flask(__name__, static_folder=os.path.join(AQUI, "static"), static_url_path="/static")
app.secret_key = _secret_key()
app.config.update(MAX_CONTENT_LENGTH=2 * 1024 * 1024, JSON_AS_ASCII=False)
for modulo in (api_cuenta, api_clinica, api_gestion, api_plataforma):
    app.register_blueprint(modulo.bp)

# Mensajes para las restricciones del esquema (nombre de restricción -> texto para el usuario)
RESTRICCIONES = {
    "citas_clinica_id_doctor_id_tstzrange_excl": "El doctor ya tiene una cita que se cruza con ese horario.",
    "pacientes_clinica_id_tipo_documento_numero_documento_key": "Ya existe un paciente con ese documento.",
    "usuarios_clinica_id_nombre_usuario_key": "Ese nombre de usuario ya está en uso en tu clínica.",
    "usuarios_clinica_id_correo_key": "Ese correo ya pertenece a otro usuario de tu clínica.",
    "doctores_clinica_id_numero_colegiatura_key": "Esa colegiatura ya está registrada para otro doctor.",
    "registros_clinicos_clinica_id_cita_id_key": "Esta cita ya tiene una consulta registrada.",
    "recetas_clinica_id_registro_clinico_id_key": "Esta consulta ya tiene una receta.",
    "receta_detalles_receta_id_medicamento_id_key": "Hay un medicamento repetido en la receta.",
    "usuarios_nombre_usuario_check": "El usuario debe tener 3 a 32 caracteres: letras minúsculas, números, punto, guion o guion bajo.",
    "pacientes_check": "El DNI debe tener 8 dígitos.",
    "pacientes_fecha_nacimiento_check": "La fecha de nacimiento no puede ser futura.",
    "usuarios_plataforma_correo_key": "Ya existe un administrador con ese correo.",
}


def _mensaje_bd(e, por_defecto):
    nombre = getattr(e.diag, "constraint_name", None) or ""
    return RESTRICCIONES.get(nombre, por_defecto)


@app.errorhandler(ValueError)
def _err_valor(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(PermissionError)
def _err_permiso(e):
    return jsonify(error=str(e)), 403


@app.errorhandler(errors.ExclusionViolation)
def _err_exclusion(e):
    return jsonify(error=_mensaje_bd(e, "El horario se cruza con otra cita.")), 409


@app.errorhandler(errors.UniqueViolation)
def _err_unico(e):
    return jsonify(error=_mensaje_bd(e, "Ya existe un registro con esos datos.")), 409


@app.errorhandler(errors.CheckViolation)
def _err_check(e):
    return jsonify(error=_mensaje_bd(e, "Algún dato no cumple el formato esperado.")), 400


@app.errorhandler(errors.ForeignKeyViolation)
def _err_fk(_e):
    return jsonify(error="El registro relacionado no existe o pertenece a otra clínica."), 400


@app.errorhandler(errors.RaiseException)
def _err_trigger(e):
    return jsonify(error=e.diag.message_primary or "Operación no permitida."), 400


@app.errorhandler(errors.InsufficientPrivilege)
def _err_privilegio(_e):
    logging.exception("Privilegio insuficiente en la base de datos")
    return jsonify(error="No tienes permisos para esta acción."), 403


@app.errorhandler(413)
def _err_grande(_e):
    return jsonify(error="La solicitud es demasiado grande."), 413


@app.errorhandler(404)
def _err_404(e):
    if request.path.startswith("/api/"):
        return jsonify(error="Recurso no encontrado."), 404
    return e


@app.after_request
def cabeceras(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'"
    )
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html", max_age=0)


@app.get("/healthz")
def healthz():
    from web import db
    with db.transaccion() as con:
        con.execute("SELECT 1")
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
