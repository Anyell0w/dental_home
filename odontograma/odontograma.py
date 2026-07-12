# -*- coding: utf-8 -*-
"""
Odontograma autonomo (standalone).

- No necesita imagenes externas: los dientes se dibujan con codigo.
- No necesita MySQL ni ninguna base de datos.
- Permite marcar condiciones por diente y por superficie.
- Exporta el odontograma a PNG y PDF (requiere Pillow para exportar).

Ejecutar:
    python odontograma.py

Numeracion FDI (denticion permanente / adulto).
"""

import json
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ---------------------------------------------------------------------------
# Geometria / disposicion del odontograma
# ---------------------------------------------------------------------------
CELL = 42          # tamano de cada diente (cuadrado)
GAP = 6            # separacion entre dientes contiguos
MID = 24           # separacion extra en la linea media
MARGIN_X = 30      # margen izquierdo/derecho

UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]

TOP_NUM_Y = 28
TOP_CELL_Y0 = 42
TOP_CELL_Y1 = TOP_CELL_Y0 + CELL
BOT_CELL_Y0 = TOP_CELL_Y1 + 70
BOT_CELL_Y1 = BOT_CELL_Y0 + CELL
BOT_NUM_Y = BOT_CELL_Y1 + 14

CHART_W = MARGIN_X * 2 + 16 * (CELL + GAP) - GAP + MID
CHART_H = BOT_NUM_Y + 20


def _col_x(i):
    x = MARGIN_X + i * (CELL + GAP)
    if i >= 8:
        x += MID
    return x


def build_layout():
    layout = {}
    for i, num in enumerate(UPPER):
        x0 = _col_x(i)
        layout[num] = {"x0": x0, "y0": TOP_CELL_Y0, "x1": x0 + CELL,
                       "y1": TOP_CELL_Y1, "num_y": TOP_NUM_Y, "row": "upper"}
    for i, num in enumerate(LOWER):
        x0 = _col_x(i)
        layout[num] = {"x0": x0, "y0": BOT_CELL_Y0, "x1": x0 + CELL,
                       "y1": BOT_CELL_Y1, "num_y": BOT_NUM_Y, "row": "lower"}
    return layout


LAYOUT = build_layout()


# ---------------------------------------------------------------------------
# Condiciones que se pueden marcar
# scope: 'surface' (una cara), 'whole' (todo el diente), 'erase' (borrar)
# ---------------------------------------------------------------------------
CONDITIONS = [
    {"key": "caries",       "label": "Caries",              "color": "#e53935", "scope": "surface"},
    {"key": "restauracion", "label": "Restauracion",        "color": "#1e88e5", "scope": "surface"},
    {"key": "sellante",     "label": "Sellante",            "color": "#43a047", "scope": "surface"},
    {"key": "corona",       "label": "Corona",              "color": "#8e24aa", "scope": "whole"},
    {"key": "endodoncia",   "label": "Endodoncia",          "color": "#fb8c00", "scope": "whole"},
    {"key": "extraccion",   "label": "Extraccion indicada", "color": "#d32f2f", "scope": "whole"},
    {"key": "ausente",      "label": "Ausente / Extraido",  "color": "#757575", "scope": "whole"},
    {"key": "implante",     "label": "Implante",            "color": "#00897b", "scope": "whole"},
    {"key": "erase",        "label": "Borrar diente",       "color": "#ffffff", "scope": "erase"},
]
COND_MAP = {c["key"]: c for c in CONDITIONS}

SURFACE_ORDER = ["V", "M", "O", "D", "L"]


def surface_polys(x0, y0, x1, y1):
    """Devuelve los 5 poligonos (caras) de un diente."""
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    ins = (x1 - x0) * 0.22
    ax0, ay0, ax1, ay1 = cx - ins, cy - ins, cx + ins, cy + ins
    return {
        "V": [(x0, y0), (x1, y0), (ax1, ay0), (ax0, ay0)],   # vestibular (arriba)
        "D": [(x1, y0), (x1, y1), (ax1, ay1), (ax1, ay0)],   # distal (derecha)
        "L": [(x1, y1), (x0, y1), (ax0, ay1), (ax1, ay1)],   # lingual/palatino (abajo)
        "M": [(x0, y1), (x0, y0), (ax0, ay0), (ax0, ay1)],   # mesial (izquierda)
        "O": [(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)],  # oclusal/incisal (centro)
    }


