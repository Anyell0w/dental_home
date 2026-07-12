"""
Módulo de Mantenimiento Preventivo y Respaldos Automatizados en Caliente.
Soporta compresión física nativa ZIP e inyección segura por hilos.
"""
import os
import shutil
import zipfile
import threading
import time
from datetime import datetime
import logging
from config import PATHS

class BackupManager:
    @staticmethod
    def ejecutar_copia_seguridad_fisica(comprimir_zip: bool = True) -> str:
        """Duplica de manera íntegra el archivo de base de datos de producción."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_base = f"backup_{timestamp}"
            ruta_salida_db = os.path.join(PATHS["backups"], f"{nombre_base}.db")
            
            # Copiar archivo maestro relacional
            shutil.copy2(PATHS["db"], ruta_salida_db)
            
            if comprimir_zip:
                ruta_zip = os.path.join(PATHS["backups"], f"{nombre_base}.zip")
                with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(ruta_salida_db, arcname=f"{nombre_base}.db")
                os.remove(ruta_salida_db)  # Limpieza del archivo intermedio descompreso
                return ruta_zip
                
            return ruta_salida_db
        except Exception as e:
            logging.error(f"Error de infraestructura en proceso de Backup: {str(e)}")
            raise e

    @staticmethod
    def iniciar_daemon_automatico_24h(al_completar=None) -> None:
        """Lanza un hilo secundario infinito (Daemon) para respaldos cada 24 horas.

        Args:
            al_completar: callback opcional invocado tras cada intento con
                la firma (ruta: Optional[str], estado: str). Permite que la
                capa superior registre el backup automático en la base de datos.
        """
        def loop_cron():
            while True:
                # Intervalo estricto de espera de 24 horas (86400 segundos)
                time.sleep(86400)
                ruta = None
                estado = "Exitoso"
                try:
                    ruta = BackupManager.ejecutar_copia_seguridad_fisica(comprimir_zip=True)
                except Exception as e:
                    estado = "Fallido"
                    logging.error(f"Error en ejecución del Daemon de backup continuo: {str(e)}")

                if al_completar is not None:
                    try:
                        al_completar(ruta, estado)
                    except Exception as e:
                        logging.error(f"Error al registrar backup automático en BD: {str(e)}")

        daemon = threading.Thread(target=loop_cron, daemon=True)
        daemon.start()
