import tkinter as tk
from tkinter import ttk, messagebox
from utils.theme import COLORS, FONTS
from controllers.cita_controller import CitaController
from controllers.usuario_controller import UsuarioController
from dao.gestor_paciente import GestorPaciente
from dao.gestor_usuario import GestorUsuario
from tkcalendar import DateEntry

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}


# ---------------------------------------------------------------------- #
#  Puente de sesión (sin modificar main.py ni usuario_controller.py)
#
#  main.py no le pasa a CitaView el usuario logueado, y no está permitido
#  tocar main.py ni usuario_controller.py. Para que la agenda pueda saber
#  qué rol entró (Doctor vs Secretaria/Administrador) y filtrarse cuando
#  corresponda, se intercepta (monkey-patch) UsuarioController.iniciar_sesion
#  / cerrar_sesion la primera vez que se importa este módulo. El parche solo
#  AÑADE un efecto secundario (guardar el usuario en _SesionCitas); no cambia
#  el comportamiento original de esos métodos ni su valor de retorno.
# ---------------------------------------------------------------------- #
class _SesionCitas:
    """Guarda el usuario logueado más reciente, alimentado por el parche."""
    usuario_activo = None


def _instalar_puente_sesion() -> None:
    if getattr(UsuarioController, "_puente_sesion_citas_instalado", False):
        return  # Ya instalado (por ejemplo, si esta vista se recarga varias veces)

    _iniciar_sesion_original = UsuarioController.iniciar_sesion
    _cerrar_sesion_original = UsuarioController.cerrar_sesion

    def _iniciar_sesion_parcheado(self, nombre_usuario, contrasena):
        usuario = _iniciar_sesion_original(self, nombre_usuario, contrasena)
        if usuario:
            _SesionCitas.usuario_activo = usuario
        return usuario

    def _cerrar_sesion_parcheado(self):
        _cerrar_sesion_original(self)
        _SesionCitas.usuario_activo = None

    UsuarioController.iniciar_sesion = _iniciar_sesion_parcheado
    UsuarioController.cerrar_sesion = _cerrar_sesion_parcheado
    UsuarioController._puente_sesion_citas_instalado = True


_instalar_puente_sesion()


