"""Pacientes, agenda, historial clínico, odontograma, recetas y panel de inicio."""
import io
from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request, send_file

from web.comun import (ADMIN, CLINICO, GESTION, api, auditar, correo, datos, entero, fecha, hoy, hora, iso, limite,
                       texto, uso)

bp = Blueprint("clinica", __name__)

TIPOS_DOC = {"DNI": r"^[0-9]{8}$", "CE": r"^[A-Za-z0-9]{6,12}$", "PASAPORTE": r"^[A-Za-z0-9]{6,12}$"}
SUPERFICIES = ("vestibular", "lingual", "mesial", "distal", "oclusal")
COND_SUPERFICIE = {"caries", "obturacion", "sellante", "fractura"}
COND_PIEZA = {"endodoncia", "corona", "implante", "puente", "ausente", "extraccion_indicada"}
DURACIONES = (15, 30, 45, 60, 90, 120)


def es_doctor_rol() -> bool:
    return g.user["rol"] == "doctor"


# ----------------------------------------------------------------------------
# Pacientes
# ----------------------------------------------------------------------------
SQL_PACIENTE = """
SELECT p.id, p.tipo_documento::text AS tipo_documento, p.numero_documento, p.nombres, p.apellidos,
       p.sexo::text AS sexo, p.fecha_nacimiento, p.telefono, p.correo, p.direccion, p.activo, p.creado_en,
       date_part('year', age(p.fecha_nacimiento))::int AS edad
  FROM pacientes p"""


def paciente_dict(p) -> dict:
    return {
        "id": p["id"], "tipoDocumento": p["tipo_documento"], "numeroDocumento": p["numero_documento"],
        "nombres": p["nombres"], "apellidos": p["apellidos"], "nombreCompleto": f"{p['nombres']} {p['apellidos']}",
        "sexo": p["sexo"] or "", "fechaNacimiento": iso(p["fecha_nacimiento"]) or "", "edad": p["edad"],
        "telefono": p["telefono"] or "", "correo": p["correo"] or "", "direccion": p["direccion"] or "",
        "activo": p["activo"], "creadoEn": iso(p["creado_en"]),
    }


def buscar_paciente(pid: int, activo=None):
    p = g.db.execute(SQL_PACIENTE + " WHERE p.id = %s", (pid,)).fetchone()
    if not p or (activo is not None and p["activo"] != activo):
        raise ValueError("El paciente no existe o está dado de baja." if p else "El paciente no existe.")
    return p


def _datos_paciente(d) -> dict:
    import re
    tipo = (d.get("tipoDocumento") or "DNI").upper()
    if tipo not in TIPOS_DOC:
        raise ValueError("Tipo de documento inválido.")
    numero = texto(d.get("numeroDocumento"), 12, True, "número de documento").upper()
    if not re.match(TIPOS_DOC[tipo], numero):
        raise ValueError("El DNI debe tener 8 dígitos." if tipo == "DNI" else "El documento debe tener de 6 a 12 letras o números.")
    sexo = (d.get("sexo") or "").upper() or None
    if sexo not in (None, "M", "F"):
        raise ValueError("Sexo inválido.")
    nac = fecha(d["fechaNacimiento"], "fecha de nacimiento") if d.get("fechaNacimiento") else None
    if nac and (nac > hoy(g.db) or nac.year < 1900):
        raise ValueError("La fecha de nacimiento no es válida.")
    return {
        "tipo_documento": tipo, "numero_documento": numero,
        "nombres": texto(d.get("nombres"), 80, True, "nombres"), "apellidos": texto(d.get("apellidos"), 80, True, "apellidos"),
        "sexo": sexo, "fecha_nacimiento": nac, "telefono": texto(d.get("telefono"), 20) or None,
        "correo": correo(d.get("correo"), False) or None, "direccion": texto(d.get("direccion"), 160) or None,
    }


@bp.get("/api/pacientes")
@api()
def listar_pacientes():
    q = texto(request.args.get("q"), 80)
    todos = request.args.get("todos") == "1"
    where, params = [], []
    if not todos:
        where.append("p.activo")
    if q:
        where.append("(p.numero_documento ILIKE %s OR (p.nombres || ' ' || p.apellidos) ILIKE %s "
                     "OR (p.apellidos || ' ' || p.nombres) ILIKE %s)")
        q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params += [f"{q}%", f"%{q}%", f"%{q}%"]
    sql = SQL_PACIENTE + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.apellidos, p.nombres LIMIT 500"
    return jsonify([paciente_dict(p) for p in g.db.execute(sql, params).fetchall()])


