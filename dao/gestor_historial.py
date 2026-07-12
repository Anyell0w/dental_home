import sqlite3
from typing import Optional
from models.historial_clinico import HistorialClinico

class GestorHistorial:
    """Operaciones relacionales sobre la entidad raíz del historial general."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[HistorialClinico]:
        if not r: return None
        columnas = r.keys()
        estado = r['odontogramaEstado'] if 'odontogramaEstado' in columnas else '{}'
        return HistorialClinico(
            r['id'],
            r['pacienteId'],
            r['fechaCreacion'],
            r['observaciones'],
            r['odontograma'],
            r['descripcionOdontograma'],
            bool(r['activo']),
            odontograma_estado=estado,
        )


    def buscar_por_id(self, hist_id: int) -> Optional[HistorialClinico]:
        cursor = self._con.execute("SELECT * FROM historiales_clinicos WHERE id = ?", (hist_id,))
        return self._row_to_entity(cursor.fetchone())

    def buscar_por_paciente(self, paciente_id: int) -> Optional[HistorialClinico]:
        cursor = self._con.execute("SELECT * FROM historiales_clinicos WHERE pacienteId = ?", (paciente_id,))
        return self._row_to_entity(cursor.fetchone())

    def guardar(self, h: HistorialClinico) -> int:
        cursor = self._con.execute(
            """INSERT INTO historiales_clinicos
               (pacienteId, fechaCreacion, observaciones, odontograma, descripcionOdontograma, activo)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                h.pacienteId,
                h._fechaCreacion,
                h.observaciones,
                h.odontograma,
                h.descripcionOdontograma,
                1 if h.activo else 0,
            ),
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar_observaciones(self, hist_id: int, obs: str) -> bool:
        self._con.execute("UPDATE historiales_clinicos SET observaciones = ? WHERE id = ?", (obs, hist_id))
        self._con.commit()
        return True

    def actualizar_odontograma(self, hist_id: int, odontograma: str, descripcion: str = '') -> bool:
        """Actualiza la ruta de imagen del odontograma y su descripción clínica."""
        self._con.execute(
            """UPDATE historiales_clinicos
               SET odontograma = ?, descripcionOdontograma = ?
               WHERE id = ?""",
            (odontograma, descripcion, hist_id),
        )
        self._con.commit()
        return True

    def actualizar_odontograma_estado(
        self, hist_id: int, estado_json: str,
        imagen_path: str = '', descripcion: str = ''
    ) -> bool:
        """Persiste el estado interactivo (JSON) del odontograma del paciente,
        junto con la imagen PNG exportada y la descripción clínica."""
        self._con.execute(
            """UPDATE historiales_clinicos
               SET odontogramaEstado = ?, odontograma = ?, descripcionOdontograma = ?
               WHERE id = ?""",
            (estado_json, imagen_path, descripcion, hist_id),
        )
        self._con.commit()
        return True

    def desactivar(self, hist_id: int) -> bool:
        self._con.execute("UPDATE historiales_clinicos SET activo = 0 WHERE id = ?", (hist_id,))
        self._con.commit()
        return True