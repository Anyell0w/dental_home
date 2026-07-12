import sqlite3
from typing import List, Optional
from models.receta import Receta

class GestorReceta:
    """Mapeador transaccional de cabeceras de recetas odontológicas."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[Receta]:
        if not r: return None
        return Receta(r['id'], r['registroClinicoId'], r['pacienteId'], r['doctorId'],
                      r['fecha'], r['indicacionesGenerales'], r['archivoPDF'])

    def buscar_por_id(self, rec_id: int) -> Optional[Receta]:
        cursor = self._con.execute("SELECT * FROM recetas WHERE id = ?", (rec_id,))
        return self._row_to_entity(cursor.fetchone())

    def buscar_por_registro(self, registro_id: int) -> Optional[Receta]:
        cursor = self._con.execute("SELECT * FROM recetas WHERE registroClinicoId = ?", (registro_id,))
        return self._row_to_entity(cursor.fetchone())

    def guardar(self, r: Receta) -> int:
        cursor = self._con.execute(
            """INSERT INTO recetas (registroClinicoId, pacienteId, doctorId, fecha, indicacionesGenerales, archivoPDF)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (r.registroClinicoId, r.pacienteId, r.doctorId, r.fecha, r.indicacionesGenerales, r.archivoPDF)
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar_ruta_pdf(self, rec_id: int, ruta: str) -> bool:
        self._con.execute("UPDATE recetas SET archivoPDF = ? WHERE id = ?", (ruta, rec_id))
        self._con.commit()
        return True

    def listar_por_paciente(self, paciente_id: int) -> List[Receta]:
        cursor = self._con.execute("SELECT * FROM recetas WHERE pacienteId = ? ORDER BY fecha DESC", (paciente_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_doctor(self, doctor_id: int) -> List[Receta]:
        cursor = self._con.execute("SELECT * FROM recetas WHERE doctorId = ? ORDER BY fecha DESC", (doctor_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]
