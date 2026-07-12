import tkinter as tk
from tkinter import messagebox
from typing import Dict, Any, Callable
from utils.theme import COLORS, FONTS
from config import SESSION_TIMEOUT_MINUTES

class MainMenu:
    """Dashboard Central con Sidebar adaptativo según el rol de seguridad."""
    def __init__(self, root: tk.Tk, usuario: Any, vistas_mapping: Dict[str, Callable[[], None]], on_logout: Callable[[], None]) -> None:
        self._root: tk.Tk = root
        self._usuario: Any = usuario
        self._vistas: Dict[str, Callable[[], None]] = vistas_mapping
        self._on_logout: Callable[[], None] = on_logout

        # Control de expiración de sesión por inactividad
        self._timeout_ms: int = int(SESSION_TIMEOUT_MINUTES) * 60 * 1000
        self._timeout_id = None

        self._root.title("Dental Home - Panel Principal")
        self._root.state('normal')
        
        # Set window size
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"{int(sw*0.8)}x{int(sh*0.8)}+{int(sw*0.1)}+{int(sh*0.1)}")

    def inicializar(self) -> None:
        # Layout estructural base de la aplicación
        self.sidebar = tk.Frame(self._root, bg=COLORS['dark'], width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Cabecera Corporativa del Sidebar
        tk.Label(self.sidebar, text="🦷 Dental Home", font=FONTS['subtitle'], fg=COLORS['white'], bg=COLORS['dark'], pady=20).pack()

        # Marco de Contenido Principal (Frame Dinámico Intercambiable)
        self.contenedor_principal = tk.Frame(self._root, bg=COLORS['background'])
        self.contenedor_principal.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._renderizar_opciones_por_rol()
        self._iniciar_control_inactividad()

    def _renderizar_opciones_por_rol(self) -> None:
        rol = self._usuario.rol
        
        # Matriz de accesibilidad de módulos autorizados por rol de usuario
        modulos = ["Inicio", "Pacientes", "Citas"]
        if rol == "Administrador":
            modulos += ["Reportes", "Copias Seguridad", "Usuarios"]
        elif rol == "Doctor":
            modulos += ["Historial Clínico"]

        for m in modulos:
            if m not in self._vistas:
                continue
            btn = tk.Button(self.sidebar, text=f"  {m}", font=FONTS['body'], fg=COLORS['white'],
                            bg=COLORS['dark'], bd=0, anchor="w", cursor="hand2", pady=12,
                            command=self._vistas[m])
            btn.pack(fill=tk.X, padx=10)

        # Botón de desconexión segura en la base del sidebar
        tk.Button(self.sidebar, text="🚪 Cerrar Sesión", font=FONTS['body'], fg=COLORS['danger'],
                  bg=COLORS['dark'], bd=0, anchor="w", cursor="hand2", pady=12,
                  command=self._confirmar_salida).pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=20)

    # ------------------------------------------------------------------ #
    #  Expiración de sesión por inactividad (SESSION_TIMEOUT_MINUTES)
    # ------------------------------------------------------------------ #
    def _iniciar_control_inactividad(self) -> None:
        if self._timeout_ms <= 0:
            return
        for evento in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):
            self._root.bind_all(evento, self._reiniciar_temporizador_inactividad, add="+")
        self._programar_expiracion()

    def _programar_expiracion(self) -> None:
        self._cancelar_temporizador()
        try:
            self._timeout_id = self._root.after(self._timeout_ms, self._expirar_sesion)
        except tk.TclError:
            self._timeout_id = None

    def _reiniciar_temporizador_inactividad(self, event=None) -> None:
        self._programar_expiracion()

    def _cancelar_temporizador(self) -> None:
        if self._timeout_id is not None:
            try:
                self._root.after_cancel(self._timeout_id)
            except tk.TclError:
                pass
            self._timeout_id = None

    def _expirar_sesion(self) -> None:
        self._cancelar_temporizador()
        try:
            self._root.unbind_all("<Any-KeyPress>")
            self._root.unbind_all("<Any-Button>")
            self._root.unbind_all("<Motion>")
        except tk.TclError:
            pass
        messagebox.showinfo(
            "Sesión expirada",
            f"Su sesión se cerró por {SESSION_TIMEOUT_MINUTES} minutos de inactividad.",
        )
        self._on_logout()

    def _confirmar_salida(self) -> None:
        if messagebox.askyesno("Confirmar", "¿Está seguro de que desea cerrar la sesión actual?"):
            self._cancelar_temporizador()
            self._on_logout()
