"""Webhook de pagos (idempotente), pasarela de prueba y consola de la plataforma."""
import json
import uuid
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.types.json import Jsonb

from web import db
from web.comun import api, correo, datos, entero, iso, plan_dict, texto
from web.pasarela import SIMULADA_ACTIVA, secreto_webhook, verificar_firma
from web.seguridad import firmar, verificar

bp = Blueprint("plataforma", __name__)
COOKIE_PLATAFORMA = "dh_plataforma"
HORAS_CONSOLA = 8


def _auditar(con, accion, recurso, recurso_id=None, detalle=None, cid=None):
    con.execute("""INSERT INTO auditoria (clinica_id, usuario_id, accion, recurso, recurso_id, ip, detalle)
                   VALUES (%s, NULL, %s, %s, %s, %s, %s)""",
                (cid, accion, recurso, recurso_id, request.remote_addr, Jsonb(detalle) if detalle else None))


# ----------------------------------------------------------------------------
# Webhook de la pasarela
# ----------------------------------------------------------------------------
def _sumar_mes(d):
    m = d.month + 1
    y = d.year + (m > 12)
    m = (m - 1) % 12 + 1
    import calendar
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def _aplicar_pago(con, pago) -> None:
    """Pago aprobado: renueva el mismo plan activo o abre un periodo nuevo (cambio de plan o fin de prueba)."""
    hoy = con.execute("SELECT current_date AS d").fetchone()["d"]
    cur = con.execute("""SELECT id, plan_id, estado::text AS estado, vence_en FROM suscripciones
                          WHERE clinica_id = %s AND estado IN ('prueba', 'activa') FOR UPDATE""", (pago["clinica_id"],)).fetchone()
    if cur and cur["estado"] == "activa" and cur["plan_id"] == pago["plan_id"]:
        inicio = max(hoy, cur["vence_en"] + timedelta(days=1))
        fin = _sumar_mes(inicio) - timedelta(days=1)
        con.execute("UPDATE suscripciones SET vence_en = %s WHERE id = %s", (fin, cur["id"]))
        sus_id = cur["id"]
    else:
        if cur:
            con.execute("UPDATE suscripciones SET estado = 'cancelada', vence_en = greatest(inicia_en, least(vence_en, %s)) WHERE id = %s",
                        (hoy, cur["id"]))
        inicio, fin = hoy, _sumar_mes(hoy) - timedelta(days=1)
        sus_id = con.execute("""INSERT INTO suscripciones (clinica_id, plan_id, estado, inicia_en, vence_en)
                                VALUES (%s, %s, 'activa', %s, %s) RETURNING id""",
                             (pago["clinica_id"], pago["plan_id"], inicio, fin)).fetchone()["id"]
    con.execute("""UPDATE pagos SET estado = 'pagado', pagado_en = now(), suscripcion_id = %s, periodo_inicio = %s, periodo_fin = %s
                    WHERE id = %s""", (sus_id, inicio, fin, pago["id"]))


def procesar_evento(pasarela: str, cuerpo: bytes) -> str:
    evento = json.loads(cuerpo)
    evento_id, tipo, ref = str(evento.get("id", "")), str(evento.get("tipo", "")), str(evento.get("referencia", ""))
    if not evento_id or not tipo:
        raise ValueError("Evento inválido.")
    with db.plataforma() as con:
        nuevo = con.execute("""INSERT INTO eventos_webhook (pasarela, evento_id, tipo, payload) VALUES (%s, %s, %s, %s)
                               ON CONFLICT DO NOTHING RETURNING evento_id""", (pasarela, evento_id, tipo, Jsonb(evento))).fetchone()
        if not nuevo:
            return "duplicado"
        pago = con.execute("""SELECT * FROM pagos WHERE pasarela = %s AND referencia_externa = %s FOR UPDATE""",
                           (pasarela, ref)).fetchone()
        resultado = "ignorado"
        if pago and pago["estado"] == "pendiente":
            if tipo == "pago.aprobado":
                if round(float(evento.get("monto", 0)), 2) != round(float(pago["monto"]), 2):
                    raise ValueError("El monto del evento no coincide con el cobro.")
                _aplicar_pago(con, pago)
                resultado = "pagado"
            elif tipo == "pago.rechazado":
                con.execute("UPDATE pagos SET estado = 'fallido' WHERE id = %s", (pago["id"],))
                resultado = "fallido"
            _auditar(con, f"pago_{resultado}", "pagos", pago["id"], {"evento": evento_id}, cid=pago["clinica_id"])
        con.execute("UPDATE eventos_webhook SET procesado_en = now() WHERE pasarela = %s AND evento_id = %s", (pasarela, evento_id))
    return resultado


@bp.post("/api/webhooks/<pasarela>")
def webhook(pasarela):
    cuerpo = request.get_data(cache=False)
    if len(cuerpo) > 64 * 1024 or not verificar_firma(cuerpo, request.headers.get("X-Firma", "")):
        return jsonify(error="Firma inválida."), 401
    try:
        return jsonify(resultado=procesar_evento(texto(pasarela, 30, True), cuerpo))
    except (ValueError, json.JSONDecodeError) as e:
        return jsonify(error=str(e)), 400