def hit_surface(px, py, x0, y0, x1, y1):
    """Determina que cara fue clicada dentro de un diente."""
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    ins = (x1 - x0) * 0.22
    dx, dy = px - cx, py - cy
    if abs(dx) < ins and abs(dy) < ins:
        return "O"
    if abs(dx) >= abs(dy):
        return "D" if dx > 0 else "M"
    return "L" if dy > 0 else "V"


# ---------------------------------------------------------------------------
# Painters: mismo dibujo sobre Tk Canvas (interactivo) o sobre Pillow (export)
# ---------------------------------------------------------------------------
class TkPainter:
    def __init__(self, canvas):
        self.c = canvas

    def polygon(self, pts, fill, outline, width=1):
        flat = [coord for p in pts for coord in p]
        self.c.create_polygon(*flat, fill=fill or "", outline=outline or "", width=width)

    def line(self, x0, y0, x1, y1, fill, width=1):
        self.c.create_line(x0, y0, x1, y1, fill=fill, width=width)

    def ellipse(self, x0, y0, x1, y1, fill, outline, width=1):
        self.c.create_oval(x0, y0, x1, y1, fill=fill or "", outline=outline or "", width=width)

    def text(self, x, y, text, fill="black", size=10, bold=False, anchor="center"):
        font = ("Arial", int(size), "bold" if bold else "normal")
        self.c.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)


_PIL_FONT_CACHE = {}


def _get_pil_font(px, bold):
    from PIL import ImageFont
    key = (int(px), bold)
    if key in _PIL_FONT_CACHE:
        return _PIL_FONT_CACHE[key]
    candidates = (["arialbd.ttf", "C:/Windows/Fonts/arialbd.ttf", "DejaVuSans-Bold.ttf"]
                  if bold else
                  ["arial.ttf", "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"])
    font = None
    for name in candidates:
        try:
            font = ImageFont.truetype(name, int(px))
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _PIL_FONT_CACHE[key] = font
    return font


class PILPainter:
    _ANCHOR = {"center": "mm", "w": "lm", "e": "rm", "n": "ma", "s": "ms"}

    def __init__(self, draw, scale):
        self.d = draw
        self.s = scale

    def _sc(self, v):
        return v * self.s

    def polygon(self, pts, fill, outline, width=1):
        spts = [(p[0] * self.s, p[1] * self.s) for p in pts]
        try:
            self.d.polygon(spts, fill=fill, outline=outline, width=max(1, int(width * self.s)))
        except TypeError:
            self.d.polygon(spts, fill=fill, outline=outline)

    def line(self, x0, y0, x1, y1, fill, width=1):
        self.d.line([(x0 * self.s, y0 * self.s), (x1 * self.s, y1 * self.s)],
                    fill=fill, width=max(1, int(width * self.s)))

    def ellipse(self, x0, y0, x1, y1, fill, outline, width=1):
        self.d.ellipse([x0 * self.s, y0 * self.s, x1 * self.s, y1 * self.s],
                       fill=fill, outline=outline, width=max(1, int(width * self.s)))

    def text(self, x, y, text, fill="black", size=10, bold=False, anchor="center"):
        font = _get_pil_font(size * self.s, bold)
        try:
            self.d.text((x * self.s, y * self.s), text, fill=fill, font=font,
                        anchor=self._ANCHOR.get(anchor, "mm"))
        except TypeError:
            self.d.text((x * self.s, y * self.s), text, fill=fill, font=font)


# ---------------------------------------------------------------------------
# Dibujo del odontograma (compartido por Tk y Pillow)
# ---------------------------------------------------------------------------
def draw_tooth(painter, num, geo, tstate, ox, oy):
    x0, y0 = geo["x0"] + ox, geo["y0"] + oy
    x1, y1 = geo["x1"] + ox, geo["y1"] + oy
    surfaces = tstate.get("surf", {})
    whole = tstate.get("whole", set())
    ausente = "ausente" in whole

    polys = surface_polys(x0, y0, x1, y1)
    for s in SURFACE_ORDER:
        if ausente:
            fill = "#d9d9d9"
        else:
            key = surfaces.get(s)
            fill = COND_MAP[key]["color"] if key else "#ffffff"
        painter.polygon(polys[s], fill=fill, outline="#333333", width=1)

    if ausente:
        painter.line(x0, y0, x1, y1, fill="#616161", width=3)
        painter.line(x1, y0, x0, y1, fill="#616161", width=3)
    if "extraccion" in whole:
        painter.line(x0, y0, x1, y1, fill=COND_MAP["extraccion"]["color"], width=3)
        painter.line(x1, y0, x0, y1, fill=COND_MAP["extraccion"]["color"], width=3)
    if "corona" in whole:
        painter.ellipse(x0 - 3, y0 - 3, x1 + 3, y1 + 3, fill=None,
                        outline=COND_MAP["corona"]["color"], width=2)
    if "endodoncia" in whole:
        cx = (x0 + x1) / 2.0
        painter.line(cx, y0, cx, y1, fill=COND_MAP["endodoncia"]["color"], width=3)
    if "implante" in whole:
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        painter.text(cx, cy, "I", fill=COND_MAP["implante"]["color"],
                     size=int(CELL * 0.55), bold=True)

    cx = (x0 + x1) / 2.0
    painter.text(cx, geo["num_y"] + oy, str(num), fill="black", size=9, bold=True)


