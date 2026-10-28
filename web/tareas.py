"""
Tareas programadas (ejecutar con cron o un scheduler):

  python -m web.tareas recordatorios   # cada 5 min: envía recordatorios de cita y avisos pendientes
  python -m web.tareas avisos          # diario: avisa a los administradores 3 días antes del vencimiento
  python -m web.tareas copias          # diario: copia automática de cada clínica con respaldos en su plan
  python -m web.tareas todo
"""
import logging
import sys

from web import copias, db, notificador

MAX_INTENTOS = 3
log = logging.getLogger("dental.tareas")


def _clinicas(solo_respaldo=False):
    with db.plataforma() as con:
        sql = """SELECT c.id, c.nombre FROM clinicas c
                   JOIN suscripciones s ON s.clinica_id = c.id AND s.estado IN ('prueba', 'activa') AND s.vence_en >= current_date
                   JOIN planes p ON p.id = s.plan_id WHERE c.activa"""
        return con.execute(sql + (" AND p.permite_respaldos" if solo_respaldo else "")).fetchall()


def _mensaje(con, n, clinica: str):
    if n["tipo"] == "recordatorio_cita":
        c = con.execute(
            """SELECT p.nombres, p.correo, p.telefono, to_char(c.inicia_en, 'DD/MM') AS dia, to_char(c.inicia_en, 'HH24:MI') AS hora,
                      u.nombre_usuario AS doctor, c.estado::text AS estado
                 FROM citas c JOIN pacientes p ON p.clinica_id = c.clinica_id AND p.id = c.paciente_id
                 JOIN usuarios u ON u.clinica_id = c.clinica_id AND u.id = c.doctor_id WHERE c.id = %s""", (n["cita_id"],)).fetchone()
        if not c or c["estado"] != "pendiente":
            return None
        texto = (f"Hola {c['nombres']}, te recordamos tu cita en {clinica} el {c['dia']} a las {c['hora']} "
                 f"con Dr(a). {c['doctor']}. Si no puedes asistir, avísanos para reprogramarla.")
        return (c["correo"] if n["canal"] == "correo" else c["telefono"]), "Recordatorio de tu cita", texto
    u = con.execute("SELECT correo, nombre_usuario FROM usuarios WHERE id = %s AND activo", (n["usuario_id"],)).fetchone()
    if not u:
        return None
    s = con.execute("SELECT to_char(vence_en, 'DD/MM/YYYY') AS v FROM v_suscripcion_actual").fetchone()
    return u["correo"], "Tu suscripción de Dental Home vence pronto", (
        f"Hola {u['nombre_usuario']}: la suscripción de {clinica} vence el {s['v'] if s else 'pronto'}. "
        "Renueva desde Suscripción para no perder el acceso a registrar cambios.")


def recordatorios() -> int:
    enviados = 0
    for cli in _clinicas():
        with db.clinica(cli["id"]) as con:
            pendientes = con.execute(
                """SELECT * FROM notificaciones WHERE estado = 'pendiente' AND programada_para <= now()
                    ORDER BY programada_para LIMIT 200 FOR UPDATE SKIP LOCKED""").fetchall()
            for n in pendientes:
                try:
                    msg = _mensaje(con, n, cli["nombre"])
                    if msg is None or not msg[0]:
                        con.execute("UPDATE notificaciones SET estado = 'fallida', intentos = intentos + 1 WHERE id = %s", (n["id"],))
                        continue
                    destino, asunto, cuerpo = msg
                    if n["canal"] == "correo":
                        notificador.enviar_correo(destino, asunto, cuerpo)
                    else:
                        notificador.enviar_whatsapp(destino, cuerpo)
                    con.execute("UPDATE notificaciones SET estado = 'enviada', enviada_en = now(), intentos = intentos + 1 WHERE id = %s",
                                (n["id"],))
                    enviados += 1
                except Exception:  # noqa: BLE001 — se reintenta en la próxima ejecución
                    log.exception("Fallo al enviar la notificación %s", n["id"])
                    con.execute("""UPDATE notificaciones SET intentos = intentos + 1,
                                          estado = CASE WHEN intentos + 1 >= %s THEN 'fallida'::estado_notificacion ELSE estado END
                                    WHERE id = %s""", (MAX_INTENTOS, n["id"]))
    return enviados


def avisos() -> int:
    creados = 0
    for cli in _clinicas():
        with db.clinica(cli["id"]) as con:
            s = con.execute("SELECT vence_en FROM v_suscripcion_actual WHERE vence_en <= current_date + 3").fetchone()
            if not s:
                continue
            for u in con.execute("SELECT id FROM usuarios WHERE rol = 'administrador' AND activo").fetchall():
                ya = con.execute("""SELECT 1 FROM notificaciones WHERE usuario_id = %s AND tipo = 'aviso_suscripcion'
                                     AND programada_para > now() - interval '20 hours'""", (u["id"],)).fetchone()
                if not ya:
                    con.execute("""INSERT INTO notificaciones (clinica_id, tipo, canal, usuario_id, programada_para)
                                   VALUES (%s, 'aviso_suscripcion', 'correo', %s, now())""", (cli["id"], u["id"]))
                    creados += 1
    return creados


def copias_automaticas() -> int:
    hechas = 0
    for cli in _clinicas(solo_respaldo=True):
        with db.clinica(cli["id"]) as con:
            hechas += copias.crear(con, cli["id"])["estado"] == "exitoso"
    return hechas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    orden = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if orden in ("avisos", "todo"):
        log.info("Avisos de suscripción creados: %s", avisos())
    if orden in ("recordatorios", "todo"):
        log.info("Notificaciones enviadas: %s", recordatorios())
    if orden in ("copias", "todo"):
        log.info("Copias automáticas: %s", copias_automaticas())
    if orden not in ("avisos", "recordatorios", "copias", "todo"):
        print(__doc__)
        sys.exit(2)