@bp.post("/api/pacientes")
@api(escritura=True)
def crear_paciente():
    plan = g.sub["plan"]
    if plan["max_pacientes"] is not None and uso(g.db)["pacientes"] >= plan["max_pacientes"]:
        return limite(f"Alcanzaste el límite de {plan['max_pacientes']} pacientes activos del plan {plan['nombre']}.")
    v = _datos_paciente(datos())
    pid = g.db.execute(
        """INSERT INTO pacientes (clinica_id, tipo_documento, numero_documento, nombres, apellidos, sexo,
                                  fecha_nacimiento, telefono, correo, direccion, registrado_por)
           VALUES (%(cid)s, %(tipo_documento)s, %(numero_documento)s, %(nombres)s, %(apellidos)s, %(sexo)s,
                   %(fecha_nacimiento)s, %(telefono)s, %(correo)s, %(direccion)s, %(uid)s) RETURNING id""",
        {**v, "cid": g.cid, "uid": g.user["id"]}).fetchone()["id"]
    g.db.execute("INSERT INTO historiales_clinicos (clinica_id, paciente_id) VALUES (%s, %s)", (g.cid, pid))
    auditar("paciente_creado", "pacientes", pid)
    return jsonify(paciente_dict(buscar_paciente(pid))), 201


@bp.put("/api/pacientes/<int:pid>")
@api(escritura=True)
def editar_paciente(pid):
    antes = buscar_paciente(pid)
    v = _datos_paciente(datos())
    g.db.execute(
        """UPDATE pacientes SET tipo_documento = %(tipo_documento)s, numero_documento = %(numero_documento)s,
                  nombres = %(nombres)s, apellidos = %(apellidos)s, sexo = %(sexo)s, fecha_nacimiento = %(fecha_nacimiento)s,
                  telefono = %(telefono)s, correo = %(correo)s, direccion = %(direccion)s WHERE id = %(id)s""",
        {**v, "id": pid})
    cambios = sorted(k for k in v if (antes[k] or None) != (v[k] or None))
    auditar("paciente_editado", "pacientes", pid, {"campos": cambios})
    return jsonify(paciente_dict(buscar_paciente(pid)))


@bp.post("/api/pacientes/<int:pid>/baja")
@api(roles=GESTION, escritura=True)
def baja_paciente(pid):
    buscar_paciente(pid, activo=True)
    g.db.execute("UPDATE pacientes SET activo = false WHERE id = %s", (pid,))
    canceladas = g.db.execute(
        """UPDATE citas SET estado = 'cancelada', motivo_cancelacion = 'Paciente dado de baja'
            WHERE paciente_id = %s AND estado = 'pendiente' AND inicia_en > now() RETURNING id""", (pid,)).fetchall()
    if canceladas:
        g.db.execute("DELETE FROM notificaciones WHERE cita_id = ANY(%s) AND estado = 'pendiente'",
                     ([c["id"] for c in canceladas],))
    auditar("paciente_baja", "pacientes", pid, {"citas_canceladas": len(canceladas)})
    return jsonify(ok=True, citasCanceladas=len(canceladas))


@bp.post("/api/pacientes/<int:pid>/reactivar")
@api(roles=ADMIN, escritura=True)
def reactivar_paciente(pid):
    buscar_paciente(pid, activo=False)
    plan = g.sub["plan"]
    if plan["max_pacientes"] is not None and uso(g.db)["pacientes"] >= plan["max_pacientes"]:
        return limite(f"Alcanzaste el límite de {plan['max_pacientes']} pacientes activos del plan {plan['nombre']}.")
    g.db.execute("UPDATE pacientes SET activo = true WHERE id = %s", (pid,))
    auditar("paciente_reactivado", "pacientes", pid)
    return jsonify(ok=True)


# ----------------------------------------------------------------------------
# Agenda
# ----------------------------------------------------------------------------
@bp.get("/api/doctores")
@api()
def doctores():
    filas = g.db.execute(
        """SELECT u.id, u.nombre_usuario, d.numero_colegiatura, d.turno::text AS turno
             FROM doctores d JOIN usuarios u ON u.clinica_id = d.clinica_id AND u.id = d.usuario_id
            WHERE u.activo ORDER BY u.nombre_usuario""").fetchall()
    return jsonify([{"id": f["id"], "usuario": f["nombre_usuario"], "colegiatura": f["numero_colegiatura"],
                     "turno": f["turno"]} for f in filas])


SQL_CITA = """
SELECT c.id, to_char(c.inicia_en, 'YYYY-MM-DD') AS fecha, to_char(c.inicia_en, 'HH24:MI') AS hora,
       to_char(c.termina_en, 'HH24:MI') AS hora_fin, (extract(epoch FROM c.termina_en - c.inicia_en) / 60)::int AS minutos,
       c.estado::text AS estado, c.motivo_cancelacion, c.paciente_id, p.nombres || ' ' || p.apellidos AS paciente,
       p.tipo_documento::text AS tipo_documento, p.numero_documento, p.telefono, c.doctor_id, u.nombre_usuario AS doctor,
       (r.id IS NOT NULL) AS tiene_registro, c.inicia_en < now() AS pasada
  FROM citas c
  JOIN pacientes p ON p.clinica_id = c.clinica_id AND p.id = c.paciente_id
  JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id
  LEFT JOIN registros_clinicos r ON r.clinica_id = c.clinica_id AND r.cita_id = c.id"""


