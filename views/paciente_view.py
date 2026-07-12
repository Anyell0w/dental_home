from datetime import datetime
import tkinter as tk
from tkcalendar import DateEntry
from tkinter import ttk, messagebox
from utils.theme import COLORS, FONTS
from controllers.paciente_controller import PacienteController


class PacienteView:
    """Módulo de presentación para administración clínica de Pacientes."""

    COL_EDITAR = "Editar"

    def __init__(self, contenedor: tk.Frame, controller: PacienteController, usuario_id: int) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: PacienteController = controller
        self._usuario_id: int = usuario_id

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def inicializar(self) -> None:
        for widget in self._contenedor.winfo_children():
            widget.destroy()

        self._configurar_estilos_formulario()
        self._construir_barra_busqueda()
        self._construir_tabla()

        self.cargar_lista_pacientes()

    def _configurar_estilos_formulario(self) -> None:
        """Garantiza texto oscuro legible en los campos de entrada de los modales."""
        estilo = ttk.Style()
        estilo.configure("TEntry", foreground=COLORS['dark'], fieldbackground=COLORS['white'])
        estilo.configure("TCombobox", foreground=COLORS['dark'], fieldbackground=COLORS['white'])

    def _crear_label_modal(self, modal: tk.Toplevel, texto: str) -> None:
        tk.Label(
            modal, text=texto, bg=COLORS['white'], fg=COLORS['dark'],
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=20, pady=2)

    def _construir_barra_busqueda(self) -> None:
        barra_busqueda = tk.Frame(self._contenedor, bg=COLORS['background'], pady=20)
        barra_busqueda.pack(fill=tk.X)

        tk.Label(
            barra_busqueda, text="Búsqueda Nombre o DNI", font=FONTS['subtitle'],
            bg=COLORS['background'], fg=COLORS['dark']
        ).pack(pady=(0, 8))

        contenedor_busqueda = tk.Frame(barra_busqueda, bg=COLORS['background'])
        contenedor_busqueda.pack()

        self.txt_busqueda = ttk.Entry(contenedor_busqueda, font=("Segoe UI", 14), width=45)
        self.txt_busqueda.pack(side=tk.LEFT, ipady=8, padx=10)
        self.txt_busqueda.bind("<Return>", lambda e: self._accion_buscar())

        tk.Button(
            contenedor_busqueda, text="🔍 Buscar", font=FONTS['body'],
            bg=COLORS['primary'], fg=COLORS['white'], width=12,
            command=self._accion_buscar
        ).pack(side=tk.LEFT, padx=5)

        # Filtro de estado: permite ver solo Activos, solo Inactivos o Todos
        tk.Label(
            contenedor_busqueda, text="Estado:", font=FONTS['body'],
            bg=COLORS['background'], fg=COLORS['dark']
        ).pack(side=tk.LEFT, padx=(20, 5))

        self.cb_filtro_estado = ttk.Combobox(
            contenedor_busqueda, values=["Activos", "Inactivos", "Todos"],
            state="readonly", width=10
        )
        self.cb_filtro_estado.current(0)
        self.cb_filtro_estado.pack(side=tk.LEFT)
        self.cb_filtro_estado.bind("<<ComboboxSelected>>", lambda e: self._accion_buscar())

        tk.Button(
            barra_busqueda, text="➕ Nuevo Paciente", 
            command=self._abrir_formulario_registro,
            bg="#0D5D32",
            fg="white",
            activebackground="#2F994A",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=30)

    def _construir_tabla(self) -> None:
        frame_tabla = tk.Frame(self._contenedor, bg="white", bd=0)
        frame_tabla.pack(fill=tk.BOTH, expand=True, padx=30, pady=15)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Paciente.Treeview", background="#FFFFFF", foreground="#333333",
            rowheight=42, fieldbackground="#FFFFFF", font=("Segoe UI", 11), borderwidth=0
        )
        style.configure(
            "Paciente.Treeview.Heading", background=COLORS['primary'],
            foreground="white", font=("Segoe UI", 11, "bold"), relief="flat"
        )
        style.map(
            "Paciente.Treeview",
            background=[("selected", "#0c9351")],
            foreground=[("selected", "white")]
        )

        # Columnas según el diseño: Paciente, DNI, Teléfono, Sexo, Edad, Estado, Editar
        columnas = ("Paciente", "DNI", "Teléfono", "Sexo", "Edad", "Estado", self.COL_EDITAR)

        self.tabla = ttk.Treeview(
            frame_tabla, columns=columnas, show='headings',
            selectmode="browse", style="Paciente.Treeview"
        )

        config_columnas = {
            "Paciente": 240,
            "DNI": 110,
            "Teléfono": 130,
            "Sexo": 60,
            "Edad": 60,
            "Estado": 100,
            self.COL_EDITAR: 70,
        }

        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=config_columnas[col], anchor="center")

        scrollbar = ttk.Scrollbar(frame_tabla, orient=tk.VERTICAL, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)

        self.tabla.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tabla.tag_configure("par", background="#F7F9F8")
        self.tabla.tag_configure("impar", background="#FFFFFF")
        self.tabla.tag_configure("inactivo", foreground="#B0B0B0")

        # El botón de editar vive dentro de la fila; se detecta el clic
        # sobre esa columna en lugar de tener un botón separado abajo.
        self.tabla.bind("<Button-1>", self._on_click_tabla)

        # Panel inferior: se conserva la acción de dar de baja
        frame_acciones = tk.Frame(self._contenedor, bg=COLORS['background'], pady=10)
        frame_acciones.pack(fill=tk.X, padx=15)

        tk.Button(
            frame_acciones,
            text="Dar de Baja",
            command=self._solicitar_baja,
            bg="#D42929",          # Rojo
            fg="white",            # Texto blanco
            activebackground="#860303",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------------
    # Carga y filtrado de datos
    # ------------------------------------------------------------------
    def cargar_lista_pacientes(self) -> None:
        """Puebla la tabla respetando el filtro de estado seleccionado."""
        filtro = getattr(self, "cb_filtro_estado", None)
        valor_filtro = filtro.get() if filtro else "Activos"

        if valor_filtro == "Todos":
            pacientes = self._controller.listar_pacientes(solo_activos=False)
        elif valor_filtro == "Inactivos":
            pacientes = [p for p in self._controller.listar_pacientes(solo_activos=False) if not p.estado]
        else:  # Activos
            pacientes = self._controller.listar_pacientes(solo_activos=True)

        self._pintar_tabla(pacientes)

    def _pintar_tabla(self, pacientes) -> None:
        self.tabla.delete(*self.tabla.get_children())
        for i, p in enumerate(pacientes):
            try:
                edad = p.calcular_edad()
            except ValueError:
                edad = "—"
            est = "Activo" if p.estado else "Inactivo"
            fila_tag = "par" if i % 2 == 0 else "impar"
            tags = (fila_tag,) if p.estado else (fila_tag, "inactivo")
            self.tabla.insert(
                '', tk.END, iid=str(p.id), tags=tags,
                values=(p.obtener_nombre_completo(), p.dni, p.telefono, p.sexo, edad, est, "✏️")
            )

    def _accion_buscar(self) -> None:
        term = self.txt_busqueda.get().strip()
        if not term:
            self.cargar_lista_pacientes()
            return

        resultados = self._controller.buscar_paciente(term)

        filtro = self.cb_filtro_estado.get()
        if filtro == "Activos":
            resultados = [p for p in resultados if p.estado]
        elif filtro == "Inactivos":
            resultados = [p for p in resultados if not p.estado]

        self._pintar_tabla(resultados)

    # ------------------------------------------------------------------
    # Interacción con la tabla (botón editar embebido en la fila)
    # ------------------------------------------------------------------
    def _on_click_tabla(self, event: tk.Event) -> None:
        region = self.tabla.identify("region", event.x, event.y)
        if region != "cell":
            return

        fila_id = self.tabla.identify_row(event.y)
        columna_id = self.tabla.identify_column(event.x)
        if not fila_id:
            return

        indice_columna = int(columna_id.replace("#", "")) - 1
        columnas = self.tabla["columns"]
        if 0 <= indice_columna < len(columnas) and columnas[indice_columna] == self.COL_EDITAR:
            self._abrir_formulario_edicion(int(fila_id))
        else:
            self.tabla.selection_set(fila_id)

    # ------------------------------------------------------------------
    # Formulario de registro
    # ------------------------------------------------------------------
    def _abrir_formulario_registro(self) -> None:
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Registro de Paciente")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.configure(bg=COLORS['white'])

        sw, sh = modal.winfo_screenwidth(), modal.winfo_screenheight()
        modal.geometry(f"400x480+{(sw-400)//2}+{(sh-480)//2}")

        self._crear_label_modal(modal, "Nombre:")
        ent_nom = ttk.Entry(modal)
        ent_nom.pack(fill=tk.X, padx=20)

        self._crear_label_modal(modal, "Apellido:")
        ent_ape = ttk.Entry(modal)
        ent_ape.pack(fill=tk.X, padx=20)

        self._crear_label_modal(modal, "DNI:")
        ent_dni = ttk.Entry(modal)
        ent_dni.pack(fill=tk.X, padx=20)

        self._crear_label_modal(modal, "Teléfono:")
        ent_tel = ttk.Entry(modal)
        ent_tel.pack(fill=tk.X, padx=20)

        self._crear_label_modal(modal, "Sexo (M/F):")
        cb_sexo = ttk.Combobox(modal, values=["M", "F"], state="readonly")
        cb_sexo.pack(fill=tk.X, padx=20)

        self._crear_label_modal(modal, "Fecha de Nacimiento:")

        ent_fn = ttk.Entry(modal)
        ent_fn.pack(fill=tk.X, padx=20)

        self._crear_label_modal(modal, "Dirección:")
        ent_dir = ttk.Entry(modal)
        ent_dir.pack(fill=tk.X, padx=20)

        PLACEHOLDER_FECHA = "DD/MM/AAAA"

        def poner_placeholder_fecha():
            ent_fn.insert(0, PLACEHOLDER_FECHA)
            ent_fn.config(foreground="gray")

        def quitar_placeholder_fecha(event=None):
            if ent_fn.get() == PLACEHOLDER_FECHA:
                ent_fn.delete(0, tk.END)
                ent_fn.config(foreground="black")

        def restaurar_placeholder_fecha(event=None):
            if not ent_fn.get():
                poner_placeholder_fecha()

        def formatear_fecha(event=None):
            texto = ent_fn.get()

            # No formatear si todavía está el placeholder
            if texto == PLACEHOLDER_FECHA:
                return

            # Solo números, máximo 8 dígitos
            numeros = "".join(c for c in texto if c.isdigit())[:8]

            resultado = numeros[:2]
            if len(numeros) > 2:
                resultado += "/" + numeros[2:4]
            if len(numeros) > 4:
                resultado += "/" + numeros[4:]

            # Evita bucle infinito de KeyRelease si no cambió nada
            if resultado != texto:
                pos = ent_fn.index(tk.INSERT)
                ent_fn.delete(0, tk.END)
                ent_fn.insert(0, resultado)
                # Reubica el cursor al final (o donde corresponda)
                nueva_pos = min(pos + (len(resultado) - len(texto)), len(resultado))
                ent_fn.icursor(max(nueva_pos, 0))

        ent_fn.bind("<FocusIn>", quitar_placeholder_fecha)
        ent_fn.bind("<FocusOut>", restaurar_placeholder_fecha)
        ent_fn.bind("<KeyRelease>", formatear_fecha)
        poner_placeholder_fecha()


        def salvar() -> None:
            nombre = ent_nom.get().strip()
            apellido = ent_ape.get().strip()
            dni = ent_dni.get().strip()
            telefono = ent_tel.get().strip()
            sexo = cb_sexo.get().strip()
            f_nac = ent_fn.get().strip()
            direccion = ent_dir.get().strip()

            if not all([nombre, apellido, dni, telefono, sexo, f_nac, direccion]):
                messagebox.showerror("Datos incompletos", "Todos los campos son obligatorios.", parent=modal)
                return

            try:
                datetime.strptime(f_nac, "%d/%m/%Y")
            except ValueError:
                messagebox.showerror(
                    "Fecha inválida", "La fecha de nacimiento debe tener el formato DD/MM/AAAA.", parent=modal
                )
                return

            try:
                self._controller.registrar_paciente(
                    nombre, apellido, dni, telefono, sexo, f_nac, direccion, self._usuario_id
                )
                self.cargar_lista_pacientes()
                modal.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        tk.Button(
            modal, text="Guardar",command=salvar,
            bg="#0D6C30",
            fg="white",
            activebackground="#36905E",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=40, pady=20)
        tk.Button(
            modal, text="Cancelar",command=modal.destroy,
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
        ).pack(side=tk.RIGHT, padx=40, pady=20)

        modal.bind("<Return>", lambda e: salvar())
        modal.bind("<Escape>", lambda e: modal.destroy())

    # ------------------------------------------------------------------
    # Formulario de edición de nombre , apellido, dni, telefono,sexo, fecha de nacimiento, direccion 
    
 # Formulario de edición de nombre , apellido, dni, telefono,sexo, fecha de nacimiento, direccion 
    # ------------------------------------------------------------------
    def _abrir_formulario_edicion(self, pac_id: int) -> None:
        paciente = self._controller.buscar_por_id(pac_id)
        if not paciente:
            messagebox.showerror("Error", "El paciente seleccionado ya no existe.")
            self.cargar_lista_pacientes()
            return
 
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Editar Paciente")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.configure(bg=COLORS['white'])
 
        sw, sh = modal.winfo_screenwidth(), modal.winfo_screenheight()
        modal.geometry(f"400x400+{(sw-400)//2}+{(sh-400)//2}")
 
        self._crear_label_modal(modal, "Nombre:")
        ent_nom = ttk.Entry(modal)
        ent_nom.insert(0, paciente.nombre)
        ent_nom.pack(fill=tk.X, padx=20)
 
        self._crear_label_modal(modal, "Apellido:")
        ent_ape = ttk.Entry(modal)
        ent_ape.insert(0, paciente.apellido)
        ent_ape.pack(fill=tk.X, padx=20)
 
        self._crear_label_modal(modal, "DNI:")
        ent_dni = ttk.Entry(modal)
        ent_dni.insert(0, paciente.dni)
        ent_dni.pack(fill=tk.X, padx=20)
 
        self._crear_label_modal(modal, "Teléfono:")
        ent_tel = ttk.Entry(modal)
        ent_tel.insert(0, paciente.telefono)
        ent_tel.pack(fill=tk.X, padx=20)
 
        self._crear_label_modal(modal, "Sexo:")
        ent_sexo = ttk.Entry(modal)
        ent_sexo.insert(0, paciente.sexo)
        ent_sexo.pack(fill=tk.X, padx=20)
 
        self._crear_label_modal(modal, "Fecha de Nacimiento:")
 
        ent_fn = ttk.Entry(modal)
        ent_fn.pack(fill=tk.X, padx=20)
 
        self._crear_label_modal(modal, "Dirección:")
        ent_dir = ttk.Entry(modal)
        ent_dir.insert(0, paciente.direccion)
        ent_dir.pack(fill=tk.X, padx=20)
 
        PLACEHOLDER_FECHA = "DD/MM/AAAA"
 
        def poner_placeholder_fecha():
            ent_fn.insert(0, PLACEHOLDER_FECHA)
            ent_fn.config(foreground="gray")
 
        def quitar_placeholder_fecha(event=None):
            if ent_fn.get() == PLACEHOLDER_FECHA:
                ent_fn.delete(0, tk.END)
                ent_fn.config(foreground="black")
 
        def restaurar_placeholder_fecha(event=None):
            if not ent_fn.get():
                poner_placeholder_fecha()
 
        def formatear_fecha(event=None):
            texto = ent_fn.get()
 
            # No formatear si todavía está el placeholder
            if texto == PLACEHOLDER_FECHA:
                return
 
            # Solo números, máximo 8 dígitos
            numeros = "".join(c for c in texto if c.isdigit())[:8]
 
            resultado = numeros[:2]
            if len(numeros) > 2:
                resultado += "/" + numeros[2:4]
            if len(numeros) > 4:
                resultado += "/" + numeros[4:]
 
            # Evita bucle infinito de KeyRelease si no cambió nada
            if resultado != texto:
                pos = ent_fn.index(tk.INSERT)
                ent_fn.delete(0, tk.END)
                ent_fn.insert(0, resultado)
                # Reubica el cursor al final (o donde corresponda)
                nueva_pos = min(pos + (len(resultado) - len(texto)), len(resultado))
                ent_fn.icursor(max(nueva_pos, 0))
 
        ent_fn.bind("<FocusIn>", quitar_placeholder_fecha)
        ent_fn.bind("<FocusOut>", restaurar_placeholder_fecha)
        ent_fn.bind("<KeyRelease>", formatear_fecha)
 
        # Precargar la fecha existente del paciente; si no hubiera, mostrar placeholder
        if paciente.fecha_nacimiento:
            ent_fn.insert(0, paciente.fecha_nacimiento)
            ent_fn.config(foreground="black")
        else:
            poner_placeholder_fecha()
 
        def actualizar() -> None:
            nombre = ent_nom.get().strip()
            apellido = ent_ape.get().strip()
            dni = ent_dni.get().strip()
            telefono = ent_tel.get().strip()
            sexo = ent_sexo.get().strip()
            f_nac = ent_fn.get().strip()
            if f_nac == PLACEHOLDER_FECHA:
                f_nac = ""
            direccion = ent_dir.get().strip()
 
            if not all([nombre, apellido, dni, telefono, sexo, f_nac, direccion]):
                messagebox.showerror("Datos incompletos", "Todos los campos son obligatorios.", parent=modal)
                return
 
            try:
                datetime.strptime(f_nac, "%d/%m/%Y")
            except ValueError:
                messagebox.showerror(
                    "Fecha inválida", "La fecha de nacimiento debe tener el formato DD/MM/AAAA.", parent=modal
                )
                return
 
            try:
                self._controller.actualizar_paciente(pac_id, nombre, apellido, dni, telefono, sexo, f_nac, direccion)
                self.cargar_lista_pacientes()
                modal.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)
 
        tk.Button(
            modal, text="Actualizar",command=actualizar,
            bg="#116435",
            fg="white",
            activebackground="#29BD5C",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=40, pady=20)
        tk.Button(
            modal, text="Cancelar",  command=modal.destroy,
            bg="#C62828",
            fg="white",
            activebackground="#E36161",
            activeforeground="white",
            font=("Segoe UI", 10, "bold"),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=40, pady=20)
 
        modal.bind("<Return>", lambda e: actualizar())
        modal.bind("<Escape>", lambda e: modal.destroy())

    # ------------------------------------------------------------------
    # Dar de baja
    # ------------------------------------------------------------------
    def _solicitar_baja(self) -> None:
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Atención", "Debe seleccionar un paciente de la tabla.")
            return

        pac_id = int(seleccion[0])
        if messagebox.askyesno("Confirmar", "¿Está seguro de dar de baja a este paciente?\n"
                                             "El paciente no será eliminado, solo pasará a estado Inactivo."):
            self._controller.dar_de_baja_paciente(pac_id)
            self.cargar_lista_pacientes()