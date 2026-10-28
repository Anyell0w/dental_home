"""Equipo y roles, auditoría, reportes, copias de seguridad y suscripción de la clínica."""
import io
import os
import uuid
from datetime import date

from flask import Blueprint, g, jsonify, request, send_file

from web import copias, db
from web.comun import (ADMIN, ROLES, USUARIO_RE, api, auditar, correo, datos, entero, fecha, iso, limite, plan_dict, texto,
                       uso)
from web.seguridad import hashear, validar_clave

bp = Blueprint("gestion", __name__)
TURNOS = ("manana", "tarde", "tiempo_completo")


# ----------------------------------------------------------------------------
# Equipo
# ----------------------------------------------------------------------------
SQL_USUARIO = """
SELECT u.id, u.nombre_usuario, u.correo, u.rol::text AS rol, u.activo, u.creado_en,
       u.bloqueado_hasta > now() AS bloqueado, d.numero_colegiatura, d.turno::text AS turno,
       (d.usuario_id IS NOT NULL) AS es_doctor,
       (SELECT max(s.creada_en) FROM sesiones s WHERE s.usuario_id = u.id) AS ultimo_acceso
  FROM usuarios u LEFT JOIN doctores d ON d.clinica_id = u.clinica_id AND d.usuario_id = u.id"""


def usuario_dict(u) -> dict:
    return {"id": u["id"], "usuario": u["nombre_usuario"], "correo": u["correo"], "rol": u["rol"], "activo": u["activo"],
            "bloqueado": bool(u["bloqueado"]), "esDoctor": u["es_doctor"], "colegiatura": u["numero_colegiatura"] or "",
            "turno": u["turno"] or "tiempo_completo", "creado": iso(u["creado_en"]), "ultimoAcceso": iso(u["ultimo_acceso"])}


def _usuario(uid: int):
    u = g.db.execute(SQL_USUARIO + " WHERE u.id = %s", (uid,)).fetchone()
    if not u:
        raise ValueError("El usuario no existe.")
    return u


def _cupo():
    maximo = g.sub["plan"]["max_usuarios"]
    if maximo is not None and uso(g.db)["usuarios"] >= maximo:
        raise ValueError(f"El plan {g.sub['plan']['nombre']} permite hasta {maximo} usuarios activos. Mejora tu plan para sumar más.")


def _perfil_doctor(uid: int, rol: str, d: dict, existente: bool):
    """Doctor: colegiatura obligatoria. Administrador: opcional (si también atiende). Secretaria: sin perfil."""
    colegiatura = texto(d.get("colegiatura"), 20, rol == "doctor", "número de colegiatura")
    turno = d.get("turno") if d.get("turno") in TURNOS else "tiempo_completo"
    if rol == "secretaria" or (rol == "administrador" and not colegiatura):
        if existente:
            if g.db.execute("SELECT 1 FROM citas WHERE doctor_id = %s LIMIT 1", (uid,)).fetchone():
                raise ValueError("Este usuario tiene citas como doctor; no se puede quitar su perfil profesional.")
            g.db.execute("DELETE FROM doctores WHERE usuario_id = %s", (uid,))
        return
    g.db.execute("""INSERT INTO doctores (usuario_id, clinica_id, numero_colegiatura, turno) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (usuario_id) DO UPDATE SET numero_colegiatura = EXCLUDED.numero_colegiatura,
                                                          turno = EXCLUDED.turno""", (uid, g.cid, colegiatura, turno))


@bp.get("/api/usuarios")
@api(roles=ADMIN)
def listar_usuarios():
    return jsonify([usuario_dict(u) for u in g.db.execute(SQL_USUARIO + " ORDER BY u.activo DESC, u.rol, u.nombre_usuario").fetchall()])


