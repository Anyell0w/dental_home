"""
Módulo de Gestión de Persistencia - Dental Home
Implementa el patrón Singleton para asegurar una única instancia de conexión 
operando de forma segura con restricciones de clave foránea activas.
"""
import sqlite3
import os
from typing import Optional
import logging

class Database:
    _instancia: Optional['Database'] = None
    RUTA_DB: str = os.path.join(os.path.dirname(__file__), "dental_home.db")

    def __new__(cls) -> 'Database':
        if cls._instancia is None:
            cls._instancia = super(Database, cls).__new__(cls)
        return cls._instancia

    @classmethod
    def obtener_instancia(cls) -> 'Database':
        if cls._instancia is None:
            cls._instancia = cls()
        return cls._instancia

    def __init__(self) -> None:
        if not hasattr(self, '_inicializado'):
            self._con: Optional[sqlite3.Connection] = None
            self._inicializado: bool = True

    @classmethod
    def para_ruta(cls, ruta: str) -> sqlite3.Connection:
        """Abre (y migra) una base independiente sin pasar por el Singleton.
        Lo usa la versión web: cada clínica tiene su propio archivo SQLite."""
        inst = object.__new__(cls)
        inst._con = None
        inst._inicializado = True
        inst.RUTA_DB = ruta
        return inst.obtener_conexion()

    def cerrar_conexion(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def obtener_conexion(self) -> sqlite3.Connection:
        if self._con is None:
            try:
                # check_same_thread=False evita bloqueos entre la GUI de Tkinter y los DAOs
                self._con = sqlite3.connect(self.RUTA_DB, check_same_thread=False, timeout=10.0)
                self._con.row_factory = sqlite3.Row
                # Habilitar llaves foráneas de forma segura
                self._con.execute("PRAGMA foreign_keys = ON;")
                self._crear_tablas()
                self._migrar_esquema()
            except sqlite3.Error as e:
                logging.error(f"Error al conectar a SQLite: {e}")
                raise e
        return self._con

    def _columnas_tabla(self, tabla: str) -> set:
        """Devuelve el conjunto de nombres de columna de una tabla existente."""
        cursor = self._con.execute(f"PRAGMA table_info({tabla})")
        return {fila[1] for fila in cursor.fetchall()}

    def _migrar_esquema(self) -> None:
        """Aplica cambios incrementales sobre bases ya creadas (CREATE IF NOT EXISTS no altera columnas)."""
        try:
            cols_hist = self._columnas_tabla("historiales_clinicos")
            if "odontograma" not in cols_hist:
                self._con.execute(
                    "ALTER TABLE historiales_clinicos ADD COLUMN odontograma TEXT DEFAULT ''"
                )
            if "descripcionOdontograma" not in cols_hist:
                self._con.execute(
                    "ALTER TABLE historiales_clinicos ADD COLUMN descripcionOdontograma TEXT DEFAULT ''"
                )
            if "odontogramaEstado" not in cols_hist:
                self._con.execute(
                    "ALTER TABLE historiales_clinicos ADD COLUMN odontogramaEstado TEXT DEFAULT '{}'"
                )
            self._con.commit()
        except sqlite3.Error as e:
            self._con.rollback()
            logging.error(f"Error en migración de esquema: {e}")
            raise e

    def _crear_tablas(self) -> None:
        """Crea el esquema relacional completo del sistema bajo una única transacción."""
        cursor = self._con.cursor()
        try:
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombreUsuario TEXT NOT NULL UNIQUE,
                contrasena TEXT NOT NULL,
                rol TEXT NOT NULL CHECK (rol IN ('Doctor', 'Secretaria', 'Administrador')),
                activo INTEGER NOT NULL DEFAULT 1,
                fechaCreacion TEXT NOT NULL,
                numeroColegiatura TEXT,
                turno TEXT CHECK (turno IN ('Mañana', 'Tarde', 'Tiempo Completo', NULL))
            );

            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                dni TEXT NOT NULL UNIQUE,
                telefono TEXT,
                sexo TEXT CHECK (sexo IN ('M', 'F')),
                fechaNacimiento TEXT,
                direccion TEXT,
                estado INTEGER NOT NULL DEFAULT 1,
                registradoPor INTEGER REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS historiales_clinicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pacienteId INTEGER NOT NULL UNIQUE REFERENCES pacientes(id) ON DELETE RESTRICT,
                fechaCreacion TEXT NOT NULL,
                observaciones TEXT DEFAULT '',
                odontograma TEXT DEFAULT '',
                descripcionOdontograma TEXT DEFAULT '',
                odontogramaEstado TEXT DEFAULT '{}',
                activo INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS citas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pacienteId INTEGER NOT NULL REFERENCES pacientes(id),
                doctorId INTEGER NOT NULL REFERENCES usuarios(id),
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Completada', 'Cancelada')),
                motivoCancelacion TEXT DEFAULT '',
                fechaRegistro TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS registros_clinicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                historialId INTEGER NOT NULL REFERENCES historiales_clinicos(id),
                citaId INTEGER NOT NULL UNIQUE REFERENCES citas(id),
                doctorId INTEGER NOT NULL REFERENCES usuarios(id),
                diagnostico TEXT NOT NULL,
                tratamiento TEXT NOT NULL,
                observaciones TEXT DEFAULT '',
                fechaConsulta TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recetas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registroClinicoId INTEGER NOT NULL UNIQUE REFERENCES registros_clinicos(id),
                pacienteId INTEGER NOT NULL REFERENCES pacientes(id),
                doctorId INTEGER NOT NULL REFERENCES usuarios(id),
                fecha TEXT NOT NULL,
                indicacionesGenerales TEXT DEFAULT '',
                archivoPDF TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS medicamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recetaId INTEGER NOT NULL REFERENCES recetas(id) ON DELETE CASCADE,
                nombre TEXT NOT NULL,
                cantidad REAL NOT NULL,
                indicaciones TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reportes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generadoPor TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('Citas', 'Pacientes', 'Ingresos', 'Actividad')),
                fechaInicio TEXT NOT NULL,
                fechaFin TEXT NOT NULL,
                formato TEXT NOT NULL CHECK (formato IN ('PDF', 'Excel')),
                fechaGeneracion TEXT NOT NULL,
                archivo TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS copias_seguridad (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fechaHora TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('Manual', 'Automatico')),
                ubicacion TEXT DEFAULT '',
                estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Exitoso', 'Fallido')),
                adminId INTEGER REFERENCES usuarios(id)
            );
            """)
            self._con.commit()
        except sqlite3.Error as e:
            self._con.rollback()
            print(f"[CRITICAL] Error en la creación del esquema: {e}")
            raise e
