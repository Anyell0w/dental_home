"""
Capa de plataforma (SaaS): clínicas suscritas, planes y estado de la suscripción.

Cada clínica tiene su propio archivo SQLite (aislamiento total de datos);
esta base central solo guarda quién es cliente y qué plan tiene.
"""
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, Optional

DATA_DIR = os.environ.get(
    "DENTAL_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
)
TRIAL_DAYS = 14

# Precios de ejemplo (S/ al mes). Los límites los aplica la API.
PLANES: Dict[str, dict] = {
    "esencial": {
        "id": "esencial", "nombre": "Esencial", "precio": 59,
        "descripcion": "Para consultorios que empiezan.",
        "max_usuarios": 3, "max_pacientes": 150, "excel": False,
        "extras": ["Agenda y pacientes", "Historial y odontograma", "Recetas en PDF"],
    },
    "profesional": {
        "id": "profesional", "nombre": "Profesional", "precio": 129,
        "descripcion": "El favorito de los consultorios en crecimiento.",
        "max_usuarios": 10, "max_pacientes": 1500, "excel": True,
        "extras": ["Todo lo de Esencial", "Reportes PDF y Excel", "Copias de seguridad"],
        "destacado": True,
    },
    "clinica": {
        "id": "clinica", "nombre": "Clínica", "precio": 249,
        "descripcion": "Sin límites para equipos grandes.",
        "max_usuarios": None, "max_pacientes": None, "excel": True,
        "extras": ["Todo lo de Profesional", "Usuarios y pacientes ilimitados", "Soporte prioritario"],
    },
}


def _ahora() -> datetime:
    return datetime.now()


def slugify(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return t[:32] or "clinica"


class Plataforma:
    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self.data_dir = data_dir
        os.makedirs(os.path.join(data_dir, "clinicas"), exist_ok=True)
        self.ruta_db = os.path.join(data_dir, "plataforma.db")
        with self._con() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS clinicas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    nombre TEXT NOT NULL,
                    email TEXT NOT NULL,
                    plan TEXT NOT NULL DEFAULT 'profesional',
                    estado TEXT NOT NULL DEFAULT 'prueba'
                        CHECK (estado IN ('prueba', 'activa', 'cancelada')),
                    prueba_hasta TEXT,
                    renueva_el TEXT,
                    creada TEXT NOT NULL
                );
                """
            )
        self._clave_secreta: Optional[str] = None

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta_db, timeout=10)
        con.row_factory = sqlite3.Row
        return con

    # ---- secreto de sesión persistente ----
    def secret_key(self) -> str:
        env = os.environ.get("DENTAL_SECRET_KEY")
        if env:
            return env
        ruta = os.path.join(self.data_dir, "secret.key")
        if not os.path.exists(ruta):
            with open(ruta, "w") as f:
                f.write(secrets.token_hex(32))
            os.chmod(ruta, 0o600)
        with open(ruta) as f:
            return f.read().strip()

    # ---- rutas del inquilino ----
    def rutas(self, slug: str) -> Dict[str, str]:
        base = os.path.join(self.data_dir, "clinicas", slug)
        rutas = {
            "db": os.path.join(base, "dental_home.db"),
            "backups": os.path.join(base, "backups"),
            "recetas": os.path.join(base, "recetas"),
            "reportes": os.path.join(base, "reportes"),
        }
        for k, v in rutas.items():
            if k != "db":
                os.makedirs(v, exist_ok=True)
        return rutas

    # ---- clínicas ----
    def crear(self, nombre: str, email: str, plan: str = "profesional") -> sqlite3.Row:
        base = slugify(nombre)
        slug, n = base, 1
        with self._con() as con:
            while con.execute("SELECT 1 FROM clinicas WHERE slug = ?", (slug,)).fetchone():
                n += 1
                slug = f"{base}-{n}"
            hasta = (_ahora() + timedelta(days=TRIAL_DAYS)).strftime("%Y-%m-%d")
            con.execute(
                """INSERT INTO clinicas (slug, nombre, email, plan, estado, prueba_hasta, creada)
                   VALUES (?, ?, ?, ?, 'prueba', ?, ?)""",
                (slug, nombre, email, plan, hasta, _ahora().isoformat()),
            )
        return self.por_slug(slug)

    def por_slug(self, slug: str) -> Optional[sqlite3.Row]:
        with self._con() as con:
            return con.execute("SELECT * FROM clinicas WHERE slug = ?", (slug,)).fetchone()

    def por_id(self, cid: int) -> Optional[sqlite3.Row]:
        with self._con() as con:
            return con.execute("SELECT * FROM clinicas WHERE id = ?", (cid,)).fetchone()

    def activar_plan(self, cid: int, plan: str) -> None:
        if plan not in PLANES:
            raise ValueError("Plan inexistente.")
        renueva = (_ahora() + timedelta(days=30)).strftime("%Y-%m-%d")
        with self._con() as con:
            con.execute(
                "UPDATE clinicas SET plan = ?, estado = 'activa', renueva_el = ? WHERE id = ?",
                (plan, renueva, cid),
            )

    def cancelar(self, cid: int) -> None:
        with self._con() as con:
            con.execute("UPDATE clinicas SET estado = 'cancelada' WHERE id = ?", (cid,))

    # ---- estado calculado de la suscripción ----
    @staticmethod
    def estado_suscripcion(c: sqlite3.Row) -> dict:
        hoy = _ahora().strftime("%Y-%m-%d")
        plan = PLANES[c["plan"]]
        if c["estado"] == "prueba":
            vigente = hoy <= (c["prueba_hasta"] or "")
            dias = (datetime.strptime(c["prueba_hasta"], "%Y-%m-%d") - datetime.strptime(hoy, "%Y-%m-%d")).days
            return {"estado": "prueba" if vigente else "vencida", "vigente": vigente,
                    "dias_restantes": max(dias, 0), "vence": c["prueba_hasta"], "plan": plan}
        if c["estado"] == "activa":
            vigente = hoy <= (c["renueva_el"] or "")
            return {"estado": "activa" if vigente else "vencida", "vigente": vigente,
                    "dias_restantes": None, "vence": c["renueva_el"], "plan": plan}
        return {"estado": "cancelada", "vigente": False, "dias_restantes": None,
                "vence": c["renueva_el"], "plan": plan}
