"""
Dental Home Web — API Flask multi-clínica.

Reutiliza sin cambios la lógica del sistema de escritorio (models / dao /
controllers). Este módulo solo traduce HTTP ⇄ controladores, aplica roles y
los límites del plan de suscripción.

Ejecutar:  python -m web.app        (desarrollo)
           gunicorn web.app:app      (producción)
"""
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, jsonify, request, send_file, send_from_directory, session

from config import MIN_PASSWORD_LENGTH, SESSION_TIMEOUT_MINUTES
from models.usuario import Administrador, Doctor, Secretaria, Usuario
from web import tenant
from web.platform import PLANES, Plataforma

logging.getLogger("werkzeug").setLevel(logging.WARNING)  # config.py enruta el log raíz a log.txt
AQUI = os.path.dirname(os.path.abspath(__file__))
plataforma = Plataforma()

app = Flask(__name__, static_folder=os.path.join(AQUI, "static"), static_url_path="/static")
app.secret_key = plataforma.secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("DENTAL_HTTPS") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_TIMEOUT_MINUTES),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    JSON_AS_ASCII=False,
)

ROLES = ("Doctor", "Secretaria", "Administrador")
TURNOS = ("Mañana", "Tarde", "Tiempo Completo")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------- #
#  Utilidades
# --------------------------------------------------------------------------- #
def texto(v, maximo=200, obligatorio=False, nombre="campo") -> str:
    v = (v or "")
    if not isinstance(v, str):
        raise ValueError(f"Valor inválido en {nombre}.")
    v = v.strip()
    if obligatorio and not v:
        raise ValueError(f"El campo {nombre} es obligatorio.")
    if len(v) > maximo:
        raise ValueError(f"El campo {nombre} excede {maximo} caracteres.")
    return v


