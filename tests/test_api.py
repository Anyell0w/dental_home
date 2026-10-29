"""
Prueba de humo de la API contra un PostgreSQL real con db/schema.sql aplicado.

  python -m web.db init && python -m pytest tests/ -q
"""
import json
import re
import uuid
from datetime import date, timedelta

import pytest

from web import db, tareas
from web.app import app
from web.pasarela import secreto_webhook
from web.seguridad import firmar

H = {"X-Requested-With": "fetch"}
MANANA = (date.today() + timedelta(days=1)).isoformat()


def cliente():
    return app.test_client()


def registrar(c, nombre, demo=False):
    r = c.post("/api/registro", headers=H, json={
        "clinica": nombre, "correo": f"{uuid.uuid4().hex[:6]}@prueba.pe", "usuario": "admin",
        "password": "clave12345", "plan": "esencial", "demo": demo, "atiende": True, "colegiatura": f"COP-{uuid.uuid4().hex[:5]}"})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["codigo"]


@pytest.fixture(scope="module")
def clinica_a():
    c = cliente()
    codigo = registrar(c, f"Sonrisa {uuid.uuid4().hex[:4]}", demo=True)
    return c, codigo


def test_planes_publicos():
    planes = cliente().get("/api/planes").get_json()
    assert [p["codigo"] for p in planes] == ["esencial", "profesional", "clinica"]


def test_contexto_y_demo(clinica_a):
    c, codigo = clinica_a
    me = c.get("/api/me").get_json()
    assert me["usuario"]["rol"] == "administrador" and me["usuario"]["esDoctor"]
    assert me["suscripcion"]["estado"] == "prueba" and me["suscripcion"]["vigente"]
    assert me["uso"]["pacientes"] == 5
    d = c.get("/api/dashboard").get_json()
    assert d["stats"]["citas_hoy"] == 5 and len(d["agenda"]) == 5


def test_csrf_y_sin_sesion():
    assert cliente().post("/api/pacientes", json={}).status_code == 403
    assert cliente().get("/api/pacientes").status_code == 401


def test_aislamiento_entre_clinicas(clinica_a):
    c, _ = clinica_a
    otra = cliente()
    registrar(otra, f"Otra {uuid.uuid4().hex[:4]}")
    assert otra.get("/api/pacientes").get_json() == []
    pid = c.get("/api/pacientes").get_json()[0]["id"]
    assert otra.get(f"/api/pacientes/{pid}/historial").status_code == 400  # RLS: no existe para la otra clínica


def test_paciente_y_validaciones(clinica_a):
    c, _ = clinica_a
    r = c.post("/api/pacientes", headers=H, json={"tipoDocumento": "DNI", "numeroDocumento": "1234", "nombres": "A", "apellidos": "B"})
    assert r.status_code == 400 and "8 dígitos" in r.get_json()["error"]
    nuevo = {"tipoDocumento": "DNI", "numeroDocumento": "45678901", "nombres": "Ana", "apellidos": "Ccama",
             "sexo": "F", "fechaNacimiento": "1990-05-01", "correo": "ANA@correo.pe", "telefono": "900111222"}
    r = c.post("/api/pacientes", headers=H, json=nuevo)
    assert r.status_code == 201 and r.get_json()["correo"] == "ana@correo.pe"
    assert c.post("/api/pacientes", headers=H, json=nuevo).status_code == 409


