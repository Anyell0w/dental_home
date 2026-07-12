import sqlite3
from typing import List, Optional
from models.cita import Cita


class GestorCita:
    """DAO encargado del control operativo de la Agenda médica (Citas)."""

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[Cita]:
        if not r:
            return None
        return Cita(r['id'], r['pacienteId'], r['doctorId'], r['fecha'], r['hora'],
                    r['estado'], r['motivoCancelacion'], r['fechaRegistro'])

    def buscar_por_id(self, cita_id: int) -> Optional[Cita]:
        cursor = self._con.execute("SELECT * FROM citas WHERE id = ?", (cita_id,))
        return self._row_to_entity(cursor.fetchone())

    def guardar(self, c: Cita) -> int:
        cursor = self._con.execute(
            """INSERT INTO citas (pacienteId, doctorId, fecha, hora, estado, motivoCancelacion, fechaRegistro)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (c.pacienteId, c.doctorId, c.fecha, c.hora, c.estado, c.motivoCancelacion, c._fechaRegistro)
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar(self, c: Cita) -> bool:
        self._con.execute(
            """UPDATE citas SET fecha = ?, hora = ?, estado = ?, motivoCancelacion = ? WHERE id = ?""",
            (c.fecha, c.hora, c.estado, c.motivoCancelacion, c.id)
        )
        self._con.commit()
        return True

    def cancelar(self, cita_id: int, motivo: str) -> bool:
        self._con.execute(
            "UPDATE citas SET estado = 'Cancelada', motivoCancelacion = ? WHERE id = ?",
            (motivo, cita_id)
        )
        self._con.commit()
        return True

    def completar(self, cita_id: int) -> bool:
        self._con.execute("UPDATE citas SET estado = 'Completada' WHERE id = ?", (cita_id,))
        self._con.commit()
        return True

    def listar_por_fecha(self, fecha: str) -> List[Cita]:
        cursor = self._con.execute("SELECT * FROM citas WHERE fecha = ? ORDER BY hora ASC", (fecha,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_doctor(self, doctor_id: int, fecha: Optional[str] = None) -> List[Cita]:
        if fecha:
            cursor = self._con.execute(
                "SELECT * FROM citas WHERE doctorId = ? AND fecha = ? ORDER BY hora ASC",
                (doctor_id, fecha)
            )
        else:
            cursor = self._con.execute(
                "SELECT * FROM citas WHERE doctorId = ? ORDER BY fecha DESC, hora ASC",
                (doctor_id,)
            )
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_paciente(self, paciente_id: int) -> List[Cita]:
        cursor = self._con.execute("SELECT * FROM citas WHERE pacienteId = ? ORDER BY fecha DESC", (paciente_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_rango(self, fecha_inicio: str, fecha_fin: str) -> List[Cita]:
        """Trae todas las citas cuya fecha cae dentro de [fecha_inicio, fecha_fin] (usado para vistas de Semana/Mes)."""
        cursor = self._con.execute(
            "SELECT * FROM citas WHERE fecha BETWEEN ? AND ? ORDER BY fecha ASC, hora ASC",
            (fecha_inicio, fecha_fin)
        )
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_doctor_y_rango(self, doctor_id: int, fecha_inicio: str, fecha_fin: str) -> List[Cita]:
        """Igual que listar_por_rango pero acotado a un doctor específico."""
        cursor = self._con.execute(
            "SELECT * FROM citas WHERE doctorId = ? AND fecha BETWEEN ? AND ? ORDER BY fecha ASC, hora ASC",
            (doctor_id, fecha_inicio, fecha_fin)
        )
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def listar_por_estado(self, estado: str) -> List[Cita]:
        cursor = self._con.execute("SELECT * FROM citas WHERE estado = ?", (estado,))
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def hay_conflicto_horario(self, doctor_id: int, fecha: str, hora: str, excluir_id: Optional[int] = None) -> bool:
        """Algoritmo de control horario para evitar doble asignación de consultas."""
        if excluir_id:
            cursor = self._con.execute(
                "SELECT COUNT(*) FROM citas WHERE doctorId = ? AND fecha = ? AND hora = ? "
                "AND estado = 'Pendiente' AND id != ?",
                (doctor_id, fecha, hora, excluir_id)
            )
        else:
            cursor = self._con.execute(
                "SELECT COUNT(*) FROM citas WHERE doctorId = ? AND fecha = ? AND hora = ? AND estado = 'Pendiente'",
                (doctor_id, fecha, hora)
            )
        return cursor.fetchone()[0] > 0