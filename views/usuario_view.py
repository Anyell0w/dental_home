import tkinter as tk
from tkinter import ttk, messagebox
from utils.theme import COLORS, FONTS
from controllers.usuario_controller import UsuarioController


class UsuarioView:
    """Módulo de administración de usuarios del sistema (solo Administrador)."""

    ROLES = ("Doctor", "Secretaria", "Administrador")

    def __init__(self, contenedor: tk.Frame, controller: UsuarioController) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: UsuarioController = controller

    # ------------------------------------------------------------------ #
    # Estilos
    # ------------------------------------------------------------------ #
    def _configurar_estilos_tabla(self) -> None:
        estilo = ttk.Style()
        estilo.configure(
            "Usuario.Treeview",
            background=COLORS["white"],
            foreground=COLORS["dark"],
            fieldbackground=COLORS["white"],
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "Usuario.Treeview.Heading",
            background=COLORS["primary"],
            foreground=COLORS["white"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        estilo.map(
            "Usuario.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", COLORS["white"])],
        )

        # Estilo moderno para los comboboxes de los formularios
        estilo.configure(
            "Formulario.TCombobox",
            background="#f8fafc",
            fieldbackground="#f8fafc",
            foreground=COLORS["dark"],
            font=("Segoe UI", 10),
            relief="flat"
        )

    # ------------------------------------------------------------------ #
    # Construcción de la vista
    # ------------------------------------------------------------------ #
    def inicializar(self) -> None:
        for widget in self._contenedor.winfo_children():
            widget.destroy()

        self._configurar_estilos_tabla()
        self._contenedor.configure(bg=COLORS["background"])

        # ---------------- Encabezado ---------------- #
        header = tk.Frame(self._contenedor, bg=COLORS["background"])
        header.pack(fill=tk.X, padx=20, pady=(15, 5))

        tk.Label(
            header,
            text="ADMINISTRACIÓN / USUARIOS",
            font=("Segoe UI", 9),
            fg=COLORS.get("muted", "#888888"),
            bg=COLORS["background"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Gestión de Usuarios",
            font=FONTS.get("title", ("Segoe UI", 16, "bold")),
            fg=COLORS["dark"],
            bg=COLORS["background"],
        ).pack(anchor="w")

        # ---------------- Barra de acciones ---------------- #
        barra = tk.Frame(self._contenedor, bg=COLORS["background"])
        barra.pack(fill=tk.X, padx=20, pady=(10, 5))

        tk.Button(
            barra,
            text="🔁 Activar / Desactivar",
            bg=COLORS["primary"],
            fg=COLORS["white"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["white"],
            font=FONTS.get("body", ("Segoe UI", 9, "bold")),
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._alternar_estado,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            barra,
            text="🔑 Restablecer contraseña",
            bg=COLORS["primary"],
            fg=COLORS["white"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["white"],
            font=FONTS.get("body", ("Segoe UI", 9, "bold")),
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._restablecer_contrasena,
        ).pack(side=tk.LEFT)

        tk.Button(
            barra,
            text="➕ Nuevo usuario",
            bg="#166534",
            fg=COLORS["white"],
            activebackground=COLORS["success"],
            activeforeground=COLORS["white"],
            font=FONTS.get("body", ("Segoe UI", 9, "bold")),
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._abrir_formulario_nuevo,
        ).pack(side=tk.RIGHT)

        # ---------------- Tarjeta: cuentas del sistema ---------------- #
        frame_tabla = tk.LabelFrame(
            self._contenedor,
            text="  Cuentas del sistema  ",
            font=FONTS.get("subtitle", ("Segoe UI", 11, "bold")),
            bg=COLORS["white"],
            fg=COLORS["dark"],
            bd=1,
            relief="solid",
            labelanchor="n",
            padx=10,
            pady=10,
        )
        frame_tabla.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 15))

        columnas = ("ID", "Usuario", "Rol", "Estado")
        self.tabla = ttk.Treeview(
            frame_tabla, columns=columnas, show="headings", selectmode="browse",
            style="Usuario.Treeview",
        )
        anchos = {"ID": 60, "Usuario": 220, "Rol": 160, "Estado": 120}
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos.get(col, 120), anchor="center")

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        self.tabla.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self._cargar_tabla()

    # ------------------------------------------------------------------ #
    # Datos
    # ------------------------------------------------------------------ #
    def _cargar_tabla(self) -> None:
        self.tabla.delete(*self.tabla.get_children())
        try:
            usuarios = self._controller.listar_usuarios()
        except PermissionError as e:
            messagebox.showerror("Acceso denegado", str(e))
            return
        for u in usuarios:
            estado = "Activo" if u.activo else "Inactivo"
            self.tabla.insert("", tk.END, iid=str(u.id), values=(u.id, u.nombreUsuario, u.rol, estado))

    def _obtener_seleccion(self):
        sel = self.tabla.selection()
        if not sel:
            messagebox.showwarning("Usuarios", "Seleccione un usuario de la lista.")
            return None
        return int(sel[0])

    # ------------------------------------------------------------------ #
    # Componente Auxiliar de Diseño Moderno
    # ------------------------------------------------------------------ #
    def _crear_campo_entrada(self, parent: tk.Frame, label_text: str, show_char: str = None) -> tk.Entry:
        """Helper para construir campos de entrada limpios con estética plana moderna."""
        frame_campo = tk.Frame(parent, bg="white")
        frame_campo.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            frame_campo,
            text=label_text,
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="white"
        ).pack(anchor="w", pady=(0, 4))

        # Contenedor del borde plano
        borde_entry = tk.Frame(
            frame_campo,
            bg="#f8fafc",
            bd=0,
            highlightthickness=1,
            highlightbackground="#cbd5e1"
        )
        borde_entry.pack(fill=tk.X)

        entrada = tk.Entry(
            borde_entry,
            bg="#f8fafc",
            fg=COLORS["dark"],
            font=("Segoe UI", 10),
            bd=0,
            relief="flat",
            insertbackground=COLORS["primary"]
        )
        if show_char:
            entrada.configure(show=show_char)
        entrada.pack(fill=tk.X, padx=10, pady=8)

        # Efecto de foco en el campo de entrada
        def al_enfocar(e):
            borde_entry.configure(highlightbackground=COLORS["primary"])
        def al_desenfocar(e):
            borde_entry.configure(highlightbackground="#cbd5e1")

        entrada.bind("<FocusIn>", al_enfocar)
        entrada.bind("<FocusOut>", al_desenfocar)

        return entrada

    # ------------------------------------------------------------------ #
    # Acciones
    # ------------------------------------------------------------------ #
    def _abrir_formulario_nuevo(self) -> None:
        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Nuevo usuario")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("400x440")
        modal.configure(bg="white")
        modal.resizable(False, False)

        # Banner de título
        header_modal = tk.Frame(modal, bg=COLORS["primary"], pady=18)
        header_modal.pack(fill=tk.X, side="top")

        tk.Label(
            header_modal,
            text="REGISTRAR NUEVO USUARIO",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg="#166534"
        ).pack()

        # Cuerpo del formulario
        cuerpo_modal = tk.Frame(modal, bg="white", padx=30, pady=20)
        cuerpo_modal.pack(fill=tk.BOTH, expand=True)

        # Crear inputs con el nuevo helper de diseño
        ent_nombre = self._crear_campo_entrada(cuerpo_modal, "Nombre de usuario:")
        
        # Campo de selección de Rol
        frame_rol = tk.Frame(cuerpo_modal, bg="white")
        frame_rol.pack(fill=tk.X, pady=(0, 12))
        
        tk.Label(
            frame_rol,
            text="Rol del sistema:",
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="white"
        ).pack(anchor="w", pady=(0, 4))

        cb_rol = ttk.Combobox(frame_rol, values=list(self.ROLES), state="readonly", style="Formulario.TCombobox")
        cb_rol.pack(fill=tk.X, ipady=4)
        cb_rol.current(0)

        ent_pass = self._crear_campo_entrada(cuerpo_modal, "Contraseña de acceso:", show_char="*")

        def guardar() -> None:
            if not ent_nombre.get().strip() or not ent_pass.get().strip():
                messagebox.showwarning("Campos requeridos", "Por favor, complete todos los campos del formulario.", parent=modal)
                return
            try:
                self._controller.registrar_usuario(
                    ent_nombre.get().strip(), ent_pass.get().strip(), cb_rol.get()
                )
                modal.destroy()
                self._cargar_tabla()
                messagebox.showinfo("Usuarios", "Usuario creado correctamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        # Botones de Acción
        frame_botones = tk.Frame(cuerpo_modal, bg="white")
        frame_botones.pack(fill=tk.X, pady=(15, 0))

        btn_cancelar = tk.Button(
            frame_botones,
            text="Cancelar",
            bg="#f1f5f9",
            fg="#475569",
            activebackground="#e2e8f0",
            activeforeground="#334155",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=modal.destroy
        )
        btn_cancelar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_guardar = tk.Button(
            frame_botones,
            text="Guardar Usuario",
            bg="#166534",
            fg="white",
            activebackground="#15803d",
            activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=guardar
        )
        btn_guardar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))

        # Animación interactiva al pasar el cursor (Hover)
        btn_guardar.bind("<Enter>", lambda e: btn_guardar.configure(bg="#16a34a"))
        btn_guardar.bind("<Leave>", lambda e: btn_guardar.configure(bg=COLORS["success"]))
        btn_cancelar.bind("<Enter>", lambda e: btn_cancelar.configure(bg="#e2e8f0"))
        btn_cancelar.bind("<Leave>", lambda e: btn_cancelar.configure(bg="#f1f5f9"))

    def _alternar_estado(self) -> None:
        user_id = self._obtener_seleccion()
        if user_id is None:
            return
        valores = self.tabla.item(str(user_id))["values"]
        estado_actual = valores[3]
        try:
            if estado_actual == "Activo":
                self._controller.desactivar_usuario(user_id)
            else:
                self._controller.activar_usuario(user_id)
            self._cargar_tabla()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _restablecer_contrasena(self) -> None:
        user_id = self._obtener_seleccion()
        if user_id is None:
            return

        modal = tk.Toplevel(self._contenedor.winfo_toplevel())
        modal.title("Restablecer contraseña")
        modal.transient(self._contenedor.winfo_toplevel())
        modal.grab_set()
        modal.geometry("380x280")
        modal.configure(bg="white")
        modal.resizable(False, False)

        # Banner de título
        header_modal = tk.Frame(modal, bg=COLORS["primary"], pady=18)
        header_modal.pack(fill=tk.X, side="top")

        tk.Label(
            header_modal,
            text="RESTABLECER CONTRASEÑA",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg=COLORS["primary"]
        ).pack()

        # Cuerpo del formulario
        cuerpo_modal = tk.Frame(modal, bg="white", padx=30, pady=20)
        cuerpo_modal.pack(fill=tk.BOTH, expand=True)

        ent_pass = self._crear_campo_entrada(cuerpo_modal, "Nueva contraseña de acceso:", show_char="*")

        def guardar() -> None:
            if not ent_pass.get().strip():
                messagebox.showwarning("Campo requerido", "Debe ingresar una nueva contraseña.", parent=modal)
                return
            try:
                self._controller.restablecer_contrasena(user_id, ent_pass.get().strip())
                modal.destroy()
                messagebox.showinfo("Usuarios", "Contraseña actualizada exitosamente.")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=modal)

        # Botones de Acción
        frame_botones = tk.Frame(cuerpo_modal, bg="white")
        frame_botones.pack(fill=tk.X, pady=(20, 0))

        btn_cancelar = tk.Button(
            frame_botones,
            text="Cancelar",
            bg="#f1f5f9",
            fg="#475569",
            activebackground="#e2e8f0",
            activeforeground="#334155",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=modal.destroy
        )
        btn_cancelar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_actualizar = tk.Button(
            frame_botones,
            text="Actualizar",
            bg=COLORS["primary"],
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=guardar
        )
        btn_actualizar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0))

        # Animación interactiva al pasar el cursor (Hover)
        btn_actualizar.bind("<Enter>", lambda e: btn_actualizar.configure(bg="#2563eb"))
        btn_actualizar.bind("<Leave>", lambda e: btn_actualizar.configure(bg=COLORS["primary"]))
        btn_cancelar.bind("<Enter>", lambda e: btn_cancelar.configure(bg="#e2e8f0"))
        btn_cancelar.bind("<Leave>", lambda e: btn_cancelar.configure(bg="#f1f5f9"))