def iso_a_dmy(iso: str) -> str:
    """El modelo Paciente guarda DD/MM/AAAA; el navegador envía AAAA-MM-DD."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        raise ValueError("Fecha de nacimiento inválida.")


def dmy_a_iso(dmy: str) -> str:
    try:
        return datetime.strptime(dmy, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def fecha_iso(v, nombre="fecha") -> str:
    try:
        return datetime.strptime(v or "", "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(f"La {nombre} no es válida (AAAA-MM-DD).")


def hora_hhmm(v) -> str:
    try:
        return datetime.strptime(v or "", "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError("La hora no es válida (HH:MM).")


def paciente_dict(p) -> dict:
    try:
        edad = p.calcular_edad()
    except ValueError:
        edad = None
    return {
        "id": p.id, "nombre": p.nombre, "apellido": p.apellido, "dni": p.dni,
        "telefono": p.telefono or "", "sexo": p.sexo, "direccion": p.direccion or "",
        "fechaNacimiento": dmy_a_iso(p.fecha_nacimiento), "edad": edad,
        "activo": p.estado, "nombreCompleto": p.obtener_nombre_completo(),
    }


def usuario_dict(u) -> dict:
    return {
        "id": u.id, "usuario": u.nombreUsuario, "rol": u.rol, "activo": u.activo,
        "creado": (u._fechaCreacion or "")[:10],
        "colegiatura": getattr(u, "numeroColegiatura", None),
        "turno": getattr(u, "_turno", None),
    }


def cita_dict(c, pacientes, doctores) -> dict:
    p = pacientes.get(c.pacienteId)
    d = doctores.get(c.doctorId)
    return {
        "id": c.id, "fecha": c.fecha, "hora": c.hora, "estado": c.estado,
        "motivoCancelacion": c.motivoCancelacion or "",
        "pacienteId": c.pacienteId, "paciente": p.obtener_nombre_completo() if p else "—",
        "dni": p.dni if p else "", "doctorId": c.doctorId,
        "doctor": d.nombreUsuario if d else "—",
    }


def receta_dict(r) -> dict:
    return {
        "id": r.id, "fecha": r.fecha, "indicaciones": r.indicacionesGenerales or "",
        "medicamentos": [
            {"id": m.id, "nombre": m.nombre, "cantidad": m.cantidad, "indicaciones": m.indicaciones}
            for m in r.obtener_medicamentos()
        ],
    }


def registro_dict(r, doctores, receta=None) -> dict:
    d = doctores.get(r.doctorId)
    return {
        "id": r.id, "citaId": r.citaId, "fecha": r.fechaConsulta,
        "diagnostico": r.diagnostico, "tratamiento": r.tratamiento,
        "observaciones": (r.observaciones or "").strip(),
        "doctor": d.nombreUsuario if d else "—",
        "receta": receta_dict(receta) if receta else None,
    }


def dentro_de(ruta: str, base: str) -> bool:
    ruta, base = os.path.realpath(ruta), os.path.realpath(base)
    return ruta.startswith(base + os.sep)


# --------------------------------------------------------------------------- #
#  Autenticación, roles y suscripción
# --------------------------------------------------------------------------- #
_intentos = {}  # (ip, clinica, usuario) -> (fallos, bloqueado_hasta)


def _bloqueado(clave) -> bool:
    fallos, hasta = _intentos.get(clave, (0, 0))
    return fallos >= 5 and time.time() < hasta


def _registrar_fallo(clave) -> None:
    fallos, _ = _intentos.get(clave, (0, 0))
    _intentos[clave] = (fallos + 1, time.time() + 300)


def api(roles=None, escritura=False, publica=False):
    """Decorador: sesión + inquilino + rol + suscripción vigente (si escribe)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if request.method != "GET" and request.headers.get("X-Requested-With") != "fetch":
                return jsonify(error="Solicitud no permitida."), 403  # defensa CSRF
            if publica:
                return fn(*a, **kw)
            cid, uid = session.get("clinica_id"), session.get("usuario_id")
            clinica = plataforma.por_id(cid) if cid else None
            if not clinica or not uid:
                session.clear()
                return jsonify(error="Sesión expirada. Inicia sesión de nuevo."), 401
            g.clinica = clinica
            g.sub = Plataforma.estado_suscripcion(clinica)
            g.t = tenant.abrir(plataforma.rutas(clinica["slug"]), clinica["nombre"], uid)
            g.user = g.t.usuario._usuario_activo
            if not g.user or not g.user.activo:
                session.clear()
                return jsonify(error="Tu usuario ya no está activo."), 401
            if roles and g.user.rol not in roles:
                return jsonify(error="No tienes permisos para esta acción."), 403
            if escritura and not g.sub["vigente"]:
                return jsonify(error="Tu suscripción no está activa. Elige un plan para continuar.",
                               codigo="suscripcion"), 402
            session.permanent = True  # renueva el tiempo de inactividad
            return fn(*a, **kw)
        return wrapper
    return deco


@app.teardown_request
def cerrar_conexion(_exc):
    t = g.pop("t", None)
    if t is not None:
        t.con.close()


@app.errorhandler(ValueError)
def _err_valor(e):
    return jsonify(error=str(e)), 400


@app.errorhandler(PermissionError)
def _err_permiso(e):
    return jsonify(error=str(e)), 403


@app.errorhandler(sqlite3.IntegrityError)
def _err_integridad(e):
    return jsonify(error="No se pudo guardar: los datos entran en conflicto con un registro existente."), 400


@app.errorhandler(413)
def _err_grande(_e):
    return jsonify(error="La solicitud es demasiado grande."), 413


@app.after_request
def cabeceras(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; object-src 'self'"
    )
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------- #
#  Sitio estático
# --------------------------------------------------------------------------- #
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html", max_age=0)


@app.get("/healthz")
def healthz():
    return "ok"


# --------------------------------------------------------------------------- #
#  Cuenta / plataforma
# --------------------------------------------------------------------------- #
@app.get("/api/planes")
def planes():
    return jsonify(list(PLANES.values()))


def _contexto():
    uso = {
        "usuarios": sum(1 for u in g.t.dao_usuario.listar_todos() if u.activo),
        "pacientes": len(g.t.dao_paciente.listar_todos(solo_activos=False)),
    }
    sub = dict(g.sub)
    return {
        "usuario": usuario_dict(g.user),
        "clinica": {"nombre": g.clinica["nombre"], "slug": g.clinica["slug"], "email": g.clinica["email"]},
        "suscripcion": sub, "uso": uso,
    }


@app.get("/api/me")
def me():
    if not session.get("usuario_id"):
        return jsonify(usuario=None)  # visitante: no es un error
    return _me_autenticado()


