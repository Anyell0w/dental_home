from datetime import datetime
from typing import Any, Dict, Optional

class Reporte:
    """Gestor operativo de análisis de datos clínicos y métricas gerenciales."""
    def __init__(self, id_reporte: Optional[int], generado_por: str, tipo: str,
                 fecha_inicio: str, fecha_fin: str, formato: str,
                 fecha_generacion: Optional[str] = None, archivo: str = '') -> None:
        self._id: Optional[int] = id_reporte
        self._generadoPor: str = generado_por
        self._tipo: str = tipo  # 'Citas', 'Pacientes', 'Ingresos', 'Actividad'
        self._fechaInicio: str = fecha_inicio
        self._fechaFin: str = fecha_fin
        self._formato: str = formato  # 'PDF', 'Excel'
        self._fechaGeneracion: str = fecha_generacion or datetime.now().isoformat()
        self._archivo: str = archivo

    @property
    def id(self) -> Optional[int]: return self._id
    @property
    def tipo(self) -> str: return self._tipo
    @property
    def fechaInicio(self) -> str: return self._fechaInicio
    @property
    def fechaFin(self) -> str: return self._fechaFin
    @property
    def formato(self) -> str: return self._formato

    def validar_periodo(self) -> bool:
        """Valida que los rangos del filtro temporal sean lógicamente consistentes."""
        try:
            inicio = datetime.strptime(self._fechaInicio, "%Y-%m-%d")
            fin = datetime.strptime(self._fechaFin, "%Y-%m-%d")
            return fin >= inicio
        except ValueError:
            return False

    def generar(self, datos: Dict[str, Any]) -> str:
        if not self.validar_periodo():
            raise ValueError("Rango de fechas erróneo. No se puede procesar el reporte.")
        # Simulación de renderizado del motor de exportación
        self._archivo = f"reporte_{self._tipo.lower()}_{self._fechaInicio}.{self._formato.lower()}"
        return self._archivo

    def exportar_pdf(self) -> str: return self._archivo
    def exportar_excel(self) -> str: return self._archivo
    def obtener_ruta_archivo(self) -> str: return self._archivo