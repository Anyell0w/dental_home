"""Genera docs/brief-corporativo-dental-home.pdf  ->  python docs/brief_corporativo.py
Todas las cifras de proyección salen del modelo de este archivo (supuestos en SUPUESTOS)."""
import os

from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.fonts import addMapping

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "brief-corporativo-dental-home.pdf")
FUENTES = "/usr/share/fonts/truetype/liberation/LiberationSans-"
for nombre, archivo in (("S", "Regular"), ("SB", "Bold"), ("SI", "Italic"), ("SBI", "BoldItalic")):
    pdfmetrics.registerFont(TTFont(nombre, FUENTES + archivo + ".ttf"))
pdfmetrics.registerFontFamily("S", normal="S", bold="SB", italic="SI", boldItalic="SBI")

W, H, MX = 960, 540, 64
INK, INK2, MUTED, LINE = HexColor("#1D1D1F"), HexColor("#424245"), HexColor("#6E6E73"), HexColor("#D2D2D7")
BG, SURF, SOFT = HexColor("#FBFBFD"), HexColor("#FFFFFF"), HexColor("#F5F5F7")
BRAND, BRAND2, BRANDINK = HexColor("#12B5A5"), HexColor("#3AA7F0"), HexColor("#0B7F74")
BRANDSOFT, WARN, BAD, DARK = HexColor("#E3F6F3"), HexColor("#F0A13A"), HexColor("#E5484D"), HexColor("#05090B")

MESES = ["Nov 26", "Dic", "Ene 27", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct 27"]

# ----------------------------------------------------------------------------------------------
# Modelo financiero (soles). Todo lo que se muestra en el brief deriva de aquí.
# ----------------------------------------------------------------------------------------------
PLANES = [("Esencial", 59, 0.45), ("Profesional", 129, 0.45), ("Clínica", 249, 0.10)]
ARPU = sum(p * m for _, p, m in PLANES)
COMISION = 0.04            # pasarela de pago sobre ingresos (supuesto)
CONTINGENCIA = 0.10
TRIALS = [0, 0, 10, 14, 24, 32, 40, 44, 48, 52, 56, 60]   # pruebas gratuitas iniciadas por mes
RUBROS = ["Producto, seguridad y mantenimiento", "Infraestructura y backups", "Legal y datos personales",
          "Marketing y adquisición", "Ventas, onboarding y soporte"]


def costo_rubros(i):
    """Costo del mes i (0-based) por rubro, sin contingencia."""
    return [4000 if i < 6 else 1500, 450, 3000 if i < 2 else 0, 1500 if i < 2 else 2700, 0 if i < 2 else 2400]


def simular(escala=1.0, conv=0.25, conv_piloto=0.60, churn=0.03, horizonte=36):
    trials = [t * escala for t in TRIALS] + [TRIALS[-1] * escala] * (horizonte - 12)
    base, nuevos, mrr, costo, neto, acum = [], [], [], [], [], []
    for i in range(horizonte):
        n = trials[i - 1] * (conv_piloto if i - 1 == 2 else conv) if i >= 1 else 0
        b = (base[-1] if base else 0) * (1 - churn) + n
        c = sum(costo_rubros(i)) * (1 + CONTINGENCIA)
        m = b * ARPU
        nt = m * (1 - COMISION) - c
        base.append(b); nuevos.append(n); mrr.append(m); costo.append(c); neto.append(nt)
        acum.append((acum[-1] if acum else 0) + nt)
    eq = next((i + 1 for i in range(horizonte) if neto[i] >= 0 and i >= 6), None)
    pb = next((i + 1 for i in range(horizonte) if acum[i] >= 0 and i >= 6), None)
    return dict(base=base, nuevos=nuevos, mrr=mrr, costo=costo, neto=neto, acum=acum, eq=eq, pb=pb,
                caja=-min(acum))


BASE = simular()
CONSERV = simular(0.6, 0.18, 0.45, 0.045)
OPTIM = simular(1.3, 0.30, 0.70, 0.025)
TOT_RUBROS = [sum(costo_rubros(i)[k] for i in range(12)) for k in range(5)]
SUBTOTAL = sum(TOT_RUBROS)
CONT = SUBTOTAL * CONTINGENCIA
TOTAL = SUBTOTAL + CONT
FASE1 = sum(BASE["costo"][:2])
CLI12, MRR12 = BASE["base"][11], BASE["mrr"][11]
CLI6 = BASE["base"][5]
NUEVOS12 = sum(BASE["nuevos"][:12])
CAC = (TOT_RUBROS[3] + TOT_RUBROS[4]) / NUEVOS12
LTV = ARPU * 0.90 / 0.03


def s(n):  # S/ 1,234
    return f"S/ {n:,.0f}"


def mes(n):
    return "más allá del mes 36" if n is None else f"mes {n} ({MESES[n - 1] if n <= 12 else 'año ' + str(2026 + (n + 9) // 12)})"


# ----------------------------------------------------------------------------------------------
# Primitivas de dibujo
# ----------------------------------------------------------------------------------------------
def Ac(color, a):
    return Color(color.red, color.green, color.blue, alpha=a)


def alpha(c, a):
    c.setFillAlpha(a); c.setStrokeAlpha(a)


def T(c, txt, x, top, size=12, color=INK, font="S", anchor="l", space=0):
    y = H - top
    if space:
        t = c.beginText(x, y); t.setFont(font, size); t.setFillColor(color); t.setCharSpace(space); t.textOut(txt); t.setCharSpace(0); c.drawText(t)
        return
    c.setFont(font, size); c.setFillColor(color)
    {"l": c.drawString, "r": c.drawRightString, "c": c.drawCentredString}[anchor](x, y, txt)


def P(c, txt, x, top, w, size=12, color=INK2, lead=None, font="S", align=0):
    st = ParagraphStyle("p", fontName=font, fontSize=size, leading=lead or size * 1.42, textColor=color, alignment=align)
    p = Paragraph(txt, st); _, h = p.wrap(w, 2000); p.drawOn(c, x, H - top - h)
    return h


def card(c, x, top, w, h, fill=SURF, stroke=LINE, r=14, shadow=True):
    y = H - top - h
    if shadow:
        for k in range(4):
            c.setFillColor(Color(0, 0, 0, alpha=0.018))
            c.roundRect(x - k + 0, y - 2 - k * 1.4, w + 2 * k, h + 2 * k, r + k, stroke=0, fill=1)
        alpha(c, 1)
    c.setFillColor(fill); c.setStrokeColor(stroke or fill); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1)