@bp.post("/api/usuarios")
@api(roles=ADMIN, escritura=True)
def crear_usuario():
    d = datos()
    _cupo()
    nombre = texto(d.get("usuario"), 32, True, "usuario").lower()
    if not USUARIO_RE.match(nombre):
        raise ValueError("El usuario debe tener 3 a 32 caracteres: letras minúsculas, números, punto, guion o guion bajo.")
    rol = d.get("rol")
    if rol not in ROLES:
        raise ValueError("Rol inválido.")
    uid = g.db.execute("""INSERT INTO usuarios (clinica_id, nombre_usuario, correo, contrasena_hash, rol)
                          VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                       (g.cid, nombre, correo(d.get("correo")), hashear(validar_clave(d.get("password"))), rol)).fetchone()["id"]
    _perfil_doctor(uid, rol, d, existente=False)
    auditar("usuario_creado", "usuarios", uid, {"rol": rol})
    return jsonify(usuario_dict(_usuario(uid))), 201


@bp.put("/api/usuarios/<int:uid>")
@api(roles=ADMIN, escritura=True)
def editar_usuario(uid):
    d = datos()
    u = _usuario(uid)
    rol = d.get("rol") or u["rol"]
    if rol not in ROLES:
        raise ValueError("Rol inválido.")
    if uid == g.user["id"] and rol != u["rol"]:
        raise ValueError("No puedes cambiar tu propio rol.")
    if u["rol"] == "administrador" and rol != "administrador":
        _no_ultimo_admin(uid)
    g.db.execute("UPDATE usuarios SET correo = %s, rol = %s WHERE id = %s", (correo(d.get("correo")), rol, uid))
    _perfil_doctor(uid, rol, d, existente=u["es_doctor"])
    auditar("usuario_editado", "usuarios", uid, {"rol": rol})
    return jsonify(usuario_dict(_usuario(uid)))


def _no_ultimo_admin(uid: int):
    otros = g.db.execute("SELECT count(*) AS n FROM usuarios WHERE rol = 'administrador' AND activo AND id <> %s", (uid,)).fetchone()["n"]
    if not otros:
        raise ValueError("Debe quedar al menos un administrador activo.")


@bp.post("/api/usuarios/<int:uid>/password")
@api(roles=ADMIN, escritura=True)
def restablecer_password(uid):
    _usuario(uid)
    g.db.execute("UPDATE usuarios SET contrasena_hash = %s, intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s",
                 (hashear(validar_clave(datos().get("nueva"))), uid))
    g.db.execute("UPDATE sesiones SET revocada_en = now() WHERE usuario_id = %s AND revocada_en IS NULL AND id <> %s", (uid, g.sid))
    auditar("password_restablecida", "usuarios", uid)
    return jsonify(ok=True)


@bp.post("/api/usuarios/<int:uid>/estado")
@api(roles=ADMIN, escritura=True)
def estado_usuario(uid):
    u = _usuario(uid)
    activo = bool(datos().get("activo"))
    if uid == g.user["id"]:
        raise ValueError("No puedes desactivar tu propio usuario.")
    if activo and not u["activo"]:
        _cupo()
    if not activo and u["rol"] == "administrador":
        _no_ultimo_admin(uid)
    g.db.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, uid))
    if not activo:
        g.db.execute("UPDATE sesiones SET revocada_en = now() WHERE usuario_id = %s AND revocada_en IS NULL", (uid,))
    auditar("usuario_activado" if activo else "usuario_desactivado", "usuarios", uid)
    return jsonify(ok=True)


@bp.post("/api/usuarios/<int:uid>/desbloquear")
@api(roles=ADMIN, escritura=True)
def desbloquear(uid):
    _usuario(uid)
    g.db.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s", (uid,))
    auditar("usuario_desbloqueado", "usuarios", uid)
    return jsonify(ok=True)


# ----------------------------------------------------------------------------
# Auditoría
# ----------------------------------------------------------------------------
@bp.get("/api/auditoria")
@api(roles=ADMIN)
def auditoria():
    where, params = ["true"], []
    if request.args.get("desde"):
        where.append("a.ocurrido_en >= %s::date")
        params.append(fecha(request.args["desde"], "fecha inicial"))
    if request.args.get("hasta"):
        where.append("a.ocurrido_en < %s::date + 1")
        params.append(fecha(request.args["hasta"], "fecha final"))
    if request.args.get("usuario"):
        where.append("a.usuario_id = %s")
        params.append(entero(request.args["usuario"], "usuario"))
    if request.args.get("accion"):
        where.append("a.accion = %s")
        params.append(texto(request.args["accion"], 60))
    pagina = max(1, request.args.get("pagina", 1, type=int))
    cond = " AND ".join(where)
    total = g.db.execute(f"SELECT count(*) AS n FROM auditoria a WHERE {cond}", params).fetchone()["n"]
    filas = g.db.execute(
        f"""SELECT a.id, a.accion, a.recurso, a.recurso_id, host(a.ip) AS ip, a.detalle,
                   to_char(a.ocurrido_en, 'YYYY-MM-DD HH24:MI:SS') AS cuando, u.nombre_usuario
              FROM auditoria a LEFT JOIN usuarios u ON u.clinica_id = a.clinica_id AND u.id = a.usuario_id
             WHERE {cond} ORDER BY a.ocurrido_en DESC, a.id DESC LIMIT 50 OFFSET %s""", params + [(pagina - 1) * 50]).fetchall()
    acciones = [r["accion"] for r in g.db.execute("SELECT DISTINCT accion FROM auditoria ORDER BY accion").fetchall()]
    usuarios = g.db.execute("SELECT id, nombre_usuario FROM usuarios ORDER BY nombre_usuario").fetchall()
    return jsonify(total=total, pagina=pagina, paginas=max(1, -(-total // 50)), acciones=acciones,
                   usuarios=[{"id": u["id"], "usuario": u["nombre_usuario"]} for u in usuarios],
                   items=[{"id": f["id"], "accion": f["accion"], "recurso": f["recurso"], "recursoId": f["recurso_id"],
                           "ip": f["ip"] or "", "detalle": f["detalle"], "cuando": f["cuando"],
                           "usuario": f["nombre_usuario"] or "sistema"} for f in filas])


# ----------------------------------------------------------------------------
# Reportes (se registra la solicitud; el archivo se genera al descargarlo)
# ----------------------------------------------------------------------------
TIPOS_REPORTE = {"citas": "Reporte de citas", "pacientes": "Reporte de pacientes", "actividad": "Reporte de actividad clínica"}


def _agrupacion(ini: date, fin: date):
    return ("day", "DD/MM") if (fin - ini).days <= 31 else ("month", "MM/YYYY")


def _serie(sql_col: str, tabla: str, ini, fin, extra=""):
    unidad, fmt = _agrupacion(ini, fin)
    return [(f["k"], f["n"]) for f in g.db.execute(
        f"""SELECT to_char(s, %s) AS k,
                   (SELECT count(*) FROM {tabla} WHERE date_trunc(%s, {sql_col}) = s {extra}) AS n
              FROM generate_series(date_trunc(%s, %s::date), %s::date, ('1 ' || %s)::interval) AS s ORDER BY s""",
        (fmt, unidad, unidad, ini, fin, unidad)).fetchall()]


def construir_reporte(tipo: str, ini: date, fin: date) -> dict:
    periodo = f"Del {ini:%d/%m/%Y} al {fin:%d/%m/%Y}"
    rng = (ini, fin)
    if tipo == "citas":
        k = g.db.execute("""SELECT count(*) AS total, count(*) FILTER (WHERE estado = 'completada') AS completadas,
                                   count(*) FILTER (WHERE estado = 'pendiente') AS pendientes,
                                   count(*) FILTER (WHERE estado = 'cancelada') AS canceladas
                              FROM citas WHERE inicia_en >= %s::date AND inicia_en < %s::date + 1""", rng).fetchone()
        cerradas = k["completadas"] + k["canceladas"]
        por_doc = g.db.execute(
            """SELECT u.nombre_usuario, count(*) AS total, count(*) FILTER (WHERE c.estado = 'completada') AS comp,
                      count(*) FILTER (WHERE c.estado = 'cancelada') AS canc
                 FROM citas c JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id
                WHERE c.inicia_en >= %s::date AND c.inicia_en < %s::date + 1 GROUP BY 1 ORDER BY 2 DESC""", rng).fetchall()
        detalle = g.db.execute(
            """SELECT to_char(c.inicia_en, 'DD/MM/YYYY') AS f, to_char(c.inicia_en, 'HH24:MI') AS h,
                      p.apellidos || ', ' || p.nombres AS pac, u.nombre_usuario AS doc, c.estado::text AS est,
                      coalesce(c.motivo_cancelacion, '') AS mot
                 FROM citas c JOIN pacientes p ON p.clinica_id = c.clinica_id AND p.id = c.paciente_id
                 JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id
                WHERE c.inicia_en >= %s::date AND c.inicia_en < %s::date + 1 ORDER BY c.inicia_en LIMIT 2000""", rng).fetchall()
        return {"titulo": TIPOS_REPORTE[tipo], "periodo": periodo,
                "kpis": [("Citas", k["total"]), ("Completadas", k["completadas"]), ("Pendientes", k["pendientes"]),
                         ("Canceladas", k["canceladas"]),
                         ("Asistencia", f"{round(100 * k['completadas'] / cerradas)} %" if cerradas else "—")],
                "serieTitulo": "Citas en el periodo",
                "serie": _serie("inicia_en", "citas", ini, fin, "AND estado <> 'cancelada'"),
                "tablas": [{"titulo": "Por doctor", "columnas": ["Doctor", "Citas", "Completadas", "Canceladas"],
                            "filas": [[f["nombre_usuario"], f["total"], f["comp"], f["canc"]] for f in por_doc]},
                           {"titulo": "Detalle", "columnas": ["Fecha", "Hora", "Paciente", "Doctor", "Estado", "Motivo"],
                            "filas": [[f["f"], f["h"], f["pac"], f["doc"], f["est"], f["mot"]] for f in detalle]}]}
    if tipo == "pacientes":
        k = g.db.execute("""SELECT count(*) FILTER (WHERE creado_en >= %s::date AND creado_en < %s::date + 1) AS nuevos,
                                   count(*) FILTER (WHERE activo) AS activos, count(*) FILTER (WHERE NOT activo) AS bajas
                              FROM pacientes""", rng).fetchone()
        atendidos = g.db.execute("""SELECT count(DISTINCT c.paciente_id) AS n FROM registros_clinicos r
                                      JOIN citas c ON c.clinica_id = r.clinica_id AND c.id = r.cita_id
                                     WHERE r.atendido_en >= %s::date AND r.atendido_en < %s::date + 1""", rng).fetchone()["n"]
        edades = g.db.execute(
            """SELECT CASE WHEN fecha_nacimiento IS NULL THEN 'Sin dato'
                           WHEN age(fecha_nacimiento) < interval '13 years' THEN '0 a 12'
                           WHEN age(fecha_nacimiento) < interval '18 years' THEN '13 a 17'
                           WHEN age(fecha_nacimiento) < interval '40 years' THEN '18 a 39'
                           WHEN age(fecha_nacimiento) < interval '60 years' THEN '40 a 59' ELSE '60 a más' END AS r,
                      count(*) FILTER (WHERE sexo = 'F') AS f, count(*) FILTER (WHERE sexo = 'M') AS m, count(*) AS t
                 FROM pacientes WHERE activo GROUP BY 1 ORDER BY 1""").fetchall()
        nuevos = g.db.execute(
            """SELECT to_char(creado_en, 'DD/MM/YYYY') AS f, apellidos || ', ' || nombres AS n,
                      tipo_documento::text || ' ' || numero_documento AS d, coalesce(telefono, '') AS t
                 FROM pacientes WHERE creado_en >= %s::date AND creado_en < %s::date + 1 ORDER BY creado_en LIMIT 2000""", rng).fetchall()
        return {"titulo": TIPOS_REPORTE[tipo], "periodo": periodo,
                "kpis": [("Nuevos", k["nuevos"]), ("Atendidos", atendidos), ("Activos", k["activos"]), ("Dados de baja", k["bajas"])],
                "serieTitulo": "Pacientes nuevos", "serie": _serie("creado_en", "pacientes", ini, fin),
                "tablas": [{"titulo": "Edad y sexo (activos)", "columnas": ["Rango de edad", "Mujeres", "Hombres", "Total"],
                            "filas": [[e["r"], e["f"], e["m"], e["t"]] for e in edades]},
                           {"titulo": "Pacientes nuevos", "columnas": ["Registro", "Paciente", "Documento", "Teléfono"],
                            "filas": [[f["f"], f["n"], f["d"], f["t"]] for f in nuevos]}]}
    if tipo == "actividad":
        k = g.db.execute(
            """SELECT (SELECT count(*) FROM registros_clinicos WHERE atendido_en >= %(i)s::date AND atendido_en < %(f)s::date + 1) AS consultas,
                      (SELECT count(*) FROM recetas WHERE emitida_en >= %(i)s::date AND emitida_en < %(f)s::date + 1) AS recetas,
                      (SELECT count(*) FROM odontograma_hallazgos WHERE registrado_en >= %(i)s::date AND registrado_en < %(f)s::date + 1) AS hallazgos,
                      (SELECT count(*) FROM citas WHERE creada_en >= %(i)s::date AND creada_en < %(f)s::date + 1) AS agendadas""",
            {"i": ini, "f": fin}).fetchone()
        por_doc = g.db.execute(
            """SELECT u.nombre_usuario, count(DISTINCT r.id) AS consultas, count(DISTINCT rc.id) AS recetas
                 FROM registros_clinicos r JOIN citas c ON c.clinica_id = r.clinica_id AND c.id = r.cita_id
                 JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id
                 LEFT JOIN recetas rc ON rc.clinica_id = r.clinica_id AND rc.registro_clinico_id = r.id
                WHERE r.atendido_en >= %s::date AND r.atendido_en < %s::date + 1 GROUP BY 1 ORDER BY 2 DESC""", rng).fetchall()
        conds = g.db.execute(
            """SELECT cd.nombre, count(*) AS n FROM odontograma_hallazgos h JOIN condiciones_dentales cd ON cd.id = h.condicion_id
                WHERE cd.codigo <> 'sano' AND h.registrado_en >= %s::date AND h.registrado_en < %s::date + 1
                GROUP BY 1 ORDER BY 2 DESC LIMIT 12""", rng).fetchall()
        meds = g.db.execute(
            """SELECT m.nombre, count(*) AS n FROM receta_detalles d
                 JOIN recetas r ON r.clinica_id = d.clinica_id AND r.id = d.receta_id
                 JOIN medicamentos m ON m.clinica_id = d.clinica_id AND m.id = d.medicamento_id
                WHERE r.emitida_en >= %s::date AND r.emitida_en < %s::date + 1 GROUP BY 1 ORDER BY 2 DESC LIMIT 12""", rng).fetchall()
        return {"titulo": TIPOS_REPORTE[tipo], "periodo": periodo,
                "kpis": [("Consultas", k["consultas"]), ("Recetas", k["recetas"]), ("Hallazgos", k["hallazgos"]),
                         ("Citas agendadas", k["agendadas"])],
                "serieTitulo": "Consultas registradas", "serie": _serie("atendido_en", "registros_clinicos", ini, fin),
                "tablas": [{"titulo": "Por doctor", "columnas": ["Doctor", "Consultas", "Recetas"],
                            "filas": [[f["nombre_usuario"], f["consultas"], f["recetas"]] for f in por_doc]},
                           {"titulo": "Hallazgos frecuentes", "columnas": ["Condición", "Registros"],
                            "filas": [[f["nombre"], f["n"]] for f in conds]},
                           {"titulo": "Medicamentos recetados", "columnas": ["Medicamento", "Veces"],
                            "filas": [[f["nombre"], f["n"]] for f in meds]}]}
    raise ValueError("Tipo de reporte no disponible.")


@bp.get("/api/reportes")
@api(roles=ADMIN)
def listar_reportes():
    filas = g.db.execute(
        """SELECT r.id, r.tipo::text AS tipo, r.formato::text AS formato, r.fecha_inicio, r.fecha_fin,
                  to_char(r.generado_en, 'YYYY-MM-DD HH24:MI') AS cuando, u.nombre_usuario
             FROM reportes r JOIN usuarios u ON u.clinica_id = r.clinica_id AND u.id = r.generado_por
            ORDER BY r.generado_en DESC LIMIT 50""").fetchall()
    return jsonify([{"id": f["id"], "tipo": f["tipo"], "formato": f["formato"], "inicio": iso(f["fecha_inicio"]),
                     "fin": iso(f["fecha_fin"]), "cuando": f["cuando"], "usuario": f["nombre_usuario"]} for f in filas])


@bp.post("/api/reportes")
@api(roles=ADMIN, escritura=True)
def solicitar_reporte():
    d = datos()
    tipo, formato = d.get("tipo"), d.get("formato")
    if tipo not in TIPOS_REPORTE:
        raise ValueError("Tipo de reporte no disponible.")
    if formato not in ("pdf", "excel"):
        raise ValueError("Formato no soportado.")
    if formato == "excel" and not g.sub["plan"]["permite_excel"]:
        return limite("La exportación a Excel está disponible desde el plan Profesional.")
    ini, fin = fecha(d.get("inicio"), "fecha inicial"), fecha(d.get("fin"), "fecha final")
    if fin < ini:
        raise ValueError("La fecha final debe ser posterior a la inicial.")
    if (fin - ini).days > 366 * 3:
        raise ValueError("El periodo máximo es de 3 años.")
    rid = g.db.execute("""INSERT INTO reportes (clinica_id, generado_por, tipo, formato, fecha_inicio, fecha_fin)
                          VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                       (g.cid, g.user["id"], tipo, formato, ini, fin)).fetchone()["id"]
    auditar("reporte_generado", "reportes", rid, {"tipo": tipo, "formato": formato})
    return jsonify(id=rid), 201


