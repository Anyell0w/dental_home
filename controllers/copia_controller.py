from typing import List, Optional
from dao.gestor_copia import GestorCopiaSeguridad
from models.copia_seguridad import CopiaSeguridad
from utils.backup_manager import BackupManager


class CopiaSeguridadController:
    def __init__(self, gestor_copia: GestorCopiaSeguridad, ruta_db: str, ruta_respaldo: str) -> None:
        self._copia_dao: GestorCopiaSeguridad = gestor_copia
        self._ruta_db: str = ruta_db
        self._ruta_respaldo: str = ruta_respaldo

    def ejecutar_backup_manual(self, admin_id: int) -> CopiaSeguridad:
        backup = CopiaSeguridad(None, "Manual", admin_id)
        try:
            ruta_final = BackupManager.ejecutar_copia_seguridad_fisica(
                comprimir_zip=True, ruta_db=self._ruta_db, ruta_backups=self._ruta_respaldo)
            backup._ubicacion = ruta_final
            backup._estado = "Exitoso"
        except Exception:
            backup._estado = "Fallido"

        bk_id = self._copia_dao.guardar(backup)
        return self._copia_dao.buscar_por_id(bk_id)

    def registrar_backup_automatico(self, ruta: Optional[str], estado: str) -> None:
        """Persiste en BD el resultado de un respaldo generado por el daemon 24h."""
        backup = CopiaSeguridad(None, "Automatico", None)
        backup._ubicacion = ruta or ""
        backup._estado = estado if estado in ("Exitoso", "Fallido") else "Fallido"
        self._copia_dao.guardar(backup)

    def iniciar_respaldo_automatico(self) -> None:
        """Arranca el daemon de respaldo y garantiza su auditoría en la base de datos."""
        BackupManager.iniciar_daemon_automatico_24h(al_completar=self.registrar_backup_automatico)

    def listar_copias(self) -> List[CopiaSeguridad]:
        return self._copia_dao.listar_todos()
