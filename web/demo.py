"""Datos de ejemplo para que una clínica nueva no empiece vacía."""
import secrets
from datetime import timedelta

from web.api_clinica import insertar_cita, programar_recordatorios
from web.seguridad import hashear

PACIENTES = [
    ("Lucía", "Fernández Ccori", "40123456", "F", "1991-04-12", "987654321", "lucia.fernandez@ejemplo.pe"),
    ("Carlos", "Quispe Mamani", "41234567", "M", "1984-09-30", "976543210", None),
    ("Valeria", "Condori Apaza", "42345678", "F", "2001-01-22", "965432109", "valeria.condori@ejemplo.pe"),
    ("Mateo", "Huanca Flores", "73456789", "M", "2015-07-08", "954321098", None),
    ("Rosa", "Apaza Ticona", "44567890", "F", "1968-11-03", "943210987", None),
]
MEDICAMENTOS = [("Ibuprofeno 400 mg", "Tableta"), ("Amoxicilina 500 mg", "Cápsula"), ("Paracetamol 500 mg", "Tableta"),
                ("Clorhexidina 0.12 %", "Colutorio 250 ml"), ("Ketorolaco 10 mg", "Tableta")]


def sembrar(con, cid: int, admin_id: int) -> None:
    clave = hashear(secrets.token_urlsafe(18))
    doctores = []
    for usuario, cop, turno in (("dra.rivera", "COP-12345", "manana"), ("dr.mamani", "COP-67890", "tarde")):
        uid = con.execute("""INSERT INTO usuarios (clinica_id, nombre_usuario, correo, contrasena_hash, rol)
                             VALUES (%s, %s, %s, %s, 'doctor') RETURNING id""",
                          (cid, usuario, f"{usuario}@ejemplo.pe", clave)).fetchone()["id"]
        con.execute("INSERT INTO doctores (usuario_id, clinica_id, numero_colegiatura, turno) VALUES (%s, %s, %s, %s)",
                    (uid, cid, cop, turno))
        doctores.append(uid)
    pacientes = []
    for nom, ape, dni, sexo, nac, tel, mail in PACIENTES:
        pid = con.execute(
            """INSERT INTO pacientes (clinica_id, numero_documento, nombres, apellidos, sexo, fecha_nacimiento,
                                      telefono, correo, direccion, registrado_por)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Puno', %s) RETURNING id""",
            (cid, dni, nom, ape, sexo, nac, tel, mail, admin_id)).fetchone()["id"]
        con.execute("INSERT INTO historiales_clinicos (clinica_id, paciente_id) VALUES (%s, %s)", (cid, pid))
        pacientes.append(pid)
    meds = {}
    for nombre, pres in MEDICAMENTOS:
        meds[nombre] = con.execute("INSERT INTO medicamentos (clinica_id, nombre, presentacion) VALUES (%s, %s, %s) RETURNING id",
                                   (cid, nombre, pres)).fetchone()["id"]

    hoy = con.execute("SELECT current_date AS d").fetchone()["d"]
    # Una consulta ya atendida (ayer) con receta y hallazgos en el odontograma
    ayer = insertar_cita(con, cid, pacientes[0], doctores[0], hoy - timedelta(days=1), "10:00", 30, "completada")
    rid = con.execute("""INSERT INTO registros_clinicos (clinica_id, cita_id, diagnostico, tratamiento, observaciones, atendido_en)
                         VALUES (%s, %s, 'Caries oclusal en pieza 16', 'Restauración con resina compuesta',
                                 'Control en 6 meses', now() - interval '1 day') RETURNING id""", (cid, ayer)).fetchone()["id"]
    rec = con.execute("""INSERT INTO recetas (clinica_id, registro_clinico_id, indicaciones_generales)
                         VALUES (%s, %s, 'Evitar alimentos muy fríos o calientes por 24 horas.') RETURNING id""", (cid, rid)).fetchone()["id"]
    con.execute("""INSERT INTO receta_detalles (clinica_id, receta_id, medicamento_id, cantidad, indicaciones)
                   VALUES (%s, %s, %s, 6, '1 tableta cada 8 horas por 2 días, después de comer')""",
                (cid, rec, meds["Ibuprofeno 400 mg"]))
    hid = con.execute("SELECT id FROM historiales_clinicos WHERE paciente_id = %s", (pacientes[0],)).fetchone()["id"]
    conds = {r["codigo"]: r["id"] for r in con.execute("SELECT id, codigo FROM condiciones_dentales").fetchall()}
    for pieza, sup, cond, reg in ((16, "oclusal", "obturacion", rid), (26, None, "corona", None), (36, "oclusal", "caries", None),
                                  (46, None, "ausente", None), (11, "mesial", "sellante", None)):
        con.execute("""INSERT INTO odontograma_hallazgos (clinica_id, historial_id, pieza_codigo, superficie, condicion_id,
                                                          registro_clinico_id, registrado_en)
                       VALUES (%s, %s, %s, %s, %s, %s, now() - interval '1 day')""", (cid, hid, pieza, sup, conds[cond], reg))
    con.execute("UPDATE historiales_clinicos SET observaciones = %s WHERE id = %s",
                ("Alergias: ninguna conocida.\nAntecedentes: bruxismo nocturno, usa férula.", hid))

    agenda = [(0, 0, "09:00", 30), (1, 0, "10:00", 45), (2, 1, "15:30", 30), (3, 1, "16:30", 60), (4, 0, "11:30", 30)]
    for p, d, h, m in agenda:
        programar_recordatorios(con, insertar_cita(con, cid, pacientes[p], doctores[d], hoy, h, m))
    for dias, p, d, h in ((1, 2, 0, "09:30"), (2, 4, 1, "17:00"), (3, 1, 0, "10:30")):
        programar_recordatorios(con, insertar_cita(con, cid, pacientes[p], doctores[d], hoy + timedelta(days=dias), h, 30))