@api()
def _me_autenticado():
    return jsonify(_contexto())


def _sembrar_demo(t, admin_id):
    """Datos de ejemplo para que la clínica nueva no empiece vacía."""
    hash_aleatorio = Usuario.hashear_contrasena(secrets.token_urlsafe(16))
    doc_id = t.dao_usuario.guardar(Doctor(None, "dra.rivera", hash_aleatorio, True, None, "COP-12345"))
    doc2_id = t.dao_usuario.guardar(Doctor(None, "dr.mamani", hash_aleatorio, True, None, "COP-67890"))
    pacientes = [
        ("Lucía", "Fernández", "40123456", "987 654 321", "F", "1991-04-12"),
        ("Carlos", "Quispe", "41234567", "976 543 210", "M", "1984-09-30"),
        ("Valeria", "Condori", "42345678", "965 432 109", "F", "2001-01-22"),
        ("Mateo", "Huanca", "43456789", "954 321 098", "M", "2015-07-08"),
        ("Rosa", "Apaza", "44567890", "943 210 987", "F", "1968-11-03"),
    ]
    ids = []
    for n, a, dni, tel, sx, nac in pacientes:
        ids.append(t.paciente.registrar_paciente(n, a, dni, tel, sx, iso_a_dmy(nac), "Puno", admin_id).id)
    hoy = datetime.now()
    plan = [(0, doc_id, "09:00"), (1, doc_id, "10:00"), (2, doc2_id, "11:30"), (3, doc_id, "15:00"), (4, doc2_id, "16:30")]
    for i, d, h in plan:
        t.cita.programar_cita(ids[i], d, hoy.strftime("%Y-%m-%d"), h)
    t.cita.programar_cita(ids[0], doc_id, (hoy + timedelta(days=1)).strftime("%Y-%m-%d"), "09:30")
    t.cita.programar_cita(ids[2], doc2_id, (hoy + timedelta(days=2)).strftime("%Y-%m-%d"), "10:00")


@app.post("/api/registro")
@api(publica=True)
def registro():
    d = request.get_json(silent=True) or {}
    nombre = texto(d.get("clinica"), 60, True, "nombre de la clínica")
    email = texto(d.get("email"), 120, True, "correo")
    usuario = texto(d.get("usuario") or "admin", 30, True, "usuario")
    clave = d.get("password") or ""
    plan = d.get("plan") if d.get("plan") in PLANES else "profesional"
    if not EMAIL_RE.match(email):
        raise ValueError("Ingresa un correo válido.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,30}", usuario):
        raise ValueError("El usuario debe tener 3-30 caracteres (letras, números, . _ -).")
    if len(clave) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")

    clinica = plataforma.crear(nombre, email, plan)
    t = tenant.abrir(plataforma.rutas(clinica["slug"]), clinica["nombre"])
    try:
        admin_id = t.dao_usuario.guardar(
            Administrador(None, usuario, Usuario.hashear_contrasena(clave), True)
        )
        if d.get("demo", True):
            _sembrar_demo(t, admin_id)
    finally:
        t.con.close()
    session.clear()
    session.update(clinica_id=clinica["id"], usuario_id=admin_id, rol="Administrador")
    session.permanent = True
    return jsonify(ok=True, slug=clinica["slug"]), 201


@app.post("/api/login")
@api(publica=True)
def login():
    d = request.get_json(silent=True) or {}
    slug = texto(d.get("clinica"), 40).lower()
    usuario = texto(d.get("usuario"), 40)
    clave = d.get("password") or ""
    clave_rl = (request.remote_addr, slug, usuario.lower())
    if _bloqueado(clave_rl):
        return jsonify(error="Demasiados intentos. Espera 5 minutos e inténtalo de nuevo."), 429
    clinica = plataforma.por_slug(slug)
    user = None
    if clinica:
        t = tenant.abrir(plataforma.rutas(slug), clinica["nombre"])
        try:
            user = t.usuario.iniciar_sesion(usuario, clave)
        finally:
            t.con.close()
    if not user:
        _registrar_fallo(clave_rl)
        return jsonify(error="Clínica, usuario o contraseña incorrectos."), 401
    _intentos.pop(clave_rl, None)
    session.clear()
    session.update(clinica_id=clinica["id"], usuario_id=user.id, rol=user.rol)
    session.permanent = True
    return jsonify(ok=True)


