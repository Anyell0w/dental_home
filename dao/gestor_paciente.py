import sqlite3
from typing import List, Optional
from models.paciente import Paciente


class GestorPaciente:
    """Controlador transaccional de lectura y persistencia física de Pacientes."""

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    @property
    def conexion(self) -> sqlite3.Connection:
        """Expone la conexión para que capas superiores puedan coordinar
        transacciones que abarcan más de una tabla (p. ej. Paciente + Historial)."""
        return self._con

    def _row_to_entity(self, r: sqlite3.Row) -> Optional[Paciente]:
        if not r:
            return None
        return Paciente(r['id'], r['nombre'], r['apellido'], r['dni'], r['telefono'],
                         r['sexo'], r['fechaNacimiento'], r['direccion'],
                         bool(r['estado']), r['registradoPor'])

    def buscar_por_id(self, pac_id: int) -> Optional[Paciente]:
        cursor = self._con.execute("SELECT * FROM pacientes WHERE id = ?", (pac_id,))
        return self._row_to_entity(cursor.fetchone())

    def buscar_por_dni(self, dni: str) -> Optional[Paciente]:
        cursor = self._con.execute("SELECT * FROM pacientes WHERE dni = ?", (dni,))
        return self._row_to_entity(cursor.fetchone())

    def buscar(self, termino: str) -> List[Paciente]:
        
        patron = f"%{termino}%"
        cursor = self._con.execute(
            """SELECT * FROM pacientes
               WHERE nombre LIKE ? OR apellido LIKE ? OR dni LIKE ?
               ORDER BY apellido, nombre""",
            (patron, patron, patron)
        )
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def guardar(self, p: Paciente) -> int:
        cursor = self._con.execute(
            """INSERT INTO pacientes (nombre, apellido, dni, telefono, sexo, fechaNacimiento, direccion, estado, registradoPor)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.nombre, p.apellido, p.dni, p.telefono, p.sexo, p.fecha_nacimiento,
             p.direccion, 1 if p.estado else 0, p.registrado_por)
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar(self, p: Paciente) -> bool:
        self._con.execute(
            """UPDATE pacientes SET nombre = ?, apellido = ?, dni = ?, telefono = ?, sexo = ?, fechaNacimiento = ?, direccion = ? WHERE id = ?""",
            (p.nombre, p.apellido, p.dni, p.telefono, p.sexo, p.fecha_nacimiento, p.direccion, p.id)
        )
        self._con.commit()
        return True

    def cambiar_estado(self, pac_id: int, estado: bool) -> bool:
        self._con.execute("UPDATE pacientes SET estado = ? WHERE id = ?", (1 if estado else 0, pac_id))
        self._con.commit()
        return True

    def eliminar_fisico(self, pac_id: int) -> bool:
        """Elimina físicamente el registro. Uso exclusivo como compensación
        de rollback cuando falla la creación atómica del historial clínico
        asociado a un paciente recién insertado."""
        self._con.execute("DELETE FROM pacientes WHERE id = ?", (pac_id,))
        self._con.commit()
        return True

    def listar_todos(self, solo_activos: bool) -> List[Paciente]:
        sql = "SELECT * FROM pacientes"
        if solo_activos:
            sql += " WHERE estado = 1"
        sql += " ORDER BY apellido, nombre"
        cursor = self._con.execute(sql)
        return [self._row_to_entity(row) for row in cursor.fetchall() if row is not None]

    def existe_dni(self, dni: str, excluir_id: Optional[int]) -> bool:
        if excluir_id:
            cursor = self._con.execute(
                "SELECT COUNT(*) FROM pacientes WHERE dni = ? AND id != ?", (dni, excluir_id)
            )
        else:
            cursor = self._con.execute("SELECT COUNT(*) FROM pacientes WHERE dni = ?", (dni,))
        return cursor.fetchone()[0] > 0