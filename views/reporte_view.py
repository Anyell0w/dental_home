import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from tkcalendar import DateEntry
from utils.theme import COLORS, FONTS
from controllers.reporte_controller import ReporteController


class ReporteView:
    """Módulo de Inteligencia de Negocio y Auditoría Operativa."""

    def __init__(self, contenedor: tk.Frame, controller: ReporteController, operador_nombre: str) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: ReporteController = controller
        self._operador: str = operador_nombre

    # ------------------------------------------------------------------ #
    # Estilos
    # ------------------------------------------------------------------ #
    def _configurar_estilos_tabla(self) -> None:
        estilo = ttk.Style()
        estilo.configure(
            "Reporte.Treeview",
            background=COLORS["white"],
            foreground=COLORS["dark"],
            fieldbackground=COLORS["white"],
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        estilo.configure(
            "Reporte.Treeview.Heading",
            background=COLORS["primary"],
            foreground=COLORS["white"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        estilo.map(
            "Reporte.Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", COLORS["white"])],
        )
        estilo.configure(
            "Reporte.TCombobox",
            fieldbackground=COLORS["white"],
            background=COLORS["white"],
            padding=4,
        )

    # ------------------------------------------------------------------ #
    # Construcción de la vista
    # ------------------------------------------------------------------ #
    def inicializar(self) -> None:
        for widget in self._contenedor.winfo_children():
            widget.destroy()

        self._configurar_estilos_tabla()

        self._contenedor.configure(bg=COLORS.get("background", COLORS["white"]))

        # ---------------- Encabezado ---------------- #
        header = tk.Frame(self._contenedor, bg=COLORS.get("background", COLORS["white"]))
        header.pack(fill=tk.X, padx=20, pady=(15, 5))

        tk.Label(
            header,
            text="ADMINISTRACIÓN / REPORTES",
            font=("Segoe UI", 9),
            fg=COLORS.get("muted", "#888888"),
            bg=COLORS.get("background", COLORS["white"]),
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Reportes Gerenciales",
            font=FONTS.get("title", ("Segoe UI", 16, "bold")),
            fg=COLORS["dark"],
            bg=COLORS.get("background", COLORS["white"]),
        ).pack(anchor="w")

        # ---------------- Cuerpo: dos columnas ---------------- #
        cuerpo = tk.Frame(self._contenedor, bg=COLORS.get("background", COLORS["white"]))
        cuerpo.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=2)
        cuerpo.rowconfigure(0, weight=1)

        # ---- Columna izquierda: historial ---- #
        frame_historial = tk.LabelFrame(
            cuerpo,
            text="  Historial de reportes  ",
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
            columns=("ID", "Tipo", "Periodo", "Generación", "Formato", "Operador"),
            show="headings",
            style="Reporte.Treeview",
        )
        anchos = {"ID": 50, "Tipo": 90, "Periodo": 170, "Generación": 100, "Formato": 70, "Operador": 100}
        for col in ("ID", "Tipo", "Periodo", "Generación", "Formato", "Operador"):
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos.get(col, 100), anchor="center")

        scrollbar = ttk.Scrollbar(frame_historial, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        self.tabla.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # Botón para abrir el reporte seleccionado (se ubica bajo la tarjeta del historial)
        boton_abrir = tk.Button(
            self._contenedor,
            text="📂 Abrir reporte seleccionado",
            bg=COLORS["primary"],
            fg=COLORS["white"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["white"],
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._abrir_seleccionado,
        )

        # ---- Columna derecha: formulario ---- #
        frame_form = tk.LabelFrame(
            cuerpo,
            text="  Generar nuevo reporte  ",
            font=FONTS.get("subtitle", ("Segoe UI", 11, "bold")),
            bg=COLORS["white"],
            fg=COLORS["dark"],
            bd=1,
            relief="solid",
            labelanchor="n",
            padx=15,
            pady=15,
        )
        frame_form.grid(row=0, column=1, sticky="nsew")
        frame_form.columnconfigure(0, weight=1)
        frame_form.columnconfigure(1, weight=1)

        # Tipo de reporte
        tk.Label(
            frame_form, text="Tipo de reporte", bg=COLORS["white"], fg=COLORS["dark"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))
        cb_tipo = ttk.Combobox(
            frame_form, values=["Citas", "Pacientes", "Actividad"], state="readonly",
            style="Reporte.TCombobox",
        )
        cb_tipo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        cb_tipo.current(0)

        # Fechas
        tk.Label(
            frame_form, text="Fecha inicio", bg=COLORS["white"], fg=COLORS["dark"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(0, 3), padx=(0, 5))
        tk.Label(
            frame_form, text="Fecha fin", bg=COLORS["white"], fg=COLORS["dark"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=1, sticky="w", pady=(0, 3), padx=(5, 0))

        ent_ini = DateEntry(frame_form, width=11, date_pattern="yyyy-mm-dd")
        ent_ini.grid(row=3, column=0, sticky="ew", pady=(0, 12), padx=(0, 5))
        ent_fin = DateEntry(frame_form, width=11, date_pattern="yyyy-mm-dd")
        ent_fin.grid(row=3, column=1, sticky="ew", pady=(0, 12), padx=(5, 0))

        # Formato
        tk.Label(
            frame_form, text="Formato", bg=COLORS["white"], fg=COLORS["dark"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 3))
        cb_form = ttk.Combobox(
            frame_form, values=["PDF", "Excel"], state="readonly",
            style="Reporte.TCombobox",
        )
        cb_form.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        cb_form.current(0)

        def generar() -> None:
            tipo = cb_tipo.get()
            formato = cb_form.get()
            f_ini = ent_ini.get_date().strftime("%Y-%m-%d")
            f_fin = ent_fin.get_date().strftime("%Y-%m-%d")

            if not tipo or not formato:
                messagebox.showerror("Datos incompletos", "Seleccione tipo y formato.")
                return
            if f_fin < f_ini:
                messagebox.showerror(
                    "Rango inválido", "La fecha fin no puede ser anterior a la fecha inicio."
                )
                return
            try:
                reporte = self._controller.generar_reporte(
                    tipo, self._operador, f_ini, f_fin, formato
                )
                self._cargar_tabla()
                if messagebox.askyesno(
                    "Éxito",
                    f"Reporte generado:\n{os.path.basename(reporte._archivo)}\n\n¿Desea abrirlo ahora?",
                ):
                    self._abrir_archivo(reporte._archivo)
            except Exception as e:
                messagebox.showerror("Error analítico", str(e))

        btn_generar = tk.Button(
            frame_form,
            text="⚙ Generar Reporte",
            bg=COLORS["primary"],
            fg=COLORS["white"],
            activebackground=COLORS["primary"],
            activeforeground=COLORS["white"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            pady=10,
            cursor="hand2",
            command=generar,
        )
        btn_generar.grid(row=6, column=0, columnspan=2, sticky="ew")

        # ---------------- Botón abrir seleccionado (bajo el historial) ---------------- #
        boton_abrir.pack(pady=(10, 5))

        self._cargar_tabla()

    # ------------------------------------------------------------------ #
    # Datos
    # ------------------------------------------------------------------ #
    def _cargar_tabla(self) -> None:
        self.tabla.delete(*self.tabla.get_children())
        for r in self._controller.listar_reportes():
            periodo = f"{r.fechaInicio} a {r.fechaFin}"
            self.tabla.insert(
                "",
                tk.END,
                iid=str(r.id),
                values=(r.id, r.tipo, periodo, r._fechaGeneracion[:10], r.formato, r._generadoPor),
            )

    def _abrir_seleccionado(self) -> None:
        sel = self.tabla.selection()
        if not sel:
            messagebox.showwarning("Reporte", "Seleccione un reporte de la lista.")
            return
        reporte = self._controller._reporte_dao.buscar_por_id(int(sel[0]))
        if reporte:
            self._abrir_archivo(reporte._archivo)

    @staticmethod
    def _abrir_archivo(ruta: str) -> None:
        if not ruta or not os.path.isfile(ruta):
            messagebox.showwarning("Archivo", "El archivo del reporte no está disponible.")
            return
        try:
            os.startfile(ruta)
        except Exception as e:
            messagebox.showerror("Archivo", f"No se pudo abrir el archivo:\n{e}")