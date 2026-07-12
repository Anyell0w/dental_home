from typing import List, Optional
from datetime import datetime
from dao.gestor_historial import GestorHistorial
from dao.gestor_registro import GestorRegistroClinico
from dao.gestor_cita import GestorCita
from models.historial_clinico import HistorialClinico
from models.registro_clinico import RegistroClinico

class HistorialController:
    """Orquesta el acceso al historial y la creación de registros clínicos asociados."""
    def __init__(self, gestor_historial: GestorHistorial, 
                 gestor_registro: GestorRegistroClinico, gestor_cita: GestorCita) -> None:
        self._historial_dao: GestorHistorial = gestor_historial
        self._registro_dao: GestorRegistroClinico = gestor_registro
        self._cita_dao: GestorCita = gestor_cita

    def obtener_historial(self, paciente_id: int) -> Optional[HistorialClinico]:
        historial = self._historial_dao.buscar_por_paciente(paciente_id)
        if historial:
            registros = self._registro_dao.listar_por_historial(historial.id)
            for r in registros:
                historial.agregar_registro(r)
        return historial

    def crear_registro_clinico(self, cita_id: int, doctor_id: int, 
                               diag: str, trat: str, obs: str) -> RegistroClinico:
        cita = self._cita_dao.buscar_por_id(cita_id)
        if not cita:
            raise ValueError("La cita de referencia no existe.")
            
        historial = self._historial_dao.buscar_por_paciente(cita.pacienteId)
        if not historial:
            raise ValueError("El paciente no posee un historial clínico activo.")

        nuevo_registro = RegistroClinico(
            id_registro=None,
            historial_id=historial.id,
            cita_id=cita_id,
            doctor_id=doctor_id,
            diagnostico=diag,
            tratamiento=trat,
            observaciones=obs,
            fecha_consulta=datetime.now().strftime("%Y-%m-%d")
        )
        reg_id = self._registro_dao.guardar(nuevo_registro)
        self._cita_dao.completar(cita_id)  # Transición automática de estado de la cita
        return self._registro_dao.buscar_por_id(reg_id)

    def actualizar_registro(self, registro_id: int, diagnostico: str, 
                            tratamiento: str, obs: str) -> RegistroClinico:
        reg = self._registro_dao.buscar_por_id(registro_id)
        if not reg:
            raise ValueError("El registro clínico especificado no existe.")
        reg.actualizar_diagnostico(diagnostico)
        reg.actualizar_tratamiento(tratamiento)
        reg.agregar_observacion(obs)
        self._registro_dao.actualizar(reg)
        return reg

    def agregar_observacion_historial(self, historial_id: int, observacion: str) -> bool:
        historial = self._historial_dao.buscar_por_id(historial_id)
        if not historial: return False
        historial.agregar_observation(observacion)
        return self._historial_dao.actualizar_observaciones(historial_id, historial.observaciones)

    def actualizar_odontograma(self, historial_id: int, ruta: str, descripcion: str = '') -> bool:
        """Guarda la imagen (ruta) del odontograma y, opcionalmente, su descripción."""
        historial = self._historial_dao.buscar_por_id(historial_id)
        if not historial:
            return False
        return self._historial_dao.actualizar_odontograma(historial_id, ruta, descripcion)

    def guardar_odontograma_estado(
        self, historial_id: int, estado_json: str,
        imagen_path: str = '', descripcion: str = ''
    ) -> bool:
        """Persiste el estado interactivo del odontograma (JSON) del paciente."""
        historial = self._historial_dao.buscar_por_id(historial_id)
        if not historial:
            return False
        return self._historial_dao.actualizar_odontograma_estado(
            historial_id, estado_json, imagen_path, descripcion
        )

    def listar_citas_paciente(self, paciente_id: int):
        return self._cita_dao.listar_por_paciente(paciente_id)

    def listar_registros(self, historial_id: int) -> List[RegistroClinico]:
        return self._registro_dao.listar_por_historial(historial_id)