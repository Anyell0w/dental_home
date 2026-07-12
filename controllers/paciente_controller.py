from typing import List, Optional
from dao.gestor_paciente import GestorPaciente
from dao.gestor_historial import GestorHistorial
from models.paciente import Paciente
from models.historial_clinico import HistorialClinico


class PacienteController:
    """Coordinador lógico a cargo de la gestión de pacientes e historiales clínicos asociados."""

    def __init__(self, gestor_paciente: GestorPaciente, gestor_historial: GestorHistorial) -> None:
        self._paciente_dao: GestorPaciente = gestor_paciente
        self._historial_dao: GestorHistorial = gestor_historial

    def registrar_paciente(self, nombre: str, apellido: str, dni: str, tel: str,
                            sexo: str, f_nac: str, dir_p: str, registrado_por: int) -> Paciente:
        """Flujo de Negocio: Registra un paciente y le genera atómicamente su Historial Clínico.

        Si la creación del historial falla luego de haber insertado al
        paciente, se revierte (compensa) la inserción para no dejar un
        paciente sin historial clínico en la base de datos.
        """
        if self._paciente_dao.existe_dni(dni, None):
            raise ValueError(f"Conflicto de integridad: El DNI {dni} ya se encuentra registrado.")
        dni = dni.strip()

        if not dni.isdigit():
            raise ValueError("El DNI solo debe contener números.")

        if len(dni) != 8:
            raise ValueError("El DNI debe tener exactamente 8 dígitos.")
        nuevo_p = Paciente(None, nombre, apellido, dni, tel, sexo, f_nac, dir_p, True, registrado_por)
        pac_id = self._paciente_dao.guardar(nuevo_p)

        try:
            nuevo_h = HistorialClinico(None, pac_id)
            self._historial_dao.guardar(nuevo_h)
        except Exception:
            # Compensación: si el historial no pudo crearse, no dejamos
            # huérfano al paciente recién insertado.
            self._paciente_dao.eliminar_fisico(pac_id)
            raise

        return self._paciente_dao.buscar_por_id(pac_id)

    def actualizar_paciente(self, pac_id: int,nombre: str, apellido: str, dni: str, tel: str,
                            sexo: str, f_nac: str, dir_p: str) -> Paciente:
        paciente = self._paciente_dao.buscar_por_id(pac_id)
        if not paciente:
            raise ValueError("El registro del paciente objetivo no existe.")

        paciente.nombre = nombre
        paciente.apellido = apellido
        paciente.dni = dni
        paciente.telefono = tel
        paciente.sexo = sexo
        paciente.fecha_nacimiento = f_nac
        paciente.direccion = dir_p

        self._paciente_dao.actualizar(paciente)
        return paciente

    def buscar_por_id(self, pac_id: int) -> Optional[Paciente]:
        return self._paciente_dao.buscar_por_id(pac_id)

    def buscar_por_dni(self, dni: str) -> Optional[Paciente]:
        return self._paciente_dao.buscar_por_dni(dni)

    def buscar_paciente(self, termino: str) -> List[Paciente]:
    
        termino = (termino or "").strip()
        if not termino:
            return self.listar_pacientes(solo_activos=True)
        return self._paciente_dao.buscar(termino)

    def listar_pacientes(self, solo_activos: bool) -> List[Paciente]:
        return self._paciente_dao.listar_todos(solo_activos)

    def dar_de_baja_paciente(self, pac_id: int) -> bool:
        """Flujo lógico: Inactiva al paciente y congela su historial clínico."""
        historial = self._historial_dao.buscar_por_paciente(pac_id)
        if historial:
            self._historial_dao.desactivar(historial.id)
        return self._paciente_dao.cambiar_estado(pac_id, False)