def grad_rect(c, x, top, w, h, r, c1=BRAND, c2=BRAND2, vertical=False):
    y = H - top - h
    c.saveState(); c.setFillAlpha(1); p = c.beginPath(); p.roundRect(x, y, w, h, r); c.clipPath(p, stroke=0, fill=0)
    if vertical:
        c.linearGradient(x, y + h, x, y, (c1, c2))
    else:
        c.linearGradient(x, y, x + w, y, (c1, c2))
    c.restoreState()


def pill(c, txt, x, top, color=BRANDINK, fill=BRANDSOFT, size=9.5):
    w = pdfmetrics.stringWidth(txt, "SB", size) + 18
    c.setFillColor(fill); c.roundRect(x, H - top - 20, w, 20, 10, stroke=0, fill=1)
    T(c, txt, x + 9, top + 14, size, color, "SB")
    return w


TOOTH = [((0.25, 1.05), (0.7, 1.28), (1.0, 1.12)), ((1.38, 0.92), (1.48, 0.42), (1.32, -0.02)),
         ((1.2, -0.4), (1.14, -0.85), (1.02, -1.3)), ((0.92, -1.78), (0.56, -1.82), (0.5, -1.36)),
         ((0.44, -0.95), (0.32, -0.62), (0, -0.62)), ((-0.32, -0.62), (-0.44, -0.95), (-0.5, -1.36)),
         ((-0.56, -1.82), (-0.92, -1.78), (-1.02, -1.3)), ((-1.14, -0.85), (-1.2, -0.4), (-1.32, -0.02)),
         ((-1.48, 0.42), (-1.38, 0.92), (-1.0, 1.12)), ((-0.7, 1.28), (-0.25, 1.05), (0, 0.78))]


def tooth(c, cx, cy, k, c1=HexColor("#FFFFFF"), c2=HexColor("#9FE9DF")):
    def path():
        p = c.beginPath(); p.moveTo(cx, cy + (0.78 + 0.27) * k)
        for a, b, d in TOOTH:
            p.curveTo(cx + a[0] * k, cy + (a[1] + 0.27) * k, cx + b[0] * k, cy + (b[1] + 0.27) * k,
                      cx + d[0] * k, cy + (d[1] + 0.27) * k)
        p.close(); return p
    c.saveState(); c.setFillAlpha(1); c.clipPath(path(), stroke=0, fill=0)
    c.linearGradient(cx - 1.4 * k, cy + 1.6 * k, cx + 1.2 * k, cy - 1.6 * k, (c1, c2)); c.restoreState()


def fondo(c, oscuro=False):
    c.setFillColor(DARK if oscuro else BG); c.rect(0, 0, W, H, stroke=0, fill=1)


def cabecera(c, n, kicker, titulo, sub=None, ancho=800):
    T(c, kicker.upper(), MX, 56, 9.5, BRANDINK, "SB", space=1.6)
    h = P(c, titulo, MX, 66, ancho, 31, INK, 36, "SB")
    if sub:
        P(c, sub, MX, 66 + h + 8, ancho - 40, 13.5, MUTED, 19)


def pie(c, n, total):
    tooth(c, MX + 6, 26, 5.2, HexColor("#12B5A5"), HexColor("#3AA7F0"))
    T(c, "Dental Home  ·  Brief corporativo  ·  Confidencial", MX + 20, 503 + 6, 8.5, MUTED)
    T(c, f"{n:02d} / {total:02d}", W - MX, 503 + 6, 8.5, MUTED, anchor="r")


def kpi(c, x, top, w, h, valor, etiqueta, nota=None, destacado=False):
    card(c, x, top, w, h, fill=INK if destacado else SURF, stroke=None if destacado else LINE)
    col, sub = (HexColor("#FFFFFF"), HexColor("#A1A1A6")) if destacado else (INK, MUTED)
    T(c, valor, x + 20, top + 44, 28, col, "SB")
    T(c, etiqueta, x + 20, top + 64, 11, col, "SB")
    if nota:
        P(c, nota, x + 20, top + 72, w - 40, 9.5, sub, 13)