@app.post("/api/logout")
@api(publica=True)
def logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/cuenta/password")
@api()
def cambiar_password():
    d = request.get_json(silent=True) or {}
    if not g.t.usuario.cambiar_contrasena(g.user.id, d.get("actual") or "", d.get("nueva") or ""):
        raise ValueError("La contraseña actual no es correcta.")
    return jsonify(ok=True)


@app.post("/api/suscripcion/plan")
@api(roles=("Administrador",))
def elegir_plan():
    """Activa/cambia el plan. Pasarela de pago NO integrada: ver README (Stripe/Culqi/MercadoPago)."""
    plan = (request.get_json(silent=True) or {}).get("plan")
    if plan not in PLANES:
        raise ValueError("Plan inexistente.")
    p = PLANES[plan]
    uso = _contexto()["uso"]
    if p["max_usuarios"] is not None and uso["usuarios"] > p["max_usuarios"]:
        raise ValueError(f"Tienes {uso['usuarios']} usuarios activos; el plan {p['nombre']} permite {p['max_usuarios']}.")
    if p["max_pacientes"] is not None and uso["pacientes"] > p["max_pacientes"]:
        raise ValueError(f"Tienes {uso['pacientes']} pacientes; el plan {p['nombre']} permite {p['max_pacientes']}.")
    plataforma.activar_plan(g.clinica["id"], plan)
    g.clinica = plataforma.por_id(g.clinica["id"])
    g.sub = Plataforma.estado_suscripcion(g.clinica)
    return jsonify(_contexto())


@app.post("/api/suscripcion/cancelar")
@api(roles=("Administrador",))
def cancelar_suscripcion():
    plataforma.cancelar(g.clinica["id"])
    g.clinica = plataforma.por_id(g.clinica["id"])
    g.sub = Plataforma.estado_suscripcion(g.clinica)
    return jsonify(_contexto())


# --------------------------------------------------------------------------- #
#  Dashboard
# --------------------------------------------------------------------------- #
@app.get("/api/dashboard")
@api()
def dashboard():
    t = g.t
    stats = t.dashboard.obtener_estadisticas()
    agenda = [dict(r) for r in t.dashboard.obtener_agenda_hoy()]
    actividad = t.dashboard.obtener_actividad_reciente()
    hoy = datetime.now().date()
    inicio = hoy - timedelta(days=6)
    por_dia = {(inicio + timedelta(days=i)).isoformat(): 0 for i in range(7)}
    for c in t.dao_cita.listar_por_rango(inicio.isoformat(), hoy.isoformat()):
        if c.estado != "Cancelada" and c.fecha in por_dia:
            por_dia[c.fecha] += 1
    n_doctores = len(t.dao_usuario.listar_por_rol("Doctor"))
    n_pacientes = len(t.dao_paciente.listar_todos(solo_activos=False))
    n_citas = len(t.dao_cita.listar_por_rango("2000-01-01", "2999-12-31"))
    return jsonify(
        stats=stats, agenda=agenda, actividad=actividad,
        semana=[{"fecha": k, "citas": v} for k, v in por_dia.items()],
        inicio=[
            {"id": "doctor", "texto": "Agrega a tu primer odontólogo", "hecho": n_doctores > 0, "ruta": "equipo"},
            {"id": "paciente", "texto": "Registra un paciente", "hecho": n_pacientes > 0, "ruta": "pacientes"},
            {"id": "cita", "texto": "Agenda tu primera cita", "hecho": n_citas > 0, "ruta": "citas"},
        ],
    )


# --------------------------------------------------------------------------- #
#  Pacientes
# --------------------------------------------------------------------------- #
def _datos_paciente(d):
    sexo = (d.get("sexo") or "").upper()
    if sexo not in ("M", "F"):
        raise ValueError("Selecciona el sexo del paciente.")
    return dict(
        nombre=texto(d.get("nombre"), 60, True, "nombre"),
        apellido=texto(d.get("apellido"), 60, True, "apellido"),
        dni=texto(d.get("dni"), 8, True, "DNI"),
        tel=texto(d.get("telefono"), 20),
        sexo=sexo,
        f_nac=iso_a_dmy(d.get("fechaNacimiento")),
        dir_p=texto(d.get("direccion"), 120),
    )


