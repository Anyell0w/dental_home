import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from utils.theme import COLORS, FONTS
from config import PATHS
from controllers.historial_controller import HistorialController
from controllers.receta_controller import RecetaController
from dao.gestor_paciente import GestorPaciente
from dao.gestor_cita import GestorCita
from dao.gestor_usuario import GestorUsuario
from odontograma import OdontogramaWidget

class HistorialView:
    """Módulo médico exclusivo para el control patológico del paciente."""

    def __init__(
        self,
        contenedor: tk.Frame,
        controller: HistorialController,
        gestor_paciente: GestorPaciente,
        gestor_cita: GestorCita,
        doctor_id: int,
        ctrl_receta: RecetaController,
        gestor_usuario: GestorUsuario,
    ) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: HistorialController = controller
        self._gestor_paciente: GestorPaciente = gestor_paciente
        self._gestor_cita: GestorCita = gestor_cita
        self._gestor_usuario: GestorUsuario = gestor_usuario
        self._ctrl_receta: RecetaController = ctrl_receta
        self._doctor_id: int = doctor_id
        self.paciente_id_actual = None
        self.historial_id_actual = None

    def _configurar_estilos_tabla(self) -> None:
        """Fuerza texto oscuro legible en las tablas para evitar bajo contraste."""
        estilo = ttk.Style()
        estilo.configure(
            "Historial.Treeview",
            background=COLORS["white"],
            foreground=COLORS["dark"],
            fieldbackground=COLORS["white"],
            rowheight=42,
            font=("Segoe UI", 10),
        )
        estilo.configure(
            "Historial.Treeview.Heading",
            background=COLORS["primary"],
            foreground=COLORS["white"],
            font=("Segoe UI", 10, "bold"),
        )
        estilo.map(
            "Historial.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", COLORS["white"])],
        )
        # Texto oscuro también en los campos de entrada del módulo
        estilo.configure("TEntry", foreground=COLORS["dark"], fieldbackground=COLORS["white"])
        estilo.configure("TCombobox", foreground=COLORS["dark"], fieldbackground=COLORS["white"])

        # ==========================
        # ESTILO DE PESTAÑAS
        # ==========================

        estilo.configure(
            "Historial.TNotebook",
            background=COLORS["background"],
            borderwidth=0
        )

        estilo.configure(
            "Historial.TNotebook.Tab",
            background="#E8F5EE",
            foreground=COLORS["dark"],
            padding=[20, 10],
            font=("Segoe UI", 11, "bold")
        )

        estilo.map(
            "Historial.TNotebook.Tab",
            background=[
                ("selected", COLORS["primary"])
            ],
            foreground=[
                ("selected", "white")
            ]
        )


    def _crear_boton(
        self,
        parent,
        texto,
        comando,
        color=None
    ):
        if color is None:
            color = COLORS["primary"]

        boton = tk.Button(
            parent,
            text=texto,
            command=comando,
            font=FONTS["body"],
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2"
        )

        return boton



    def inicializar(self) -> None:

        
        for widget in self._contenedor.winfo_children():
            widget.destroy()

        self._configurar_estilos_tabla()


        def _crear_boton(
            self,
            parent,
            texto,
            comando,
            color=None
        ):
            if color is None:
                color = COLORS["primary"]

            boton = tk.Button(
                parent,
                text=texto,
                command=comando,
                font=FONTS["body"],
                bg=color,
                fg="white",
                activebackground=color,
                activeforeground="white",
                highlightthickness=0,
                borderwidth=0,
                relief="flat",
                padx=15,
                pady=8,
                cursor="hand2"
            )

            return boton
        # ==========================
        # CONTENEDOR CON SCROLL
        # ==========================
        canvas = tk.Canvas(
            self._contenedor,
            bg=COLORS["background"],
            highlightthickness=0
        )

        scroll = ttk.Scrollbar(
            self._contenedor,
            orient="vertical",
            command=canvas.yview
        )

        canvas.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        contenido = tk.Frame(canvas, bg=COLORS["background"])

        canvas.create_window((0, 0), window=contenido, anchor="nw")

        contenido.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(
                canvas.find_all()[0],
                width=e.width
            )
        )

        self._contenedor_scroll = contenido

        barra = tk.Frame(self._contenedor_scroll, bg=COLORS["background"], pady=15, padx=15)
        barra.pack(fill=tk.X)

        tk.Label(
            barra, text="Buscar paciente", font=FONTS["subtitle"], bg=COLORS["background"]
        ).pack()

        self.txt_busqueda = ttk.Entry(barra, font=("Arial", 14), width=45)
        self.txt_busqueda.pack(pady=10)

        tk.Button(
            barra,
            text="🔍 Buscar",
            font=FONTS["body"],
            bg=COLORS["primary"],
            fg="white",
            command=self._buscar_paciente,
        ).pack()

        self._crear_boton(
            barra,
            "📖 Ver Historial",
            self._cargar_historial
        ).pack(side=tk.LEFT, padx=5)

        self.frame_ficha = tk.Frame(
            self._contenedor_scroll, bg=COLORS["white"], padx=15, pady=15
        )
        self.frame_ficha.pack(fill=tk.X, padx=25, pady=10)
        self.lbl_info = tk.Label(
            self.frame_ficha,
            text="Ningún paciente cargado en memoria.",
            font=FONTS["body"],
            bg=COLORS["white"],
        )
        self.lbl_info.pack(anchor="w")

        self.tabs = ttk.Notebook(
            self._contenedor_scroll,
            style="Historial.TNotebook"
        )
        self.tabs.pack(fill=tk.BOTH, expand=True, padx=25, pady=10)

        self.tab_registros = tk.Frame(self.tabs)
        self.tab_observaciones = tk.Frame(self.tabs)
        self.tab_citas = tk.Frame(self.tabs)

        self.tabs.add(self.tab_registros, text="Registros Clínicos")
        self.tabs.add(self.tab_observaciones, text="Observaciones Generales")
        self.tabs.add(self.tab_citas, text="Citas del paciente")

        frame_tabla = tk.Frame(self.tab_registros)
        frame_tabla.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        columnas = ("Fecha", "Diagnóstico", "Tratamiento", "Doctor", "Receta")
        self.tabla = ttk.Treeview(
            frame_tabla, columns=columnas, show="headings", selectmode="browse",
            style="Historial.Treeview",
        )
        anchos = {
            "Fecha": 100,
            "Diagnóstico": 180,
            "Tratamiento": 180,
            "Doctor": 120,
            "Receta": 90,
        }
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos.get(col, 140), anchor="center")
        self.tabla.pack(fill=tk.BOTH, expand=True)

        frame_acc_reg = tk.Frame(self.tab_registros, bg=COLORS.get("background", "#F5F5F5"))
        frame_acc_reg.pack(fill=tk.X, padx=15, pady=8)

        tk.Button(
            frame_acc_reg,
            text="💊 Emitir / Ver receta",
            font=FONTS["body"],
            bg="#166534",
            fg="white",
            command=self._emitir_o_ver_receta_seleccionada,
        ).pack(side=tk.LEFT, padx=5)

        self._construir_tab_observaciones()
        self._construir_tab_citas()

        
    def _construir_tab_observaciones(self) -> None:

        # =========================
        # Título
        # =========================
        tk.Label(
            self.tab_observaciones,
            text="Odontograma y observaciones del paciente",
            font=FONTS["title"],
            fg=COLORS["primary"],
            bg=COLORS["background"],
        ).pack(anchor="w", padx=20, pady=(15, 10))

        # =========================
        # Contenedor principal
        # =========================
        contenedor = tk.Frame(
            self.tab_observaciones,
            bg=COLORS["background"]
        )
        contenedor.pack(fill=tk.BOTH, expand=True, padx=20)

        # =========================
        # ODONTOGRAMA INTERACTIVO
        # =========================
        frame_odontograma = tk.Frame(
            contenedor,
            bg="white",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        frame_odontograma.pack(fill=tk.X, pady=(0, 15))

        cab_odontograma = tk.Frame(frame_odontograma, bg=COLORS["primary"])
        cab_odontograma.pack(fill=tk.X)
        tk.Label(
            cab_odontograma,
            text="🦷  Odontograma del paciente",
            font=FONTS["subtitle"],
            fg="white",
            bg=COLORS["primary"],
        ).pack(anchor="w", padx=14, pady=8)

        self.odontograma_widget = OdontogramaWidget(
            frame_odontograma,
            bg="white",
            accent=COLORS["primary"],
            accent_soft=COLORS["success"],
        )
        self.odontograma_widget.pack(fill=tk.X, padx=12, pady=10)

        # Notas / descripción clínica del odontograma
        tk.Label(
            frame_odontograma,
            text="Notas del odontograma:",
            font=FONTS["body"],
            bg="white",
        ).pack(anchor="w", padx=12, pady=(6, 2))

        self.txt_desc_odontograma = tk.Text(
            frame_odontograma,
            height=3,
            bg=COLORS["white"],
            fg=COLORS["dark"],
            relief="solid",
            bd=1,
        )
        self.txt_desc_odontograma.pack(fill=tk.X, padx=12, pady=(0, 8))

        acc_odontograma = tk.Frame(frame_odontograma, bg="white")
        acc_odontograma.pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Button(
            acc_odontograma,
            text="💾 Guardar odontograma",
            bg=COLORS["primary"],
            fg="white",
            activebackground=COLORS["secondary"],
            activeforeground="white",
            font=FONTS["body"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._guardar_odontograma,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            acc_odontograma,
            text="🖼️ Exportar PNG/PDF",
            bg=COLORS["secondary"],
            fg="white",
            activebackground=COLORS["primary"],
            activeforeground="white",
            font=FONTS["body"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._exportar_odontograma,
        ).pack(side=tk.LEFT, padx=8)

        tk.Button(
            acc_odontograma,
            text="🧹 Limpiar",
            bg="#90A4AE",
            fg="white",
            activebackground="#78909C",
            activeforeground="white",
            font=FONTS["body"],
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._limpiar_odontograma,
        ).pack(side=tk.LEFT, padx=8)

        # =========================
        # OBSERVACIONES
        # =========================
        frame_obs = tk.Frame(
            contenedor,
            bg=COLORS["background"]
        )
        frame_obs.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            frame_obs,
            text="Historial de observaciones registradas:",
            font=FONTS["subtitle"],
        ).pack(anchor="w")

        self.txt_observaciones = tk.Text(
            frame_obs,
            height=15,
            state=tk.DISABLED,
            bg=COLORS["white"],
            fg=COLORS["dark"],
            relief="solid",
            bd=1
        )
        self.txt_observaciones.pack(fill=tk.BOTH, expand=True, pady=(5,10))

        # =========================
        # NUEVA OBSERVACIÓN
        # =========================
        tk.Label(
            frame_obs,
            text="Agregar nueva observación:",
            font=FONTS["subtitle"],
        ).pack(anchor="w")

        fila_obs = tk.Frame(frame_obs, bg=COLORS["background"])
        fila_obs.pack(fill=tk.X, pady=5)

        self.ent_nueva_obs = ttk.Entry(
            fila_obs,
            font=FONTS["body"]
        )
        self.ent_nueva_obs.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            fila_obs,
            text="💾 Guardar observación",
            
            command=self._guardar_observacion,
        ).pack(side=tk.LEFT, padx=8)

   

    def _construir_tab_citas(self) -> None:
        frame = tk.Frame(self.tab_citas)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        columnas = ("Fecha", "Hora", "Doctor", "Estado", "Motivo cancelación")
        self.tabla_citas = ttk.Treeview(
            frame, columns=columnas, show="headings", selectmode="browse",
            style="Historial.Treeview",
        )
        anchos = {
            "Fecha": 100,
            "Hora": 80,
            "Doctor": 140,
            "Estado": 110,
            "Motivo cancelación": 200,
        }
        for col in columnas:
            self.tabla_citas.heading(col, text=col)
            self.tabla_citas.column(col, width=anchos.get(col, 120), anchor="center")

        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tabla_citas.yview)
        self.tabla_citas.configure(yscrollcommand=scroll.set)
        self.tabla_citas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _buscar_paciente(self) -> None:
        texto = self.txt_busqueda.get().strip()
        if not texto:
            return

        pacientes = self._gestor_paciente.buscar(texto)
        if not pacientes:
            messagebox.showinfo("Búsqueda", "No se encontró ningún paciente")
            return

        paciente = pacientes[0]
        self.paciente_id_actual = paciente.id
        self._mostrar_ficha(paciente)
        self._cargar_historial()

    def _mostrar_ficha(self, pac) -> None:
        for widget in self.frame_ficha.winfo_children():
            widget.destroy()

        self._paciente_nombre_actual = pac.obtener_nombre_completo()

        frame_info = tk.Frame(self.frame_ficha, bg=COLORS["white"])
        frame_info.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            frame_info,
            text=f"(RA) {pac.obtener_nombre_completo()}",
            font=("Arial", 18, "bold"),
            bg=COLORS["white"],
        ).pack(anchor="w")

        tk.Label(
            frame_info,
            text=f"DNI {pac.dni} · {pac.calcular_edad()} años · Paciente #{pac.id}",
            font=FONTS["body"],
            bg=COLORS["white"],
        ).pack(anchor="w", pady=5)

        botones = tk.Frame(self.frame_ficha, bg=COLORS["white"])
        botones.pack(side=tk.RIGHT)

        tk.Button(
            botones,
            text="Ver recetas",
            bg=COLORS["primary"],
            fg="white",
            font=FONTS["body"],
            command=self._abrir_lista_recetas,
        ).pack(side=tk.LEFT, padx=5)

        self._crear_boton(
            botones,
            "+ Nuevo registro",
            self._abrir_formulario_registro_clinico,
            "#F4C542"
        ).pack(side=tk.LEFT, padx=5)

    def _cargar_historial(self) -> None:
        if not self.paciente_id_actual:
            messagebox.showwarning(
                "Historial", "Primero debe buscar y seleccionar un paciente."
            )
            return

        hist = self._controller.obtener_historial(self.paciente_id_actual)
        if not hist:
            messagebox.showinfo(
                "Historial",
                "El paciente no tiene historial clínico."
            )
            self.historial_id_actual = None
            return

        self.tabla.delete(*self.tabla.get_children())

        self.historial_id_actual = hist.id
        self.odontograma_widget.cargar_estado(hist.odontogramaEstado)
        self.txt_desc_odontograma.delete("1.0", tk.END)
        if hist.descripcionOdontograma:
            self.txt_desc_odontograma.insert("1.0", hist.descripcionOdontograma)
        registros = self._controller.listar_registros(hist.id)
        for r in registros:
            doctor = self._gestor_usuario.buscar_por_id(r.doctorId)
            nombre_doctor = f"Dr. {doctor.nombreUsuario}" if doctor else "—"
            receta = self._ctrl_receta.obtener_por_registro(r.id)
            estado_receta = "Emitida" if receta else "Sin receta"
            self.tabla.insert(
                "",
                tk.END,
                iid=str(r.id),
                values=(
                    r.fechaConsulta,
                    r.diagnostico,
                    r.tratamiento,
                    nombre_doctor,
                    estado_receta,
                ),
            )

        self._poblar_observaciones(hist)
        self._poblar_citas()

    def _poblar_observaciones(self, hist) -> None:
        texto = (hist.observaciones or "").strip() or "Sin observaciones registradas."
        self.txt_observaciones.configure(state=tk.NORMAL)
        self.txt_observaciones.delete("1.0", tk.END)
        self.txt_observaciones.insert("1.0", texto)
        self.txt_observaciones.configure(state=tk.DISABLED)

    def _poblar_citas(self) -> None:
        self.tabla_citas.delete(*self.tabla_citas.get_children())
        citas = self._controller.listar_citas_paciente(self.paciente_id_actual)
        for c in citas:
            doctor = self._gestor_usuario.buscar_por_id(c.doctorId)
            nombre_doctor = f"Dr. {doctor.nombreUsuario}" if doctor else "—"
            self.tabla_citas.insert(
                "",
                tk.END,
                iid=str(c.id),
                values=(
                    c.fecha,
                    c.hora,
                    nombre_doctor,
                    c.estado,
                    c.motivoCancelacion or "—",
                ),
            )

    def _guardar_observacion(self) -> None:
        if not getattr(self, "historial_id_actual", None):
            messagebox.showwarning(
                "Observaciones", "Primero cargue el historial de un paciente."
            )
            return
        texto = self.ent_nueva_obs.get().strip()
        if not texto:
            messagebox.showwarning("Observaciones", "Escriba una observación.")
            return
        try:
            self._controller.agregar_observacion_historial(self.historial_id_actual, texto)
            self.ent_nueva_obs.delete(0, tk.END)
            hist = self._controller.obtener_historial(self.paciente_id_actual)
            self._poblar_observaciones(hist)
            messagebox.showinfo("Observaciones", "Observación guardada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _abrir_formulario_registro_clinico(self) -> None:
        if not self.paciente_id_actual:
            messagebox.showwarning("Registro", "Primero debe buscar un paciente.")
            return

        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Nueva Ficha de Consulta")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("450x400")

        citas = self._gestor_cita.listar_por_paciente(self.paciente_id_actual)
        citas_pendientes = [c for c in citas if c.is_pendiente()]
        dict_citas = {
            f"Cita ID: {c.id} - Fecha: {c.fecha} Horario: {c.hora}": c.id
            for c in citas_pendientes
        }

        if not citas_pendientes:
            messagebox.showinfo(
                "Información",
                "El paciente no tiene citas agendadas pendientes para atender.",
                parent=modal,
            )
            modal.destroy()
            return
        

        tk.Label(modal, text="Vincular Cita Pendiente:").pack(anchor="w", padx=20, pady=5)
        cb_cit = ttk.Combobox(modal, values=list(dict_citas.keys()), state="readonly")
        cb_cit.pack(fill=tk.X, padx=20)

        tk.Label(modal, text="Diagnóstico Odontológico:").pack(anchor="w", padx=20, pady=5)
        ent_diag = ttk.Entry(modal)
        ent_diag.pack(fill=tk.X, padx=20)

        tk.Label(modal, text="Plan de Tratamiento Ejecutado:").pack(
            anchor="w", padx=20, pady=5
        )
        ent_trat = ttk.Entry(modal)
        ent_trat.pack(fill=tk.X, padx=20)

        tk.Label(modal, text="Observaciones de Consulta:").pack(anchor="w", padx=20, pady=5)
        ent_obs = ttk.Entry(modal)
        ent_obs.pack(fill=tk.X, padx=20)

        def registrar() -> None:
            try:
                c_sel = cb_cit.get()
                if not c_sel:
                    raise ValueError("Debe seleccionar una cita obligatoriamente.")
                registro = self._controller.crear_registro_clinico(
                    dict_citas[c_sel],
                    self._doctor_id,
                    ent_diag.get().strip(),
                    ent_trat.get().strip(),
                    ent_obs.get().strip(),
                )
                modal.destroy()
                self._cargar_historial()
                if messagebox.askyesno(
                    "Receta",
                    "Registro guardado. ¿Desea emitir una receta ahora?",
                ):
                    self._abrir_formulario_receta(registro.id)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(
            modal,
            text="Guardar Registro",
            bg="#166534",
            fg=COLORS["white"],
            command=registrar,
        ).pack(pady=20)

    def _emitir_o_ver_receta_seleccionada(self) -> None:
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Receta", "Seleccione un registro clínico de la tabla.")
            return
        registro_id = int(seleccion[0])
        receta = self._ctrl_receta.obtener_por_registro(registro_id)
        if receta:
            self._mostrar_detalle_receta(receta)
        else:
            self._abrir_formulario_receta(registro_id)

    def _abrir_formulario_receta(self, registro_id: int) -> None:
        if not self.paciente_id_actual:
            return

        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Emitir Receta Médica")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("520x480")

        medicamentos_temp = []

        tk.Label(modal, text="Indicaciones generales:", font=FONTS["body"]).pack(
            anchor="w", padx=20, pady=(15, 5)
        )
        ent_ind = ttk.Entry(modal)
        ent_ind.pack(fill=tk.X, padx=20)

        frame_med = tk.LabelFrame(modal, text="Medicamentos", padx=10, pady=10)
        frame_med.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        fila = tk.Frame(frame_med)
        fila.pack(fill=tk.X, pady=5)
        tk.Label(fila, text="Nombre", width=14).pack(side=tk.LEFT)
        ent_nombre = ttk.Entry(fila, width=18)
        ent_nombre.pack(side=tk.LEFT, padx=3)
        tk.Label(fila, text="Cant.").pack(side=tk.LEFT)
        ent_cant = ttk.Entry(fila, width=6)
        ent_cant.pack(side=tk.LEFT, padx=3)
        tk.Label(fila, text="Indicaciones").pack(side=tk.LEFT)
        ent_med_ind = ttk.Entry(fila, width=20)
        ent_med_ind.pack(side=tk.LEFT, padx=3)

        lista = ttk.Treeview(
            frame_med,
            columns=("Nombre", "Cantidad", "Indicaciones"),
            show="headings",
            height=6,
            style="Historial.Treeview",
        )
        for col in ("Nombre", "Cantidad", "Indicaciones"):
            lista.heading(col, text=col)
            lista.column(col, width=140, anchor="center")
        lista.pack(fill=tk.BOTH, expand=True, pady=8)

        def agregar_med() -> None:
            nombre = ent_nombre.get().strip()
            cant_txt = ent_cant.get().strip()
            indic = ent_med_ind.get().strip()
            try:
                cantidad = float(cant_txt)
            except ValueError:
                messagebox.showerror("Error", "La cantidad debe ser numérica.", parent=modal)
                return
            if not nombre or cantidad <= 0 or not indic:
                messagebox.showerror(
                    "Error",
                    "Complete nombre, cantidad (>0) e indicaciones.",
                    parent=modal,
                )
                return
            medicamentos_temp.append(
                {"nombre": nombre, "cantidad": cantidad, "indicaciones": indic}
            )
            lista.insert("", tk.END, values=(nombre, cantidad, indic))
            ent_nombre.delete(0, tk.END)
            ent_cant.delete(0, tk.END)
            ent_med_ind.delete(0, tk.END)

        tk.Button(
            frame_med,
            text="+ Agregar medicamento",
            bg=COLORS["primary"],
            fg="white",
            command=agregar_med,
        ).pack(anchor="e")

        def guardar() -> None:
            try:
                receta = self._ctrl_receta.generar_receta(
                    registro_id,
                    self.paciente_id_actual,
                    self._doctor_id,
                    ent_ind.get().strip(),
                    medicamentos_temp,
                )
                modal.destroy()
                self._cargar_historial()
                messagebox.showinfo(
                    "Receta emitida",
                    f"Receta REC-{receta.id} generada.\nPDF: {receta.archivoPDF}",
                )
                self._abrir_pdf(receta.archivoPDF)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(
            modal,
            text="Guardar y generar PDF",
            bg="#166534",
            fg="white",
            command=guardar,
        ).pack(pady=12)

    def _abrir_lista_recetas(self) -> None:
        if not self.paciente_id_actual:
            messagebox.showwarning("Recetas", "Primero debe buscar un paciente.")
            return

        recetas = self._ctrl_receta.listar_recetas_por_paciente(self.paciente_id_actual)
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Recetas del paciente")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("560x320")

        tabla = ttk.Treeview(
            modal,
            columns=("ID", "Fecha", "Medicamentos", "PDF"),
            show="headings",
            selectmode="browse",
            style="Historial.Treeview",
        )
        for col, w in (("ID", 60), ("Fecha", 100), ("Medicamentos", 120), ("PDF", 220)):
            tabla.heading(col, text=col)
            tabla.column(col, width=w, anchor="center")
        tabla.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        for r in recetas:
            tabla.insert(
                "",
                tk.END,
                iid=str(r.id),
                values=(
                    f"REC-{r.id}",
                    r.fecha,
                    len(r.obtener_medicamentos()),
                    os.path.basename(r.archivoPDF) if r.archivoPDF else "—",
                ),
            )

        if not recetas:
            tk.Label(modal, text="Este paciente no tiene recetas emitidas.").pack(pady=5)

        def abrir_seleccionada() -> None:
            sel = tabla.selection()
            if not sel:
                messagebox.showwarning("Receta", "Seleccione una receta.", parent=modal)
                return
            receta = self._ctrl_receta.obtener_receta(int(sel[0]))
            if receta:
                self._mostrar_detalle_receta(receta)

        tk.Button(
            modal,
            text="Abrir PDF / Detalle",
            bg=COLORS["primary"],
            fg="white",
            command=abrir_seleccionada,
        ).pack(pady=10)

    def _mostrar_detalle_receta(self, receta) -> None:
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title(f"Receta REC-{receta.id}")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("480x360")

        tk.Label(
            modal, text=f"Receta REC-{receta.id} — {receta.fecha}", font=FONTS["subtitle"]
        ).pack(pady=10)

        if receta.indicacionesGenerales:
            tk.Label(
                modal,
                text=f"Indicaciones: {receta.indicacionesGenerales}",
                wraplength=420,
                justify="left",
            ).pack(anchor="w", padx=20)

        lista = ttk.Treeview(
            modal,
            columns=("Nombre", "Cantidad", "Indicaciones"),
            show="headings",
            height=8,
            style="Historial.Treeview",
        )
        for col in ("Nombre", "Cantidad", "Indicaciones"):
            lista.heading(col, text=col)
            lista.column(col, width=140, anchor="center")
        lista.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        for m in receta.obtener_medicamentos():
            lista.insert("", tk.END, values=(m.nombre, m.cantidad, m.indicaciones))

        def abrir_pdf() -> None:
            ruta = receta.archivoPDF
            if not ruta or not os.path.isfile(ruta):
                try:
                    ruta = self._ctrl_receta.generar_pdf(receta.id)
                    self._cargar_historial()
                except Exception as e:
                    messagebox.showerror("PDF", str(e), parent=modal)
                    return
            self._abrir_pdf(ruta)

        tk.Button(
            modal, text="Abrir PDF", bg=COLORS["primary"], fg="white", command=abrir_pdf
        ).pack(pady=10)

    @staticmethod
    def _abrir_pdf(ruta: str) -> None:
        if not ruta or not os.path.isfile(ruta):
            messagebox.showwarning("PDF", "El archivo PDF no está disponible.")
            return
        try:
            os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("PDF", f"No se pudo abrir el archivo:\n{e}")

    def _guardar_odontograma(self) -> None:
        """Persiste el estado interactivo del odontograma del paciente en la BD
        y exporta automáticamente una imagen PNG dentro del sistema."""
        if not self.historial_id_actual:
            messagebox.showwarning(
                "Odontograma",
                "Primero debe cargar el historial de un paciente."
            )
            return

        estado_json = self.odontograma_widget.obtener_estado_json()
        descripcion = self.txt_desc_odontograma.get("1.0", tk.END).strip()

        # Exportar PNG del paciente dentro del sistema (si Pillow está disponible)
        imagen_path = ""
        try:
            os.makedirs(PATHS["odontogramas"], exist_ok=True)
            destino = os.path.join(
                PATHS["odontogramas"],
                f"paciente_{self.paciente_id_actual}.png"
            )
            self.odontograma_widget.exportar(
                destino,
                paciente=getattr(self, "_paciente_nombre_actual", ""),
                fecha=datetime.now().strftime("%d/%m/%Y"),
            )
            imagen_path = destino
        except ImportError:
            imagen_path = ""  # sin Pillow no hay PNG, pero el estado sí se guarda
        except Exception as e:
            imagen_path = ""
            print("Error exportando odontograma:", e)

        try:
            self._controller.guardar_odontograma_estado(
                self.historial_id_actual,
                estado_json,
                imagen_path,
                descripcion,
            )
            messagebox.showinfo(
                "Odontograma",
                "Odontograma guardado correctamente."
            )
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"No se pudo guardar el odontograma:\n{e}"
            )

    def _exportar_odontograma(self) -> None:
        """Exporta el odontograma actual a un archivo PNG o PDF elegido por el usuario."""
        if not self.historial_id_actual:
            messagebox.showwarning(
                "Odontograma",
                "Primero debe cargar el historial de un paciente."
            )
            return

        from tkinter import filedialog

        ruta = filedialog.asksaveasfilename(
            title="Exportar odontograma",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf")],
            initialfile=f"odontograma_paciente_{self.paciente_id_actual}.png",
        )
        if not ruta:
            return

        kind = "pdf" if ruta.lower().endswith(".pdf") else "png"
        try:
            self.odontograma_widget.exportar(
                ruta,
                paciente=getattr(self, "_paciente_nombre_actual", ""),
                fecha=datetime.now().strftime("%d/%m/%Y"),
                kind=kind,
            )
            messagebox.showinfo("Odontograma", f"Odontograma exportado en:\n{ruta}")
        except ImportError:
            messagebox.showerror(
                "Falta Pillow",
                "Para exportar necesitas instalar Pillow:\n\n    pip install Pillow"
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def _limpiar_odontograma(self) -> None:
        """Borra todas las marcas del odontograma en pantalla (no guarda hasta pulsar Guardar)."""
        if messagebox.askyesno(
            "Limpiar",
            "¿Borrar todas las marcas del odontograma?\n"
            "(El cambio no se guarda hasta pulsar «Guardar odontograma».)"
        ):
            self.odontograma_widget.limpiar()