# ----------------------------------------------------------------------------------------------
# Páginas
# ----------------------------------------------------------------------------------------------
def p_portada(c, n, total):
    fondo(c, True)
    for k in range(70):  # resplandor
        c.setFillColor(Ac(BRAND, 0.010)); c.circle(700, 250, 300 - k * 3.6, stroke=0, fill=1)
    for k in range(50):
        c.setFillColor(Ac(BRAND2, 0.010)); c.circle(790, 360, 210 - k * 3.6, stroke=0, fill=1)
    alpha(c, 1)
    tooth(c, 700, 262, 118)
    c.saveState(); c.setFillColor(Color(1, 1, 1, alpha=0.30))
    c.ellipse(655, 330, 690, 380, stroke=0, fill=1); c.restoreState(); alpha(c, 1)
    for (x, y, r, a) in [(560, 420, 2.4, .8), (860, 150, 3, .7), (590, 130, 1.8, .6), (850, 410, 2, .7),
                         (780, 460, 1.6, .6), (520, 300, 1.6, .5), (880, 280, 2.2, .6)]:
        c.setFillColor(Ac(HexColor("#7FF0E2"), a)); c.circle(x, y, r, stroke=0, fill=1)
    alpha(c, 1)
    T(c, "BRIEF CORPORATIVO  ·  2026", MX, 150, 10.5, BRAND, "SB", space=2)
    T(c, "Dental Home", MX, 232, 66, HexColor("#FFFFFF"), "SB")
    P(c, "El software que cuida tu consultorio.<br/>Simple, en el navegador y por suscripción.", MX, 262, 460, 20, HexColor("#A1A1A6"), 29)
    grad_rect(c, MX, 372, 120, 3, 1.5)
    T(c, "Octubre 2026  ·  v1.0  ·  Documento confidencial", MX, 480, 10, HexColor("#6E6E73"))


def p_resumen(c, n, total):
    fondo(c); cabecera(c, n, "01 · Resumen ejecutivo", "Gestión dental simple, en el navegador y por suscripción.")
    bloques = [("QUÉ ES", "Plataforma web para gestionar pacientes, citas, historial clínico, odontograma y recetas. "
                          "Evolución de una aplicación de escritorio ya validada en funciones."),
               ("PARA QUIÉN", "Consultorios dentales pequeños y medianos (1 a 10 usuarios) que hoy dependen de papel, "
                              "WhatsApp, Excel o un programa instalado en una sola PC."),
               ("CÓMO GANA DINERO", f"Suscripción mensual en soles desde S/ 59, con 14 días de prueba. Ingreso medio "
                                    f"esperado por clínica: ≈ {s(ARPU)} al mes."),
               ("QUÉ SE PIDE", f"Aprobar un presupuesto de {s(TOTAL)} a 12 meses, en fases con puntos de decisión, "
                               f"para pasar de producto funcional a negocio que cobra.")]
    y = 178
    for t, d in bloques:
        T(c, t, MX, y, 9, BRANDINK, "SB", space=1.4)
        h = P(c, d, MX, y + 8, 410, 12.5, INK2, 18)
        y += 8 + h + 22
    x0, w, h = 520, 184, 150
    kpi(c, x0, 170, w, h, "3 planes", "S/ 59 – 249 al mes", "Esencial, Profesional y Clínica")
    kpi(c, x0 + w + 16, 170, w, h, "14 días", "de prueba gratis", "Con las funciones del plan Profesional")
    kpi(c, x0, 170 + h + 16, w, h, s(TOTAL).replace("S/ ", "S/ "), "presupuesto a 12 meses", f"Fase 1 (2 meses): {s(FASE1)}")
    kpi(c, x0 + w + 16, 170 + h + 16, w, h, f"≈ {CLI12:.0f}", "clínicas de pago al mes 12", f"MRR ≈ {s(MRR12)} · escenario base", destacado=True)
    pie(c, n, total)


def p_empresa(c, n, total):
    fondo(c); cabecera(c, n, "02 · La empresa", "Tecnología que devuelve tiempo al odontólogo.")
    cols = [("Misión", "Que cualquier consultorio dental, sin importar su tamaño, trabaje con orden, datos seguros "
                       "y una herramienta agradable de usar, por el precio de un par de consultas al mes."),
            ("Visión", "Ser el sistema de gestión de referencia para consultorios independientes de "
                       "Latinoamérica, empezando por Perú."),
            ("Propuesta de valor", "Alta en minutos, sin instalación ni servidores. Interfaz moderna, precios públicos "
                                   "en soles, datos aislados por clínica y copias de seguridad incluidas.")]
    x, w = MX, 256
    for t, d in cols:
        card(c, x, 150, w, 178)
        T(c, t, x + 22, 186, 15, INK, "SB")
        grad_rect(c, x + 22, 196, 26, 3, 1.5)
        P(c, d, x + 22, 214, w - 44, 11.5, INK2, 17)
        x += w + 20
    card(c, MX, 350, 832, 128, fill=INK, stroke=None)
    T(c, "ESTADO ACTUAL", MX + 26, 382, 9, BRAND, "SB", space=1.4)
    P(c, "<b><font color='#FFFFFF'>Producto funcional (MVP completo).</font></b> Migración de la aplicación de escritorio "
         "(Python/Tkinter) a web (Flask, Alpine.js, three.js): pacientes, citas, historial, odontograma, recetas, "
         "reportes, copias, equipo y suscripciones con límites por plan.", MX + 26, 392, 380, 11, HexColor("#A1A1A6"), 16)
    T(c, "PENDIENTE PARA COBRAR", MX + 452, 382, 9, BRAND, "SB", space=1.4)
    P(c, "<b><font color='#FFFFFF'>Antes del lanzamiento comercial:</font></b> pasarela de pagos real (hoy el plan se "
         "activa en modo demostración), contraseñas con argon2/bcrypt, HTTPS, recuperación de clave por correo, "
         "backups externos y constitución legal de la empresa.", MX + 452, 392, 354, 11, HexColor("#A1A1A6"), 16)
    pie(c, n, total)