def test_citas_sin_cruces_y_recordatorios(clinica_a):
    c, _ = clinica_a
    doc = c.get("/api/doctores").get_json()[0]["id"]
    pac = [p for p in c.get("/api/pacientes?q=Ccama").get_json()][0]["id"]
    r = c.post("/api/citas", headers=H, json={"pacienteId": pac, "doctorId": doc, "fecha": MANANA, "hora": "12:00", "minutos": 60})
    assert r.status_code == 201, r.get_json()
    cid = r.get_json()["id"]
    r = c.post("/api/citas", headers=H, json={"pacienteId": pac, "doctorId": doc, "fecha": MANANA, "hora": "12:30", "minutos": 30})
    assert r.status_code == 409 and "cruza" in r.get_json()["error"]
    with db.clinica(_cid(c)) as con:
        canales = {n["canal"] for n in con.execute("SELECT canal::text FROM notificaciones WHERE cita_id = %s", (cid,)).fetchall()}
    assert canales == {"correo", "whatsapp"}
    assert c.post(f"/api/citas/{cid}/reprogramar", headers=H, json={"fecha": MANANA, "hora": "13:00"}).status_code == 200
    assert c.post(f"/api/citas/{cid}/cancelar", headers=H, json={"motivo": "corto"}).status_code == 200


def _cid(c):
    return int(c.get_cookie("dh_sesion").value.split(".")[0])


def test_consulta_receta_odontograma(clinica_a):
    c, _ = clinica_a
    pid = c.get("/api/pacientes?q=Quispe").get_json()[0]["id"]
    h = c.get(f"/api/pacientes/{pid}/historial").get_json()
    r = c.post(f"/api/pacientes/{pid}/atencion", headers=H, json={"diagnostico": "Gingivitis", "tratamiento": "Profilaxis"})
    assert r.status_code == 201, r.get_json()
    rid = r.get_json()["id"]
    r = c.post(f"/api/registros/{rid}/receta", headers=H, json={"indicaciones": "Control", "medicamentos": [
        {"nombre": "Clorhexidina 0.12 %", "cantidad": 1, "indicaciones": "Enjuague 2 veces al día"},
        {"nombre": "Nuevo Gel 1 %", "presentacion": "Tubo", "cantidad": 1, "indicaciones": "Aplicar en encías"}]})
    assert r.status_code == 201, r.get_json()
    pdf = c.get(f"/api/recetas/{r.get_json()['id']}/pdf")
    assert pdf.status_code == 200 and pdf.data[:4] == b"%PDF"
    hid = h["historial"]["id"]
    r = c.put(f"/api/historiales/{hid}/odontograma", headers=H, json={"registroId": rid, "cambios": [
        {"pieza": 16, "superficie": "oclusal", "condicion": "caries"}, {"pieza": 21, "superficie": None, "condicion": "corona"},
        {"pieza": 55, "superficie": "vestibular", "condicion": "sellante"}]})
    assert r.status_code == 200 and r.get_json()["odontograma"]["16"]["surf"]["oclusal"] == "caries"
    r = c.put(f"/api/historiales/{hid}/odontograma", headers=H, json={"cambios": [{"pieza": 16, "superficie": "oclusal", "condicion": "sano"}]})
    assert "16" not in r.get_json()["odontograma"]
    bad = c.put(f"/api/historiales/{hid}/odontograma", headers=H, json={"cambios": [{"pieza": 99, "superficie": None, "condicion": "corona"}]})
    assert bad.status_code == 400
    assert len(c.get(f"/api/historiales/{hid}/hallazgos").get_json()) == 4


def test_equipo_limites_y_bloqueo(clinica_a):
    c, codigo = clinica_a
    r = c.post("/api/usuarios", headers=H, json={"usuario": "recepcion", "correo": "recepcion@x.pe", "rol": "secretaria", "password": "clave12345"})
    assert r.status_code == 400 and "permite hasta 3" in r.get_json()["error"]  # esencial: admin + 2 doctores demo
    c2 = cliente()
    for _ in range(5):
        assert c2.post("/api/login", headers=H, json={"clinica": codigo, "usuario": "admin", "password": "mala"}).status_code == 401
    r = c2.post("/api/login", headers=H, json={"clinica": codigo, "usuario": "admin", "password": "clave12345"})
    assert r.status_code == 429
    uid = c.get("/api/me").get_json()["usuario"]["id"]
    assert c.post(f"/api/usuarios/{uid}/desbloquear", headers=H).status_code == 200
    assert c2.post("/api/login", headers=H, json={"clinica": codigo, "usuario": "admin", "password": "clave12345"}).status_code == 200
    acciones = {a["accion"] for a in c.get("/api/auditoria").get_json()["items"]}
    assert {"login_fallido", "usuario_bloqueado", "usuario_desbloqueado", "login"} <= acciones