@app.get("/api/pacientes")
@api()
def listar_pacientes():
    q = request.args.get("q", "")
    todos = request.args.get("todos") == "1"
    pacientes = g.t.paciente.buscar_paciente(q) if q.strip() else g.t.paciente.listar_pacientes(solo_activos=not todos)
    if q.strip() and not todos:
        pacientes = [p for p in pacientes if p.estado]
    return jsonify([paciente_dict(p) for p in pacientes])


@app.post("/api/pacientes")
@api(escritura=True)
def crear_paciente():
    plan = g.sub["plan"]
    if plan["max_pacientes"] is not None:
        total = len(g.t.dao_paciente.listar_todos(solo_activos=False))
        if total >= plan["max_pacientes"]:
            return jsonify(error=f"Alcanzaste el límite de {plan['max_pacientes']} pacientes del plan {plan['nombre']}.",
                           codigo="limite"), 402
    p = g.t.paciente.registrar_paciente(**_datos_paciente(request.get_json(silent=True) or {}),
                                        registrado_por=g.user.id)
    return jsonify(paciente_dict(p)), 201


@app.put("/api/pacientes/<int:pid>")
@api(escritura=True)
def editar_paciente(pid):
    datos = _datos_paciente(request.get_json(silent=True) or {})
    if g.t.dao_paciente.existe_dni(datos["dni"], pid):
        raise ValueError(f"El DNI {datos['dni']} ya pertenece a otro paciente.")
    p = g.t.paciente.actualizar_paciente(pid, **datos)
    return jsonify(paciente_dict(p))


@app.post("/api/pacientes/<int:pid>/baja")
@api(roles=("Administrador", "Secretaria"), escritura=True)
def baja_paciente(pid):
    g.t.paciente.dar_de_baja_paciente(pid)
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  Citas
# --------------------------------------------------------------------------- #
def _mapas():
    pac = {p.id: p for p in g.t.dao_paciente.listar_todos(solo_activos=False)}
    doc = {u.id: u for u in g.t.dao_usuario.listar_por_rol("Doctor")}
    return pac, doc


@app.get("/api/doctores")
@api()
def doctores():
    return jsonify([usuario_dict(u) for u in g.t.dao_usuario.listar_por_rol("Doctor") if u.activo])


@app.get("/api/citas")
@api()
def listar_citas():
    fecha = fecha_iso(request.args.get("fecha") or datetime.now().strftime("%Y-%m-%d"))
    periodo = request.args.get("periodo", "dia")
    doctor_id = g.user.id if g.user.rol == "Doctor" else request.args.get("doctor", type=int)
    if doctor_id:
        citas = g.t.cita.listar_citas_doctor_periodo(doctor_id, fecha, periodo)
    else:
        citas = g.t.cita.listar_citas_periodo(fecha, periodo)
    inicio, fin = g.t.cita.rango_periodo(fecha, periodo)
    pac, doc = _mapas()
    return jsonify(rango={"inicio": inicio, "fin": fin}, citas=[cita_dict(c, pac, doc) for c in citas])


@app.post("/api/citas")
@api(escritura=True)
def crear_cita():
    d = request.get_json(silent=True) or {}
    doctor_id = g.user.id if g.user.rol == "Doctor" else d.get("doctorId")
    cita = g.t.cita.programar_cita(d.get("pacienteId"), doctor_id, fecha_iso(d.get("fecha")), hora_hhmm(d.get("hora")))
    pac, doc = _mapas()
    return jsonify(cita_dict(cita, pac, doc)), 201


def _cita_accesible(cid):
    c = g.t.dao_cita.buscar_por_id(cid)
    if not c:
        raise ValueError("La cita seleccionada es inexistente.")
    if g.user.rol == "Doctor" and c.doctorId != g.user.id:
        raise PermissionError("Esta cita pertenece a otro doctor.")
    return c


@app.post("/api/citas/<int:cid>/cancelar")
@api(escritura=True)
def cancelar_cita(cid):
    _cita_accesible(cid)
    g.t.cita.cancelar_cita(cid, (request.get_json(silent=True) or {}).get("motivo"))
    return jsonify(ok=True)