def p_producto(c, n, total):
    fondo(c); cabecera(c, n, "03 · El producto", "Todo lo que un consultorio necesita. Nada que sobre.")
    mods = [("Pacientes", "Fichas, búsqueda instantánea y estados."), ("Citas", "Agenda por día, semana y mes, sin cruces de horario."),
            ("Historial clínico", "Consultas, diagnósticos y tratamientos por paciente."),
            ("Odontograma", "32 piezas, 5 caras, 8 condiciones. Exporta a PNG."),
            ("Recetas", "Emisión y descarga en PDF con datos de la clínica."), ("Reportes", "PDF y Excel de atención y actividad."),
            ("Copias de seguridad", "Respaldo y restauración de la base de la clínica."),
            ("Equipo y roles", "Tres roles con permisos distintos.")]
    cw, ch, gx = 192, 118, 21.3
    for i, (t, d) in enumerate(mods):
        x, top = MX + (i % 4) * (cw + gx), 148 + (i // 4) * (ch + 16)
        card(c, x, top, cw, ch)
        grad_rect(c, x + 20, top + 20, 26, 26, 8, BRAND, BRAND2)
        T(c, f"{i + 1}", x + 33, top + 38, 12, HexColor("#FFFFFF"), "SB", "c")
        T(c, t, x + 20, top + 68, 13.5, INK, "SB")
        P(c, d, x + 20, top + 78, cw - 40, 10.5, MUTED, 14.5)
    T(c, "ARQUITECTURA", MX, 452, 9, BRANDINK, "SB", space=1.4)
    items = ["Una base de datos aislada por clínica", "Roles y permisos en servidor", "Límites de usuarios y pacientes por plan",
             "Modo solo lectura al vencer la suscripción"]
    x = MX
    for it in items:
        x += pill(c, it, x, 462, INK2, SOFT, 9.5) + 8
    pie(c, n, total)


def p_cliente(c, n, total):
    fondo(c); cabecera(c, n, "04 · Cliente y oportunidad", "Hoy se arreglan con herramientas que no escalan.")
    T(c, "DOLOR ACTUAL", MX, 160, 9, BRANDINK, "SB", space=1.4)
    T(c, "CÓMO LO RESUELVE DENTAL HOME", 500, 160, 9, BRANDINK, "SB", space=1.4)
    filas = [("Agenda en papel o WhatsApp; citas cruzadas y olvidadas", "Agenda visual con control de conflictos"),
             ("Historias clínicas en carpetas, difíciles de buscar", "Historial digital por paciente, en segundos"),
             ("Odontograma dibujado a mano o en archivos sueltos", "Odontograma interactivo y exportable"),
             ("Programa en una sola PC, sin acceso remoto ni copias", "Acceso desde cualquier dispositivo y copias incluidas")]
    top = 174
    for a, b in filas:
        card(c, MX, top, 396, 42, shadow=False, r=10); card(c, 500, top, 396, 42, fill=BRANDSOFT, stroke=None, shadow=False, r=10)
        P(c, a, MX + 16, top + 13, 366, 11, INK2, 15); P(c, b, 516, top + 13, 366, 11, BRANDINK, 15, "SB")
        T(c, "→", 475, top + 27, 14, MUTED, anchor="c")
        top += 52
    T(c, "TRES PERSONAS, UN MISMO SISTEMA", MX, 398, 9, BRANDINK, "SB", space=1.4)
    pers = [("Doctor", "Atiende, registra y receta. Quiere velocidad."), ("Secretaria", "Agenda y cobra. Quiere claridad."),
            ("Administrador", "Decide y controla. Quiere reportes.")]
    for k, (t, d) in enumerate(pers):
        x = MX + k * 288
        pill(c, t, x, 408, BRANDINK, BRANDSOFT, 10)
        T(c, d, x, 446, 10.5, INK2)
    P(c, "<b>Dimensionamiento de mercado (TAM/SAM/SOM): pendiente.</b> Se validará en la Fase 1 con registros del Colegio "
         "Odontológico del Perú y SUSALUD antes de fijar metas de expansión regional.", MX, 466, 832, 10, MUTED, 14)
    pie(c, n, total)


def p_modelo(c, n, total):
    fondo(c); cabecera(c, n, "05 · Modelo de negocio", "Tres planes. Precio claro. Sin letra chica.")
    info = [("Esencial", 59, "Para consultorios que empiezan.", ["Hasta 3 usuarios", "Hasta 150 pacientes", "Agenda, historial y odontograma", "Recetas en PDF"]),
            ("Profesional", 129, "El favorito de los consultorios en crecimiento.", ["Hasta 10 usuarios", "Hasta 1,500 pacientes", "Reportes PDF y Excel", "Copias de seguridad"]),
            ("Clínica", 249, "Sin límites para equipos grandes.", ["Usuarios y pacientes ilimitados", "Todo lo de Profesional", "Soporte prioritario"])]
    w, x = 264, MX
    for i, (nom, pr, d, fs) in enumerate(info):
        dest = nom == "Profesional"
        if dest:
            grad_rect(c, x - 2, 148, w + 4, 252, 18, BRAND, BRAND2, True)
            card(c, x, 150, w, 248, shadow=False, stroke=None, r=16)
            pill(c, "Más elegido", x + w - 98, 164, HexColor("#FFFFFF"), BRANDINK, 9)
        else:
            card(c, x, 150, w, 248)
        T(c, nom, x + 24, 186, 15, INK, "SB")
        T(c, f"S/ {pr}", x + 24, 232, 38, INK, "SB"); T(c, "/mes", x + 24 + pdfmetrics.stringWidth(f"S/ {pr}", "SB", 38) + 6, 232, 12, MUTED)
        P(c, d, x + 24, 244, w - 48, 10.5, MUTED, 14)
        yy = 286
        for f in fs:
            c.setFillColor(BRAND); c.circle(x + 29, H - yy + 4, 2.6, stroke=0, fill=1)
            T(c, f, x + 40, yy, 11, INK2); yy += 25
        x += w + 20
    P(c, f"<b>Supuesto de mezcla:</b> 45 % Esencial · 45 % Profesional · 10 % Clínica → ingreso medio por clínica (ARPU) ≈ <b>{s(ARPU)}</b> al mes. "
         "Cobro mensual recurrente; cancelación en cualquier momento (los datos quedan en solo lectura).",
      MX, 420, 832, 11, INK2, 16)
    P(c, "Ingresos secundarios por validar: implementación asistida, capacitación y módulos adicionales (WhatsApp, facturación electrónica).",
      MX, 456, 832, 10, MUTED, 14)
    pie(c, n, total)


def p_objetivos(c, n, total):
    fondo(c); cabecera(c, n, "06 · Objetivos a 12 meses", "Metas medibles, con una fecha y una cifra cada una.")
    cols = [("Producto", [f"Pasarela de pagos y seguridad reforzada antes del mes 3", "Piloto cerrado con 10 consultorios (ene–feb 2027)",
                          "Disponibilidad ≥ 99.5 % mensual", "Restauración de backup probada cada trimestre"]),
            ("Comercial", [f"Primeras clínicas de pago en el mes 4 (feb 2027)", f"≈ {CLI6:.0f} clínicas de pago al mes 6",
                           f"≈ {CLI12:.0f} clínicas y MRR ≈ {s(MRR12)} al mes 12", "Conversión de prueba a pago ≥ 25 %"]),
            ("Calidad", ["Cancelación mensual (churn) ≤ 3 %", "NPS de pilotos ≥ 50", "Respuesta de soporte < 4 h hábiles",
                         "Cero incidentes de pérdida de datos"])]
    w, x = 264, MX
    for t, items in cols:
        card(c, x, 140, w, 262)
        T(c, t, x + 24, 176, 16, INK, "SB"); grad_rect(c, x + 24, 186, 26, 3, 1.5)
        yy = 208
        for it in items:
            c.setFillColor(BRAND); c.circle(x + 27, H - yy - 6, 2.4, stroke=0, fill=1)
            h = P(c, it, x + 40, yy, w - 62, 11.5, INK2, 16); yy += h + 14
        x += w + 20
    card(c, MX, 420, 832, 62, fill=INK, stroke=None)
    T(c, "Meta del año", MX + 26, 456, 11, HexColor("#A1A1A6"), "SB")
    T(c, f"≈ {CLI12:.0f} clínicas", MX + 150, 458, 22, HexColor("#FFFFFF"), "SB")
    T(c, f"{s(MRR12)} MRR", MX + 360, 458, 22, HexColor("#FFFFFF"), "SB")
    T(c, f"{s(MRR12 * 12)} ARR", MX + 570, 458, 22, BRAND, "SB")
    pie(c, n, total)


def p_competencia(c, n, total):
    fondo(c); cabecera(c, n, "07 · Competencia", "Hay jugadores sólidos; el hueco es la simplicidad.")
    cab = ["Alternativa", "Qué ofrece (fuente pública)", "Brecha probable (hipótesis)", "Nuestra respuesta"]
    xs, ws = [MX, MX + 150, MX + 372, MX + 620], [140, 212, 238, 212]
    filas = [("Dentalink", "Nube, sin permanencia; agenda, historia clínica, odontograma, presupuestos y pagos.",
              "Suite amplia; precios no visibles en la fuente consultada.", "Precio público desde S/ 59 y alta en minutos."),
             ("Dentidesk", "Software dental en la nube, operando desde 2013.", "Mayor trayectoria y base instalada.",
              "Interfaz moderna y onboarding autoservicio."),
             ("Medesk / Clinic Cloud", "Plataformas multi-especialidad; Clinic Cloud desde 27 €/mes (comparador).",
              "Pensadas para otros mercados; adaptación local por validar.", "Soles, DNI y flujo pensado para Perú."),
             ("Programa de escritorio", "Instalado en una PC, normalmente de pago único.", "Sin acceso remoto; copias y actualizaciones manuales.",
              "Acceso desde cualquier dispositivo, copias incluidas."),
             ("Papel, WhatsApp, Excel", "Costo cero aparente.", "Sin historial centralizado; riesgo de pérdida.",
              "Alta guiada; importación desde Excel (fase 3).")]
    top = 156
    for x, w, t in zip(xs, ws, cab):
        T(c, t.upper(), x, top, 8.5, BRANDINK, "SB", space=1.2)
    top += 10
    for f in filas:
        c.setStrokeColor(LINE); c.setLineWidth(0.5); c.line(MX, H - top, MX + 832, H - top)
        hs = []
        for k, (x, w, t) in enumerate(zip(xs, ws, f)):
            hs.append(P(c, t, x, top + 9, w - 14, 10.5 if k else 11.5, INK if k == 0 else (BRANDINK if k == 3 else INK2),
                        14.5, "SB" if k in (0, 3) else "S"))
        top += max(hs) + 18
    c.line(MX, H - top, MX + 832, H - top)
    P(c, "Evaluación interna sobre información pública; debe contrastarse con demos y cotizaciones reales durante la Fase 1. "
         "Fuentes: softwaredentalink.com/en/planes · capterra.es/software/184029/dentidesk · medesk.net/es/blog/software-para-clinicas-dentales · "
         "softwaredoit.es/software-medico/software-clinica-dental.html",
      MX, 458, 832, 8.5, MUTED, 12)
    pie(c, n, total)


def p_plazos(c, n, total):
    fondo(c); cabecera(c, n, "08 · Plazos", "Cuatro fases, tres puntos de decisión.")
    gx, gw = MX, 832; mw = gw / 12
    for i, m in enumerate(MESES):
        T(c, m, gx + i * mw + mw / 2, 160, 8.5, MUTED, anchor="c")
    fases = [(0, 2, "1  Fundamentos", BRAND), (2, 4, "2  Piloto", HexColor("#17A6BC")), (4, 7, "3  Lanzamiento", HexColor("#2C9BDB")), (7, 12, "4  Escala", BRAND2)]
    for a, b, t, col in fases:
        c.setFillColor(col); c.roundRect(gx + a * mw + 1.5, H - 198, (b - a) * mw - 3, 24, 8, stroke=0, fill=1)
        T(c, t, gx + a * mw + 12, 191, 10.5, HexColor("#FFFFFF"), "SB")
    for k, (mm, lab) in enumerate([(4, "G1"), (7, "G2"), (12, "G3")]):
        x = gx + mm * mw
        c.setFillColor(INK); c.circle(x - 1, H - 222, 9, stroke=0, fill=1)
        T(c, lab, x - 1, 226, 8, HexColor("#FFFFFF"), "SB", "c")
    cont = [("Nov – Dic 2026", ["Pasarela de pagos (pruebas y producción)", "Contraseñas con argon2/bcrypt", "HTTPS, correo y recuperación de clave",
                               "Términos, privacidad y registro de datos (Ley 29733)", "Backups externos diarios"]),
            ("Ene – Feb 2027", ["10 consultorios con onboarding asistido", "Llamada semanal y medición de NPS", "Pulir agenda y odontograma", "Probar precios con cobro real"]),
            ("Mar – May 2027", ["Apertura pública con cobro", "Contenido, demos y referidos de pilotos", "Recordatorios por WhatsApp y correo", "Importación de pacientes desde Excel"]),
            ("Jun – Oct 2027", ["Facturación electrónica (SUNAT)", "Plan Clínica multi-sede", "App móvil instalable (PWA)", "Reportes de gestión avanzados"])]
    cw, x = 196, MX
    for (a, b, t, col), (fe, its) in zip(fases, cont):
        card(c, x, 250, cw, 190)
        T(c, t.split("  ")[1], x + 16, 276, 13, INK, "SB"); T(c, fe, x + 16, 292, 9.5, MUTED)
        yy = 308
        for it in its:
            c.setFillColor(col); c.circle(x + 19, H - yy - 4, 2, stroke=0, fill=1)
            h = P(c, it, x + 28, yy - 2, cw - 42, 9.5, INK2, 12.5); yy += h + 5
        x += cw + 16
    T(c, "G1", MX, 462, 9, INK, "SB"); T(c, "Mes 4 · ≥ 60 % de los pilotos aceptan pagar.", MX + 20, 462, 9.5, INK2)
    T(c, "G2", MX + 290, 462, 9, INK, "SB"); T(c, "Mes 7 · conversión ≥ 20 % y churn ≤ 5 %.", MX + 310, 462, 9.5, INK2)
    T(c, "G3", MX + 580, 462, 9, INK, "SB"); T(c, f"Mes 12 · ≥ 70 clínicas y equilibrio a la vista.", MX + 600, 462, 9.5, INK2)
    P(c, "Si un punto de decisión no se cumple, se detiene la inversión de la fase siguiente y se corrige antes de continuar.", MX, 474, 800, 9, MUTED, 12)
    pie(c, n, total)


def p_presupuesto(c, n, total):
    fondo(c); cabecera(c, n, "09 · Presupuesto", f"{s(TOTAL)} para pasar de producto a negocio.",
                       "Estimación a 12 meses (nov 2026 – oct 2027). Margen de error ±20 % hasta contar con cotizaciones.")
    top = 176; mx = max(TOT_RUBROS)
    for nom, v in zip(RUBROS, TOT_RUBROS):
        T(c, nom, MX, top + 14, 12, INK, "SB"); T(c, s(v), MX + 470, top + 14, 12, INK, "SB", "r")
        c.setFillColor(SOFT); c.roundRect(MX, H - top - 30, 470, 8, 4, stroke=0, fill=1)
        grad_rect(c, MX, top + 22, max(470 * v / mx, 8), 8, 4)
        top += 46
    c.setStrokeColor(LINE); c.line(MX, H - top + 4, MX + 470, H - top + 4)
    T(c, f"Contingencia ({CONTINGENCIA:.0%})", MX, top + 22, 11.5, INK2); T(c, s(CONT), MX + 470, top + 22, 11.5, INK2, anchor="r")
    T(c, "Total", MX, top + 46, 14, INK, "SB"); T(c, s(TOTAL), MX + 470, top + 46, 14, INK, "SB", "r")
    x0 = 580
    kpi(c, x0, 176, 316, 112, s(FASE1), "Fase 1 · Fundamentos", "Comprometer solo esto hasta superar G1", destacado=True)
    card(c, x0, 304, 316, 150)
    T(c, "SUPUESTOS CLAVE", x0 + 22, 332, 9, BRANDINK, "SB", space=1.4)
    for i, t in enumerate(["Equipo mínimo: 1 fundador + 1 desarrollador a tiempo parcial.", "Infraestructura en la nube ≈ S/ 450 al mes.",
                           f"Comisión de pasarela ≈ {COMISION:.0%} sobre ingresos (no incluida).", "Sueldo del fundador no incluido."]):
        P(c, t, x0 + 22, 342 + i * 26, 272, 10, INK2, 13.5)
    pie(c, n, total)


def p_proyeccion(c, n, total):
    fondo(c); cabecera(c, n, "10 · Proyección", f"El equilibrio operativo llega hacia el {mes(BASE['eq'])}.")
    gx, gt, gw, gh = MX + 34, 136, 480, 158
    top_v = max(max(BASE["mrr"][:12]), max(BASE["costo"][:12])) * 1.15
    xs = lambda i: gx + gw * i / 11
    ys = lambda v: H - (gt + gh - gh * v / top_v)
    c.setStrokeColor(LINE); c.setLineWidth(0.4)
    for k in range(5):
        yv = top_v * k / 4; yy = ys(yv); c.line(gx, yy, gx + gw, yy)
        T(c, f"{yv / 1000:.0f}k", gx - 8, H - yy + 3, 8, MUTED, anchor="r")
    for i in (0, 2, 4, 6, 8, 11):
        T(c, MESES[i], xs(i), gt + gh + 16, 8, MUTED, anchor="c")
    p = c.beginPath(); p.moveTo(xs(0), ys(0))
    for i in range(12):
        p.lineTo(xs(i), ys(BASE["mrr"][i]))
    p.lineTo(xs(11), ys(0)); p.close()
    c.saveState(); c.clipPath(p, stroke=0, fill=0); c.linearGradient(gx, ys(top_v), gx, ys(0), (HexColor("#BFEFE9"), BG)); c.restoreState()
    c.setStrokeColor(BRAND); c.setLineWidth(2.2); c.setLineJoin(1)
    q = c.beginPath(); q.moveTo(xs(0), ys(BASE["mrr"][0]))
    for i in range(1, 12):
        q.lineTo(xs(i), ys(BASE["mrr"][i]))
    c.drawPath(q, stroke=1, fill=0)
    c.setStrokeColor(WARN); c.setLineWidth(1.6); c.setDash(4, 3)
    q = c.beginPath(); q.moveTo(xs(0), ys(BASE["costo"][0]))
    for i in range(1, 12):
        q.lineTo(xs(i), ys(BASE["costo"][i]))
    c.drawPath(q, stroke=1, fill=0); c.setDash()
    T(c, "Ingresos recurrentes (MRR)", gx + 8, gt + 14, 9.5, BRANDINK, "SB")
    T(c, "Costo mensual", gx + 168, gt + 14, 9.5, HexColor("#B7791F"), "SB")
    for i, v, col in ((11, BASE["mrr"][11], BRAND), (11, BASE["costo"][11], WARN)):
        c.setFillColor(col); c.circle(xs(i), ys(v), 3.5, stroke=0, fill=1)
    x0 = 612
    stats = [(f"≈ {CLI12:.0f}", "clínicas de pago · mes 12"), (s(BASE["mrr"][11]), "MRR al mes 12"),
             (s(BASE["caja"]), "necesidad máxima de caja"), (f"{CAC / (ARPU * .9):.1f} meses", f"recupera el costo de adquirir un cliente (CAC ≈ {s(CAC)})")]
    for i, (v, l) in enumerate(stats):
        T(c, v, x0, 158 + i * 46, 21, INK, "SB"); T(c, l, x0, 174 + i * 46, 9.5, MUTED)
    # escenarios
    top = 346
    cab = ["ESCENARIO", "CLÍNICAS MES 12", "MRR MES 12", "EQUILIBRIO OPERATIVO", "RECUPERA LA INVERSIÓN", "CAJA MÁXIMA"]
    xs_ = [MX, MX + 160, MX + 290, MX + 410, MX + 570, MX + 730]
    for x, t in zip(xs_, cab):
        T(c, t, x, top, 8, BRANDINK, "SB", space=1)
    top += 10
    for nom, sim in (("Conservador", CONSERV), ("Base", BASE), ("Optimista", OPTIM)):
        c.setStrokeColor(LINE); c.setLineWidth(0.5); c.line(MX, H - top, MX + 832, H - top)
        if nom == "Base":
            c.setFillColor(BRANDSOFT); c.rect(MX, H - top - 30, 832, 30, stroke=0, fill=1)
        vals = [nom, f"{sim['base'][11]:.0f}", s(sim["mrr"][11]), mes(sim["eq"]), mes(sim["pb"]), s(sim["caja"])]
        for x, v, k in zip(xs_, vals, range(6)):
            T(c, v, x + (8 if nom == "Base" else 0) * (k == 0), top + 19, 10.5, INK, "SB" if k == 0 else "S")
        top += 30
    c.line(MX, H - top, MX + 832, H - top)
    P(c, f"Supuestos del escenario base: conversión de prueba a pago 25 % (60 % en el piloto), cancelación 3 % mensual, ARPU {s(ARPU)}, "
         "pruebas gratuitas crecientes hasta 60 al mes. Conservador: 40 % menos pruebas, 18 % de conversión, 4.5 % de cancelación. "
         f"LTV estimado ≈ {s(LTV)} (LTV/CAC ≈ {LTV / CAC:.1f}); la cancelación es el supuesto más sensible.",
      MX, top + 12, 832, 8.5, MUTED, 12)
    pie(c, n, total)


def p_riesgos(c, n, total):
    fondo(c); cabecera(c, n, "11 · Riesgos", "Lo que puede salir mal, y cómo lo evitamos.")
    cab = ["Riesgo", "Prob.", "Impacto", "Mitigación"]
    xs, ws = [MX, MX + 270, MX + 330, MX + 405], [260, 56, 70, 427]
    filas = [("Datos de salud: obligaciones de la Ley 29733", "Media", "Alto", "Registro del banco de datos, consentimiento, cifrado y contratos con la clínica."),
             ("Seguridad: contraseñas heredadas con SHA-256 sin sal", "Alta", "Alto", "Migrar a argon2/bcrypt y activar HTTPS antes de cualquier cobro (Fase 1)."),
             ("Adopción lenta por inercia de papel y Excel", "Alta", "Medio", "Piloto con onboarding asistido, prueba de 14 días e importación de pacientes."),
             ("Competidores establecidos con más funciones", "Media", "Medio", "No competir en suites completas: simplicidad, precio visible y soporte cercano."),
             ("Dependencia de un equipo muy pequeño", "Media", "Alto", "Documentación, pruebas automáticas y un desarrollador de respaldo."),
             ("Cobranza: tarjetas limitadas en el segmento", "Media", "Medio", "Pasarela local con tarjeta y billeteras, más transferencia como alternativa."),
             ("Caída del servicio o pérdida de datos", "Baja", "Alto", "Backups externos diarios y restauración probada cada trimestre.")]
    top = 150
    for x, t in zip(xs, cab):
        T(c, t.upper(), x, top, 8.5, BRANDINK, "SB", space=1.2)
    top += 10
    col = {"Alta": BAD, "Media": WARN, "Baja": BRAND, "Alto": BAD, "Medio": WARN}
    for f in filas:
        c.setStrokeColor(LINE); c.setLineWidth(0.5); c.line(MX, H - top, MX + 832, H - top)
        h1 = P(c, f[0], xs[0], top + 9, ws[0] - 10, 10.5, INK, 14, "SB"); h2 = P(c, f[3], xs[3], top + 9, ws[3] - 4, 10.5, INK2, 14)
        for k in (1, 2):
            c.setFillColor(col[f[k]]); c.circle(xs[k] + 4, H - top - 16, 3.5, stroke=0, fill=1)
            T(c, f[k], xs[k] + 13, top + 20, 10, INK2)
        top += max(h1, h2, 22) + 16
    c.line(MX, H - top, MX + 832, H - top)
    pie(c, n, total)


def p_cierre(c, n, total):
    fondo(c, True)
    for k in range(60):
        c.setFillColor(Ac(BRAND, 0.009)); c.circle(820, 120, 260 - k * 4, stroke=0, fill=1)
    alpha(c, 1)
    T(c, "SIGUIENTES PASOS", MX, 84, 10, BRAND, "SB", space=2)
    P(c, "Cinco decisiones para empezar.", MX, 98, 700, 40, HexColor("#FFFFFF"), 46, "SB")
    pasos = [("Aprobar la Fase 1", f"{s(FASE1)} para fundamentos: pagos, seguridad y base legal."),
             ("Constituir la empresa y proteger la marca", "Definir razón social, búsqueda y registro de marca."),
             ("Elegir la pasarela de pago", "Comparar comisiones y medios de pago locales; integrar y probar."),
             ("Reclutar 10 consultorios piloto", "Con onboarding asistido y compromiso de feedback semanal."),
             ("Validar precios y mercado", "8 a 10 entrevistas y dimensionamiento con fuentes sectoriales.")]
    top = 196
    for i, (t, d) in enumerate(pasos):
        grad_rect(c, MX, top, 30, 30, 15)
        T(c, str(i + 1), MX + 15, top + 20, 13, HexColor("#FFFFFF"), "SB", "c")
        T(c, t, MX + 50, top + 14, 15, HexColor("#FFFFFF"), "SB"); T(c, d, MX + 50, top + 32, 11, HexColor("#A1A1A6"))
        top += 52
    T(c, "Dental Home  ·  Brief corporativo  ·  Octubre 2026  ·  Confidencial", MX, 510, 8.5, HexColor("#6E6E73"))


def main():
    paginas = [p_portada, p_resumen, p_empresa, p_producto, p_cliente, p_modelo, p_objetivos, p_competencia,
               p_plazos, p_presupuesto, p_proyeccion, p_riesgos, p_cierre]
    c = canvas.Canvas(SALIDA, pagesize=(W, H))
    c.setTitle("Dental Home · Brief corporativo"); c.setAuthor("Dental Home"); c.setSubject("Brief corporativo 2026")
    for i, f in enumerate(paginas, 1):
        f(c, i, len(paginas)); c.showPage()
    c.save()
    print("PDF:", SALIDA)
    print(f"ARPU {ARPU:.1f} | total {TOTAL:,.0f} | fase1 {FASE1:,.0f} | clin12 {CLI12:.1f} | mrr12 {MRR12:,.0f} | "
          f"eq {BASE['eq']} | pb {BASE['pb']} | caja {BASE['caja']:,.0f} | CAC {CAC:.0f} | LTV {LTV:.0f}")
    for nom, sim in (("cons", CONSERV), ("base", BASE), ("opt", OPTIM)):
        print(nom, f"{sim['base'][11]:.0f}", f"{sim['mrr'][11]:,.0f}", sim["eq"], sim["pb"], f"{sim['caja']:,.0f}")


if __name__ == "__main__":
    main()
