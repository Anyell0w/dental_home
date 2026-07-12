import tkinter as tk
from tkinter import ttk
from utils.theme import COLORS, FONTS

class DashboardView:
    """
    Dashboard optimizado con diseño Bento Grid, minimalista y corporativo.
    Garantiza la visibilidad completa de tablas, reportes y actividades recientes.
    Requiere un DashboardController con:
      - obtener_estadisticas()
      - obtener_agenda_hoy()
      - obtener_actividad_reciente()
    """
    def __init__(self, contenedor, controller):
        self._contenedor = contenedor
        self.controller = controller

    def inicializar(self):
        # Limpieza de la interfaz previa
        for w in self._contenedor.winfo_children():
            w.destroy()
            
        # Configuración del fondo general de la aplicación
        self._contenedor.configure(bg=COLORS.get("gray_light", "#f8fafc"))
        datos = self.controller.obtener_estadisticas()

        # ==========================================
        # ENCABEZADO
        # ==========================================
        header = tk.Frame(self._contenedor, bg=COLORS.get("gray_light", "#f8fafc"), padx=30, pady=20)
        header.pack(fill="x")
        
        tk.Label(
            header,
            text="GENERAL / INICIO",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS.get("gray_light", "#f8fafc"),
            fg=COLORS.get("gray", "#64748b"),
            justify="left"
        ).pack(anchor="w")
        
        tk.Label(
            header,
            text="Panel de Control",
            font=FONTS.get("title", ("Segoe UI", 22, "bold")),
            bg=COLORS.get("gray_light", "#f8fafc"),
            fg=COLORS.get("dark", "#0f172a"),
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

        # ==========================================
        # CONTENEDOR BENTO GRID (Estructura de 4 Columnas)
        # ==========================================
        grid_container = tk.Frame(self._contenedor, bg=COLORS.get("gray_light", "#f8fafc"))
        grid_container.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        # Distribución proporcional y homogénea de las columnas estilo Bento
        for i in range(4):
            grid_container.columnconfigure(i, weight=1, uniform="bento_column")
            
        grid_container.rowconfigure(0, weight=0)  # Fila superior fija para indicadores de control
        grid_container.rowconfigure(1, weight=1)  # Fila inferior expandible para datos operativos

        # Creación de Tarjetas de Indicadores Métricos
        card1 = self._card(grid_container, "CITAS DE HOY", datos["citas_hoy"], f'{datos["citas_completadas"]} completadas')
        card2 = self._card(grid_container, "PACIENTES ACTIVOS", datos["pacientes_activos"], "Registrados")
        card3 = self._card(grid_container, "RECETAS EMITIDAS", datos["recetas_mes"], "Este mes")
        card4 = self._card(grid_container, "ESTADO COPIA SEGURIDAD", datos["ultima_copia"], datos["estado_backup"])

        # Posicionamiento Bento Horizontal de los Indicadores
        card1.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        card2.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        card3.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)
        card4.grid(row=0, column=3, sticky="nsew", padx=6, pady=6)

        # ==========================================
        # BLOQUE: AGENDA DE HOY (Sección Inferior Izquierda Ampliada)
        # ==========================================
        left_block = tk.Frame(
            grid_container, 
            bg="white", 
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#e2e8f0"
        )
        left_block.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
        
        tk.Label(
            left_block,
            text="Agenda de hoy",
            font=FONTS.get("subtitle", ("Segoe UI", 12, "bold")),
            bg="white",
            fg=COLORS.get("dark", "#0f172a")
        ).pack(anchor="w", padx=20, pady=(18, 12))

        # Configuración visual avanzada de la tabla para evitar truncamiento
        style = ttk.Style()
        style.configure(
            "Dashboard.Treeview", 
            background="white", 
            foreground=COLORS.get("dark", "#0f172a"), 
            rowheight=35,  # Mayor altura por fila para legibilidad premium
            fieldbackground="white", 
            borderwidth=0, 
            font=("Segoe UI", 10)
        )
        style.configure(
            "Dashboard.Treeview.Heading", 
            background="#f8fafc", 
            foreground=COLORS.get("gray", "#64748b"), 
            font=("Segoe UI", 9, "bold"), 
            relief="flat"
        )
        # Remueve bordes decorativos innecesarios de la estructura nativa
        style.layout("Dashboard.Treeview", [('Dashboard.Treeview.treearea', {'sticky': 'nswe'})]) 
        
        cols = ("Hora", "Paciente", "Doctor", "Estado")
        tv = ttk.Treeview(left_block, columns=cols, show="headings", style="Dashboard.Treeview")
        
        # Dimensiones explícitas y holgadas para evitar el corte de texto ("...")
        tv.heading("Hora", text="Hora")
        tv.column("Hora", width=90, anchor="center", stretch=False)
        
        tv.heading("Paciente", text="Paciente")
        tv.column("Paciente", width=240, anchor="w", stretch=True)
        
        tv.heading("Doctor", text="Doctor")
        tv.column("Doctor", width=160, anchor="w", stretch=True)
        
        tv.heading("Estado", text="Estado")
        tv.column("Estado", width=120, anchor="center", stretch=False)
        
        tv.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Configuración de tags para emular badges de estado corporativos
        tv.tag_configure("confirmada", background="#f0fdf4", foreground="#16a34a")
        tv.tag_configure("pendiente", background="#fffbeb", foreground="#d97706")

        for fila in self.controller.obtener_agenda_hoy():
            estado_texto = str(fila["estado"]).lower()
            tag_asignado = "confirmada" if "conf" in estado_texto or "éxit" in estado_texto else "pendiente"
            tv.insert("", "end", values=(fila["hora"], fila["paciente"], fila["doctor"], fila["estado"]), tags=(tag_asignado,))

        # ==========================================
        # BLOQUE: ACTIVIDAD RECIENTE (Sección Inferior Derecha Lateral)
        # ==========================================
        right_block = tk.Frame(
            grid_container, 
            bg="white", 
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#e2e8f0"
        )
        right_block.grid(row=1, column=3, sticky="nsew", padx=6, pady=6)

        tk.Label(
            right_block,
            text="Actividad reciente",
            font=FONTS.get("subtitle", ("Segoe UI", 12, "bold")),
            bg="white",
            fg=COLORS.get("dark", "#0f172a")
        ).pack(anchor="w", padx=20, pady=(18, 12))

        actividad_frame = tk.Frame(right_block, bg="white")
        actividad_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for indexing, actividad in enumerate(self.controller.obtener_actividad_reciente()):
            tarjeta = tk.Frame(actividad_frame, bg="white", pady=8)
            tarjeta.pack(fill="x")

            icon_canvas = tk.Canvas(tarjeta, width=24, height=24, bg="white", highlightthickness=0)
            icon_canvas.pack(side="left", padx=(0, 12))
            
            es_seguridad = "copia" in actividad["titulo"].lower()
            color_circulo = "#dcfce7" if es_seguridad else "#e0f2fe"
            color_texto = "#15803d" if es_seguridad else COLORS.get("primary", "#0284c7")
            simbolo = "✓" if es_seguridad else "•"
            
            icon_canvas.create_oval(2, 2, 22, 22, fill=color_circulo, outline="")
            icon_canvas.create_text(12, 12, text=simbolo, fill=color_texto, font=("Segoe UI", 10, "bold"))

            contenido = tk.Frame(tarjeta, bg="white")
            contenido.pack(side="left", fill="x", expand=True)

            lbl_titulo = tk.Label(
                contenido,
                text=actividad["titulo"],
                font=("Segoe UI", 9, "bold"), # Cambiado a entero
                bg="white",
                fg=COLORS.get("dark", "#0f172a"),
                anchor="w",
                justify="left",
                wraplength=170  
            )
            lbl_titulo.pack(fill="x")

            lbl_detalle = tk.Label(
                contenido,
                text=actividad["detalle"],
                font=("Segoe UI", 9),  # Cambiado de 8.5 a 9 entero
                bg="white",
                fg=COLORS.get("gray", "#64748b"),
                anchor="w",
                justify="left"
            )
            lbl_detalle.pack(fill="x", pady=(2, 0))

    def _card(self, parent, titulo, valor, sub):
        """Genera un módulo individual adaptado a los lineamientos estructurales Bento Grid."""
        f = tk.Frame(
            parent, 
            bg="white", 
            padx=20, 
            pady=18, 
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#e2e8f0"
        )
        
        tk.Label(
            f, 
            text=titulo, 
            font=("Segoe UI", 8, "bold"), 
            bg="white",
            fg=COLORS.get("gray", "#64748b")
        ).pack(anchor="w")
        
        tk.Label(
            f, 
            text=str(valor), 
            font=("Segoe UI", 22, "bold"), 
            bg="white",
            fg=COLORS.get("primary", "#0284c7")
        ).pack(anchor="w", pady=4)
        
        tk.Label(
            f, 
            text=sub, 
            font=("Segoe UI", 9),  # Cambiado de 8.5 a 9 entero
            bg="white",
            fg=COLORS.get("muted", "#94a3b8")
        ).pack(anchor="w")
        
        return f