def cita_dict(c) -> dict:
    return {
        "id": c["id"], "fecha": c["fecha"], "hora": c["hora"], "horaFin": c["hora_fin"], "minutos": c["minutos"],
        "estado": c["estado"], "motivoCancelacion": c["motivo_cancelacion"] or "", "pacienteId": c["paciente_id"],
        "paciente": c["paciente"], "documento": f"{c['tipo_documento']} {c['numero_documento']}",
        "telefono": c["telefono"] or "", "doctorId": c["doctor_id"], "doctor": c["doctor"],
        "tieneRegistro": c["tiene_registro"], "pasada": c["pasada"],
    }


def rango(f: date, periodo: str):
    if periodo == "semana":
        ini = f - timedelta(days=f.weekday())
        return ini, ini + timedelta(days=6)
    if periodo == "mes":
        ini = f.replace(day=1)
        sig = (ini + timedelta(days=32)).replace(day=1)
        return ini, sig - timedelta(days=1)
    return f, f


@bp.get("/api/citas")
@api()
def listar_citas():
    f = fecha(request.args["fecha"]) if request.args.get("fecha") else hoy(g.db)
    ini, fin = rango(f, request.args.get("periodo", "dia"))
    params = [ini, fin]
    sql = SQL_CITA + " WHERE c.inicia_en >= %s::date AND c.inicia_en < (%s::date + 1)"
    doctor = g.user["id"] if es_doctor_rol() else request.args.get("doctor", type=int)
    if doctor:
        sql += " AND c.doctor_id = %s"
        params.append(doctor)
    filas = g.db.execute(sql + " ORDER BY c.inicia_en", params).fetchall()
    return jsonify(rango={"inicio": ini.isoformat(), "fin": fin.isoformat()}, citas=[cita_dict(c) for c in filas])


def obtener_cita(cid: int):
    c = g.db.execute(SQL_CITA + " WHERE c.id = %s", (cid,)).fetchone()
    if not c:
        raise ValueError("La cita no existe.")
    if es_doctor_rol() and c["doctor_id"] != g.user["id"]:
        raise PermissionError("Esta cita pertenece a otro doctor.")
    return c


def programar_recordatorios(con, cita_id: int) -> None:
    """Recordatorio 24 h antes por cada canal disponible del paciente (correo y/o WhatsApp)."""
    c = con.execute(
        """SELECT c.inicia_en, p.correo, p.telefono FROM citas c
             JOIN pacientes p ON p.clinica_id = c.clinica_id AND p.id = c.paciente_id
            WHERE c.id = %s AND c.estado = 'pendiente' AND c.inicia_en > now()""", (cita_id,)).fetchone()
    con.execute("DELETE FROM notificaciones WHERE cita_id = %s AND estado <> 'enviada'", (cita_id,))
    if not c:
        return
    canales = [k for k, v in (("correo", c["correo"]), ("whatsapp", c["telefono"])) if v]
    for canal in canales:
        con.execute(
            """INSERT INTO notificaciones (clinica_id, tipo, canal, cita_id, programada_para)
               VALUES (current_setting('app.clinica_id')::bigint, 'recordatorio_cita', %s, %s,
                       greatest(now(), %s - interval '24 hours'))
               ON CONFLICT (cita_id, canal, tipo) WHERE cita_id IS NOT NULL
               DO UPDATE SET programada_para = EXCLUDED.programada_para, estado = 'pendiente', intentos = 0, enviada_en = NULL""",
            (canal, cita_id, c["inicia_en"]))


def insertar_cita(con, cid: int, paciente_id: int, doctor_id: int, dia, hhmm: str, minutos: int, estado="pendiente") -> int:
    return con.execute(
        """INSERT INTO citas (clinica_id, paciente_id, doctor_id, inicia_en, termina_en, estado)
           VALUES (%s, %s, %s, (%s::date + %s::time)::timestamptz,
                   (%s::date + %s::time)::timestamptz + make_interval(mins => %s), %s) RETURNING id""",
        (cid, paciente_id, doctor_id, dia, hhmm, dia, hhmm, minutos, estado)).fetchone()["id"]


def _duracion(v) -> int:
    m = entero(v or 30, "duración")
    if m not in DURACIONES:
        raise ValueError("Duración de cita no válida.")
    return m


def _doctor_valido(doctor_id) -> int:
    doctor_id = entero(doctor_id, "doctor")
    ok = g.db.execute("""SELECT 1 FROM doctores d JOIN usuarios u ON u.clinica_id = d.clinica_id AND u.id = d.usuario_id
                          WHERE d.usuario_id = %s AND u.activo""", (doctor_id,)).fetchone()
    if not ok:
        raise ValueError("Selecciona un doctor válido.")
    return doctor_id


