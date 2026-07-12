from datetime import datetime
from typing import List, Optional
from models.registro_clinico import RegistroClinico

class HistorialClinico:
    """Contenedor raíz en relación de composición directa con la ficha del paciente."""
    def __init__(
        self,
        id_historial: Optional[int],
        paciente_id: int,
        fecha_creacion: Optional[str] = None,
        observaciones: str = '',
        odontograma: str = '',
        descripcion_odontograma: str = '',
        activo: bool = True,
        odontograma_estado: str = '{}'
    ) -> None:
        self._id = id_historial
        self._pacienteId = paciente_id
        self._fechaCreacion = fecha_creacion or datetime.now().isoformat()

        self._observaciones = observaciones

        # NUEVO
        self._odontograma = odontograma
        self._descripcionOdontograma = descripcion_odontograma
        self._odontogramaEstado = odontograma_estado or '{}'

        self._activo = activo

        self._registros = []

    @property
    def id(self) -> Optional[int]: return self._id
    @property
    def pacienteId(self) -> int: return self._pacienteId
    @property
    def observaciones(self) -> str: return self._observaciones
    @property
    def odontograma(self):
        return self._odontograma


    @property
    def descripcionOdontograma(self):
        return self._descripcionOdontograma

    @property
    def odontogramaEstado(self) -> str:
        """Estado interactivo del odontograma serializado en JSON."""
        return self._odontogramaEstado
    @property
    def activo(self) -> bool: return self._activo

    def agregar_registro(self, registro: RegistroClinico) -> None:
        self._registros.append(registro)

    def obtener_registros(self) -> List[RegistroClinico]:
        """Retorna la colección cronológica inversa (más reciente primero)."""
        return sorted(self._registros, key=lambda r: r.fechaConsulta, reverse=True)

    def obtener_ultimo_registro(self) -> Optional[RegistroClinico]:
        registros = self.obtener_registros()
        return registros[0] if registros else None

    def agregar_observation(self, texto: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._observaciones += f"\n[{timestamp}] {texto}"

    def desactivar(self) -> None: self._activo = False
    def contar_consultas(self) -> int: return len(self._registros)