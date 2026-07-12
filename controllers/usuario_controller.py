from typing import List, Optional
from dao.gestor_usuario import GestorUsuario
from models.usuario import Usuario, Doctor, Secretaria, Administrador
from config import MIN_PASSWORD_LENGTH

class UsuarioController:
    """Controlador que orquesta la seguridad, sesiones corporativas y control de accesos."""
    def __init__(self, gestor_usuario: GestorUsuario) -> None:
        self._usuario_dao: GestorUsuario = gestor_usuario
        self._usuario_activo: Optional[Usuario] = None

    @staticmethod
    def _validar_contrasena(contrasena: str) -> None:
        if len(contrasena or "") < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
            )

    def iniciar_sesion(self, nombre_usuario: str, contrasena: str) -> Optional[Usuario]:
        hash_c = Usuario.hashear_contrasena(contrasena)
        usuario = self._usuario_dao.autenticar(nombre_usuario, hash_c)
        if usuario:
            self._usuario_activo = usuario
            return usuario
        return None

    def cerrar_sesion(self) -> None:
        self._usuario_activo = None

    def obtener_usuario_activo(self) -> Optional[Usuario]:
        return self._usuario_activo

    def registrar_usuario(self, nombre_usuario: str, contrasena: str, rol: str) -> Usuario:
        if self._usuario_activo is None or self._usuario_activo.rol != 'Administrador':
            raise PermissionError("Operación denegada: Privilegios de Administrador requeridos.")

        nombre_usuario = (nombre_usuario or "").strip()
        if not nombre_usuario:
            raise ValueError("El nombre de usuario es obligatorio.")
        if rol not in ("Doctor", "Secretaria", "Administrador"):
            raise ValueError("Rol no válido.")
        if self._usuario_dao.buscar_por_nombre_usuario(nombre_usuario):
            raise ValueError(f"El usuario '{nombre_usuario}' ya existe.")
        self._validar_contrasena(contrasena)

        hash_c = Usuario.hashear_contrasena(contrasena)
        if rol == "Doctor":
            nuevo_usuario = Doctor(None, nombre_usuario, hash_c, True, None, "")
        elif rol == "Secretaria":
            nuevo_usuario = Secretaria(None, nombre_usuario, hash_c, True, None, "Tiempo Completo")
        else:
            nuevo_usuario = Administrador(None, nombre_usuario, hash_c, True)
        user_id = self._usuario_dao.guardar(nuevo_usuario)
        return self._usuario_dao.buscar_por_id(user_id)

    def cambiar_contrasena(self, usuario_id: int, actual: str, nueva: str) -> bool:
        self._validar_contrasena(nueva)
        user = self._usuario_dao.buscar_por_id(usuario_id)
        if user and user.autenticar(user.nombreUsuario, actual):
            nuevo_hash = Usuario.hashear_contrasena(nueva)
            return self._usuario_dao.cambiar_contrasena(usuario_id, nuevo_hash)
        return False

    def restablecer_contrasena(self, usuario_id: int, nueva: str) -> bool:
        """Reinicio de contraseña por parte de un Administrador (sin requerir la actual)."""
        if self._usuario_activo is None or self._usuario_activo.rol != 'Administrador':
            raise PermissionError("Operación denegada: Privilegios de Administrador requeridos.")
        self._validar_contrasena(nueva)
        nuevo_hash = Usuario.hashear_contrasena(nueva)
        return self._usuario_dao.cambiar_contrasena(usuario_id, nuevo_hash)

    def desactivar_usuario(self, usuario_id: int) -> bool:
        if self._usuario_activo and self._usuario_activo.id == usuario_id:
            raise ValueError("Error de consistencia: No puede auto-desactivar la sesión en uso.")
        return self._usuario_dao.cambiar_estado(usuario_id, False)

    def activar_usuario(self, usuario_id: int) -> bool:
        return self._usuario_dao.cambiar_estado(usuario_id, True)

    def listar_usuarios(self) -> List[Usuario]:
        if self._usuario_activo is None or self._usuario_activo.rol != 'Administrador':
            raise PermissionError("Acceso restringido solo a perfiles de tipo Administrador.")
        return self._usuario_dao.listar_todos()

    def verificar_permiso(self, rol_requerido: str) -> bool:
        return self._usuario_activo is not None and self._usuario_activo.rol == rol_requerido
