from typing import Dict, Any, Tuple

COLORS: Dict[str, str] = {
    'primary': '#2A5C4D',      # Verde oscuro corporativo (Sidebar y botones primarios)
    'secondary': '#3A7A67',    # Verde medio
    'success': '#E8F5E9',      # Fondo verde claro (para etiquetas de estado)
    'success_text': '#2E7D32', # Texto verde oscuro (para etiquetas de estado)
    'danger': '#FFEBEE',       # Fondo rojo claro
    'danger_text': '#C62828',  # Texto rojo oscuro
    'warning': '#FFF8E1',
    'dark': '#1C1C1E',
    'gray': '#8E8E93',
    'gray_light': '#F4F6F5',   # Fondo general de la aplicación
    'background': '#F4F6F5',
    'white': '#FFFFFF',
    'border': '#E0E0E0'
}

FONTS: Dict[str, Tuple[str, int, str]] = {
    'large': ('Segoe UI', 24, 'bold'),
    'title': ('Segoe UI', 18, 'bold'),
    'subtitle': ('Segoe UI', 12, 'bold'),
    'body': ('Segoe UI', 10, 'normal'),
    'small': ('Segoe UI', 9, 'normal')
}

def configurar_treeview_styles(style_obj: Any) -> None:
    style_obj.theme_use("clam") # Permite mayor personalización
    
    style_obj.configure("Treeview",
                        background=COLORS['white'],
                        foreground=COLORS['dark'],
                        rowheight=40,
                        fieldbackground=COLORS['white'],
                        font=FONTS['body'],
                        borderwidth=0)
    
    style_obj.configure("Treeview.Heading",
                        background=COLORS['white'],
                        foreground=COLORS['gray'],
                        font=FONTS['subtitle'],
                        borderwidth=0,
                        relief="flat")
                        
    style_obj.map("Treeview", 
                  background=[('selected', '#E8F0ED')], 
                  foreground=[('selected', COLORS['primary'])])