def draw_chart(painter, teeth, ox=0, oy=0):
    for num, geo in LAYOUT.items():
        draw_tooth(painter, num, geo, teeth.get(num, {}), ox, oy)


# ---------------------------------------------------------------------------
# Serializacion del estado (para persistir en base de datos)
#   estructura interna: {num:int -> {'surf': {cara: cond}, 'whole': set()}}
#   estructura JSON:     {"num": {"surf": {...}, "whole": [...]}}
# ---------------------------------------------------------------------------
def estado_a_dict(teeth):
    """Convierte el estado interno a un dict serializable (sets -> listas)."""
    out = {}
    for num, st in teeth.items():
        surf = st.get("surf", {}) or {}
        whole = st.get("whole", set()) or set()
        if not surf and not whole:
            continue  # no se guardan dientes sin marcas
        out[str(num)] = {"surf": dict(surf), "whole": sorted(whole)}
    return out


def estado_a_json(teeth):
    """Serializa el estado del odontograma a una cadena JSON."""
    return json.dumps(estado_a_dict(teeth), ensure_ascii=False)


def json_a_estado(cadena):
    """Reconstruye el estado interno a partir de una cadena JSON."""
    teeth = {}
    if not cadena:
        return teeth
    try:
        data = json.loads(cadena)
    except (ValueError, TypeError):
        return teeth
    if not isinstance(data, dict):
        return teeth
    for k, v in data.items():
        try:
            num = int(k)
        except (ValueError, TypeError):
            continue
        if not isinstance(v, dict):
            continue
        surf = dict(v.get("surf", {}) or {})
        whole = set(v.get("whole", []) or [])
        teeth[num] = {"surf": surf, "whole": whole}
    return teeth


# ---------------------------------------------------------------------------
# Exportacion headless (sin ventana): dibuja el odontograma en PNG o PDF
# ---------------------------------------------------------------------------
def render_imagen(teeth, path, paciente="", fecha="", kind="png", scale=3):
    """Renderiza el odontograma completo (con leyenda) a un archivo PNG/PDF.

    Requiere Pillow. Lanza ImportError si no esta instalado.
    """
    from PIL import Image, ImageDraw

    header_h = 64
    cols = 2
    rows = (len(CONDITIONS) + cols - 1) // cols
    legend_h = 34 + rows * 24 + 10
    total_w = CHART_W
    total_h = header_h + CHART_H + legend_h

    img = Image.new("RGB", (int(total_w * scale), int(total_h * scale)), "white")
    painter = PILPainter(ImageDraw.Draw(img), scale)

    painter.text(total_w / 2, 20, "ODONTOGRAMA", fill="#00695c",
                 size=18, bold=True, anchor="center")
    painter.text(MARGIN_X, 46, "Paciente: " + (paciente or "-"),
                 fill="black", size=11, anchor="w")
    painter.text(total_w - MARGIN_X, 46, "Fecha: " + (fecha or "-"),
                 fill="black", size=11, anchor="e")

    draw_chart(painter, teeth, ox=0, oy=header_h)

    legend_y = header_h + CHART_H
    painter.line(MARGIN_X, legend_y + 4, total_w - MARGIN_X, legend_y + 4,
                 fill="#cccccc", width=1)
    painter.text(MARGIN_X, legend_y + 18, "Leyenda", fill="black", size=11,
                 bold=True, anchor="w")
    for i, c in enumerate(CONDITIONS):
        col, row = i % cols, i // cols
        x = MARGIN_X + col * 300
        y = legend_y + 40 + row * 24
        sw = "#ffffff" if c["scope"] == "erase" else c["color"]
        painter.polygon([(x, y - 8), (x + 16, y - 8), (x + 16, y + 8), (x, y + 8)],
                        fill=sw, outline="#333333", width=1)
        painter.text(x + 24, y, c["label"], fill="black", size=10, anchor="w")

    if kind == "pdf":
        img.save(path, "PDF", resolution=200.0)
    else:
        img.save(path, "PNG")
    return path