# Pasarela de prueba: la página de pago simula el checkout y envía el webhook firmado.
@bp.get("/api/pasarela/simulada/<ref>")
def cobro_simulado(ref):
    if not SIMULADA_ACTIVA:
        return jsonify(error="No disponible."), 404
    try:
        uuid.UUID(ref)
    except ValueError:
        return jsonify(error="Cobro no encontrado."), 404
    with db.plataforma() as con:
        p = con.execute("""SELECT g.monto, g.moneda, g.estado::text AS estado, pl.nombre AS plan, c.nombre AS clinica
                             FROM pagos g JOIN planes pl ON pl.id = g.plan_id JOIN clinicas c ON c.id = g.clinica_id
                            WHERE g.pasarela = 'simulada' AND g.referencia_externa = %s""", (ref,)).fetchone()
    if not p:
        return jsonify(error="Cobro no encontrado."), 404
    return jsonify(monto=float(p["monto"]), moneda=p["moneda"], estado=p["estado"], plan=p["plan"], clinica=p["clinica"])


@bp.post("/api/pasarela/simulada/<ref>")
@api(publica=True)
def pagar_simulado(ref):
    if not SIMULADA_ACTIVA:
        return jsonify(error="No disponible."), 404
    aprobado = datos().get("resultado") == "aprobado"
    with db.plataforma() as con:
        p = con.execute("SELECT monto FROM pagos WHERE pasarela = 'simulada' AND referencia_externa = %s", (ref,)).fetchone()
    if not p:
        return jsonify(error="Cobro no encontrado."), 404
    cuerpo = json.dumps({"id": f"evt_{uuid.uuid4().hex}", "tipo": "pago.aprobado" if aprobado else "pago.rechazado",
                         "referencia": ref, "monto": float(p["monto"])}).encode()
    with current_app.test_client() as cli:  # mismo camino que un webhook externo (firma incluida)
        r = cli.post("/api/webhooks/simulada", data=cuerpo, content_type="application/json",
                     headers={"X-Firma": firmar(secreto_webhook(), cuerpo)})
    return jsonify(r.get_json()), r.status_code


# ----------------------------------------------------------------------------
# Consola de plataforma (usuarios_plataforma)
# ----------------------------------------------------------------------------
def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="consola-plataforma")


def admin_plataforma():
    try:
        pid = _serializer().loads(request.cookies.get(COOKIE_PLATAFORMA, ""), max_age=HORAS_CONSOLA * 3600)
    except (BadSignature, SignatureExpired):
        return None
    with db.plataforma() as con:
        return con.execute("SELECT id, correo FROM usuarios_plataforma WHERE id = %s AND activo", (pid,)).fetchone()