def _no_en_pasado(dia, hhmm):
    pasado = g.db.execute("SELECT (%s::date + %s::time)::timestamptz < now() - interval '5 minutes' AS p", (dia, hhmm)).fetchone()["p"]
    if pasado:
        raise ValueError("No puedes agendar en una fecha u hora que ya pasó.")


@bp.post("/api/citas")
@api(escritura=True)
def crear_cita():
    d = datos()
    if es_doctor_rol():
        if not g.user["esDoctor"]:
            raise ValueError("Tu usuario no tiene perfil de doctor. Pide al administrador que registre tu colegiatura.")
        doctor_id = g.user["id"]
    else:
        doctor_id = _doctor_valido(d.get("doctorId"))
    paciente = buscar_paciente(entero(d.get("pacienteId"), "paciente"), activo=True)
    dia, hhmm, minutos = fecha(d.get("fecha")), hora(d.get("hora")), _duracion(d.get("minutos"))
    _no_en_pasado(dia, hhmm)
    cita_id = insertar_cita(g.db, g.cid, paciente["id"], doctor_id, dia, hhmm, minutos)
    programar_recordatorios(g.db, cita_id)
    auditar("cita_creada", "citas", cita_id, {"inicia": f"{dia} {hhmm}", "minutos": minutos})
    return jsonify(cita_dict(obtener_cita(cita_id))), 201


@bp.post("/api/citas/<int:cid>/reprogramar")
@api(escritura=True)
def reprogramar_cita(cid):
    c = obtener_cita(cid)
    if c["estado"] != "pendiente":
        raise ValueError("Solo se pueden reprogramar citas pendientes.")
    d = datos()
    dia, hhmm = fecha(d.get("fecha")), hora(d.get("hora"))
    minutos = _duracion(d.get("minutos") or c["minutos"])
    _no_en_pasado(dia, hhmm)
    g.db.execute(
        """UPDATE citas SET inicia_en = (%s::date + %s::time)::timestamptz,
                  termina_en = (%s::date + %s::time)::timestamptz + make_interval(mins => %s) WHERE id = %s""",
        (dia, hhmm, dia, hhmm, minutos, cid))
    programar_recordatorios(g.db, cid)
    auditar("cita_reprogramada", "citas", cid, {"antes": f"{c['fecha']} {c['hora']}", "ahora": f"{dia} {hhmm}"})
    return jsonify(cita_dict(obtener_cita(cid)))


@bp.post("/api/citas/<int:cid>/cancelar")
@api(escritura=True)
def cancelar_cita(cid):
    c = obtener_cita(cid)
    if c["estado"] != "pendiente":
        raise ValueError("Solo se pueden cancelar citas pendientes.")
    motivo = texto(datos().get("motivo"), 300, True, "motivo")
    if len(motivo) < 5:
        raise ValueError("Describe el motivo de la cancelación (mínimo 5 caracteres).")
    g.db.execute("UPDATE citas SET estado = 'cancelada', motivo_cancelacion = %s WHERE id = %s", (motivo, cid))
    g.db.execute("DELETE FROM notificaciones WHERE cita_id = %s AND estado <> 'enviada'", (cid,))
    auditar("cita_cancelada", "citas", cid, {"motivo": motivo})
    return jsonify(ok=True)


@bp.post("/api/citas/<int:cid>/completar")
@api(escritura=True)
def completar_cita(cid):
    c = obtener_cita(cid)
    if c["estado"] != "pendiente":
        raise ValueError("La cita ya no está pendiente.")
    g.db.execute("UPDATE citas SET estado = 'completada' WHERE id = %s", (cid,))
    g.db.execute("DELETE FROM notificaciones WHERE cita_id = %s AND estado <> 'enviada'", (cid,))
    auditar("cita_completada", "citas", cid)
    return jsonify(ok=True)


# ----------------------------------------------------------------------------
# Historial clínico
# ----------------------------------------------------------------------------
def odontograma_actual(hid: int) -> dict:
    estado = {}
    for h in g.db.execute(
            """SELECT v.pieza_codigo, v.superficie::text AS superficie, c.codigo
                 FROM v_odontograma_actual v JOIN condiciones_dentales c ON c.id = v.condicion_id
                WHERE v.historial_id = %s AND c.codigo <> 'sano'""", (hid,)).fetchall():
        t = estado.setdefault(str(h["pieza_codigo"]), {"surf": {}, "whole": None})
        if h["superficie"]:
            t["surf"][h["superficie"]] = h["codigo"]
        else:
            t["whole"] = h["codigo"]
    return estado


def _historial_de(pid: int):
    h = g.db.execute("SELECT id, observaciones, actualizado_en FROM historiales_clinicos WHERE paciente_id = %s", (pid,)).fetchone()
    if not h:
        h = g.db.execute("""INSERT INTO historiales_clinicos (clinica_id, paciente_id) VALUES (%s, %s)
                            RETURNING id, observaciones, actualizado_en""", (g.cid, pid)).fetchone()
    return h