# ---------------------------------------------------------------------------
# Widget embebible: odontograma interactivo dentro de otra vista (historial)
# ---------------------------------------------------------------------------
class OdontogramaWidget(tk.Frame):
    """Odontograma interactivo reutilizable como componente de una vista.

    Metodos publicos clave:
      - cargar_estado(json_str): pinta el estado guardado del paciente.
      - obtener_estado_json(): devuelve el estado actual serializado.
      - exportar(path, paciente, fecha, kind): genera PNG/PDF del odontograma.
      - tiene_marcas(): indica si hay al menos un diente marcado.
      - limpiar(): borra todas las marcas.
    """

    def __init__(self, master, bg="#FFFFFF", on_change=None,
                 accent="#2A5C4D", accent_soft="#E8F0ED", **kw):
        super().__init__(master, bg=bg, **kw)
        self._bg = bg
        self._accent = accent          # verde corporativo de la app
        self._accent_soft = accent_soft
        self.teeth = {}
        self.current = tk.StringVar(value="caries")
        self._on_change = on_change
        self._cond_rows = {}           # key -> frame (para resaltar selección)
        self._build()
        self.redraw()

    def _build(self):
        # ---- Lienzo del odontograma ------------------------------------
        left = tk.Frame(self, bg=self._bg)
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, width=CHART_W, height=CHART_H,
                                bg="#FBFDFC", highlightthickness=1,
                                highlightbackground=self._accent)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.on_click(e, left_btn=True))
        self.canvas.bind("<Button-3>", lambda e: self.on_click(e, left_btn=False))
        tk.Label(left, bg=self._bg, fg="#6B7B76",
                 text=("Elige una condición y haz clic sobre el diente o su cara.   "
                       "Clic derecho = borrar ese diente."),
                 font=("Segoe UI", 9)).pack(pady=(8, 0))

        # ---- Panel de condiciones (tarjeta) ----------------------------
        right = tk.Frame(self, bg=self._bg)
        right.pack(side="left", fill="y", padx=(16, 0))

        card = tk.Frame(right, bg="white", highlightthickness=1,
                        highlightbackground=self._accent_soft)
        card.pack(fill="y")

        cab = tk.Frame(card, bg=self._accent)
        cab.pack(fill="x")
        tk.Label(cab, text="CONDICIONES", bg=self._accent, fg="white",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=6)

        for c in CONDITIONS:
            row = tk.Frame(card, bg="white", cursor="hand2")
            row.pack(fill="x", padx=6, pady=1)
            sw = "#ffffff" if c["scope"] == "erase" else c["color"]
            tk.Label(row, width=2, bg=sw, relief="solid", bd=1).pack(
                side="left", padx=(6, 0), pady=3)
            rb = tk.Radiobutton(
                row, text=c["label"], value=c["key"], variable=self.current,
                bg="white", activebackground="white",
                selectcolor="white", anchor="w", font=("Segoe UI", 10),
                highlightthickness=0, bd=0,
                command=self._resaltar_condicion,
            )
            rb.pack(side="left", padx=4, fill="x", expand=True)
            # Clic en cualquier parte de la fila selecciona la condición
            for w in (row, rb):
                w.bind("<Button-1>", lambda e, k=c["key"]: self._seleccionar_condicion(k))
            self._cond_rows[c["key"]] = row

        self._resaltar_condicion()

    def _seleccionar_condicion(self, key):
        self.current.set(key)
        self._resaltar_condicion()

    def _resaltar_condicion(self):
        activo = self.current.get()
        for key, row in self._cond_rows.items():
            color = self._accent_soft if key == activo else "white"
            row.config(bg=color)
            for hijo in row.winfo_children():
                if isinstance(hijo, tk.Radiobutton):
                    hijo.config(bg=color, activebackground=color, selectcolor=color)

    # -- interaccion ------------------------------------------------------
    def _state(self, num):
        return self.teeth.setdefault(num, {"surf": {}, "whole": set()})

    def on_click(self, event, left_btn):
        for num, geo in LAYOUT.items():
            if geo["x0"] <= event.x <= geo["x1"] and geo["y0"] <= event.y <= geo["y1"]:
                if not left_btn:
                    self.teeth[num] = {"surf": {}, "whole": set()}
                else:
                    self._apply(num, event.x, event.y)
                self.redraw()
                self._changed()
                return

    def _apply(self, num, px, py):
        cond = COND_MAP[self.current.get()]
        st = self._state(num)
        if cond["scope"] == "erase":
            self.teeth[num] = {"surf": {}, "whole": set()}
        elif cond["scope"] == "surface":
            geo = LAYOUT[num]
            s = hit_surface(px, py, geo["x0"], geo["y0"], geo["x1"], geo["y1"])
            if st["surf"].get(s) == cond["key"]:
                del st["surf"][s]
            else:
                st["surf"][s] = cond["key"]
        else:  # whole
            if cond["key"] in st["whole"]:
                st["whole"].discard(cond["key"])
            else:
                st["whole"].add(cond["key"])

    def _changed(self):
        if callable(self._on_change):
            self._on_change()

    def redraw(self):
        self.canvas.delete("all")
        self._dibujar_guias()
        draw_chart(TkPainter(self.canvas), self.teeth)

    def _dibujar_guias(self):
        """Decoración de fondo: arcadas, línea media y rótulos de orientación."""
        c = self.canvas
        # Franjas suaves para arcada superior e inferior
        c.create_rectangle(MARGIN_X - 10, TOP_CELL_Y0 - 4,
                           CHART_W - MARGIN_X + 10, TOP_CELL_Y1 + 4,
                           fill="#F1F6F4", outline="")
        c.create_rectangle(MARGIN_X - 10, BOT_CELL_Y0 - 4,
                           CHART_W - MARGIN_X + 10, BOT_CELL_Y1 + 4,
                           fill="#F1F6F4", outline="")

        # Línea media vertical (separa lado derecho / izquierdo del paciente)
        mid_x = _col_x(8) - (GAP + MID) / 2.0
        c.create_line(mid_x, TOP_CELL_Y0 - 12, mid_x, BOT_CELL_Y1 + 12,
                     fill="#B9C8C2", dash=(4, 3))

        # Línea media horizontal (separa superior / inferior)
        mid_y = (TOP_CELL_Y1 + BOT_CELL_Y0) / 2.0
        c.create_line(MARGIN_X - 10, mid_y, CHART_W - MARGIN_X + 10, mid_y,
                     fill="#B9C8C2", dash=(4, 3))

        # Rótulos de arcada
        c.create_text(MARGIN_X - 16, (TOP_CELL_Y0 + TOP_CELL_Y1) / 2.0,
                     text="SUP.", fill=self._accent, font=("Segoe UI", 7, "bold"),
                     angle=90)
        c.create_text(MARGIN_X - 16, (BOT_CELL_Y0 + BOT_CELL_Y1) / 2.0,
                     text="INF.", fill=self._accent, font=("Segoe UI", 7, "bold"),
                     angle=90)

    # -- API publica ------------------------------------------------------
    def limpiar(self):
        self.teeth = {}
        self.redraw()
        self._changed()

    def cargar_estado(self, json_str):
        self.teeth = json_a_estado(json_str)
        self.redraw()

    def obtener_estado_json(self):
        return estado_a_json(self.teeth)

    def tiene_marcas(self):
        return bool(estado_a_dict(self.teeth))

    def exportar(self, path, paciente="", fecha="", kind="png"):
        return render_imagen(self.teeth, path, paciente=paciente,
                             fecha=fecha, kind=kind)