@app.post("/api/citas/<int:cid>/reprogramar")
@api(escritura=True)
def reprogramar_cita(cid):
    _cita_accesible(cid)
    d = request.get_json(silent=True) or {}
    g.t.cita.reprogramar_cita(cid, fecha_iso(d.get("fecha")), hora_hhmm(d.get("hora")))
    return jsonify(ok=True)


@app.post("/api/citas/<int:cid>/completar")
@api(escritura=True)
def completar_cita(cid):
    _cita_accesible(cid)
    g.t.cita.completar_cita(cid)
    return jsonify(ok=True)


# --------------------------------------------------------------------------- #
#  Historial clínico, odontograma y recetas (Doctor / Administrador)
# --------------------------------------------------------------------------- #
CLINICO = ("Doctor", "Administrador")
SUPERFICIES = {"V", "M", "O", "D", "L"}
COND_SUPERFICIE = {"caries", "restauracion", "sellante"}
COND_DIENTE = {"corona", "endodoncia", "extraccion", "ausente", "implante"}
DIENTES = {f"{c}{n}" for c in (1, 2, 3, 4) for n in range(1, 9)}


def validar_odontograma(estado) -> str:
    """Acepta solo el formato {"18": {"surf": {"V": "caries"}, "whole": ["corona"]}}."""
    if not isinstance(estado, dict):
        raise ValueError("Odontograma inválido.")
    limpio = {}
    for num, st in estado.items():
        if num not in DIENTES or not isinstance(st, dict):
            raise ValueError("Odontograma inválido: diente desconocido.")
        surf = {s: c for s, c in (st.get("surf") or {}).items() if s in SUPERFICIES and c in COND_SUPERFICIE}
        whole = sorted({c for c in (st.get("whole") or []) if c in COND_DIENTE})
        if surf or whole:
            limpio[num] = {"surf": surf, "whole": whole}
    return json.dumps(limpio, ensure_ascii=False)


@app.get("/api/pacientes/<int:pid>/historial")
@api(roles=CLINICO)
def ver_historial(pid):
    t = g.t
    paciente = t.paciente.buscar_por_id(pid)
    if not paciente:
        raise ValueError("El paciente no existe.")
    h = t.historial.obtener_historial(pid)
    if not h:
        raise ValueError("El paciente no posee un historial clínico.")
    _, doc = _mapas()
    doc.update({u.id: u for u in t.dao_usuario.listar_por_rol("Administrador")})
    registros = []
    citas_con_registro = set()
    for r in h.obtener_registros():
        citas_con_registro.add(r.citaId)
        registros.append(registro_dict(r, doc, t.receta.obtener_por_registro(r.id)))
    pendientes = [c for c in t.cita.listar_citas_por_paciente(pid) if c.is_pendiente()
                  and (g.user.rol != "Doctor" or c.doctorId == g.user.id)]
    try:
        estado = json.loads(h.odontogramaEstado or "{}")
    except ValueError:
        estado = {}
    return jsonify(
        paciente=paciente_dict(paciente),
        historial={"id": h.id, "activo": h.activo, "observaciones": (h.observaciones or "").strip(),
                   "odontograma": estado, "descripcionOdontograma": h.descripcionOdontograma or ""},
        registros=registros,
        citasPendientes=[{"id": c.id, "fecha": c.fecha, "hora": c.hora} for c in pendientes],
    )


@app.post("/api/citas/<int:cid>/registro")
@api(roles=CLINICO, escritura=True)
def crear_registro(cid):
    d = request.get_json(silent=True) or {}
    cita = _cita_accesible(cid)
    if not cita.is_pendiente():
        raise ValueError("Solo se puede registrar una consulta sobre una cita pendiente.")
    r = g.t.historial.crear_registro_clinico(
        cid, cita.doctorId,
        texto(d.get("diagnostico"), 1000, True, "diagnóstico"),
        texto(d.get("tratamiento"), 1000, True, "tratamiento"),
        texto(d.get("observaciones"), 1000),
    )
    return jsonify(id=r.id), 201


