from typing import List, Optional, Dict, Any
from datetime import datetime
import os
from dao.gestor_receta import GestorReceta
from dao.gestor_medicamento import GestorMedicamento
from dao.gestor_registro import GestorRegistroClinico
from dao.gestor_paciente import GestorPaciente
from dao.gestor_usuario import GestorUsuario
from models.receta import Receta
from models.medicamento import Medicamento
from utils.pdf_generator import PDFRecetaGenerator
from config import PATHS


class RecetaController:
    """Gestiona la prescripción de medicamentos y la preparación documental de recetas."""

    def __init__(
        self,
        gestor_receta: GestorReceta,
        gestor_medicamento: GestorMedicamento,
        gestor_registro: GestorRegistroClinico,
        gestor_paciente: GestorPaciente,
        gestor_usuario: GestorUsuario,
    ) -> None:
        self._receta_dao: GestorReceta = gestor_receta
        self._medicamento_dao: GestorMedicamento = gestor_medicamento
        self._registro_dao: GestorRegistroClinico = gestor_registro
        self._paciente_dao: GestorPaciente = gestor_paciente
        self._usuario_dao: GestorUsuario = gestor_usuario

    def generar_receta(
        self,
        registro_id: int,
        paciente_id: int,
        doctor_id: int,
        indicaciones: str,
        medicamentos: List[Dict[str, Any]],
    ) -> Receta:
        if not medicamentos:
            raise ValueError("Debe agregar al menos un medicamento a la receta.")

        registro = self._registro_dao.buscar_por_id(registro_id)
        if not registro:
            raise ValueError("El registro clínico de referencia no existe.")

        receta_existente = self._receta_dao.buscar_por_registro(registro_id)
        if receta_existente:
            raise ValueError("Ya existe una receta médica emitida para este registro clínico.")

        nueva_receta = Receta(
            id_receta=None,
            registro_clinico_id=registro_id,
            paciente_id=paciente_id,
            doctor_id=doctor_id,
            fecha=datetime.now().strftime("%Y-%m-%d"),
            indicaciones_generales=indicaciones,
        )
        rec_id = self._receta_dao.guardar(nueva_receta)

        for m in medicamentos:
            self.agregar_medicamento(rec_id, m["nombre"], m["cantidad"], m["indicaciones"])

        receta = self.obtener_receta(rec_id)
        self.generar_pdf(rec_id)
        return self.obtener_receta(rec_id)

    def agregar_medicamento(
        self, receta_id: int, nombre: str, cantidad: float, indicaciones: str
    ) -> Medicamento:
        med = Medicamento(None, receta_id, nombre, cantidad, indicaciones)
        if not med.validar():
            raise ValueError("Campos obligatorios del medicamento vacíos o cantidad errónea.")
        med_id = self._medicamento_dao.guardar(med)
        return self._medicamento_dao.buscar_por_id(med_id)

    def eliminar_medicamento(self, medicamento_id: int) -> bool:
        return self._medicamento_dao.eliminar(medicamento_id)

    def generar_pdf(self, receta_id: int, ruta_destino: Optional[str] = None) -> str:
        receta = self.obtener_receta(receta_id)
        if not receta:
            raise ValueError("Receta no encontrada.")

        paciente = self._paciente_dao.buscar_por_id(receta.pacienteId)
        doctor = self._usuario_dao.buscar_por_id(receta.doctorId)
        if not paciente or not doctor:
            raise ValueError("No se pudo resolver paciente o doctor para el PDF.")

        colegiatura = getattr(doctor, "numeroColegiatura", None) or "N/A"
        if not ruta_destino:
            ruta_destino = os.path.join(
                PATHS["recetas"], f"receta_{receta_id}_{receta.fecha}.pdf"
            )

        ruta = PDFRecetaGenerator.generar_receta_pdf(
            receta,
            paciente.obtener_nombre_completo(),
            paciente.dni,
            doctor.nombreUsuario,
            colegiatura,
            receta.obtener_medicamentos(),
            ruta_destino,
        )
        self._receta_dao.actualizar_ruta_pdf(receta_id, ruta)
        return ruta

    def obtener_receta(self, rec_id: int) -> Optional[Receta]:
        receta = self._receta_dao.buscar_por_id(rec_id)
        if receta:
            meds = self._medicamento_dao.listar_por_receta(rec_id)
            for m in meds:
                receta.agregar_medicamento(m)
        return receta

    def obtener_por_registro(self, registro_id: int) -> Optional[Receta]:
        receta = self._receta_dao.buscar_por_registro(registro_id)
        if not receta:
            return None
        return self.obtener_receta(receta.id)

    def listar_recetas_por_paciente(self, paciente_id: int) -> List[Receta]:
        recetas = self._receta_dao.listar_por_paciente(paciente_id)
        resultado: List[Receta] = []
        for r in recetas:
            completa = self.obtener_receta(r.id)
            if completa:
                resultado.append(completa)
        return resultado