@bp.get("/api/reportes/<int:rid>/archivo")
@api(roles=ADMIN)
def descargar_reporte(rid):
    from web.documentos import excel_reporte, pdf_reporte
    r = g.db.execute("SELECT tipo::text AS tipo, formato::text AS formato, fecha_inicio, fecha_fin FROM reportes WHERE id = %s",
                     (rid,)).fetchone()
    if not r:
        return jsonify(error="Reporte no encontrado."), 404
    rep = construir_reporte(r["tipo"], r["fecha_inicio"], r["fecha_fin"])
    nombre = f"reporte-{r['tipo']}-{r['fecha_inicio']}-{r['fecha_fin']}"
    if r["formato"] == "excel":
        return send_file(io.BytesIO(excel_reporte(g.clinica["nombre"], rep)), as_attachment=True, download_name=nombre + ".xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return send_file(io.BytesIO(pdf_reporte(g.clinica["nombre"], rep)), as_attachment=True, download_name=nombre + ".pdf",
                     mimetype="application/pdf")


# ----------------------------------------------------------------------------
# Copias de seguridad
# ----------------------------------------------------------------------------
def copia_dict(c) -> dict:
    return {"id": c["id"], "tipo": c["tipo"], "estado": c["estado"], "inicio": c["ini"], "fin": c["fin"],
            "usuario": c["nombre_usuario"] or "automática", "disponible": c["estado"] == "exitoso" and os.path.exists(copias.ruta(g.cid, c["id"]))}


