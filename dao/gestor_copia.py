import sqlite3
from typing import List, Optional
from models.copia_seguridad import CopiaSeguridad

class GestorCopiaSeguridad:
    """DAO encargado del control e historial de backups."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[CopiaSeguridad]:
        if not r: return None
        return CopiaSeguridad(r['id'], r['tipo'], r['adminId'], r['fechaHora'], r['ubicacion'], r['estado'])

    def guardar(self, cs: CopiaSeguridad) -> int:
        cursor = self._con.execute(
            "INSERT INTO copias_seguridad (fechaHora, tipo, ubicacion, estado, adminId) VALUES (?, ?, ?, ?, ?)",
            (cs._fechaHora, cs._tipo, cs.ubicacion, cs.estado, cs._adminId)
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar(self, cs: CopiaSeguridad) -> bool:
        self._con.execute(
            "UPDATE copias_seguridad SET ubicacion = ?, estado = ? WHERE id = ?",
            (cs.ubicacion, cs.estado, cs.id)
        )
        self._con.commit()
        return True

    def listar_todos(self) -> List[CopiaSeguridad]:
        cursor = self._con.execute("SELECT * FROM copias_seguridad ORDER BY fechaHora DESC")
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def obtener_ultima_exitosa(self) -> Optional[CopiaSeguridad]:
        cursor = self._con.execute("SELECT * FROM copias_seguridad WHERE estado = 'Exitoso' ORDER BY fechaHora DESC LIMIT 1")
        return self._row_to_entity(cursor.fetchone())

    def listar_por_tipo(self, tipo: str) -> List[CopiaSeguridad]:
        cursor = self._con.execute("SELECT * FROM copias_seguridad WHERE tipo = ?", (tipo,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def buscar_por_id(self, cs_id: int) -> Optional[CopiaSeguridad]:
        cursor = self._con.execute("SELECT * FROM copias_seguridad WHERE id = ?", (cs_id,))
        return self._row_to_entity(cursor.fetchone())