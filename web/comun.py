"""Piezas compartidas por los módulos de la API: sesión, permisos, validación y auditoría."""
import re
from datetime import date, datetime
from functools import wraps

from flask import g, jsonify, request
from psycopg.types.json import Jsonb

from web import db
from web.seguridad import huella

COOKIE = "dh_sesion"
MINUTOS_INACTIVIDAD = 30
HORAS_MAXIMAS = 12
ROLES = ("administrador", "doctor", "secretaria")
CLINICO = ("administrador", "doctor")
GESTION = ("administrador", "secretaria")
ADMIN = ("administrador",)
CORREO_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USUARIO_RE = re.compile(r"^[a-z0-9._-]{3,32}$")


# ----------------------------------------------------------------------------
# Validación
# ----------------------------------------------------------------------------
def datos() -> dict:
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def texto(v, maximo=200, obligatorio=False, nombre="campo") -> str:
    if v is None:
        v = ""
    if not isinstance(v, str):
        raise ValueError(f"Valor inválido en {nombre}.")
    v = re.sub(r"\s+", " ", v).strip() if maximo <= 200 else v.strip()
    if obligatorio and not v:
        raise ValueError(f"El campo {nombre} es obligatorio.")
    if len(v) > maximo:
        raise ValueError(f"El campo {nombre} excede {maximo} caracteres.")
    return v


def correo(v, obligatorio=True) -> str:
    v = texto(v, 120, obligatorio, "correo").lower()
    if v and not CORREO_RE.match(v):
        raise ValueError("Ingresa un correo válido.")
    return v


