import hashlib
from datetime import datetime
from typing import Optional

class Usuario:
    """Clase base que representa a los actores y gestores de credenciales del sistema."""
    def __init__(self, id_user: Optional[int], nombre_usuario: str, contrasena: str, 
                 rol: str, activo: bool = True, fecha_creacion: Optional[str] = None) -> None:
        self._id: Optional[int] = id_user
        self._nombreUsuario: str = nombre_usuario
        self._contrasena: str = contrasena
        self._rol: str = rol
        self._activo: bool = activo
        self._fechaCreacion: str = fecha_creacion or datetime.now().isoformat()

    @property
    def id(self) -> Optional[int]: return self._id
    
    @property
    def nombreUsuario(self) -> str: return self._nombreUsuario
    
    @property
    def rol(self) -> str: return self._rol
    
    @property
    def activo(self) -> bool: return self._activo

    @staticmethod
    def hashear_contrasena(contrasena: str) -> str:
        """Aplica cifrado SHA-256 de forma determinista."""
        return hashlib.sha256(contrasena.encode('utf-8')).hexdigest()

    def autenticar(self, nombre: str, contrasena_plana: str) -> bool:
        """Verifica las credenciales mediante el contraste de hashes."""
        return self._nombreUsuario == nombre and self._contrasena == self.hashear_contrasena(contrasena_plana)

    def activar(self) -> None: self._activo = True
    def desactivar(self) -> None: self._activo = False
    def obtener_rol(self) -> str: return self._rol
    def esta_activo(self) -> bool: return self._activo

    def __str__(self) -> str:
        return f"Usuario('{self._nombreUsuario}', rol='{self._rol}', activo={self._activo})"


class Doctor(Usuario):
    """Subclase operativa con facultades médicas y firma de colegiatura."""
    def __init__(self, id_user: Optional[int], nombre_usuario: str, contrasena: str, 
                 activo: bool, fecha_creacion: Optional[str], numero_colegiatura: str) -> None:
        super().__init__(id_user, nombre_usuario, contrasena, 'Doctor', activo, fecha_creacion)
        self._numeroColegiatura: str = numero_colegiatura

    @property
    def numeroColegiatura(self) -> str: return self._numeroColegiatura

    def obtener_numero_colegiatura(self) -> str: return self._numeroColegiatura


class Secretaria(Usuario):
    """Subclase operativa administrativa a cargo del flujo de la agenda."""
    def __init__(self, id_user: Optional[int], nombre_usuario: str, contrasena: str, 
                 activo: bool, fecha_creacion: Optional[str], turno: str) -> None:
        super().__init__(id_user, nombre_usuario, contrasena, 'Secretaria', activo, fecha_creacion)
        if turno not in ['Mañana', 'Tarde', 'Tiempo Completo']:
            raise ValueError("Turno asignado inválido para el personal administrativo.")
        self._turno: str = turno

    def obtener_turno(self) -> str: return self._turno


class Administrador(Usuario):
    """Subclase gerencial con privilegios irrestrictos del sistema."""
    def __init__(self, id_user: Optional[int], nombre_usuario: str, contrasena: str, 
                 activo: bool = True, fecha_creacion: Optional[str] = None) -> None:
        super().__init__(id_user, nombre_usuario, contrasena, 'Administrador', activo, fecha_creacion)