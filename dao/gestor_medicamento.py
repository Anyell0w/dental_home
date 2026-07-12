import sqlite3
from typing import List, Optional
from models.medicamento import Medicamento

class GestorMedicamento:
    """Gestor transaccional de los fármacos inyectados en las recetas médicas."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[Medicamento]:
        if not r: return None
        return Medicamento(r['id'], r['recetaId'], r['nombre'], r['cantidad'], r['indicaciones'])

    def buscar_por_id(self, med_id: int) -> Optional[Medicamento]:
        cursor = self._con.execute("SELECT * FROM medicamentos WHERE id = ?", (med_id,))
        return self._row_to_entity(cursor.fetchone())

    def guardar(self, m: Medicamento) -> int:
        cursor = self._con.execute(
            "INSERT INTO medicamentos (recetaId, nombre, cantidad, indicaciones) VALUES (?, ?, ?, ?)",
            (m.recetaId, m.nombre, m.cantidad, m.indicaciones)
        )
        self._con.commit()
        return cursor.lastrowid

    def listar_por_receta(self, receta_id: int) -> List[Medicamento]:
        cursor = self._con.execute("SELECT * FROM medicamentos WHERE recetaId = ?", (receta_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def eliminar(self, med_id: int) -> bool:
        self._con.execute("DELETE FROM medicamentos WHERE id = ?", (med_id,))
        self._con.commit()
        return True

    def eliminar_por_receta(self, receta_id: int) -> bool:
        self._con.execute("DELETE FROM medicamentos WHERE recetaId = ?", (receta_id,))
        self._con.commit()
        return True