def fecha(v, nombre="fecha") -> date:
    try:
        return datetime.strptime(v or "", "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"La {nombre} no es válida.")


def hora(v) -> str:
    try:
        return datetime.strptime(v or "", "%H:%M").strftime("%H:%M")
    except (TypeError, ValueError):
        raise ValueError("La hora no es válida (HH:MM).")


def entero(v, nombre="valor") -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ValueError(f"El {nombre} no es válido.")


def iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# ----------------------------------------------------------------------------
# Sesión de clínica
# ----------------------------------------------------------------------------
def leer_cookie():
    raw = request.cookies.get(COOKIE, "")
    partes = raw.split(".")
    if len(partes) != 3 or not partes[0].isdigit() or not re.fullmatch(r"[0-9a-f-]{36}", partes[1]):
        return None
    return int(partes[0]), partes[1], partes[2]


def poner_cookie(resp, cid: int, sid: str, tok: str):
    import os
    resp.set_cookie(COOKIE, f"{cid}.{sid}.{tok}", httponly=True, samesite="Lax",
                    secure=os.environ.get("DENTAL_HTTPS") == "1", path="/")
    return resp


def borrar_cookie(resp):
    resp.delete_cookie(COOKIE, path="/")
    return resp


def hoy(con) -> date:
    """Fecha de la clínica (zona horaria de la conexión, DENTAL_TZ), no la del servidor."""
    return con.execute("SELECT current_date AS d").fetchone()["d"]


def suscripcion(con) -> dict:
    fila = con.execute(
        """SELECT v.estado_efectivo AS estado, v.vigente, v.inicia_en, v.vence_en, p.*
             FROM v_suscripcion_actual v JOIN planes p ON p.id = v.plan_id""").fetchone()
    if not fila:
        fila = con.execute(
            """SELECT 'cancelada' AS estado, false AS vigente, s.inicia_en, s.vence_en, p.*
                 FROM suscripciones s JOIN planes p ON p.id = s.plan_id
                ORDER BY s.creada_en DESC LIMIT 1""").fetchone()
    if not fila:
        return {"estado": "sin_plan", "vigente": False, "vence": None, "dias_restantes": None, "plan": None}
    dias = (fila["vence_en"] - hoy(con)).days
    return {
        "estado": fila["estado"], "vigente": fila["vigente"], "inicia": iso(fila["inicia_en"]),
        "vence": iso(fila["vence_en"]), "dias_restantes": max(dias, 0),
        "plan": plan_dict(fila),
    }


def plan_dict(p) -> dict:
    return {
        "id": p["id"], "codigo": p["codigo"], "nombre": p["nombre"], "precio": float(p["precio_mensual"]),
        "max_usuarios": p["max_usuarios"], "max_pacientes": p["max_pacientes"],
        "permite_excel": p["permite_excel"], "permite_respaldos": p["permite_respaldos"], "activo": p["activo"],
    }


def uso(con) -> dict:
    f = con.execute(
        """SELECT (SELECT count(*) FROM usuarios WHERE activo) AS usuarios,
                  (SELECT count(*) FROM pacientes WHERE activo) AS pacientes""").fetchone()
    return {"usuarios": f["usuarios"], "pacientes": f["pacientes"]}


def _cargar_sesion(con, sid: str, tok: str):
    fila = con.execute(
        """SELECT u.id, u.nombre_usuario, u.correo, u.rol::text AS rol, u.activo,
                  d.numero_colegiatura, d.turno::text AS turno, (d.usuario_id IS NOT NULL) AS es_doctor,
                  s.expira_en, c.nombre AS clinica_nombre, c.codigo AS clinica_codigo, c.activa
             FROM sesiones s
             JOIN usuarios u ON u.clinica_id = s.clinica_id AND u.id = s.usuario_id
             JOIN clinicas c ON c.id = s.clinica_id
             LEFT JOIN doctores d ON d.clinica_id = u.clinica_id AND d.usuario_id = u.id
            WHERE s.id = %s AND s.token_hash = %s AND s.revocada_en IS NULL
              AND s.expira_en > now() AND s.creada_en > now() - make_interval(hours => %s)""",
        (sid, huella(tok), HORAS_MAXIMAS)).fetchone()
    if not fila or not fila["activo"] or not fila["activa"]:
        return None
    # Expiración deslizante por inactividad, con tope absoluto desde el inicio de sesión
    con.execute(
        """UPDATE sesiones SET expira_en = least(creada_en + make_interval(hours => %s), now() + make_interval(mins => %s))
            WHERE id = %s AND expira_en < now() + make_interval(mins => %s)""",
        (HORAS_MAXIMAS, MINUTOS_INACTIVIDAD, sid, MINUTOS_INACTIVIDAD - 5))
    return fila


def usuario_publico(u) -> dict:
    return {
        "id": u["id"], "usuario": u["nombre_usuario"], "correo": u["correo"], "rol": u["rol"],
        "esDoctor": bool(u.get("es_doctor")), "colegiatura": u.get("numero_colegiatura"), "turno": u.get("turno"),
    }


def api(roles=None, escritura=False, publica=False):
    """Decorador: CSRF + sesión + transacción de la clínica (RLS) + rol + suscripción vigente."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if request.method not in ("GET", "HEAD") and request.headers.get("X-Requested-With") != "fetch":
                return jsonify(error="Solicitud no permitida."), 403
            if publica:
                return fn(*a, **kw)
            ses = leer_cookie()
            if not ses:
                return borrar_cookie(jsonify(error="Sesión expirada. Inicia sesión de nuevo.")), 401
            cid, sid, tok = ses
            with db.clinica(cid) as con:
                fila = _cargar_sesion(con, sid, tok)
                if not fila:
                    return borrar_cookie(jsonify(error="Sesión expirada. Inicia sesión de nuevo.")), 401
                g.db, g.cid, g.sid = con, cid, sid
                g.user = usuario_publico(fila)
                g.clinica = {"id": cid, "nombre": fila["clinica_nombre"], "codigo": fila["clinica_codigo"]}
                g.sub = suscripcion(con)
                if roles and g.user["rol"] not in roles:
                    return jsonify(error="No tienes permisos para esta acción."), 403
                if escritura and not g.sub["vigente"]:
                    return jsonify(error="Tu suscripción no está activa. Elige un plan para continuar.",
                                   codigo="suscripcion"), 402
                return fn(*a, **kw)
        return wrapper
    return deco


_YO = object()


def auditar(accion: str, recurso: str, recurso_id=None, detalle=None, con=None, cid=None, uid=_YO) -> None:
    con = con or g.db
    con.execute(
        """INSERT INTO auditoria (clinica_id, usuario_id, accion, recurso, recurso_id, ip, detalle)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (cid if cid is not None else g.cid, g.user["id"] if uid is _YO else uid, accion, recurso, recurso_id,
         request.remote_addr if request else None, Jsonb(detalle) if detalle is not None else None))


def limite(error: str):
    return jsonify(error=error, codigo="limite"), 402