SQL_COPIAS = """SELECT c.id, c.tipo::text AS tipo, c.estado::text AS estado, to_char(c.iniciada_en, 'YYYY-MM-DD HH24:MI') AS ini,
                       to_char(c.finalizada_en, 'YYYY-MM-DD HH24:MI') AS fin, u.nombre_usuario
                  FROM copias_seguridad c LEFT JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.solicitada_por"""


@bp.get("/api/copias")
@api(roles=ADMIN)
def listar_copias():
    return jsonify([copia_dict(c) for c in g.db.execute(SQL_COPIAS + " ORDER BY c.iniciada_en DESC LIMIT 50").fetchall()])


@bp.post("/api/copias")
@api(roles=ADMIN, escritura=True)
def crear_copia():
    if not g.sub["plan"]["permite_respaldos"]:
        return limite("Las copias de seguridad están disponibles desde el plan Profesional.")
    c = copias.crear(g.db, g.cid, g.user["id"])
    auditar("copia_creada", "copias_seguridad", c["id"], {"estado": c["estado"]})
    return jsonify(copia_dict(g.db.execute(SQL_COPIAS + " WHERE c.id = %s", (c["id"],)).fetchone())), 201


@bp.get("/api/copias/<int:cid>/descargar")
@api(roles=ADMIN)
def descargar_copia(cid):
    c = g.db.execute("SELECT id, estado::text AS estado, to_char(iniciada_en, 'YYYYMMDD-HH24MI') AS f FROM copias_seguridad WHERE id = %s",
                     (cid,)).fetchone()
    ruta = copias.ruta(g.cid, cid)
    if not c or c["estado"] != "exitoso" or not os.path.exists(ruta):
        return jsonify(error="Archivo no disponible."), 404
    auditar("copia_descargada", "copias_seguridad", cid)
    return send_file(ruta, as_attachment=True, download_name=f"dental-home-{g.clinica['codigo']}-{c['f']}.json.gz",
                     mimetype="application/gzip")