def _recetas_por_registro(ids):
    if not ids:
        return {}
    recetas = {}
    for r in g.db.execute(
            """SELECT r.id, r.registro_clinico_id, r.indicaciones_generales, r.emitida_en,
                      m.nombre, m.presentacion, d.cantidad, d.indicaciones
                 FROM recetas r
                 LEFT JOIN receta_detalles d ON d.clinica_id = r.clinica_id AND d.receta_id = r.id
                 LEFT JOIN medicamentos m ON m.clinica_id = d.clinica_id AND m.id = d.medicamento_id
                WHERE r.registro_clinico_id = ANY(%s) ORDER BY d.id""", (ids,)).fetchall():
        x = recetas.setdefault(r["registro_clinico_id"], {"id": r["id"], "indicaciones": r["indicaciones_generales"],
                                                          "emitida": iso(r["emitida_en"]), "medicamentos": []})
        if r["nombre"]:
            x["medicamentos"].append({"nombre": r["nombre"], "presentacion": r["presentacion"] or "",
                                      "cantidad": float(r["cantidad"]), "indicaciones": r["indicaciones"]})
    return recetas


@bp.get("/api/pacientes/<int:pid>/historial")
@api(roles=CLINICO)
def ver_historial(pid):
    paciente = buscar_paciente(pid)
    h = _historial_de(pid)
    regs = g.db.execute(
        """SELECT r.id, r.cita_id, to_char(r.atendido_en, 'YYYY-MM-DD') AS fecha, to_char(c.inicia_en, 'HH24:MI') AS hora,
                  r.diagnostico, r.tratamiento, r.observaciones, c.doctor_id, u.nombre_usuario AS doctor
             FROM registros_clinicos r
             JOIN citas c ON c.clinica_id = r.clinica_id AND c.id = r.cita_id
             JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id
            WHERE c.paciente_id = %s ORDER BY r.atendido_en DESC""", (pid,)).fetchall()
    recetas = _recetas_por_registro([r["id"] for r in regs])
    sql_citas = SQL_CITA + """ WHERE c.paciente_id = %s AND c.estado <> 'cancelada' AND r.id IS NULL
                               AND c.inicia_en < (current_date + 1)"""
    params = [pid]
    if es_doctor_rol():
        sql_citas += " AND c.doctor_id = %s"
        params.append(g.user["id"])
    atendibles = g.db.execute(sql_citas + " ORDER BY c.inicia_en DESC LIMIT 20", params).fetchall()
    proximas = g.db.execute(SQL_CITA + " WHERE c.paciente_id = %s AND c.estado = 'pendiente' AND c.inicia_en >= (current_date + 1)"
                            " ORDER BY c.inicia_en LIMIT 5", (pid,)).fetchall()
    conds = g.db.execute("SELECT codigo, nombre FROM condiciones_dentales ORDER BY id").fetchall()
    return jsonify(
        paciente=paciente_dict(paciente),
        historial={"id": h["id"], "observaciones": h["observaciones"], "actualizado": iso(h["actualizado_en"])},
        registros=[{"id": r["id"], "citaId": r["cita_id"], "fecha": r["fecha"], "hora": r["hora"], "doctor": r["doctor"],
                    "doctorId": r["doctor_id"], "diagnostico": r["diagnostico"], "tratamiento": r["tratamiento"],
                    "observaciones": r["observaciones"], "receta": recetas.get(r["id"]),
                    "editable": not es_doctor_rol() or r["doctor_id"] == g.user["id"]} for r in regs],
        citasAtendibles=[cita_dict(c) for c in atendibles],
        proximas=[cita_dict(c) for c in proximas],
        odontograma=odontograma_actual(h["id"]),
        condiciones=[dict(c) for c in conds],
    )


@bp.put("/api/historiales/<int:hid>/observaciones")
@api(roles=CLINICO, escritura=True)
def guardar_observaciones(hid):
    obs = texto(datos().get("texto"), 5000, nombre="antecedentes y notas")
    if not g.db.execute("UPDATE historiales_clinicos SET observaciones = %s WHERE id = %s RETURNING id", (obs, hid)).fetchone():
        raise ValueError("El historial no existe.")
    auditar("historial_notas", "historiales_clinicos", hid)
    return jsonify(ok=True)


def _textos_consulta(d):
    return (texto(d.get("diagnostico"), 2000, True, "diagnóstico"), texto(d.get("tratamiento"), 2000, True, "tratamiento"),
            texto(d.get("observaciones"), 2000))


def _insertar_registro(cita_id: int, d) -> int:
    diag, trat, obs = _textos_consulta(d)
    rid = g.db.execute(
        """INSERT INTO registros_clinicos (clinica_id, cita_id, diagnostico, tratamiento, observaciones)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""", (g.cid, cita_id, diag, trat, obs)).fetchone()["id"]
    g.db.execute("UPDATE citas SET estado = 'completada' WHERE id = %s AND estado = 'pendiente'", (cita_id,))
    g.db.execute("DELETE FROM notificaciones WHERE cita_id = %s AND estado <> 'enviada'", (cita_id,))
    auditar("consulta_registrada", "registros_clinicos", rid, {"cita": cita_id})
    return rid


