import tkinter as tk
from tkinter import ttk
from typing import Callable, Any
from utils.theme import COLORS, FONTS
from controllers.usuario_controller import UsuarioController

class LoginView:
    def __init__(self, root: tk.Tk, controller: UsuarioController, on_login_success: Callable[[Any], None]) -> None:
        self._root = root
        self._controller = controller
        self._on_success = on_login_success
        
        self._root.title("Dental Home - Sistema de Gestión Odontológica")
        self._root.config(bg=COLORS['white'])
        self._centrar_ventana(800, 500)
        self._root.bind("<Return>", lambda e: self._accion_iniciar_sesion())

    def _centrar_ventana(self, ancho: int, alto: int) -> None:
        sw, sh = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        self._root.geometry(f"{ancho}x{alto}+{(sw-ancho)//2}+{(sh-alto)//2}")

    def inicializar(self) -> None:
        # Contenedor Principal
        main_frame = tk.Frame(self._root, bg=COLORS['white'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Panel Izquierdo (Verde Corporativo)
        left_panel = tk.Frame(main_frame, bg=COLORS['primary'], width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        tk.Label(left_panel, text="🦷", font=("Segoe UI", 48), fg=COLORS['white'], bg=COLORS['primary']).pack(pady=(120, 10))
        tk.Label(left_panel, text="Dental Home", font=FONTS['large'], fg=COLORS['white'], bg=COLORS['primary']).pack()
        tk.Label(left_panel, text="La ficha clínica y la\nagenda del\nconsultorio, en un\nmismo lugar.", 
                 font=FONTS['subtitle'], fg=COLORS['white'], bg=COLORS['primary'], justify="left").pack(pady=40, padx=40, anchor="w")

        # Panel Derecho (Formulario)
        right_panel = tk.Frame(main_frame, bg=COLORS['white'])
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        form_container = tk.Frame(right_panel, bg=COLORS['white'])
        form_container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form_container, text="ACCESO AL SISTEMA", font=FONTS['small'], fg=COLORS['gray'], bg=COLORS['white']).pack(pady=(0, 5))
        tk.Label(form_container, text="INICIA SESIÓN", font=FONTS['title'], fg=COLORS['dark'], bg=COLORS['white']).pack(pady=(0, 30))

        tk.Label(form_container, text="NOMBRE DE USUARIO", font=FONTS['small'], fg=COLORS['gray'], bg=COLORS['white']).pack(anchor="w")
        self.entrada_usuario = tk.Entry(form_container, font=FONTS['body'], width=35, bg=COLORS['gray_light'], relief="flat")
        self.entrada_usuario.pack(fill=tk.X, pady=(5, 15), ipady=8)
        self.entrada_usuario.focus_set()

        tk.Label(form_container, text="CONTRASEÑA", font=FONTS['small'], fg=COLORS['gray'], bg=COLORS['white']).pack(anchor="w")
        self.entrada_contrasena = tk.Entry(form_container, font=FONTS['body'], show="*", width=35, bg=COLORS['gray_light'], relief="flat")
        self.entrada_contrasena.pack(fill=tk.X, pady=(5, 5), ipady=8)

        self.etiqueta_error = tk.Label(form_container, text="", font=FONTS['small'], fg=COLORS['danger_text'], bg=COLORS['white'])
        self.etiqueta_error.pack(pady=5)

        btn_login = tk.Button(form_container, text="INICIAR SESIÓN", font=FONTS['subtitle'], bg=COLORS['primary'],
                              fg=COLORS['white'], bd=0, cursor="hand2", command=self._accion_iniciar_sesion)
        btn_login.pack(fill=tk.X, pady=20, ipady=10)

    def _accion_iniciar_sesion(self) -> None:
        user, clv = self.entrada_usuario.get().strip(), self.entrada_contrasena.get().strip()
        if not user or not clv:
            self.mostrar_error("Complete todos los campos.")
            return

        usuario_autenticado = self._controller.iniciar_sesion(user, clv)
        if usuario_autenticado:
            self.entrada_usuario.delete(0, tk.END)
            self.entrada_contrasena.delete(0, tk.END)
            self.etiqueta_error.config(text="")
            self._on_success(usuario_autenticado)
        else:
            self.mostrar_error("Credenciales inválidas.")

    def mostrar_error(self, mensaje: str) -> None:
        self.etiqueta_error.config(text=mensaje)
