import tkinter as tk
from tkinter import ttk, messagebox
from utils.theme import COLORS, FONTS
from controllers.copia_controller import CopiaSeguridadController


class CopiaSeguridadView:
    """Consola Administrativa de Respaldo e Integridad de Archivos de Servidor."""

    def __init__(self, contenedor: tk.Frame, controller: CopiaSeguridadController, admin_id: int) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: CopiaSeguridadController = controller
        self._admin_id: int = admin_id

    # ------------------------------------------------------------------ #
    # Estilos
    # ------------------------------------------------------------------ #
    def _configurar_estilos_tabla(self) -> None:
        estilo = ttk.Style()
        estilo.configure(
            "Copia.Treeview",
            background=COLORS["white"],
            foreground=COLORS["dark"],
            fieldbackground=COLORS["white"],
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "Copia.Treeview.Heading",
            background=COLORS["primary"],
            foreground=COLORS["white"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        estilo.map(
            "Copia.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", COLORS["white"])],
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
            text="ADMINISTRACIÓN / BACKUP",
            font=("Segoe UI", 9),
            fg=COLORS.get("muted", "#888888"),
            bg=COLORS["background"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Copias de seguridad",
            font=FONTS.get("title", ("Segoe UI", 16, "bold")),
            fg=COLORS["dark"],
            bg=COLORS["background"],
        ).pack(anchor="w")

        # ---------------- Cuerpo: dos columnas ---------------- #
        cuerpo = tk.Frame(self._contenedor, bg=COLORS["background"])
        cuerpo.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=2)
        cuerpo.rowconfigure(0, weight=1)

        # ---- Columna izquierda: historial ---- #
        frame_historial = tk.LabelFrame(
            cuerpo,
            text="  Historial de copias de seguridad  ",
            font=FONTS.get("subtitle", ("Segoe UI", 11, "bold")),
            bg=COLORS["white"],
            fg=COLORS["dark"],
            bd=1,
            relief="solid",
            labelanchor="n",
            padx=10,
            pady=10,
        )
        frame_historial.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.tabla = ttk.Treeview(
            frame_historial,
            columns=("ID", "Fecha", "Tipo", "Estado", "Ubicación"),
            show="headings",
            style="Copia.Treeview",
        )
        anchos = {"ID": 50, "Fecha": 130, "Tipo": 90, "Estado": 80, "Ubicación": 220}
        for col in ("ID", "Fecha", "Tipo", "Estado", "Ubicación"):
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos.get(col, 110), anchor="center")

        scrollbar = ttk.Scrollbar(frame_historial, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        self.tabla.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # ---- Columna derecha: acciones ---- #
        frame_acciones = tk.LabelFrame(
            cuerpo,
            text="  Acciones  ",
            font=FONTS.get("subtitle", ("Segoe UI", 11, "bold")),
            bg=COLORS["white"],
            fg=COLORS["dark"],
            bd=1,
            relief="solid",
            labelanchor="n",
            padx=15,
            pady=15,
        )
        frame_acciones.grid(row=0, column=1, sticky="nsew")

        tk.Label(
            frame_acciones,
            text=(
                "Ejecuta un respaldo manual de la base de datos SQLite "
                "en cualquier momento. Los respaldos automáticos corren "
                "diariamente."
            ),
            font=FONTS.get("body", ("Segoe UI", 9)),
            bg=COLORS["white"],
            fg=COLORS["dark"],
            wraplength=260,
            justify="left",
        ).pack(anchor="w", pady=(0, 15))

        tk.Button(
            frame_acciones,
            text="⚡ Ejecutar copia manual ahora",
            font=FONTS.get("body", ("Segoe UI", 9, "bold")),
            bg="#166534",
            fg=COLORS["white"],
            activebackground=COLORS["success"],
            activeforeground=COLORS["white"],
            relief="flat",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._ejecutar_backup,
        ).pack(fill=tk.X)

        self._cargar_historial()

    # ------------------------------------------------------------------ #
    # Datos y acciones
    # ------------------------------------------------------------------ #
    def _cargar_historial(self) -> None:
        self.tabla.delete(*self.tabla.get_children())
        for bk in self._controller.listar_copias():
            self.tabla.insert(
                "",
                tk.END,
                values=(bk.id, bk._fechaHora[:16].replace("T", " "), bk._tipo, bk.estado, bk.ubicacion),
            )

    def _ejecutar_backup(self) -> None:
        try:
            self._controller.ejecutar_backup_manual(self._admin_id)
            messagebox.showinfo("Servidor", "Copia física de la base de datos realizada con éxito.")
            self._cargar_historial()
        except Exception as e:
            messagebox.showerror("Fallo de Servidor", str(e))