@bp.post("/api/citas/<int:cid>/registro")
@api(roles=CLINICO, escritura=True)
def registrar_consulta(cid):
    c = obtener_cita(cid)
    if c["estado"] == "cancelada":
        raise ValueError("No se puede registrar una consulta sobre una cita cancelada.")
    if c["tiene_registro"]:
        raise ValueError("Esta cita ya tiene una consulta registrada.")
    return jsonify(id=_insertar_registro(cid, datos())), 201


@bp.post("/api/pacientes/<int:pid>/atencion")
@api(roles=CLINICO, escritura=True)
def atencion_sin_cita(pid):
    """Paciente atendido sin cita previa: se crea la cita (ahora) ya completada y su consulta."""
    d = datos()
    buscar_paciente(pid, activo=True)
    if g.user["esDoctor"] and not d.get("doctorId"):
        doctor_id = g.user["id"]
    elif es_doctor_rol():
        raise ValueError("Tu usuario no tiene perfil de doctor.")
    else:
        doctor_id = _doctor_valido(d.get("doctorId"))
    _textos_consulta(d)
    ahora = g.db.execute("SELECT current_date AS d, to_char(now(), 'HH24:MI') AS h").fetchone()
    cita_id = insertar_cita(g.db, g.cid, pid, doctor_id, ahora["d"], ahora["h"], 30, "completada")
    return jsonify(id=_insertar_registro(cita_id, d)), 201


def _registro_editable(rid: int):
    r = g.db.execute("""SELECT r.id, c.doctor_id, c.paciente_id FROM registros_clinicos r
                          JOIN citas c ON c.clinica_id = r.clinica_id AND c.id = r.cita_id WHERE r.id = %s""", (rid,)).fetchone()
    if not r:
        raise ValueError("La consulta no existe.")
    if es_doctor_rol() and r["doctor_id"] != g.user["id"]:
        raise PermissionError("Solo el doctor que atendió puede modificar esta consulta.")
    return r


@bp.put("/api/registros/<int:rid>")
@api(roles=CLINICO, escritura=True)
def editar_consulta(rid):
    _registro_editable(rid)
    diag, trat, obs = _textos_consulta(datos())
    g.db.execute("UPDATE registros_clinicos SET diagnostico = %s, tratamiento = %s, observaciones = %s WHERE id = %s",
                 (diag, trat, obs, rid))
    auditar("consulta_editada", "registros_clinicos", rid)
    return jsonify(ok=True)


# ----------------------------------------------------------------------------
# Odontograma (hallazgos fechados; el estado vigente sale de v_odontograma_actual)
# ----------------------------------------------------------------------------
@bp.put("/api/historiales/<int:hid>/odontograma")
@api(roles=CLINICO, escritura=True)
def guardar_odontograma(hid):
    d = datos()
    if not g.db.execute("SELECT 1 FROM historiales_clinicos WHERE id = %s", (hid,)).fetchone():
        raise ValueError("El historial no existe.")
    cambios = d.get("cambios")
    if not isinstance(cambios, list) or not cambios or len(cambios) > 300:
        raise ValueError("No hay cambios que guardar.")
    piezas = {r["codigo"] for r in g.db.execute("SELECT codigo FROM piezas_dentales").fetchall()}
    conds = {r["codigo"]: r["id"] for r in g.db.execute("SELECT id, codigo FROM condiciones_dentales").fetchall()}
    registro_id = d.get("registroId")
    if registro_id:
        registro_id = entero(registro_id, "consulta")
        if not g.db.execute("""SELECT 1 FROM registros_clinicos r JOIN citas c ON c.clinica_id = r.clinica_id AND c.id = r.cita_id
                               JOIN historiales_clinicos h ON h.clinica_id = c.clinica_id AND h.paciente_id = c.paciente_id
                               WHERE r.id = %s AND h.id = %s""", (registro_id, hid)).fetchone():
            raise ValueError("La consulta indicada no pertenece a este paciente.")
    notas = texto(d.get("notas"), 500) or None
    filas = []
    for c in cambios:
        if not isinstance(c, dict):
            raise ValueError("Cambio de odontograma inválido.")
        pieza, sup, cond = entero(c.get("pieza"), "pieza"), c.get("superficie") or None, c.get("condicion")
        if pieza not in piezas or cond not in conds or (sup is not None and sup not in SUPERFICIES):
            raise ValueError("Cambio de odontograma inválido.")
        if (cond in COND_SUPERFICIE and sup is None) or (cond in COND_PIEZA and sup is not None):
            raise ValueError("La condición no corresponde a la superficie indicada.")
        filas.append((g.cid, hid, pieza, sup, conds[cond], registro_id, notas))
    with g.db.cursor() as cur:
        cur.executemany(
            """INSERT INTO odontograma_hallazgos (clinica_id, historial_id, pieza_codigo, superficie, condicion_id,
                                                  registro_clinico_id, notas) VALUES (%s, %s, %s, %s, %s, %s, %s)""", filas)
    auditar("odontograma_actualizado", "historiales_clinicos", hid, {"hallazgos": len(filas)})
    return jsonify(odontograma=odontograma_actual(hid))