# ----------------------------------------------------------------------------
# Suscripción y pagos
# ----------------------------------------------------------------------------
@bp.get("/api/suscripcion")
@api(roles=ADMIN)
def ver_suscripcion():
    planes = g.db.execute("SELECT * FROM planes WHERE activo ORDER BY precio_mensual").fetchall()
    hist = g.db.execute("""SELECT s.id, s.estado::text AS estado, s.inicia_en, s.vence_en, p.nombre FROM suscripciones s
                             JOIN planes p ON p.id = s.plan_id ORDER BY s.creada_en DESC LIMIT 20""").fetchall()
    pagos = g.db.execute("""SELECT g.id, g.monto, g.moneda, g.estado::text AS estado, g.pasarela, g.periodo_inicio, g.periodo_fin,
                                   to_char(coalesce(g.pagado_en, g.creado_en), 'YYYY-MM-DD HH24:MI') AS cuando, p.nombre
                              FROM pagos g JOIN planes p ON p.id = g.plan_id ORDER BY g.creado_en DESC LIMIT 30""").fetchall()
    return jsonify(
        suscripcion=g.sub, uso=uso(g.db), planes=[plan_dict(p) for p in planes],
        historial=[{"id": h["id"], "estado": h["estado"], "inicio": iso(h["inicia_en"]), "vence": iso(h["vence_en"]),
                    "plan": h["nombre"]} for h in hist],
        pagos=[{"id": p["id"], "monto": float(p["monto"]), "moneda": p["moneda"], "estado": p["estado"], "plan": p["nombre"],
                "periodo": [iso(p["periodo_inicio"]), iso(p["periodo_fin"])], "cuando": p["cuando"]} for p in pagos])


