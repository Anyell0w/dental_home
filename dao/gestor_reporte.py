import sqlite3
from typing import List, Optional
from models.reporte import Reporte

class GestorReporte:
    """DAO encargado del registro analítico de reportes exportados."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[Reporte]:
        if not r: return None
        return Reporte(r['id'], r['generadoPor'], r['tipo'], r['fechaInicio'],
                       r['fechaFin'], r['formato'], r['fechaGeneracion'], r['archivo'])

    def guardar(self, rep: Reporte) -> int:
        cursor = self._con.execute(
            """INSERT INTO reportes (generadoPor, tipo, fechaInicio, fechaFin, formato, fechaGeneracion, archivo)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rep._generadoPor, rep.tipo, rep.fechaInicio, rep.fechaFin, rep.formato, rep._fechaGeneracion, rep._archivo)
        )
        self._con.commit()
        return cursor.lastrowid

    def buscar_por_id(self, rep_id: int) -> Optional[Reporte]:
        cursor = self._con.execute("SELECT * FROM reportes WHERE id = ?", (rep_id,))
        return self._row_to_entity(cursor.fetchone())

    def listar_todos(self) -> List[Reporte]:
        cursor = self._con.execute("SELECT * FROM reportes ORDER BY fechaGeneracion DESC")
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_tipo(self, tipo: str) -> List[Reporte]:
        cursor = self._con.execute("SELECT * FROM reportes WHERE tipo = ? ORDER BY fechaGeneracion DESC", (tipo,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_generador(self, nombre: str) -> List[Reporte]:
        cursor = self._con.execute("SELECT * FROM reportes WHERE generadoPor = ? ORDER BY fechaGeneracion DESC", (nombre,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]
