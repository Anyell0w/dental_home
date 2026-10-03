from typing import List, Dict
import os
from dao.gestor_reporte import GestorReporte
from dao.gestor_cita import GestorCita
from dao.gestor_paciente import GestorPaciente
from dao.gestor_registro import GestorRegistroClinico
from models.reporte import Reporte
from utils.reporte_pdf import PDFReporteGenerator
from utils.reporte_excel import ExcelReporteGenerator
from config import PATHS


class ReporteController:
    def __init__(self, gestor_reporte: GestorReporte, gestor_cita: GestorCita,
                 gestor_paciente: GestorPaciente, gestor_registro: GestorRegistroClinico,
                 rutas: Dict[str, str] = None) -> None:
        self._rutas: Dict[str, str] = rutas or PATHS
        self._reporte_dao: GestorReporte = gestor_reporte
        self._cita_dao: GestorCita = gestor_cita
        self._paciente_dao: GestorPaciente = gestor_paciente
        self._registro_dao: GestorRegistroClinico = gestor_registro

    def generar_reporte(self, tipo: str, generado_por: str,
                        fecha_inicio: str, fecha_fin: str, formato: str) -> Reporte:
        if tipo not in ("Citas", "Pacientes", "Actividad"):
            raise ValueError("Tipo de reporte no soportado.")
        if formato not in ("PDF", "Excel"):
            raise ValueError("Formato de exportación no soportado.")

        nuevo_rep = Reporte(None, generado_por, tipo, fecha_inicio, fecha_fin, formato)
        if not nuevo_rep.validar_periodo():
            raise ValueError("El rango cronológico de fechas provisto es inconsistente.")

        datos = self._calcular_datos(tipo, fecha_inicio, fecha_fin)

        extension = "pdf" if formato == "PDF" else "xlsx"
        nombre_archivo = f"reporte_{tipo.lower()}_{fecha_inicio}_a_{fecha_fin}.{extension}"
        destino_completo = os.path.join(self._rutas["reportes"], nombre_archivo)

        if formato == "PDF":
            PDFReporteGenerator.generar_reporte_estadistico(
                tipo, fecha_inicio, fecha_fin, datos, destino_completo
            )
        else:
            ExcelReporteGenerator.generar_reporte_estadistico(
                tipo, fecha_inicio, fecha_fin, datos, destino_completo
            )

        nuevo_rep._archivo = destino_completo
        rep_id = self._reporte_dao.guardar(nuevo_rep)
        return self._reporte_dao.buscar_por_id(rep_id)

    def _calcular_datos(self, tipo: str, fecha_inicio: str, fecha_fin: str) -> Dict[str, int]:
        """Calcula métricas reales acotadas al rango de fechas indicado."""
        if tipo == "Citas":
            citas = self._cita_dao.listar_por_rango(fecha_inicio, fecha_fin)
            completadas = [c for c in citas if c.estado == "Completada"]
            canceladas = [c for c in citas if c.estado == "Cancelada"]
            pendientes = [c for c in citas if c.estado == "Pendiente"]
            return {
                "Citas_Totales": len(citas),
                "Completadas": len(completadas),
                "Canceladas": len(canceladas),
                "Pendientes": len(pendientes),
            }

        if tipo == "Pacientes":
            # La tabla de pacientes no almacena fecha de registro, por lo que el
            # reporte refleja el estado actual del padrón (no filtrable por fecha).
            activos = self._paciente_dao.listar_todos(solo_activos=True)
            todos = self._paciente_dao.listar_todos(solo_activos=False)
            return {
                "Pacientes_Activos": len(activos),
                "Pacientes_Inactivos": len(todos) - len(activos),
                "Total_Padron": len(todos),
            }

        # Actividad: consultas clínicas y citas agendadas dentro del rango
        registros = self._registro_dao.listar_por_rango(fecha_inicio, fecha_fin)
        citas = self._cita_dao.listar_por_rango(fecha_inicio, fecha_fin)
        return {
            "Consultas_Registradas": len(registros),
            "Citas_Agendadas": len(citas),
        }

    def listar_reportes(self) -> List[Reporte]:
        return self._reporte_dao.listar_todos()