def consola(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        if request.method != "GET" and request.headers.get("X-Requested-With") != "fetch":
            return jsonify(error="Solicitud no permitida."), 403
        adm = admin_plataforma()
        if not adm:
            return jsonify(error="Inicia sesión en la consola."), 401
        with db.plataforma() as con:
            return fn(con, adm, *a, **kw)
    return wrapper


@bp.post("/api/plataforma/login")
@api(publica=True)
def login_consola():
    d = datos()
    with db.plataforma() as con:
        u = con.execute("SELECT id, contrasena_hash FROM usuarios_plataforma WHERE correo = %s AND activo",
                        (texto(d.get("correo"), 120).lower(),)).fetchone()
        if not u or not verificar(u["contrasena_hash"], d.get("password") or ""):
            return jsonify(error="Correo o contraseña incorrectos."), 401
        _auditar(con, "consola_login", "usuarios_plataforma", u["id"])
    resp = jsonify(ok=True)
    resp.set_cookie(COOKIE_PLATAFORMA, _serializer().dumps(u["id"]), httponly=True, samesite="Strict",
                    max_age=HORAS_CONSOLA * 3600, path="/")
    return resp


@bp.post("/api/plataforma/logout")
def logout_consola():
    resp = jsonify(ok=True)
    resp.delete_cookie(COOKIE_PLATAFORMA, path="/")
    return resp


@bp.get("/api/plataforma/me")
def me_consola():
    adm = admin_plataforma()
    return jsonify(admin={"id": adm["id"], "correo": adm["correo"]} if adm else None)


@bp.get("/api/plataforma/resumen")
@consola
def resumen(con, adm):
    clinicas = con.execute(
        """SELECT c.id, c.codigo, c.nombre, c.correo, c.activa, to_char(c.creada_en, 'YYYY-MM-DD') AS creada,
                  s.estado::text AS estado, s.vence_en, p.nombre AS plan,
                  (s.vence_en < current_date) AS vencida,
                  (SELECT count(*) FROM usuarios u WHERE u.clinica_id = c.id AND u.activo) AS usuarios
             FROM clinicas c
             LEFT JOIN suscripciones s ON s.clinica_id = c.id AND s.estado IN ('prueba', 'activa')
             LEFT JOIN planes p ON p.id = s.plan_id
            ORDER BY c.creada_en DESC""").fetchall()
    pagos = con.execute(
        """SELECT g.id, c.nombre AS clinica, pl.nombre AS plan, g.monto, g.estado::text AS estado, g.pasarela,
                  to_char(coalesce(g.pagado_en, g.creado_en), 'YYYY-MM-DD HH24:MI') AS cuando
             FROM pagos g JOIN clinicas c ON c.id = g.clinica_id JOIN planes pl ON pl.id = g.plan_id
            ORDER BY g.creado_en DESC LIMIT 30""").fetchall()
    mrr = con.execute("""SELECT coalesce(sum(p.precio_mensual), 0) AS mrr FROM suscripciones s JOIN planes p ON p.id = s.plan_id
                          JOIN clinicas c ON c.id = s.clinica_id
                         WHERE s.estado = 'activa' AND s.vence_en >= current_date AND c.activa""").fetchone()["mrr"]
    planes = con.execute("SELECT * FROM planes ORDER BY precio_mensual").fetchall()
    return jsonify(
        admin=adm["correo"], mrr=float(mrr), planes=[plan_dict(p) for p in planes],
        clinicas=[{"id": c["id"], "codigo": c["codigo"], "nombre": c["nombre"], "correo": c["correo"], "activa": c["activa"],
                   "creada": c["creada"], "plan": c["plan"], "usuarios": c["usuarios"], "vence": iso(c["vence_en"]),
                   "estado": "sin_plan" if not c["estado"] else ("vencida" if c["vencida"] else c["estado"])} for c in clinicas],
        pagos=[{"id": p["id"], "clinica": p["clinica"], "plan": p["plan"], "monto": float(p["monto"]), "estado": p["estado"],
                "pasarela": p["pasarela"], "cuando": p["cuando"]} for p in pagos])


@bp.post("/api/plataforma/clinicas/<int:cid>/estado")
@consola
def estado_clinica(con, adm, cid):
    activa = bool(datos().get("activa"))
    if not con.execute("UPDATE clinicas SET activa = %s WHERE id = %s RETURNING id", (activa, cid)).fetchone():
        raise ValueError("La clínica no existe.")
    _auditar(con, "clinica_activada" if activa else "clinica_suspendida", "clinicas", cid, {"admin": adm["correo"]}, cid=cid)
    return jsonify(ok=True)


@bp.post("/api/plataforma/clinicas/<int:cid>/prueba")
@consola
def extender_prueba(con, adm, cid):
    dias = entero(datos().get("dias"), "número de días")
    if not 1 <= dias <= 60:
        raise ValueError("Indica entre 1 y 60 días.")
    s = con.execute("""UPDATE suscripciones SET vence_en = greatest(vence_en, current_date) + %s
                        WHERE clinica_id = %s AND estado = 'prueba' RETURNING vence_en""", (dias, cid)).fetchone()
    if not s:
        raise ValueError("La clínica no está en periodo de prueba.")
    _auditar(con, "prueba_extendida", "clinicas", cid, {"dias": dias, "admin": adm["correo"]}, cid=cid)
    return jsonify(vence=iso(s["vence_en"]))


@bp.put("/api/plataforma/planes/<int:plan_id>")
@consola
def editar_plan(con, adm, plan_id):
    d = datos()

    def limite(v, nombre):
        if v in (None, ""):
            return None
        n = entero(v, nombre)
        if n <= 0:
            raise ValueError(f"El {nombre} debe ser mayor que cero o quedar vacío (ilimitado).")
        return n

    try:
        precio = round(float(d.get("precio")), 2)
    except (TypeError, ValueError):
        raise ValueError("Precio inválido.")
    if precio < 0:
        raise ValueError("Precio inválido.")
    fila = con.execute(
        """UPDATE planes SET nombre = %s, precio_mensual = %s, max_usuarios = %s, max_pacientes = %s,
                  permite_excel = %s, permite_respaldos = %s, activo = %s WHERE id = %s RETURNING *""",
        (texto(d.get("nombre"), 40, True, "nombre"), precio, limite(d.get("max_usuarios"), "límite de usuarios"),
         limite(d.get("max_pacientes"), "límite de pacientes"), bool(d.get("permite_excel")),
         bool(d.get("permite_respaldos")), bool(d.get("activo", True)), plan_id)).fetchone()
    if not fila:
        raise ValueError("El plan no existe.")
    _auditar(con, "plan_configurado", "planes", plan_id, {"admin": adm["correo"], "precio": precio})
    return jsonify(plan_dict(fila))


@bp.post("/api/plataforma/usuarios")
@consola
def crear_admin(con, adm):
    from web.seguridad import hashear, validar_clave
    d = datos()
    con.execute("INSERT INTO usuarios_plataforma (correo, contrasena_hash) VALUES (%s, %s)",
                (correo(d.get("correo")), hashear(validar_clave(d.get("password")))))
    _auditar(con, "consola_admin_creado", "usuarios_plataforma", None, {"admin": adm["correo"]})
    return jsonify(ok=True), 201
