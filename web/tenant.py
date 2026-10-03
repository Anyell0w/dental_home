"""
Ensamblado por petición de la pila DAO → Controlador para UNA clínica.

Es el equivalente web del orquestador de main.py: la misma inyección de
dependencias, pero con una conexión SQLite propia de cada clínica.
"""
from types import SimpleNamespace
from typing import Dict, Optional

from database import Database
from dao.gestor_usuario import GestorUsuario
from dao.gestor_paciente import GestorPaciente
from dao.gestor_cita import GestorCita
from dao.gestor_historial import GestorHistorial
from dao.gestor_registro import GestorRegistroClinico
from dao.gestor_medicamento import GestorMedicamento
from dao.gestor_receta import GestorReceta
from dao.gestor_reporte import GestorReporte
from dao.gestor_copia import GestorCopiaSeguridad
from dao.gestor_dashboard import GestorDashboard
from controllers.usuario_controller import UsuarioController
from controllers.paciente_controller import PacienteController
from controllers.cita_controller import CitaController
from controllers.historial_controller import HistorialController
from controllers.receta_controller import RecetaController
from controllers.reporte_controller import ReporteController
from controllers.copia_controller import CopiaSeguridadController
from controllers.dashboard_controller import DashboardController


def abrir(rutas: Dict[str, str], clinica_nombre: str, usuario_id: Optional[int] = None) -> SimpleNamespace:
    """Abre la conexión de la clínica y devuelve DAOs + controladores listos."""
    con = Database.para_ruta(rutas["db"])  # crea/migra el esquema si hace falta

    s = SimpleNamespace(con=con, rutas=rutas)
    s.dao_usuario = GestorUsuario(con)
    s.dao_paciente = GestorPaciente(con)
    s.dao_cita = GestorCita(con)
    s.dao_historial = GestorHistorial(con)
    s.dao_registro = GestorRegistroClinico(con)
    s.dao_medicamento = GestorMedicamento(con)
    s.dao_receta = GestorReceta(con)
    s.dao_reporte = GestorReporte(con)
    s.dao_copia = GestorCopiaSeguridad(con)
    s.dao_dashboard = GestorDashboard(con)

    s.usuario = UsuarioController(s.dao_usuario)
    s.paciente = PacienteController(s.dao_paciente, s.dao_historial)
    s.cita = CitaController(s.dao_cita, s.dao_paciente, s.dao_usuario)
    s.historial = HistorialController(s.dao_historial, s.dao_registro, s.dao_cita)
    s.receta = RecetaController(
        s.dao_receta, s.dao_medicamento, s.dao_registro, s.dao_paciente, s.dao_usuario,
        rutas=rutas, clinica={"clinica": clinica_nombre.upper(), "subtitulo": "Receta médica"},
    )
    s.reporte = ReporteController(s.dao_reporte, s.dao_cita, s.dao_paciente, s.dao_registro, rutas=rutas)
    s.copia = CopiaSeguridadController(s.dao_copia, rutas["db"], rutas["backups"])
    s.dashboard = DashboardController(s.dao_dashboard)

    if usuario_id:  # el controlador de usuarios valida privilegios con el usuario activo
        s.usuario._usuario_activo = s.dao_usuario.buscar_por_id(usuario_id)
    return s