class CitaView:
    """Módulo operativo de control de reservas y agenda de citas médicas.

    Se comporta distinto según el rol de la sesión activa (ver _SesionCitas):
      - Doctor: ve y agenda únicamente su propia agenda. No hay selector de
        doctor ni columna Doctor en la tabla; al programar una cita se
        autoasigna a sí mismo.
      - Secretaria / Administrador: ve la agenda general de la clínica, con
        columna Doctor, botón "Ver por Doctor" para filtrar, y selector de
        doctor al programar una cita.
    """

    def __init__(self, contenedor: tk.Frame, controller: CitaController,
                 gestor_paciente: GestorPaciente, gestor_usuario: GestorUsuario) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: CitaController = controller
        self._gestor_paciente: GestorPaciente = gestor_paciente
        self._gestor_usuario: GestorUsuario = gestor_usuario

        usuario_activo = _SesionCitas.usuario_activo
        if not usuario_activo:
            raise ValueError(
                "No hay una sesión activa. Inicie sesión antes de acceder a la agenda de citas."
            )

        self._es_doctor: bool = (usuario_activo.rol == 'Doctor')
        self._doctor_id: int = usuario_activo.id if self._es_doctor else None

        # Estos dos solo se usan en el modo Secretaria/Administrador (filtro "Ver por Doctor")
        self._modo: str = "fecha"          # "fecha" | "doctor"
        self._doctor_id_filtro = None
        self._nombre_doctor_filtro = ""

        self._periodo: str = "dia"         # "dia" | "semana" | "mes"
        self._botones_periodo = {}

    # ------------------------------------------------------------------ #
    #  Construcción de la interfaz
    # ------------------------------------------------------------------ #
    def _configurar_estilos_tabla(self) -> None:
        """Fuerza texto oscuro legible en la tabla de la agenda."""
        estilo = ttk.Style()
        estilo.configure(
            "Cita.Treeview",
            background=COLORS['white'],
            foreground=COLORS['dark'],
            fieldbackground=COLORS['white'],
            rowheight=32,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Cita.Treeview.Heading",
            background=COLORS['primary'],
            foreground=COLORS['white'],
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map(
            "Cita.Treeview",
            background=[("selected", COLORS['primary'])],
            foreground=[("selected", COLORS['white'])],
        )

    def inicializar(self) -> None:
        for widget in self._contenedor.winfo_children():
            widget.destroy()

        self._configurar_estilos_tabla()

        titulo_texto = "Mi Agenda de Citas" if self._es_doctor else "Agenda de Citas"
        self.lbl_titulo = tk.Label(
            self._contenedor,
            text=titulo_texto,
            font=("Arial", 22, "bold"),
            bg=COLORS['background'],
            fg=COLORS['primary']
        )
        self.lbl_titulo.pack(anchor="w", padx=25, pady=(20, 5))

        # --------------------------- Barra superior --------------------------- #
        barra = tk.Frame(self._contenedor, bg=COLORS['background'], pady=10, padx=15)
        barra.pack(fill=tk.X)

        self.txt_fecha = DateEntry(
            barra,
            width=12,
            background=COLORS['primary'],
            foreground="white",
            date_pattern="dd/mm/yyyy",
            font=FONTS['body']
        )
        self.txt_fecha.pack(side=tk.LEFT, padx=10)
        self.txt_fecha.bind("<<DateEntrySelected>>", lambda e: self._ver_por_fecha())

        tk.Button(
            barra, text="📅", font=("Arial", 14), bg=COLORS['primary'], fg="white",
            command=self._ver_por_fecha
        ).pack(side=tk.LEFT)

        # El botón "Ver por Doctor" solo tiene sentido para quien administra la
        # agenda de varios doctores (Secretaria/Administrador). Un Doctor ya
        # está viendo su propia agenda, así que ese botón no se muestra.
        if not self._es_doctor:
            tk.Button(
                barra, text="Ver por Doctor", font=FONTS['body'], bg=COLORS['background'],
                command=self._abrir_selector_doctor
            ).pack(side=tk.RIGHT, padx=10)

        tk.Button(
            barra, text="+ Programar cita", font=FONTS['body'], bg="#2D6E47",
            fg="white",
            activebackground="#77D670",
            activeforeground="white",
            command=self._abrir_formulario_programacion
        ).pack(side=tk.RIGHT)

        # --------------------------- Selector de periodo (Día/Semana/Mes) --------------------------- #
        frame_periodo = tk.Frame(self._contenedor, bg=COLORS['background'], padx=15)
        frame_periodo.pack(fill=tk.X)

        self._botones_periodo = {}
        for clave, etiqueta in (("dia", "Día"), ("semana", "Semana"), ("mes", "Mes")):
            btn = tk.Button(
                frame_periodo, text=etiqueta, font=FONTS['body'], width=8,
                command=lambda c=clave: self._cambiar_periodo(c)
            )
            btn.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 10))
            self._botones_periodo[clave] = btn

        # --------------------------- Grid de datos --------------------------- #
        frame_tabla = tk.Frame(self._contenedor)
        frame_tabla.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        if self._es_doctor:
            # Sin columna Doctor: la agenda ya está acotada al doctor de la sesión.
            columnas = ('Fecha', 'Hora', 'Paciente', 'Estado')
            anchos = {'Fecha': 100, 'Hora': 80, 'Paciente': 220, 'Estado': 120}
        else:
            columnas = ('Fecha', 'Hora', 'Paciente', 'Doctor', 'Estado')
            anchos = {'Fecha': 90, 'Hora': 70, 'Paciente': 160, 'Doctor': 140, 'Estado': 100}

        self.tabla = ttk.Treeview(frame_tabla, columns=columnas, show='headings',
                                   selectmode="browse", style="Cita.Treeview")

        scrollbar = ttk.Scrollbar(frame_tabla, orient=tk.VERTICAL, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)

        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos.get(col, 100), anchor="center")

        self.tabla.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Colores según estado. Envuelto en try/except para que un problema de estilo
        # nunca impida que la tabla y los botones de acción se terminen de construir.
        try:
            self.tabla.tag_configure('Pendiente', foreground=COLORS['primary'])
            self.tabla.tag_configure('Completada', foreground=COLORS['success_text'])
            self.tabla.tag_configure('Cancelada', foreground=COLORS['danger_text'])
        except Exception:
            pass

        # --------------------------- Acciones sobre la fila seleccionada --------------------------- #
        frame_acciones = tk.Frame(self._contenedor, bg=COLORS['background'], pady=10)
        frame_acciones.pack(fill=tk.X, padx=15)

        tk.Button(
            frame_acciones, text="✅ Completar", command=self._completar_cita_seleccionada,
            bg="#489D48",
            fg="white",
            activebackground="#70DD30",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            frame_acciones, text="🔁 Reprogramar",
            command=self._solicitar_reprogramacion,
            bg="#05522B",
            fg="white",
            activebackground="#84C37D",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            frame_acciones, text="🚫 Cancelar Cita", command=self._solicitar_cancelacion,
            bg="#C62828",
            fg="white",
            activebackground="#DB5F5F",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

        self._actualizar_botones_periodo()
        self._ver_por_fecha()

    # ------------------------------------------------------------------ #
    #  Periodo: Día / Semana / Mes
    # ------------------------------------------------------------------ #
    def _cambiar_periodo(self, periodo: str) -> None:
        self._periodo = periodo
        self._actualizar_botones_periodo()
        self._refrescar()

    def _actualizar_botones_periodo(self) -> None:
        for clave, btn in self._botones_periodo.items():
            if clave == self._periodo:
                btn.configure(bg=COLORS['primary'], fg="white", relief=tk.SUNKEN)
            else:
                btn.configure(bg=COLORS['background'], fg=COLORS['primary'], relief=tk.RAISED)

    # ------------------------------------------------------------------ #
    #  Carga / refresco de la tabla
    # ------------------------------------------------------------------ #
    def _pintar_tabla(self, citas) -> None:
        self.tabla.delete(*self.tabla.get_children())
        # Orden estable por fecha y hora (útil en vistas de Semana/Mes que mezclan varios días)
        citas_ordenadas = sorted(citas, key=lambda c: (c.fecha, c.hora))

        for c in citas_ordenadas:
            paciente = self._gestor_paciente.buscar_por_id(c.pacienteId)
            nombre_paciente = paciente.obtener_nombre_completo() if paciente else "(paciente eliminado)"
            fecha_visible = self._formatear_fecha(c.fecha)

            if self._es_doctor:
                valores = (fecha_visible, c.hora, nombre_paciente, c.estado)
            else:
                doctor = self._gestor_usuario.buscar_por_id(c.doctorId)
                nombre_doctor = f"Dr. {doctor.nombreUsuario}" if doctor else "(doctor eliminado)"
                valores = (fecha_visible, c.hora, nombre_paciente, nombre_doctor, c.estado)

            # iid = id real de la cita -> las acciones (cancelar/reprogramar/completar) siempre
            # apuntan a la cita correcta, sin importar qué columna se esté mostrando.
            self.tabla.insert('', tk.END, iid=str(c.id), values=valores, tags=(c.estado,))

    @staticmethod
    def _formatear_fecha(fecha_iso: str) -> str:
        partes = fecha_iso.split("-")
        if len(partes) == 3:
            anio, mes, dia = partes
            return f"{dia}/{mes}/{anio}"
        return fecha_iso

    def _ver_por_fecha(self) -> None:
        self._modo = "fecha"
        self._doctor_id_filtro = None
        self._refrescar()

    def _refrescar(self) -> None:
        fecha_ref = self.txt_fecha.get_date().strftime("%Y-%m-%d")
        inicio, fin = self._controller.rango_periodo(fecha_ref, self._periodo)

        if self._es_doctor:
            # La agenda siempre está acotada al doctor de la sesión.
            citas = self._controller.listar_citas_doctor_periodo(self._doctor_id, fecha_ref, self._periodo)
            base_titulo = "Mi Agenda de Citas"
        elif self._modo == "doctor" and self._doctor_id_filtro:
            citas = self._controller.listar_citas_doctor_periodo(self._doctor_id_filtro, fecha_ref, self._periodo)
            base_titulo = f"Agenda de {self._nombre_doctor_filtro}"
        else:
            citas = self._controller.listar_citas_periodo(fecha_ref, self._periodo)
            base_titulo = "Agenda de Citas"

        self.lbl_titulo.config(text=f"{base_titulo} — {self._etiqueta_rango(inicio, fin)}")
        self._pintar_tabla(citas)

    def _etiqueta_rango(self, inicio: str, fin: str) -> str:
        if self._periodo == "dia":
            return f"Día {self._formatear_fecha(inicio)}"
        if self._periodo == "semana":
            return f"Semana del {self._formatear_fecha(inicio)} al {self._formatear_fecha(fin)}"
        # mes
        anio, mes, _ = inicio.split("-")
        return f"Mes de {MESES_ES.get(int(mes), mes)} {anio}"

    # Se mantiene por compatibilidad si algo externo llamaba a este nombre
    def _actualizar_agenda(self) -> None:
        self._ver_por_fecha()

    # ------------------------------------------------------------------ #
    #  Ver por Doctor (solo Secretaria / Administrador)
    # ------------------------------------------------------------------ #
    def _abrir_selector_doctor(self) -> None:
        doctores = self._gestor_usuario.listar_por_rol("Doctor")
        if not doctores:
            messagebox.showinfo("Sin doctores", "No hay doctores registrados en el sistema.")
            return
        dict_doctores = {f"Dr. {d.nombreUsuario}": d.id for d in doctores}

        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Ver agenda por Doctor")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("320x150")

        tk.Label(modal, text="Seleccione un Doctor:", font=FONTS['body']).pack(pady=(15, 5))
        cb_doc = ttk.Combobox(modal, values=list(dict_doctores.keys()), state="readonly")
        cb_doc.pack(fill=tk.X, padx=20)

        def confirmar() -> None:
            seleccion = cb_doc.get()
            if not seleccion:
                messagebox.showerror("Error", "Debe seleccionar un doctor.", parent=modal)
                return
            self._modo = "doctor"
            self._doctor_id_filtro = dict_doctores[seleccion]
            self._nombre_doctor_filtro = seleccion
            self._refrescar()
            modal.destroy()

        tk.Button(
            modal, text="Ver agenda", bg=COLORS['primary'], fg=COLORS['white'], command=confirmar
        ).pack(pady=15)

    # ------------------------------------------------------------------ #
    #  Programar cita
    # ------------------------------------------------------------------ #
    @staticmethod
    def _generar_horarios() -> list:
        horarios = []
        h, m = 8, 0
        while (h, m) <= (19, 30):
            horarios.append(f"{h:02d}:{m:02d}")
            m += 30
            if m == 60:
                m = 0
                h += 1
        return horarios

    def _abrir_formulario_programacion(self) -> None:
        if self._es_doctor:
            self._abrir_formulario_programacion_doctor()
        else:
            self._abrir_formulario_programacion_secretaria()

    # --- Variante Doctor: sin selector de doctor, con buscador de pacientes --- #
    def _abrir_formulario_programacion_doctor(self) -> None:
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Programación de Cita")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()

        sw, sh = modal.winfo_screenwidth(), modal.winfo_screenheight()
        modal.geometry(f"400x420+{(sw - 400) // 2}+{(sh - 420) // 2}")

        # dict_pacientes se recalcula en cada tecleo con los resultados
        # visibles actualmente en la lista de sugerencias (ver _filtrar_pacientes).
        dict_pacientes: dict = {}
        paciente_seleccionado_id = {"id": None}

        # Sin selector de doctor: la cita se agenda automáticamente para
        # el doctor de la sesión actual (self._doctor_id).
        tk.Label(modal, text="Paciente (buscar por nombre, apellido o DNI):").pack(anchor="w", padx=20, pady=2)

        ent_pac = ttk.Entry(modal)
        ent_pac.pack(fill=tk.X, padx=20)

        # Lista de sugerencias siempre visible debajo del campo, con espacio
        # fijo reservado (evita que el formulario "salte" al aparecer/ocultarse).
        frame_sugerencias = tk.Frame(modal)
        frame_sugerencias.pack(fill=tk.X, padx=20, pady=(2, 8))

        lista_sugerencias = tk.Listbox(frame_sugerencias, height=5, exportselection=False)
        lista_sugerencias.pack(fill=tk.X, side=tk.LEFT, expand=True)

        scroll_sugerencias = ttk.Scrollbar(frame_sugerencias, orient=tk.VERTICAL, command=lista_sugerencias.yview)
        lista_sugerencias.configure(yscrollcommand=scroll_sugerencias.set)
        scroll_sugerencias.pack(side=tk.RIGHT, fill=tk.Y)

        def _filtrar_pacientes(event=None) -> None:
            # Las teclas de navegación/selección no deben disparar una nueva búsqueda,
            # solo dejar que muevan el cursor o naveguen la lista con normalidad.
            if event is not None and event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
                return

            texto = ent_pac.get().strip()
            resultados = (
                self._gestor_paciente.buscar(texto) if texto
                else self._gestor_paciente.listar_todos(solo_activos=True)
            )

            dict_pacientes.clear()
            lista_sugerencias.delete(0, tk.END)
            for p in resultados[:30]:  # tope razonable de sugerencias visibles
                if not p.estado:
                    continue
                etiqueta = f"{p.obtener_nombre_completo()} ({p.dni})"
                dict_pacientes[etiqueta] = p.id
                lista_sugerencias.insert(tk.END, etiqueta)

            # Si lo que hay escrito ya no coincide con la selección previa, se limpia.
            if ent_pac.get().strip() not in dict_pacientes:
                paciente_seleccionado_id["id"] = None

        def _seleccionar_de_lista(event=None) -> None:
            seleccion = lista_sugerencias.curselection()
            if not seleccion:
                return
            etiqueta = lista_sugerencias.get(seleccion[0])
            ent_pac.delete(0, tk.END)
            ent_pac.insert(0, etiqueta)
            paciente_seleccionado_id["id"] = dict_pacientes.get(etiqueta)

        # El tipeo solo actualiza la lista; nunca mueve el cursor ni roba el foco.
        ent_pac.bind("<KeyRelease>", _filtrar_pacientes)
        # Seleccionar con clic o doble clic sobre una sugerencia.
        lista_sugerencias.bind("<<ListboxSelect>>", _seleccionar_de_lista)
        lista_sugerencias.bind("<Double-Button-1>", _seleccionar_de_lista)
        # Desde el campo de texto, la flecha abajo salta a la lista para navegar con teclado.
        ent_pac.bind("<Down>", lambda e: (lista_sugerencias.focus_set(), lista_sugerencias.selection_set(0)) if lista_sugerencias.size() else None)
        lista_sugerencias.bind("<Return>", _seleccionar_de_lista)

        _filtrar_pacientes()  # precarga sugerencias con los pacientes activos

        tk.Label(modal, text="Fecha:").pack(anchor="w", padx=20, pady=2)
        ent_fec = DateEntry(modal, width=15, date_pattern="yyyy-mm-dd", font=FONTS['body'])
        ent_fec.pack(anchor="w", padx=20)

        tk.Label(modal, text="Hora:").pack(anchor="w", padx=20, pady=2)
        cb_hor = ttk.Combobox(modal, values=self._generar_horarios(), state="readonly")
        cb_hor.pack(fill=tk.X, padx=20)

        def programar() -> None:
            try:
                p_sel = ent_pac.get().strip()
                pac_id = dict_pacientes.get(p_sel) or paciente_seleccionado_id["id"]
                if not p_sel or pac_id is None:
                    raise ValueError("Seleccione un paciente válido de la lista de sugerencias.")
                if not cb_hor.get():
                    raise ValueError("Seleccione una hora.")

                self._controller.programar_cita(
                    pac_id,
                    self._doctor_id,
                    ent_fec.get_date().strftime("%Y-%m-%d"),
                    cb_hor.get()
                )
                modal.destroy()
                self._refrescar()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(modal, text="Agendar", bg="#29653B",
            fg="white",
            activebackground="#81C176",
            activeforeground="white",
                  command=programar).pack(side=tk.LEFT, padx=40, pady=20)
        tk.Button(modal, text="Cancelar", bg="#C62828",
            fg="white",
            activebackground="#DB5F5F",
            activeforeground="white",
                  command=modal.destroy).pack(side=tk.RIGHT, padx=40, pady=20)

        modal.bind("<Return>", lambda e: programar())
        modal.bind("<Escape>", lambda e: modal.destroy())

    # --- Variante Secretaria/Administrador: con selector de doctor --- #
    def _abrir_formulario_programacion_secretaria(self) -> None:
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Programación de Cita")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()

        sw, sh = modal.winfo_screenwidth(), modal.winfo_screenheight()
        modal.geometry(f"400x380+{(sw - 400) // 2}+{(sh - 380) // 2}")

        pacientes = self._gestor_paciente.listar_todos(solo_activos=True)
        dict_pacientes = {f"{p.obtener_nombre_completo()} ({p.dni})": p.id for p in pacientes}

        doctores = self._gestor_usuario.listar_por_rol("Doctor")
        dict_doctores = {f"Dr. {d.nombreUsuario}": d.id for d in doctores}

        tk.Label(modal, text="Paciente:").pack(anchor="w", padx=20, pady=2)
        cb_pac = ttk.Combobox(modal, values=list(dict_pacientes.keys()), state="readonly")
        cb_pac.pack(fill=tk.X, padx=20)

        tk.Label(modal, text="Doctor Asignado:").pack(anchor="w", padx=20, pady=2)
        cb_doc = ttk.Combobox(modal, values=list(dict_doctores.keys()), state="readonly")
        cb_doc.pack(fill=tk.X, padx=20)

        tk.Label(modal, text="Fecha:").pack(anchor="w", padx=20, pady=2)
        ent_fec = DateEntry(modal, width=15, date_pattern="yyyy-mm-dd", font=FONTS['body'])
        ent_fec.pack(anchor="w", padx=20)

        tk.Label(modal, text="Hora:").pack(anchor="w", padx=20, pady=2)
        cb_hor = ttk.Combobox(modal, values=self._generar_horarios(), state="readonly")
        cb_hor.pack(fill=tk.X, padx=20)

        def programar() -> None:
            try:
                p_sel = cb_pac.get()
                d_sel = cb_doc.get()
                if not p_sel or not d_sel:
                    raise ValueError("Seleccione un paciente y un doctor.")
                if not cb_hor.get():
                    raise ValueError("Seleccione una hora.")

                self._controller.programar_cita(
                    dict_pacientes[p_sel],
                    dict_doctores[d_sel],
                    ent_fec.get_date().strftime("%Y-%m-%d"),
                    cb_hor.get()
                )
                modal.destroy()
                self._refrescar()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(modal, text="Agendar", bg="#29653B",
            fg="white",
            activebackground="#81C176",
            activeforeground="white",
                  command=programar).pack(side=tk.LEFT, padx=40, pady=20)
        tk.Button(modal, text="Cancelar", bg="#C62828",
            fg="white",
            activebackground="#DB5F5F",
            activeforeground="white",
                  command=modal.destroy).pack(side=tk.RIGHT, padx=40, pady=20)

        modal.bind("<Return>", lambda e: programar())
        modal.bind("<Escape>", lambda e: modal.destroy())

    # ------------------------------------------------------------------ #
    #  Selección de fila -> id real de la cita
    # ------------------------------------------------------------------ #
    def _obtener_cita_seleccionada_id(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Aviso", "Seleccione una cita de la tabla.")
            return None
        return int(seleccion[0])

    # ------------------------------------------------------------------ #
    #  Reprogramar
    # ------------------------------------------------------------------ #
    def _solicitar_reprogramacion(self) -> None:
        cita_id = self._obtener_cita_seleccionada_id()
        if cita_id is None:
            return

        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Reprogramar Cita")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("320x220")

        tk.Label(modal, text="Nueva Fecha:", font=FONTS['body']).pack(anchor="w", padx=20, pady=(15, 2))
        ent_fec = DateEntry(modal, width=15, date_pattern="yyyy-mm-dd", font=FONTS['body'])
        ent_fec.pack(anchor="w", padx=20)

        tk.Label(modal, text="Nueva Hora:", font=FONTS['body']).pack(anchor="w", padx=20, pady=(10, 2))
        cb_hor = ttk.Combobox(modal, values=self._generar_horarios(), state="readonly")
        cb_hor.pack(fill=tk.X, padx=20)

        def confirmar() -> None:
            try:
                if not cb_hor.get():
                    raise ValueError("Seleccione una nueva hora.")
                self._controller.reprogramar_cita(
                    cita_id,
                    ent_fec.get_date().strftime("%Y-%m-%d"),
                    cb_hor.get()
                )
                modal.destroy()
                self._refrescar()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(modal, text="Confirmar", bg=COLORS['primary'], fg=COLORS['white'],
                  command=confirmar).pack(pady=15)

    # ------------------------------------------------------------------ #
    #  Completar
    # ------------------------------------------------------------------ #
    def _completar_cita_seleccionada(self) -> None:
        cita_id = self._obtener_cita_seleccionada_id()
        if cita_id is None:
            return
        try:
            if not messagebox.askyesno("Confirmar", "¿Marcar esta cita como Completada?"):
                return
            self._controller.completar_cita(cita_id)
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------ #
    #  Cancelar
    # ------------------------------------------------------------------ #
    def _solicitar_cancelacion(self) -> None:
        cita_id = self._obtener_cita_seleccionada_id()
        if cita_id is None:
            return

        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Cancelación de Cita")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("350x200")

        tk.Label(modal, text="Motivo de Cancelación (Mín. 5 caracteres):").pack(pady=10)
        txt_motivo = ttk.Entry(modal, width=40)
        txt_motivo.pack(pady=10)

        def confirmar() -> None:
            try:
                self._controller.cancelar_cita(cita_id, txt_motivo.get().strip())
                modal.destroy()
                self._refrescar()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(modal, text="Confirmar", bg="#166534", fg=COLORS['white'],
                  command=confirmar).pack(pady=10)
