"""
Módulo de Configuración de Entorno, Rutas y Constantes Globales.
Centraliza los parámetros del sistema y el flujo de auditoría de logs.
"""
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Diccionario de Rutas Estructurales del Sistema
PATHS = {
    "db": os.path.join(BASE_DIR, "dental_home.db"),
    "backups": os.path.join(BASE_DIR, "backups"),
    "reportes": os.path.join(BASE_DIR, "exports", "reportes"),
    "recetas": os.path.join(BASE_DIR, "exports", "recetas"),
    "odontogramas": os.path.join(BASE_DIR, "exports", "odontogramas"),
    "logs": os.path.join(BASE_DIR, "log.txt")
}

# Creación de directorios faltantes de forma atómica
for path in PATHS.values():
    if not path.endswith(".db") and not path.endswith(".txt"):
        os.makedirs(path, exist_ok=True)

# Configuración del motor de auditoría de errores
logging.basicConfig(
    filename=PATHS["logs"],
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Parámetros de Seguridad Obligatorios
SESSION_TIMEOUT_MINUTES = 30
MIN_PASSWORD_LENGTH = 8
