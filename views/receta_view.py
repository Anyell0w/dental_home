import tkinter as tk
from utils.theme import COLORS, FONTS
from controllers.receta_controller import RecetaController


class RecetaView:
    """Las recetas se emiten desde Historial Clínico; esta vista solo informa el flujo."""

    def __init__(self, contenedor: tk.Frame, controller: RecetaController) -> None:
        self._contenedor: tk.Frame = contenedor
        self._controller: RecetaController = controller

    def inicializar(self) -> None:
        for widget in self._contenedor.winfo_children():
            widget.destroy()

        tk.Label(
            self._contenedor,
            text="Módulo de Recetas Médicas",
            font=FONTS["title"],
            bg=COLORS["background"],
        ).pack(pady=20)
        tk.Label(
            self._contenedor,
            text="Las recetas se emiten desde Historial Clínico → registro → Emitir / Ver receta.",
            font=FONTS["body"],
            bg=COLORS["background"],
            fg=COLORS["gray"],
        ).pack()