@bp.get("/api/historiales/<int:hid>/hallazgos")
@api(roles=CLINICO)
def hallazgos(hid):
    filas = g.db.execute(
        """SELECT h.pieza_codigo, h.superficie::text AS superficie, c.codigo, c.nombre, h.notas, h.registrado_en,
                  to_char(h.registrado_en, 'YYYY-MM-DD HH24:MI') AS cuando
             FROM odontograma_hallazgos h JOIN condiciones_dentales c ON c.id = h.condicion_id
            WHERE h.historial_id = %s ORDER BY h.registrado_en DESC, h.id DESC LIMIT 80""", (hid,)).fetchall()
    return jsonify([{"pieza": f["pieza_codigo"], "superficie": f["superficie"], "condicion": f["codigo"],
                     "nombre": f["nombre"], "notas": f["notas"] or "", "cuando": f["cuando"]} for f in filas])


# ----------------------------------------------------------------------------
# Recetas y catálogo de medicamentos
# ----------------------------------------------------------------------------
@bp.get("/api/medicamentos")
@api(roles=CLINICO)
def medicamentos():
    q = texto(request.args.get("q"), 80)
    filas = g.db.execute("""SELECT id, nombre, presentacion FROM medicamentos
                             WHERE activo AND nombre ILIKE %s ORDER BY nombre LIMIT 10""", (f"%{q}%",)).fetchall()
    return jsonify([dict(f) for f in filas])


def _medicamento_id(nombre: str, presentacion) -> int:
    fila = g.db.execute("SELECT id FROM medicamentos WHERE lower(nombre) = lower(%s)", (nombre,)).fetchone()
    if fila:
        return fila["id"]
    return g.db.execute("INSERT INTO medicamentos (clinica_id, nombre, presentacion) VALUES (%s, %s, %s) RETURNING id",
                        (g.cid, nombre, presentacion)).fetchone()["id"]


@bp.post("/api/registros/<int:rid>/receta")
@api(roles=CLINICO, escritura=True)
def emitir_receta(rid):
    _registro_editable(rid)
    d = datos()
    meds = d.get("medicamentos") if isinstance(d.get("medicamentos"), list) else []
    if not meds:
        raise ValueError("Agrega al menos un medicamento a la receta.")
    detalles, vistos = [], set()
    for m in meds[:30]:
        if not isinstance(m, dict):
            raise ValueError("Medicamento inválido.")
        nombre = texto(m.get("nombre"), 120, True, "medicamento")
        try:
            cantidad = round(float(m.get("cantidad")), 2)
        except (TypeError, ValueError):
            cantidad = 0
        if cantidad <= 0:
            raise ValueError(f"Indica una cantidad válida para {nombre}.")
        mid = _medicamento_id(nombre, texto(m.get("presentacion"), 80) or None)
        if mid in vistos:
            raise ValueError(f"{nombre} está repetido en la receta.")
        vistos.add(mid)
        detalles.append((mid, cantidad, texto(m.get("indicaciones"), 300, True, f"indicaciones de {nombre}")))
    receta_id = g.db.execute(
        """INSERT INTO recetas (clinica_id, registro_clinico_id, indicaciones_generales) VALUES (%s, %s, %s) RETURNING id""",
        (g.cid, rid, texto(d.get("indicaciones"), 1000))).fetchone()["id"]
    with g.db.cursor() as cur:
        cur.executemany("""INSERT INTO receta_detalles (clinica_id, receta_id, medicamento_id, cantidad, indicaciones)
                           VALUES (%s, %s, %s, %s, %s)""", [(g.cid, receta_id, *x) for x in detalles])
    auditar("receta_emitida", "recetas", receta_id, {"medicamentos": len(detalles)})
    return jsonify(id=receta_id), 201


