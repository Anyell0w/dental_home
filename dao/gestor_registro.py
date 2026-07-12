import sqlite3
from typing import List, Optional
from models.registro_clinico import RegistroClinico

class GestorRegistroClinico:
    """DAO encargado de mapear los eventos clínicos y diagnósticos puntuales."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[RegistroClinico]:
        if not r: return None
        return RegistroClinico(r['id'], r['historialId'], r['citaId'], r['doctorId'],
                               r['diagnostico'], r['tratamiento'], r['observaciones'], r['fechaConsulta'])

    def buscar_por_id(self, reg_id: int) -> Optional[RegistroClinico]:
        cursor = self._con.execute("SELECT * FROM registros_clinicos WHERE id = ?", (reg_id,))
        return self._row_to_entity(cursor.fetchone())

    def buscar_por_cita(self, cita_id: int) -> Optional[RegistroClinico]:
        cursor = self._con.execute("SELECT * FROM registros_clinicos WHERE citaId = ?", (cita_id,))
        return self._row_to_entity(cursor.fetchone())

    def guardar(self, rc: RegistroClinico) -> int:
        cursor = self._con.execute(
            """INSERT INTO registros_clinicos (historialId, citaId, doctorId, diagnostico, tratamiento, observaciones, fechaConsulta)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rc.historialId, rc.citaId, rc.doctorId, rc.diagnostico, rc.tratamiento, rc.observaciones, rc.fechaConsulta)
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar(self, rc: RegistroClinico) -> bool:
        self._con.execute(
            """UPDATE registros_clinicos SET diagnostico = ?, tratamiento = ?, observaciones = ? WHERE id = ?""",
            (rc.diagnostico, rc.tratamiento, rc.observaciones, rc.id)
        )
        self._con.commit()
        return True

    def listar_por_historial(self, historial_id: int) -> List[RegistroClinico]:
        cursor = self._con.execute("SELECT * FROM registros_clinicos WHERE historialId = ? ORDER BY fechaConsulta DESC", (historial_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_doctor(self, doctor_id: int) -> List[RegistroClinico]:
        cursor = self._con.execute("SELECT * FROM registros_clinicos WHERE doctorId = ? ORDER BY fechaConsulta DESC", (doctor_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_rango(self, fecha_inicio: str, fecha_fin: str) -> List[RegistroClinico]:
        cursor = self._con.execute(
            "SELECT * FROM registros_clinicos WHERE fechaConsulta BETWEEN ? AND ? ORDER BY fechaConsulta DESC",
            (fecha_inicio, fecha_fin),
        )
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]
