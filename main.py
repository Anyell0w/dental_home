"""
Punto de Entrada Maestro y Orquestador de Dependencias - DENTAL HOME
Fase 3: Integración Completa, Interfaz Verde Corporativa y Prevención de Bloqueos.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
from datetime import datetime

from dao.gestor_dashboard import GestorDashboard
from controllers.dashboard_controller import DashboardController
from views.dashboard_view import DashboardView

# Infraestructura, Configuración y Estilos
from database import Database
from config import PATHS
from utils.theme import COLORS, FONTS, configurar_treeview_styles

# DAOs (Capa de Acceso a Datos)
from dao.gestor_usuario import GestorUsuario
from dao.gestor_paciente import GestorPaciente
from dao.gestor_cita import GestorCita
from dao.gestor_historial import GestorHistorial
from dao.gestor_registro import GestorRegistroClinico
from dao.gestor_medicamento import GestorMedicamento
from dao.gestor_receta import GestorReceta
from dao.gestor_reporte import GestorReporte
from dao.gestor_copia import GestorCopiaSeguridad

# Controladores (Capa de Lógica de Negocio)
from controllers.usuario_controller import UsuarioController
from controllers.paciente_controller import PacienteController
from controllers.cita_controller import CitaController
from controllers.historial_controller import HistorialController
from controllers.receta_controller import RecetaController
from controllers.reporte_controller import ReporteController
from controllers.copia_controller import CopiaSeguridadController

# Vistas (Capa de Presentación)
from views.login_view import LoginView
from views.main_menu import MainMenu
from views.paciente_view import PacienteView
from views.cita_view import CitaView
from views.historial_view import HistorialView
from views.reporte_view import ReporteView
from views.copia_view import CopiaSeguridadView
from views.usuario_view import UsuarioView

# Modelos para Inicialización Segura (Seeding)
from models.usuario import Administrador, Doctor, Secretaria, Usuario


class DentalHomeOrchestrator:
    """
    Coordinador de Aplicación.
    Ejecuta el patrón de Inyección de Dependencias global y controla las rutas de la UI.
    """
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()  # Mantener oculto hasta pasar el Login exitosamente
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        # 1. Levantar Infraestructura de Datos Única
        self.conexion = Database.obtener_instancia().obtener_conexion()
        
        # Aplicar personalización de las tablas de datos (Treeview)
        self.style = ttk.Style()
        configurar_treeview_styles(self.style)

        # 2. Inicialización de Capa de Datos (DAOs)
        self.dao_usuario = GestorUsuario(self.conexion)
        self.dao_paciente = GestorPaciente(self.conexion)
        self.dao_cita = GestorCita(self.conexion)
        self.dao_historial = GestorHistorial(self.conexion)
        self.dao_registro = GestorRegistroClinico(self.conexion)
        self.dao_medicamento = GestorMedicamento(self.conexion)
        self.dao_receta = GestorReceta(self.conexion)
        self.dao_reporte = GestorReporte(self.conexion)
        self.dao_copia = GestorCopiaSeguridad(self.conexion)
        self.dao_dashboard = GestorDashboard(self.conexion)
        # 3. Inyección de Dependencias hacia la Capa Lógica (Controllers)
        self.ctrl_usuario = UsuarioController(self.dao_usuario)
        self.ctrl_paciente = PacienteController(self.dao_paciente, self.dao_historial)
        self.ctrl_cita = CitaController(self.dao_cita, self.dao_paciente, self.dao_usuario)
        self.ctrl_historial = HistorialController(self.dao_historial, self.dao_registro, self.dao_cita)
        self.ctrl_receta = RecetaController(
            self.dao_receta, self.dao_medicamento, self.dao_registro,
            self.dao_paciente, self.dao_usuario,
        )
        self.ctrl_reporte = ReporteController(self.dao_reporte, self.dao_cita, self.dao_paciente, self.dao_registro)
        self.ctrl_bk = CopiaSeguridadController(self.dao_copia, PATHS["db"], PATHS["backups"])
        self.ctrl_dashboard = DashboardController(self.dao_dashboard)
        # 4. Aprovisionamiento seguro de registros mínimos (Seeding)
        self._ejecutar_seeding_obligatorio()
        
        # 5. Activar Daemon de Respaldo Asíncrono en segundo plano (Fase 3)
        #    Se delega al controlador para que cada respaldo quede auditado en BD.
        self.ctrl_bk.iniciar_respaldo_automatico()

        self.lanzar_autenticacion()

    def _ejecutar_seeding_obligatorio(self) -> None:
        """
        Aprovisiona únicamente las credenciales de infraestructura del sistema.
        Se eliminó el hardcoding de pacientes y citas para el despliegue en producción.
        """
        # Creación exclusiva de Roles Corporativos Base (Si no existen)
        if not self.dao_usuario.buscar_por_nombre_usuario("admin"):
            self.dao_usuario.guardar(Administrador(None, "admin", Usuario.hashear_contrasena("admin123"), True))
        if not self.dao_usuario.buscar_por_nombre_usuario("doctor1"):
            self.dao_usuario.guardar(Doctor(None, "doctor1", Usuario.hashear_contrasena("doctor123"), True, None, "COP-9777"))
        if not self.dao_usuario.buscar_por_nombre_usuario("secret1"):
            self.dao_usuario.guardar(Secretaria(None, "secret1", Usuario.hashear_contrasena("secret123"), True, None, "Tiempo Completo"))

    def lanzar_autenticacion(self) -> None:
        self.tl_login = tk.Toplevel(self.root)
        self.view_login = LoginView(self.tl_login, self.ctrl_usuario, on_login_success=self.conceder_acceso)
        self.view_login.inicializar()
        self.tl_login.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

    def conceder_acceso(self, usuario_instancia: any) -> None:
        """Destruye el Login y monta el Dashboard Principal de forma fluida."""
        self.tl_login.destroy()
        
        self.tl_main = tk.Toplevel(self.root)
        self.tl_main.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        
        # Mapeo dinámico y centralizado de inyección hacia las vistas funcionales
        vistas_mapeadas = {
            "Inicio": lambda: DashboardView( self.menu_dashboard.contenedor_principal, self.ctrl_dashboard).inicializar(),
            "Pacientes": lambda: PacienteView(self.menu_dashboard.contenedor_principal, self.ctrl_paciente, usuario_instancia.id).inicializar(),
            "Citas": lambda: CitaView(self.menu_dashboard.contenedor_principal, self.ctrl_cita, self.dao_paciente, self.dao_usuario).inicializar(),
            "Historial Clínico": lambda: HistorialView(
                self.menu_dashboard.contenedor_principal,
                self.ctrl_historial,
                self.dao_paciente,
                self.dao_cita,
                usuario_instancia.id,
                self.ctrl_receta,
                self.dao_usuario,
            ).inicializar(),
            "Reportes": lambda: ReporteView(self.menu_dashboard.contenedor_principal, self.ctrl_reporte, usuario_instancia.nombreUsuario).inicializar(),
            "Copias Seguridad": lambda: CopiaSeguridadView(self.menu_dashboard.contenedor_principal, self.ctrl_bk, usuario_instancia.id).inicializar(),
            "Usuarios": lambda: UsuarioView(self.menu_dashboard.contenedor_principal, self.ctrl_usuario).inicializar()
        }

        # Inicialización del Menú de Navegación Lateral (Sidebar)
        self.menu_dashboard = MainMenu(self.tl_main, usuario_instancia, vistas_mapeadas, on_logout=self.recoordinar_logout)
        self.menu_dashboard.inicializar()
        
        # Carga por defecto obligatoria: Dashboard Analítico de Inicio (Imagen 3)
        vistas_mapeadas["Inicio"]()

    def recoordinar_logout(self) -> None:
        """Cierre de sesión seguro y retorno inmediato a la pantalla de login split."""
        self.tl_main.destroy()
        self.ctrl_usuario.cerrar_sesion()
        self.lanzar_autenticacion()
    def cerrar_aplicacion(self):
        """Cierra completamente la aplicación."""
        try:
            Database.obtener_instancia().cerrar_conexion()
        except Exception:
            pass

        self.root.quit()
        self.root.destroy()

if __name__ == "__main__":
    # Arrancar el hilo de ejecución principal de Tkinter
    app = DentalHomeOrchestrator()
    app.root.mainloop()