# ---------------------------------------------------------------------------
# Aplicacion
# ---------------------------------------------------------------------------
class OdontogramaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Odontograma")
        self.root.configure(bg="#f4f6f8")

        self.teeth = {}          # num -> {'surf': {cara: cond}, 'whole': set()}
        self.current = tk.StringVar(value="caries")

        self._build_header()
        self._build_body()
        self.redraw()

    # -- construccion de la interfaz --------------------------------------
    def _build_header(self):
        top = tk.Frame(self.root, bg="#00695c")
        top.pack(fill="x")
        tk.Label(top, text="ODONTOGRAMA", bg="#00695c", fg="white",
                 font=("Arial", 16, "bold")).pack(side="left", padx=16, pady=10)

        form = tk.Frame(self.root, bg="#f4f6f8")
        form.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(form, text="Paciente:", bg="#f4f6f8").pack(side="left")
        self.paciente = tk.Entry(form, width=32)
        self.paciente.pack(side="left", padx=(4, 20))
        tk.Label(form, text="Fecha:", bg="#f4f6f8").pack(side="left")
        self.fecha = tk.Entry(form, width=14)
        self.fecha.insert(0, datetime.date.today().strftime("%d/%m/%Y"))
        self.fecha.pack(side="left", padx=4)

    def _build_body(self):
        body = tk.Frame(self.root, bg="#f4f6f8")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Lienzo del odontograma
        left = tk.Frame(body, bg="#f4f6f8")
        left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, width=CHART_W, height=CHART_H,
                                bg="white", highlightthickness=1,
                                highlightbackground="#cfd8dc")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.on_click(e, left_btn=True))
        self.canvas.bind("<Button-3>", lambda e: self.on_click(e, left_btn=False))

        tk.Label(left, bg="#f4f6f8", fg="#555",
                 text=("Elige una condicion y haz clic en un diente.  "
                       "Clic derecho = borrar ese diente."),
                 font=("Arial", 9)).pack(pady=(8, 0))

        # Panel de herramientas
        right = tk.Frame(body, bg="#f4f6f8")
        right.pack(side="left", fill="y", padx=(16, 0))
        tk.Label(right, text="Condiciones", bg="#f4f6f8",
                 font=("Arial", 11, "bold")).pack(anchor="w")

        for c in CONDITIONS:
            row = tk.Frame(right, bg="#f4f6f8")
            row.pack(fill="x", pady=1)
            sw = "#ffffff" if c["scope"] == "erase" else c["color"]
            tk.Label(row, width=2, bg=sw, relief="solid", bd=1).pack(side="left")
            tk.Radiobutton(row, text=c["label"], value=c["key"],
                           variable=self.current, bg="#f4f6f8",
                           anchor="w").pack(side="left", padx=4)

        actions = tk.Frame(right, bg="#f4f6f8")
        actions.pack(fill="x", pady=(16, 0))
        tk.Button(actions, text="Exportar PNG", width=18,
                  command=lambda: self.export("png")).pack(pady=3)
        tk.Button(actions, text="Exportar PDF", width=18,
                  command=lambda: self.export("pdf")).pack(pady=3)
        tk.Button(actions, text="Limpiar todo", width=18,
                  command=self.clear_all).pack(pady=3)

    # -- logica -----------------------------------------------------------
    def _state(self, num):
        return self.teeth.setdefault(num, {"surf": {}, "whole": set()})

    def on_click(self, event, left_btn):
        for num, geo in LAYOUT.items():
            if geo["x0"] <= event.x <= geo["x1"] and geo["y0"] <= event.y <= geo["y1"]:
                if not left_btn:
                    self.teeth[num] = {"surf": {}, "whole": set()}
                    self.redraw()
                    return
                self._apply(num, event.x, event.y)
                self.redraw()
                return

    def _apply(self, num, px, py):
        cond = COND_MAP[self.current.get()]
        st = self._state(num)
        if cond["scope"] == "erase":
            self.teeth[num] = {"surf": {}, "whole": set()}
        elif cond["scope"] == "surface":
            geo = LAYOUT[num]
            s = hit_surface(px, py, geo["x0"], geo["y0"], geo["x1"], geo["y1"])
            if st["surf"].get(s) == cond["key"]:
                del st["surf"][s]          # segundo clic desmarca
            else:
                st["surf"][s] = cond["key"]
        else:  # whole
            if cond["key"] in st["whole"]:
                st["whole"].discard(cond["key"])
            else:
                st["whole"].add(cond["key"])

    def clear_all(self):
        if messagebox.askyesno("Limpiar", "Borrar todas las marcas del odontograma?"):
            self.teeth = {}
            self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        draw_chart(TkPainter(self.canvas), self.teeth)

    # -- exportacion ------------------------------------------------------
    def export(self, kind):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            messagebox.showerror(
                "Falta Pillow",
                "Para exportar necesitas instalar Pillow:\n\n    pip install Pillow")
            return

        ext = ".png" if kind == "png" else ".pdf"
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[("PNG", "*.png")] if kind == "png" else [("PDF", "*.pdf")],
            initialfile="odontograma" + ext)
        if not path:
            return

        try:
            render_imagen(self.teeth, path, paciente=self.paciente.get(),
                          fecha=self.fecha.get(), kind=kind)
        except Exception as exc:
            messagebox.showerror("Error al exportar", str(exc))
            return
        messagebox.showinfo("Listo", "Odontograma guardado en:\n" + path)


def main():
    root = tk.Tk()
    OdontogramaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
