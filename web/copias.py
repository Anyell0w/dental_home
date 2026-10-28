"""Copias de seguridad de una clínica: exportación JSON comprimida de sus filas (aisladas por RLS)."""
import gzip
import json
import os
from datetime import datetime

from web.notificador import DATA_DIR

# Orden de dependencias: permite restaurar insertando en este mismo orden.
TABLAS = ("usuarios", "doctores", "pacientes", "historiales_clinicos", "citas", "registros_clinicos",
          "odontograma_hallazgos", "medicamentos", "recetas", "receta_detalles", "reportes", "suscripciones", "pagos")
OMITIR = {"usuarios": ("contrasena_hash", "intentos_fallidos", "bloqueado_hasta")}


def ruta(cid: int, copia_id: int) -> str:
    return os.path.join(DATA_DIR, "copias", str(int(cid)), f"{int(copia_id)}.json.gz")


def crear(con, cid: int, solicitada_por=None) -> dict:
    """Registra la copia en copias_seguridad y escribe el archivo. Nunca lanza: deja la fila como exitosa o fallida."""
    tipo = "manual" if solicitada_por else "automatica"
    c = con.execute("""INSERT INTO copias_seguridad (clinica_id, solicitada_por, tipo) VALUES (%s, %s, %s)
                       RETURNING id""", (cid, solicitada_por, tipo)).fetchone()
    try:
        datos = {"version": 1, "clinica_id": cid, "generada_en": datetime.now().isoformat(timespec="seconds"), "tablas": {}}
        with con.transaction():  # savepoint: un fallo de lectura no invalida la transacción de la bitácora
            for t in TABLAS:
                filas = [dict(f) for f in con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()]  # noqa: S608 (lista fija)
                for f in filas:
                    for k in OMITIR.get(t, ()):
                        f.pop(k, None)
                datos["tablas"][t] = filas
        destino = ruta(cid, c["id"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with gzip.open(destino, "wt", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, default=str)
        estado = "exitoso"
    except Exception:  # noqa: BLE001 — cualquier fallo queda registrado en la bitácora
        estado = "fallido"
    return con.execute("""UPDATE copias_seguridad SET estado = %s, finalizada_en = now() WHERE id = %s
                          RETURNING id, tipo::text AS tipo, estado::text AS estado""", (estado, c["id"])).fetchone()
