import sqlite3
from typing import List, Optional
from models.usuario import Usuario, Doctor, Secretaria, Administrador

class GestorUsuario:
    """DAO encargado del mapeo relacional del personal de la clínica dental."""
    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._con: sqlite3.Connection = conexion

    def _fila_a_usuario(self, f: sqlite3.Row) -> Optional[Usuario]:
        if not f: return None
        rol = f['rol']
        if rol == 'Doctor':
            return Doctor(f['id'], f['nombreUsuario'], f['contrasena'], bool(f['activo']), f['fechaCreacion'], f['numeroColegiatura'])
        elif rol == 'Secretaria':
            return Secretaria(f['id'], f['nombreUsuario'], f['contrasena'], bool(f['activo']), f['fechaCreacion'], f['turno'])
        elif rol == 'Administrador':
            return Administrador(f['id'], f['nombreUsuario'], f['contrasena'], bool(f['activo']), f['fechaCreacion'])
        return None

    def buscar_por_id(self, user_id: int) -> Optional[Usuario]:
        cursor = self._con.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
        return self._fila_a_usuario(cursor.fetchone())

    def buscar_por_nombre_usuario(self, nombre_usuario: str) -> Optional[Usuario]:
        cursor = self._con.execute("SELECT * FROM usuarios WHERE nombreUsuario = ?", (nombre_usuario,))
        return self._fila_a_usuario(cursor.fetchone())

    def autenticar(self, nombre_usuario: str, contrasena_hash: str) -> Optional[Usuario]:
        cursor = self._con.execute(
            "SELECT * FROM usuarios WHERE nombreUsuario = ? AND contrasena = ? AND activo = 1",
            (nombre_usuario, contrasena_hash)
        )
        return self._fila_a_usuario(cursor.fetchone())

    def guardar(self, u: Usuario) -> int:
        num_col = getattr(u, 'numeroColegiatura', None)
        turno = getattr(u, '_turno', None)
        cursor = self._con.execute(
            """INSERT INTO usuarios (nombreUsuario, contrasena, rol, activo, fechaCreacion, numeroColegiatura, turno)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (u.nombreUsuario, u._contrasena, u.rol, 1 if u.activo else 0, u._fechaCreacion, num_col, turno)
        )
        self._con.commit()
        return cursor.lastrowid

    def actualizar(self, u: Usuario) -> bool:
        num_col = getattr(u, 'numeroColegiatura', None)
        turno = getattr(u, '_turno', None)
        self._con.execute(
            """UPDATE usuarios SET nombreUsuario = ?, rol = ?, activo = ?, numeroColegiatura = ?, turno = ?
               WHERE id = ?""",
            (u.nombreUsuario, u.rol, 1 if u.activo else 0, num_col, turno, u.id)
        )
        self._con.commit()
        return True

    def cambiar_contrasena(self, user_id: int, nuevo_hash: str) -> bool:
        self._con.execute("UPDATE usuarios SET contrasena = ? WHERE id = ?", (nuevo_hash, user_id))
        self._con.commit()
        return True

    def cambiar_estado(self, user_id: int, activo: bool) -> bool:
        self._con.execute("UPDATE usuarios SET activo = ? WHERE id = ?", (1 if activo else 0, user_id))
        self._con.commit()
        return True

    def listar_todos(self) -> List[Usuario]:
        cursor = self._con.execute("SELECT * FROM usuarios ORDER BY rol, nombreUsuario")
        return [self._fila_a_usuario(row) for row in cursor.fetchall() if row is not None]

    def listar_por_rol(self, rol: str) -> List[Usuario]:
        cursor = self._con.execute("SELECT * FROM usuarios WHERE rol = ?", (rol,))
        return [self._fila_a_usuario(row) for row in cursor.fetchall() if row is not None]