@app.put("/api/registros/<int:rid>")
@api(roles=CLINICO, escritura=True)
def editar_registro(rid):
    d = request.get_json(silent=True) or {}
    g.t.historial.actualizar_registro(
        rid, texto(d.get("diagnostico"), 1000, True, "diagnóstico"),
        texto(d.get("tratamiento"), 1000, True, "tratamiento"), texto(d.get("observaciones"), 1000))
    return jsonify(ok=True)


@app.post("/api/historiales/<int:hid>/observacion")
@api(roles=CLINICO, escritura=True)
def agregar_observacion(hid):
    obs = texto((request.get_json(silent=True) or {}).get("texto"), 1000, True, "observación")
    if not g.t.historial.agregar_observacion_historial(hid, obs):
        raise ValueError("El historial no existe.")
    return jsonify(ok=True)


@app.put("/api/historiales/<int:hid>/odontograma")
@api(roles=CLINICO, escritura=True)
def guardar_odontograma(hid):
    d = request.get_json(silent=True) or {}
    ok = g.t.historial.guardar_odontograma_estado(
        hid, validar_odontograma(d.get("estado")), "", texto(d.get("descripcion"), 1000))
    if not ok:
        raise ValueError("El historial no existe.")
    return jsonify(ok=True)


@app.post("/api/registros/<int:rid>/receta")
@api(roles=CLINICO, escritura=True)
def crear_receta(rid):
    d = request.get_json(silent=True) or {}
    reg = g.t.dao_registro.buscar_por_id(rid)
    if not reg:
        raise ValueError("El registro clínico no existe.")
    meds = []
    for m in (d.get("medicamentos") or [])[:30]:
        try:
            cantidad = float(m.get("cantidad"))
        except (TypeError, ValueError):
            raise ValueError("La cantidad de cada medicamento debe ser un número.")
        meds.append({"nombre": texto(m.get("nombre"), 120), "cantidad": cantidad,
                     "indicaciones": texto(m.get("indicaciones"), 300)})
    historial = g.t.dao_historial.buscar_por_id(reg.historialId)
    r = g.t.receta.generar_receta(rid, historial.pacienteId, reg.doctorId,
                                  texto(d.get("indicaciones"), 1000), meds)
    return jsonify(id=r.id), 201


@app.get("/api/recetas/<int:rid>/pdf")
@api(roles=CLINICO)
def descargar_receta(rid):
    r = g.t.dao_receta.buscar_por_id(rid)
    if not r or not r.archivoPDF or not dentro_de(r.archivoPDF, g.t.rutas["recetas"]):
        # regenera si el archivo se perdió
        if r:
            g.t.receta.generar_pdf(rid)
            r = g.t.dao_receta.buscar_por_id(rid)
        else:
            return jsonify(error="Receta no encontrada."), 404
    return send_file(r.archivoPDF, mimetype="application/pdf", download_name=f"receta_{rid}.pdf")


# --------------------------------------------------------------------------- #
#  Reportes (Administrador)
# --------------------------------------------------------------------------- #
def reporte_dict(r) -> dict:
    return {"id": r.id, "tipo": r.tipo, "formato": r.formato, "inicio": r.fechaInicio,
            "fin": r.fechaFin, "generadoPor": r._generadoPor, "fecha": (r._fechaGeneracion or "")[:16].replace("T", " ")}


@app.get("/api/reportes")
@api(roles=("Administrador",))
def listar_reportes():
    return jsonify([reporte_dict(r) for r in g.t.reporte.listar_reportes()])


@app.post("/api/reportes")
@api(roles=("Administrador",), escritura=True)
def generar_reporte():
    d = request.get_json(silent=True) or {}
    if d.get("formato") == "Excel" and not g.sub["plan"]["excel"]:
        return jsonify(error="La exportación a Excel está disponible desde el plan Profesional.", codigo="limite"), 402
    r = g.t.reporte.generar_reporte(d.get("tipo"), g.user.nombreUsuario,
                                    fecha_iso(d.get("inicio"), "fecha inicial"),
                                    fecha_iso(d.get("fin"), "fecha final"), d.get("formato"))
    return jsonify(reporte_dict(r)), 201


