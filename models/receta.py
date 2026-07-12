from typing import List, Optional

class Receta:
    """Documento de indicaciones farmacológicas emitidas por el personal médico."""
    def __init__(self, id_receta: Optional[int], registro_clinico_id: int, paciente_id: int,
                 doctor_id: int, fecha: str, indicaciones_generales: str = '', archivo_pdf: str = '') -> None:
        self._id: Optional[int] = id_receta
        self._registroClinicoId: int = registro_clinico_id
        self._pacienteId: int = paciente_id
        self._doctorId: int = doctor_id
        self._fecha: str = fecha
        self._indicacionesGenerales: str = indicaciones_generales
        self._archivoPDF: str = archivo_pdf
        self._medicamentos: List['Medicamento'] = []  # Composición de ciclo de vida interno

    @property
    def id(self) -> Optional[int]: return self._id
    @property
    def registroClinicoId(self) -> int: return self._registroClinicoId
    @property
    def pacienteId(self) -> int: return self._pacienteId
    @property
    def doctorId(self) -> int: return self._doctorId
    @property
    def fecha(self) -> str: return self._fecha
    @property
    def indicacionesGenerales(self) -> str: return self._indicacionesGenerales
    @property
    def archivoPDF(self) -> str: return self._archivoPDF

    def agregar_medicamento(self, med: 'Medicamento') -> None:
        if med.validar():
            self._medicamentos.append(med)
        else:
            raise ValueError("Datos del medicamento no válidos para su anexión.")

    def obtener_medicamentos(self) -> List['Medicamento']:
        return self._medicamentos

    def generar_pdf(self, ruta_destino: str) -> str:
        # Lógica de renderizado ReportLab/Tkinter reservada para la fase correspondiente
        self._archivoPDF = ruta_destino
        return self._archivoPDF

    def obtener_ruta_pdf(self) -> str: return self._archivoPDF
    
    def esta_complete(self) -> bool:
        return len(self._medicamentos) >= 1 and bool(self._archivoPDF)