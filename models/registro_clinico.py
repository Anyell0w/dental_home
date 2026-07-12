from typing import Optional

class RegistroClinico:
    """Ficha individual que captura la información patológica y clínica de una sesión."""
    def __init__(self, id_registro: Optional[int], historial_id: int, cita_id: int,
                 doctor_id: int, diagnostico: str, tratamiento: str, 
                 observaciones: str, fecha_consulta: str) -> None:
        self._id: Optional[int] = id_registro
        self._historialId: int = historial_id
        self._citaId: int = cita_id
        self._doctorId: int = doctor_id
        self._diagnostico: str = diagnostico
        self._tratamiento: str = tratamiento
        self._observaciones: str = observaciones
        self._fechaConsulta: str = fecha_consulta

    @property
    def id(self) -> Optional[int]: return self._id
    @property
    def historialId(self) -> int: return self._historialId
    @property
    def citaId(self) -> int: return self._citaId
    @property
    def doctorId(self) -> int: return self._doctorId
    @property
    def diagnostico(self) -> str: return self._diagnostico
    @property
    def tratamiento(self) -> str: return self._tratamiento
    @property
    def observaciones(self) -> str: return self._observaciones
    @property
    def fechaConsulta(self) -> str: return self._fechaConsulta

    def actualizar_diagnostico(self, nuevo_diag: str) -> None: self._diagnostico = nuevo_diag
    def actualizar_tratamiento(self, nuevo_trat: str) -> None: self._tratamiento = nuevo_trat
    def agregar_observacion(self, texto: str) -> None: self._observaciones += f" {texto}"
    
    def tiene_receta(self) -> bool:
        # Se resolverá dinámicamente mediante el RecetaController en fases posteriores
        return False

    def __str__(self) -> str:
        return f"RegistroClinico(ID={self._id}, Consulta={self._fechaConsulta}, Diagnostico={self._diagnostico[:20]}...)"