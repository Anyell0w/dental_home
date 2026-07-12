from datetime import datetime


class GestorDashboard:
    """Consultas agregadas de solo lectura para el panel de inicio."""

    def __init__(self, conexion):
        self._con = conexion

    def obtener_estadisticas(self):
        datos = {}

        # Pacientes activos
        cur = self._con.execute("SELECT COUNT(*) FROM pacientes WHERE estado = 1")
        datos["pacientes_activos"] = cur.fetchone()[0]

        hoy = datetime.now().strftime("%Y-%m-%d")

        # Citas de hoy
        cur = self._con.execute("SELECT COUNT(*) FROM citas WHERE fecha = ?", (hoy,))
        datos["citas_hoy"] = cur.fetchone()[0]

        # Citas completadas hoy
        cur = self._con.execute(
            "SELECT COUNT(*) FROM citas WHERE fecha = ? AND estado = 'Completada'", (hoy,)
        )
        datos["citas_completadas"] = cur.fetchone()[0]

        # Recetas del mes
        mes_actual = datetime.now().strftime("%Y-%m")
        cur = self._con.execute(
            "SELECT COUNT(*) FROM recetas WHERE substr(fecha,1,7) = ?", (mes_actual,)
        )
        datos["recetas_mes"] = cur.fetchone()[0]

        # Último backup
        fila = self._con.execute(
            "SELECT fechaHora, estado FROM copias_seguridad ORDER BY fechaHora DESC LIMIT 1"
        ).fetchone()
        if fila:
            datos["ultima_copia"] = fila["fechaHora"][:10]
            datos["estado_backup"] = fila["estado"]
        else:
            datos["ultima_copia"] = "Sin copia"
            datos["estado_backup"] = "-"

        return datos

    def obtener_agenda_hoy(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        cursor = self._con.execute(
            """
            SELECT
                c.hora,
                p.nombre || ' ' || p.apellido AS paciente,
                u.nombreUsuario AS doctor,
                c.estado
            FROM citas c
            INNER JOIN pacientes p ON c.pacienteId = p.id
            INNER JOIN usuarios u ON c.doctorId = u.id
            WHERE c.fecha = ?
            ORDER BY c.hora ASC
            """,
            (hoy,),
        )
        return cursor.fetchall()

    def obtener_actividad_reciente(self):
        actividades = []

        cursor = self._con.execute(
            """
            SELECT
                'Nueva cita programada' AS titulo,
                p.nombre || ' ' || p.apellido AS detalle,
                c.fechaRegistro AS fecha
            FROM citas c
            INNER JOIN pacientes p ON c.pacienteId = p.id
            ORDER BY c.fechaRegistro DESC
            LIMIT 5
            """
        )
        for fila in cursor.fetchall():
            actividades.append(
                {"titulo": fila["titulo"], "detalle": fila["detalle"], "fecha": fila["fecha"]}
            )

        cursor = self._con.execute(
            """
            SELECT
                'Receta emitida' AS titulo,
                p.nombre || ' ' || p.apellido AS detalle,
                r.fecha AS fecha
            FROM recetas r
            INNER JOIN pacientes p ON r.pacienteId = p.id
            ORDER BY r.fecha DESC
            LIMIT 5
            """
        )
        for fila in cursor.fetchall():
            actividades.append(
                {"titulo": fila["titulo"], "detalle": fila["detalle"], "fecha": fila["fecha"]}
            )

        cursor = self._con.execute(
            """
            SELECT
                'Copia de seguridad realizada' AS titulo,
                estado AS detalle,
                fechaHora AS fecha
            FROM copias_seguridad
            ORDER BY fechaHora DESC
            LIMIT 5
            """
        )
        for fila in cursor.fetchall():
            actividades.append(
                {"titulo": fila["titulo"], "detalle": fila["detalle"], "fecha": fila["fecha"]}
            )

        actividades.sort(key=lambda a: a.get("fecha") or "", reverse=True)
        return actividades[:5]
