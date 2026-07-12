import os
from datetime import datetime
from typing import Optional

class CopiaSeguridad:
    """Entidad encargada de mapear y verificar la persistencia de los respaldos del sistema."""
    def __init__(self, id_backup: Optional[int], tipo: str, admin_id: Optional[int],
                 fecha_hora: Optional[str] = None, ubicacion: str = '', estado: str = 'Pendiente') -> None:
        self._id: Optional[int] = id_backup
        self._fechaHora: str = fecha_hora or datetime.now().isoformat()
        self._tipo: str = tipo  # 'Manual', 'Automatico'
        self._ubicacion: str = ubicacion
        self._estado: str = estado  # 'Pendiente', 'Exitoso', 'Fallido'
        self._adminId: Optional[int] = admin_id

    @property
    def id(self) -> Optional[int]: return self._id
    @property
    def estado(self) -> str: return self._estado
    @property
    def ubicacion(self) -> str: return self._ubicacion

    def ejecutar(self, ruta_origen: str, ruta_destino: str) -> bool:
        """Lógica física delegada al sistema operativo para copiar el archivo .db."""
        try:
            if not os.path.exists(ruta_origen):
                self._estado = 'Fallido'
                return False
            
            # Copia en caliente emulada / transferencia binaria de archivos
            with open(ruta_origen, 'rb') as src, open(ruta_destino, 'wb') as dst:
                dst.write(src.read())
                
            self._ubicacion = ruta_destino
            self._estado = 'Exitoso'
            return True
        except IOError:
            self._estado = 'Fallido'
            return False

    def verificar_integridad(self) -> bool:
        return os.path.exists(self._ubicacion) and os.path.getsize(self._ubicacion) > 0

    def obtener_estado(self) -> str: return self._estado
    def obtener_ubicacion(self) -> str: return self._ubicacion

    def __str__(self) -> str:
        return f"Backup(Tipo={self._tipo}, Estado={self._estado}, Path={self._ubicacion})"