@bp.get("/api/recetas/<int:rid>/pdf")
@api(roles=CLINICO)
def receta_pdf(rid):
    from web.documentos import pdf_receta
    r = g.db.execute(
        """SELECT r.id, r.indicaciones_generales, to_char(r.emitida_en, 'DD/MM/YYYY') AS emitida,
                  p.nombres || ' ' || p.apellidos AS paciente, p.tipo_documento::text AS tipo_doc, p.numero_documento,
                  date_part('year', age(p.fecha_nacimiento))::int AS edad,
                  u.nombre_usuario AS doctor, d.numero_colegiatura, rc.diagnostico
             FROM recetas r
             JOIN registros_clinicos rc ON rc.clinica_id = r.clinica_id AND rc.id = r.registro_clinico_id
             JOIN citas c ON c.clinica_id = rc.clinica_id AND c.id = rc.cita_id
             JOIN pacientes p ON p.clinica_id = c.clinica_id AND p.id = c.paciente_id
             JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id
             LEFT JOIN doctores d ON d.clinica_id = c.clinica_id AND d.usuario_id = c.doctor_id
            WHERE r.id = %s""", (rid,)).fetchone()
    if not r:
        return jsonify(error="Receta no encontrada."), 404
    meds = g.db.execute("""SELECT m.nombre, m.presentacion, d.cantidad, d.indicaciones FROM receta_detalles d
                            JOIN medicamentos m ON m.clinica_id = d.clinica_id AND m.id = d.medicamento_id
                           WHERE d.receta_id = %s ORDER BY d.id""", (rid,)).fetchall()
    contenido = pdf_receta(g.clinica["nombre"], r, meds)
    return send_file(io.BytesIO(contenido), mimetype="application/pdf", download_name=f"receta-{rid}.pdf")


# ----------------------------------------------------------------------------
# Inicio
# ----------------------------------------------------------------------------
ETIQUETAS = {
    "paciente_creado": "Nuevo paciente", "paciente_editado": "Paciente actualizado", "paciente_baja": "Paciente dado de baja",
    "cita_creada": "Nueva cita programada", "cita_reprogramada": "Cita reprogramada", "cita_cancelada": "Cita cancelada",
    "cita_completada": "Cita completada", "consulta_registrada": "Consulta registrada", "receta_emitida": "Receta emitida",
    "odontograma_actualizado": "Odontograma actualizado", "copia_creada": "Copia de seguridad",
}


@bp.get("/api/dashboard")
@api()
def dashboard():
    filtro, params = "", []
    if es_doctor_rol():
        filtro, params = " AND c.doctor_id = %s", [g.user["id"]]
    s = g.db.execute(
        f"""SELECT (SELECT count(*) FROM pacientes WHERE activo) AS pacientes_activos,
                   (SELECT count(*) FROM citas c WHERE c.inicia_en::date = current_date AND c.estado <> 'cancelada'{filtro}) AS citas_hoy,
                   (SELECT count(*) FROM citas c WHERE c.inicia_en::date = current_date AND c.estado = 'completada'{filtro}) AS completadas_hoy,
                   (SELECT count(*) FROM recetas WHERE emitida_en >= date_trunc('month', now())) AS recetas_mes""",
        params * 2).fetchone()
    agenda = g.db.execute(SQL_CITA + " WHERE c.inicia_en::date = current_date AND c.estado <> 'cancelada'" + filtro +
                          " ORDER BY c.inicia_en", params).fetchall()
    semana = g.db.execute(
        f"""SELECT to_char(d, 'YYYY-MM-DD') AS fecha,
                   (SELECT count(*) FROM citas c WHERE c.inicia_en::date = d AND c.estado <> 'cancelada'{filtro}) AS citas
              FROM generate_series(current_date - 6, current_date, interval '1 day') AS d ORDER BY d""", params).fetchall()
    actividad = g.db.execute(
        """SELECT a.accion, a.ocurrido_en, u.nombre_usuario, a.recurso, a.recurso_id FROM auditoria a
             LEFT JOIN usuarios u ON u.clinica_id = a.clinica_id AND u.id = a.usuario_id
            WHERE a.accion = ANY(%s) ORDER BY a.ocurrido_en DESC LIMIT 8""", (list(ETIQUETAS),)).fetchall()
    copia = g.db.execute("SELECT to_char(finalizada_en, 'YYYY-MM-DD HH24:MI') AS f FROM copias_seguridad "
                         "WHERE estado = 'exitoso' ORDER BY finalizada_en DESC LIMIT 1").fetchone()
    pasos = g.db.execute("""SELECT EXISTS (SELECT 1 FROM doctores) AS doctor, EXISTS (SELECT 1 FROM pacientes) AS paciente,
                                   EXISTS (SELECT 1 FROM citas) AS cita""").fetchone()
    return jsonify(
        stats={k: s[k] for k in s},
        agenda=[cita_dict(c) for c in agenda],
        semana=[dict(x) for x in semana],
        actividad=[{"titulo": ETIQUETAS[a["accion"]], "usuario": a["nombre_usuario"] or "sistema",
                    "fecha": iso(a["ocurrido_en"])} for a in actividad],
        ultimaCopia=copia["f"] if copia else None,
        inicio=[
            {"id": "doctor", "texto": "Registra a un odontólogo con su colegiatura", "hecho": pasos["doctor"], "ruta": "equipo"},
            {"id": "paciente", "texto": "Registra un paciente", "hecho": pasos["paciente"], "ruta": "pacientes"},
            {"id": "cita", "texto": "Agenda tu primera cita", "hecho": pasos["cita"], "ruta": "citas"},
        ],
    )
