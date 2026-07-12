from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dao.gestor_cita import GestorCita
from dao.gestor_paciente import GestorPaciente
from dao.gestor_usuario import GestorUsuario
from models.cita import Cita

PERIODOS_VALIDOS = ("dia", "semana", "mes")


class CitaController:
    """Validador lógico de reglas de negocio aplicadas al agendamiento de citas clínicas."""

    def __init__(self, gestor_cita: GestorCita, gestor_paciente: GestorPaciente,
                 gestor_usuario: GestorUsuario) -> None:
        self._cita_dao: GestorCita = gestor_cita
        self._paciente_dao: GestorPaciente = gestor_paciente
        self._usuario_dao: GestorUsuario = gestor_usuario

    def programar_cita(self, paciente_id: int, doctor_id: int, fecha: str, hora: str) -> Cita:
        if not paciente_id or not doctor_id:
            raise ValueError("Debe seleccionar un paciente y un doctor.")
        if not fecha or not fecha.strip():
            raise ValueError("Debe indicar la fecha de la cita.")
        if not hora or not hora.strip():
            raise ValueError("Debe indicar la hora de la cita.")

        if not self._paciente_dao.buscar_por_id(paciente_id):
            raise ValueError("Error de asignación: El paciente indicado no existe.")

        doctor = self._usuario_dao.buscar_por_id(doctor_id)
        if not doctor or doctor.rol != 'Doctor':
            raise ValueError("Error de asignación: El id asignado no corresponde a un Doctor calificado.")

        if self._cita_dao.hay_conflicto_horario(doctor_id, fecha, hora):
            raise ValueError(f"Conflicto de Agenda: El Doctor ya se encuentra ocupado el {fecha} a las {hora}.")

        nueva_cita = Cita(None, paciente_id, doctor_id, fecha, hora)
        cita_id = self._cita_dao.guardar(nueva_cita)
        return self._cita_dao.buscar_por_id(cita_id)

    def cancelar_cita(self, cita_id: int, motivo: str) -> bool:
        cita = self._cita_dao.buscar_por_id(cita_id)
        if not cita:
            raise ValueError("La cita seleccionada es inexistente.")
        if not cita.is_pendiente():
            raise ValueError("Solo se pueden cancelar citas en estado 'Pendiente'.")
        if not motivo or len(motivo.strip()) < 5:
            raise ValueError("Se requiere una justificación explícita formal (mínimo 5 caracteres).")

        return self._cita_dao.cancelar(cita_id, motivo.strip())

    def reprogramar_cita(self, cita_id: int, nueva_fecha: str, nueva_hora: str) -> Cita:
        if not nueva_fecha or not nueva_fecha.strip():
            raise ValueError("Debe indicar la nueva fecha de la cita.")
        if not nueva_hora or not nueva_hora.strip():
            raise ValueError("Debe indicar la nueva hora de la cita.")

        cita = self._cita_dao.buscar_por_id(cita_id)
        if not cita or not cita.is_pendiente():
            raise ValueError("No es posible reprogramar una cita completada o cancelada.")

        if self._cita_dao.hay_conflicto_horario(cita.doctorId, nueva_fecha, nueva_hora, excluir_id=cita_id):
            raise ValueError("El nuevo horario solicitado genera colisión en la agenda médica.")

        cita._fecha = nueva_fecha
        cita._hora = nueva_hora
        self._cita_dao.actualizar(cita)
        return cita

    def completar_cita(self, cita_id: int) -> bool:
        cita = self._cita_dao.buscar_por_id(cita_id)
        if not cita or not cita.is_pendiente():
            raise ValueError("Solo se pueden cerrar consultas en estado 'Pendiente'.")
        return self._cita_dao.completar(cita_id)

    def listar_citas_por_fecha(self, fecha: str) -> List[Cita]:
        return self._cita_dao.listar_por_fecha(fecha)

    def listar_citas_por_doctor(self, doctor_id: int, fecha: Optional[str] = None) -> List[Cita]:
        return self._cita_dao.listar_por_doctor(doctor_id, fecha)

    def listar_citas_por_paciente(self, paciente_id: int) -> List[Cita]:
        return self._cita_dao.listar_por_paciente(paciente_id)

    def listar_pendientes(self, fecha: str) -> List[Cita]:
        citas_del_dia = self._cita_dao.listar_por_fecha(fecha)
        return [c for c in citas_del_dia if c.is_pendiente()]

    # ------------------------------------------------------------------ #
    #  Vistas por periodo: Día / Semana / Mes
    # ------------------------------------------------------------------ #
    def rango_periodo(self, fecha_referencia: str, periodo: str = "dia") -> Tuple[str, str]:
        """Calcula (fecha_inicio, fecha_fin) en formato 'YYYY-MM-DD' según el periodo pedido,
        tomando fecha_referencia como el día dentro de ese rango."""
        if periodo not in PERIODOS_VALIDOS:
            raise ValueError(f"Periodo inválido: '{periodo}'. Use 'dia', 'semana' o 'mes'.")

        d = datetime.strptime(fecha_referencia, "%Y-%m-%d")

        if periodo == "dia":
            return fecha_referencia, fecha_referencia

        if periodo == "semana":
            inicio = d - timedelta(days=d.weekday())  # lunes
            fin = inicio + timedelta(days=6)          # domingo
            return inicio.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")

        # periodo == "mes"
        inicio = d.replace(day=1)
        if d.month == 12:
            fin = inicio.replace(year=d.year + 1, month=1) - timedelta(days=1)
        else:
            fin = inicio.replace(month=d.month + 1) - timedelta(days=1)
        return inicio.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")

    def listar_citas_periodo(self, fecha_referencia: str, periodo: str = "dia") -> List[Cita]:
        """Lista las citas del día, la semana (lunes-domingo) o el mes que contiene fecha_referencia."""
        inicio, fin = self.rango_periodo(fecha_referencia, periodo)
        if inicio == fin:
            return self._cita_dao.listar_por_fecha(inicio)
        return self._cita_dao.listar_por_rango(inicio, fin)

    def listar_citas_doctor_periodo(self, doctor_id: int, fecha_referencia: str, periodo: str = "dia") -> List[Cita]:
        """Igual que listar_citas_periodo pero acotado a un doctor específico."""
        inicio, fin = self.rango_periodo(fecha_referencia, periodo)
        return self._cita_dao.listar_por_doctor_y_rango(doctor_id, inicio, fin)