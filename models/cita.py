from datetime import datetime
from typing import Optional


class Cita:
    """Gestiona el ciclo de transiciones de las reservas médicas dentro del consultorio."""

    def __init__(self, id_cita: Optional[int], paciente_id: int, doctor_id: int,
                 fecha: str, hora: str, estado: str = 'Pendiente',
                 motivo_cancelacion: str = '', fecha_registro: Optional[str] = None) -> None:
        self._id: Optional[int] = id_cita
        self._pacienteId: int = paciente_id
        self._doctorId: int = doctor_id
        self._fecha: str = fecha
        self._hora: str = hora
        self._estado: str = estado
        self._motivoCancelacion: str = motivo_cancelacion
        self._fechaRegistro: str = fecha_registro or datetime.now().isoformat()

    @property
    def id(self) -> Optional[int]: return self._id

    @property
    def pacienteId(self) -> int: return self._pacienteId

    @property
    def doctorId(self) -> int: return self._doctorId

    @property
    def fecha(self) -> str: return self._fecha

    @property
    def hora(self) -> str: return self._hora

    @property
    def estado(self) -> str: return self._estado

    @property
    def motivoCancelacion(self) -> str: return self._motivoCancelacion

    def cancelar(self, motivo: str) -> None:
        if self._estado != 'Pendiente':
            raise ValueError("Acción denegada: Solo se pueden cancelar citas en estado 'Pendiente'.")
        self._estado = 'Cancelada'
        self._motivoCancelacion = motivo

    def completar(self) -> None:
        if self._estado != 'Pendiente':
            raise ValueError("Acción denegada: Solo se pueden completar citas en estado 'Pendiente'.")
        self._estado = 'Completada'

    def is_pendiente(self) -> bool: return self._estado == 'Pendiente'
    def is_completada(self) -> bool: return self._estado == 'Completada'
    def is_cancelada(self) -> bool: return self._estado == 'Cancelada'

    def __str__(self) -> str:
        return f"Cita(ID={self._id}, Fecha={self._fecha}, Hora={self._hora}, Estado='{self._estado}')"