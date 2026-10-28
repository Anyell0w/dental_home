"""Registro de clínicas, inicio/cierre de sesión, recuperación de contraseña y planes públicos."""
import os
import re
import unicodedata

from flask import Blueprint, g, jsonify, request

from web import db, notificador
from web.comun import (MINUTOS_INACTIVIDAD, USUARIO_RE, api, auditar, borrar_cookie, correo, datos, leer_cookie, plan_dict,
                       poner_cookie, texto, uso)
from web.seguridad import (MAX_INTENTOS, MINUTOS_BLOQUEO, hashear, huella, requiere_rehash, token, validar_clave,
                           verificar)

bp = Blueprint("cuenta", __name__)
DIAS_PRUEBA = 14
_HASH_FALSO = hashear("clave-de-relleno-1")  # iguala el tiempo de respuesta cuando el usuario no existe


def slugify(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return (t[:28].strip("-") or "clinica")


def abrir_sesion(con, cid: int, uid: int) -> tuple:
    tok = token()
    sid = con.execute(
        """INSERT INTO sesiones (clinica_id, usuario_id, token_hash, expira_en, ip, agente)
           VALUES (%s, %s, %s, now() + make_interval(mins => %s), %s, %s) RETURNING id""",
        (cid, uid, huella(tok), MINUTOS_INACTIVIDAD, request.remote_addr, (request.user_agent.string or "")[:200]),
    ).fetchone()["id"]
    return str(sid), tok


def contexto() -> dict:
    return {"usuario": g.user, "clinica": g.clinica, "suscripcion": g.sub, "uso": uso(g.db)}


@bp.get("/api/planes")
def planes():
    with db.plataforma() as con:
        filas = con.execute("SELECT * FROM planes WHERE activo ORDER BY precio_mensual").fetchall()
    return jsonify([plan_dict(p) for p in filas])


@bp.get("/api/me")
def me():
    if not leer_cookie():
        return jsonify(usuario=None)
    return _me()


@api()
def _me():
    return jsonify(contexto())


# ----------------------------------------------------------------------------
# Registro de una clínica nueva (prueba gratuita)
# ----------------------------------------------------------------------------
@bp.post("/api/registro")
@api(publica=True)
def registro():
    d = datos()
    nombre = texto(d.get("clinica"), 80, True, "nombre del consultorio")
    mail = correo(d.get("correo"))
    usuario = texto(d.get("usuario"), 32, True, "usuario").lower()
    clave = validar_clave(d.get("password"))
    if not USUARIO_RE.match(usuario):
        raise ValueError("El usuario debe tener 3 a 32 caracteres: letras minúsculas, números, punto, guion o guion bajo.")
    atiende = bool(d.get("atiende"))
    colegiatura = texto(d.get("colegiatura"), 20, atiende, "número de colegiatura")

    with db.transaccion() as con:
        db.usar_plataforma(con)
        plan = con.execute("SELECT * FROM planes WHERE codigo = %s AND activo", (d.get("plan") or "profesional",)).fetchone() \
            or con.execute("SELECT * FROM planes WHERE codigo = 'profesional'").fetchone()
        base, codigo, n = slugify(nombre), None, 1
        while True:
            codigo = base if n == 1 else f"{base}-{n}"
            if not con.execute("SELECT 1 FROM clinicas WHERE codigo = %s", (codigo,)).fetchone():
                break
            n += 1
        cid = con.execute("INSERT INTO clinicas (codigo, nombre, correo) VALUES (%s, %s, %s) RETURNING id",
                          (codigo, nombre, mail)).fetchone()["id"]
        con.execute("""INSERT INTO suscripciones (clinica_id, plan_id, estado, vence_en)
                       VALUES (%s, %s, 'prueba', current_date + %s)""", (cid, plan["id"], DIAS_PRUEBA))
        auditar("clinica_creada", "clinicas", cid, {"plan": plan["codigo"]}, con=con, cid=cid, uid=None)

        db.usar_clinica(con, cid)
        uid = con.execute(
            """INSERT INTO usuarios (clinica_id, nombre_usuario, correo, contrasena_hash, rol)
               VALUES (%s, %s, %s, %s, 'administrador') RETURNING id""",
            (cid, usuario, mail, hashear(clave))).fetchone()["id"]
        if atiende:
            con.execute("INSERT INTO doctores (usuario_id, clinica_id, numero_colegiatura) VALUES (%s, %s, %s)",
                        (uid, cid, colegiatura))
        if d.get("demo", True):
            from web.demo import sembrar
            sembrar(con, cid, uid)
        sid, tok = abrir_sesion(con, cid, uid)
        auditar("registro", "usuarios", uid, con=con, cid=cid, uid=uid)
    return poner_cookie(jsonify(ok=True, codigo=codigo), cid, sid, tok), 201


# ----------------------------------------------------------------------------
# Inicio y cierre de sesión
# ----------------------------------------------------------------------------
@bp.post("/api/login")
@api(publica=True)
def login():
    d = datos()
    codigo = texto(d.get("clinica"), 40).lower()
    ident = texto(d.get("usuario"), 120).lower()
    clave = d.get("password") or ""
    error = jsonify(error="Código de clínica, usuario o contraseña incorrectos.")
    with db.transaccion() as con:
        con.execute("SET LOCAL ROLE dental_app")
        cli = con.execute("SELECT id, activa FROM clinicas WHERE codigo = %s", (codigo,)).fetchone()
        if not cli:
            verificar(_HASH_FALSO, clave)
            return error, 401
        cid = cli["id"]
        db.usar_clinica(con, cid)
        u = con.execute(
            """SELECT id, contrasena_hash, activo, intentos_fallidos, bloqueado_hasta,
                      bloqueado_hasta > now() AS bloqueado, to_char(bloqueado_hasta, 'HH24:MI') AS hasta
                 FROM usuarios WHERE nombre_usuario = %s OR correo = %s ORDER BY nombre_usuario = %s DESC LIMIT 1""",
            (ident, ident, ident)).fetchone()
        if not u:
            verificar(_HASH_FALSO, clave)
            return error, 401
        if u["bloqueado"]:
            return jsonify(error=f"Cuenta bloqueada por intentos fallidos. Inténtalo después de las {u['hasta']}."), 429
        if not verificar(u["contrasena_hash"], clave):
            intentos = u["intentos_fallidos"] + 1
            if intentos >= MAX_INTENTOS:
                con.execute("""UPDATE usuarios SET intentos_fallidos = 0,
                                      bloqueado_hasta = now() + make_interval(mins => %s) WHERE id = %s""",
                            (MINUTOS_BLOQUEO, u["id"]))
                auditar("usuario_bloqueado", "usuarios", u["id"], con=con, cid=cid, uid=u["id"])
            else:
                con.execute("UPDATE usuarios SET intentos_fallidos = %s WHERE id = %s", (intentos, u["id"]))
            auditar("login_fallido", "usuarios", u["id"], con=con, cid=cid, uid=u["id"])
            return error, 401
        if not u["activo"] or not cli["activa"]:
            return jsonify(error="Tu acceso está desactivado. Contacta al administrador de tu clínica."), 403
        con.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s", (u["id"],))
        if requiere_rehash(u["contrasena_hash"]):
            con.execute("UPDATE usuarios SET contrasena_hash = %s WHERE id = %s", (hashear(clave), u["id"]))
        sid, tok = abrir_sesion(con, cid, u["id"])
        auditar("login", "sesiones", None, con=con, cid=cid, uid=u["id"])
    return poner_cookie(jsonify(ok=True), cid, sid, tok)


@bp.post("/api/logout")
@api(publica=True)
def logout():
    ses = leer_cookie()
    if ses:
        cid, sid, tok = ses
        with db.clinica(cid) as con:
            fila = con.execute("""UPDATE sesiones SET revocada_en = now()
                                   WHERE id = %s AND token_hash = %s AND revocada_en IS NULL RETURNING usuario_id""",
                               (sid, huella(tok))).fetchone()
            if fila:
                auditar("logout", "sesiones", None, con=con, cid=cid, uid=fila["usuario_id"])
    return borrar_cookie(jsonify(ok=True))


@bp.post("/api/cuenta/password")
@api()
def cambiar_password():
    d = datos()
    fila = g.db.execute("SELECT contrasena_hash FROM usuarios WHERE id = %s", (g.user["id"],)).fetchone()
    if not verificar(fila["contrasena_hash"], d.get("actual") or ""):
        raise ValueError("La contraseña actual no es correcta.")
    g.db.execute("UPDATE usuarios SET contrasena_hash = %s WHERE id = %s", (hashear(validar_clave(d.get("nueva"))), g.user["id"]))
    g.db.execute("UPDATE sesiones SET revocada_en = now() WHERE usuario_id = %s AND id <> %s AND revocada_en IS NULL",
                 (g.user["id"], g.sid))
    auditar("password_cambiada", "usuarios", g.user["id"])
    return jsonify(ok=True)


# ----------------------------------------------------------------------------
# Recuperación de contraseña (enlace de un solo uso, 1 hora)
# ----------------------------------------------------------------------------
@bp.post("/api/recuperar")
@api(publica=True)
def recuperar():
    d = datos()
    codigo = texto(d.get("clinica"), 40).lower()
    mail = texto(d.get("correo"), 120).lower()
    respuesta = jsonify(ok=True, mensaje="Si los datos coinciden, enviaremos un enlace a tu correo.")
    with db.transaccion() as con:
        con.execute("SET LOCAL ROLE dental_app")
        cli = con.execute("SELECT id, nombre FROM clinicas WHERE codigo = %s AND activa", (codigo,)).fetchone()
        if not cli:
            return respuesta
        db.usar_clinica(con, cli["id"])
        u = con.execute("SELECT id, nombre_usuario FROM usuarios WHERE correo = %s AND activo", (mail,)).fetchone()
        if not u:
            return respuesta
        recientes = con.execute("""SELECT count(*) AS n FROM tokens_recuperacion
                                    WHERE usuario_id = %s AND creado_en > now() - interval '1 hour'""", (u["id"],)).fetchone()["n"]
        if recientes >= 3:
            return respuesta
        tok = token()
        con.execute("""INSERT INTO tokens_recuperacion (clinica_id, usuario_id, token_hash, expira_en)
                       VALUES (%s, %s, %s, now() + interval '1 hour')""", (cli["id"], u["id"], huella(tok)))
        auditar("recuperacion_solicitada", "usuarios", u["id"], con=con, cid=cli["id"], uid=u["id"])
    base = os.environ.get("DENTAL_BASE_URL", request.host_url).rstrip("/")
    notificador.enviar_correo(
        mail, "Restablece tu contraseña de Dental Home",
        f"Hola {u['nombre_usuario']}:\n\nPara crear una nueva contraseña en {cli['nombre']} abre este enlace "
        f"(válido por 1 hora):\n{base}/#/restablecer?c={cli['id']}&t={tok}\n\nSi no lo pediste, ignora este correo.")
    return respuesta


@bp.post("/api/restablecer")
@api(publica=True)
def restablecer():
    d = datos()
    try:
        cid = int(d.get("c"))
    except (TypeError, ValueError):
        raise ValueError("El enlace no es válido.")
    clave = validar_clave(d.get("password"))
    with db.clinica(cid) as con:
        t = con.execute("""UPDATE tokens_recuperacion SET usado_en = now()
                            WHERE token_hash = %s AND usado_en IS NULL AND expira_en > now() RETURNING usuario_id""",
                        (huella(texto(d.get("t"), 100)),)).fetchone()
        if not t:
            raise ValueError("El enlace venció o ya fue usado. Solicita uno nuevo.")
        con.execute("""UPDATE usuarios SET contrasena_hash = %s, intentos_fallidos = 0, bloqueado_hasta = NULL
                        WHERE id = %s""", (hashear(clave), t["usuario_id"]))
        con.execute("UPDATE sesiones SET revocada_en = now() WHERE usuario_id = %s AND revocada_en IS NULL", (t["usuario_id"],))
        auditar("password_restablecida", "usuarios", t["usuario_id"], con=con, cid=cid, uid=t["usuario_id"])
    return jsonify(ok=True)