@app.get("/api/reportes/<int:rid>/archivo")
@api(roles=("Administrador",))
def descargar_reporte(rid):
    r = g.t.dao_reporte.buscar_por_id(rid)
    if not r or not dentro_de(r._archivo, g.t.rutas["reportes"]) or not os.path.exists(r._archivo):
        return jsonify(error="Archivo no disponible."), 404
    return send_file(r._archivo, as_attachment=True)


# --------------------------------------------------------------------------- #
#  Copias de seguridad (Administrador)
# --------------------------------------------------------------------------- #
def copia_dict(c) -> dict:
    return {"id": c.id, "fecha": (c._fechaHora or "")[:16].replace("T", " "), "tipo": c._tipo,
            "estado": c.estado, "disponible": bool(c.ubicacion) and os.path.exists(c.ubicacion)}


@app.get("/api/copias")
@api(roles=("Administrador",))
def listar_copias():
    return jsonify([copia_dict(c) for c in g.t.copia.listar_copias()])


@app.post("/api/copias")
@api(roles=("Administrador",), escritura=True)
def crear_copia():
    return jsonify(copia_dict(g.t.copia.ejecutar_backup_manual(g.user.id))), 201


@app.get("/api/copias/<int:cid>/descargar")
@api(roles=("Administrador",))
def descargar_copia(cid):
    c = g.t.dao_copia.buscar_por_id(cid)
    if not c or not c.ubicacion or not dentro_de(c.ubicacion, g.t.rutas["backups"]) or not os.path.exists(c.ubicacion):
        return jsonify(error="Archivo no disponible."), 404
    return send_file(c.ubicacion, as_attachment=True)


# --------------------------------------------------------------------------- #
#  Equipo (Administrador)
# --------------------------------------------------------------------------- #
@app.get("/api/usuarios")
@api(roles=("Administrador",))
def listar_usuarios():
    return jsonify([usuario_dict(u) for u in g.t.usuario.listar_usuarios()])


def _verificar_cupo_usuarios():
    maximo = g.sub["plan"]["max_usuarios"]
    if maximo is not None and sum(1 for u in g.t.dao_usuario.listar_todos() if u.activo) >= maximo:
        raise ValueError(f"El plan {g.sub['plan']['nombre']} permite hasta {maximo} usuarios activos. Mejora tu plan para sumar más.")


@app.post("/api/usuarios")
@api(roles=("Administrador",), escritura=True)
def crear_usuario():
    d = request.get_json(silent=True) or {}
    _verificar_cupo_usuarios()
    nombre = texto(d.get("usuario"), 30, True, "usuario")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,30}", nombre):
        raise ValueError("El usuario debe tener 3-30 caracteres (letras, números, . _ -).")
    u = g.t.usuario.registrar_usuario(nombre, d.get("password") or "", d.get("rol"))
    u = g.t.usuario.actualizar_perfil(u.id, texto(d.get("colegiatura"), 30), d.get("turno") if d.get("turno") in TURNOS else None)
    return jsonify(usuario_dict(u)), 201


@app.put("/api/usuarios/<int:uid>")
@api(roles=("Administrador",), escritura=True)
def editar_usuario(uid):
    d = request.get_json(silent=True) or {}
    u = g.t.usuario.actualizar_perfil(uid, texto(d["colegiatura"], 30) if "colegiatura" in d else None, d.get("turno"))
    return jsonify(usuario_dict(u))


@app.post("/api/usuarios/<int:uid>/password")
@api(roles=("Administrador",), escritura=True)
def reset_password(uid):
    g.t.usuario.restablecer_contrasena(uid, (request.get_json(silent=True) or {}).get("nueva") or "")
    return jsonify(ok=True)


@app.post("/api/usuarios/<int:uid>/estado")
@api(roles=("Administrador",), escritura=True)
def estado_usuario(uid):
    if (request.get_json(silent=True) or {}).get("activo"):
        _verificar_cupo_usuarios()
        g.t.usuario.activar_usuario(uid)
    else:
        u = g.t.dao_usuario.buscar_por_id(uid)
        if u and u.rol == "Administrador" and sum(1 for x in g.t.dao_usuario.listar_por_rol("Administrador") if x.activo) <= 1:
            raise ValueError("Debe quedar al menos un administrador activo.")
        g.t.usuario.desactivar_usuario(uid)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