@bp.post("/api/suscripcion/pagar")
@api(roles=ADMIN)
def pagar():
    """Crea un cobro pendiente en la pasarela; la suscripción cambia solo cuando llega el webhook de pago aprobado."""
    from web.pasarela import PASARELA, crear_cobro
    plan = g.db.execute("SELECT * FROM planes WHERE codigo = %s AND activo", (datos().get("plan"),)).fetchone()
    if not plan:
        raise ValueError("Plan inexistente.")
    u = uso(g.db)
    if plan["max_usuarios"] is not None and u["usuarios"] > plan["max_usuarios"]:
        raise ValueError(f"Tienes {u['usuarios']} usuarios activos; el plan {plan['nombre']} permite {plan['max_usuarios']}.")
    if plan["max_pacientes"] is not None and u["pacientes"] > plan["max_pacientes"]:
        raise ValueError(f"Tienes {u['pacientes']} pacientes activos; el plan {plan['nombre']} permite {plan['max_pacientes']}.")
    sus = g.db.execute("SELECT id FROM suscripciones ORDER BY (estado IN ('prueba', 'activa')) DESC, creada_en DESC LIMIT 1").fetchone()
    ref = str(uuid.uuid4())
    with db.como_plataforma(g.db, g.cid):
        pid = g.db.execute(
            """INSERT INTO pagos (clinica_id, suscripcion_id, plan_id, monto, pasarela, referencia_externa)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (g.cid, sus["id"], plan["id"], plan["precio_mensual"], PASARELA, ref)).fetchone()["id"]
    auditar("pago_iniciado", "pagos", pid, {"plan": plan["codigo"], "monto": float(plan["precio_mensual"])})
    return jsonify(referencia=ref, url=crear_cobro(ref, float(plan["precio_mensual"]), plan["nombre"], g.clinica["nombre"])), 201