def test_recuperar_contrasena(clinica_a, tmp_path, monkeypatch):
    c, codigo = clinica_a
    import web.notificador as n
    monkeypatch.setattr(n, "DATA_DIR", str(tmp_path))
    correo_admin = c.get("/api/me").get_json()["usuario"]["correo"]
    assert cliente().post("/api/recuperar", headers=H, json={"clinica": codigo, "correo": correo_admin}).status_code == 200
    linea = json.loads((tmp_path / "outbox.log").read_text().splitlines()[-1])
    cid, tok = re.search(r"c=(\d+)&t=([\w-]+)", linea["cuerpo"]).groups()
    assert cliente().post("/api/restablecer", headers=H, json={"c": cid, "t": tok, "password": "nueva12345"}).status_code == 200
    assert cliente().post("/api/restablecer", headers=H, json={"c": cid, "t": tok, "password": "otra12345"}).status_code == 400
    assert c.get("/api/me").status_code == 401  # sesiones revocadas al restablecer
    r = c.post("/api/login", headers=H, json={"clinica": codigo, "usuario": correo_admin, "password": "nueva12345"})
    assert r.status_code == 200


def test_pago_webhook_idempotente(clinica_a):
    c, _ = clinica_a
    r = c.post("/api/suscripcion/pagar", headers=H, json={"plan": "profesional"})
    assert r.status_code == 201, r.get_json()
    ref = r.get_json()["referencia"]
    cuerpo = json.dumps({"id": "evt_" + uuid.uuid4().hex, "tipo": "pago.aprobado", "referencia": ref, "monto": 99.0}).encode()
    with app.app_context():
        firma = firmar(secreto_webhook(), cuerpo)
    w = cliente()
    assert w.post("/api/webhooks/simulada", data=cuerpo, headers={"X-Firma": "mala"}).status_code == 401
    assert w.post("/api/webhooks/simulada", data=cuerpo, headers={"X-Firma": firma}).get_json()["resultado"] == "pagado"
    assert w.post("/api/webhooks/simulada", data=cuerpo, headers={"X-Firma": firma}).get_json()["resultado"] == "duplicado"
    s = c.get("/api/suscripcion").get_json()
    assert s["suscripcion"]["estado"] == "activa" and s["suscripcion"]["plan"]["codigo"] == "profesional"
    assert [p["estado"] for p in s["pagos"]] == ["pagado"]


def test_reportes_y_copias(clinica_a):
    c, _ = clinica_a
    hoy = date.today().isoformat()
    for tipo in ("citas", "pacientes", "actividad"):
        for formato in ("pdf", "excel"):
            r = c.post("/api/reportes", headers=H, json={"tipo": tipo, "formato": formato, "inicio": "2026-01-01", "fin": hoy})
            assert r.status_code == 201, r.get_json()
            a = c.get(f"/api/reportes/{r.get_json()['id']}/archivo")
            assert a.status_code == 200 and len(a.data) > 1000
    r = c.post("/api/copias", headers=H)
    assert r.status_code == 201 and r.get_json()["estado"] == "exitoso"
    assert c.get(f"/api/copias/{r.get_json()['id']}/descargar").status_code == 200


def test_tareas_programadas(clinica_a):
    assert tareas.recordatorios() >= 0
    assert tareas.copias_automaticas() >= 1


def test_consola_plataforma():
    c = cliente()
    assert c.get("/api/plataforma/resumen").status_code == 401
    r = c.post("/api/plataforma/login", headers=H, json={"correo": "admin@dentalhome.pe", "password": "consola2026"})
    if r.status_code != 200:
        pytest.skip("Sin administrador de plataforma (python -m web.db admin-plataforma)")
    res = c.get("/api/plataforma/resumen").get_json()
    assert res["clinicas"] and res["planes"]
