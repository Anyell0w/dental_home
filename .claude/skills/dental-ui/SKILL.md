---
name: dental-ui
description: Reglas del sistema de diseño de Dental Home (web). Úsalo al crear o modificar cualquier pantalla, componente, animación o estilo de web/static.
---

# Dental Home — guía de interfaz

La identidad sale del landing (`web/static/views/landing.html`): morado profundo, acento violeta, lavanda,
mucho aire, formas redondeadas tipo píldora y movimiento suave con la curva `cubic-bezier(.2,.8,.2,1)`.

## Paleta (tokens de `web/static/css/app.css`)
| Token | Claro | Uso |
|---|---|---|
| `--brand-deep` | `#4A2E80` | botones primarios, navegación activa, tarjetas destacadas |
| `--brand` | `#7B1FA2` | acento: hover de primarios, kickers, iconos |
| `--brand-2` | `#B39DDB` | lavanda: barras, bordes al pasar el mouse, decoración |
| `--line-2` / `--line` | `#E1D5E7` / `#EEE8F4` | bordes y separadores |
| `--surface-2` | `#F4F1F8` | superficies suaves (celdas, segmentados, tabs) |
| `--ink` / `--ink-2` / `--muted` | `#1E1433` / `#3B2D57` / `#6B5F80` | texto |

Siempre probar claro **y** oscuro (`data-theme="dark"`); nunca escribir colores sueltos en la app (el landing es
la única excepción: es claro siempre y conserva los colores literales del diseño original).

## Tipografía y marca
- Texto: **Manrope** 500–800 (titulares 800 con `letter-spacing: -.03em`). Marca y números de pasos: **Montserrat**.
  Ambas están en `web/static/vendor/fonts` (la CSP no permite fuentes externas).
- Logo: `web/static/img/logo.png` (oscuro: `logo-oscuro.png`, vía `--logo`), componente `.marca` (`.logo` + `.word` "DENTAL HOME").

## Componentes
`.btn(.primary/.ghost/.danger/.danger-fill/.sm/.lg/.icon)` píldora, `.card(.hover/.soft/.deep)`, `.tile(.deep/.accent/.outline)`,
`.badge(.ok/.warn/.bad/.brand/.deep/.plain)`, `.seg`, `.tabs`, `.input`, `.field`, `.overlay + .modal/.drawer`, `.empty`,
`.skel`, `.table`, `.toolbar`, `.page-head` con `.kicker`, `.dot-live`. Evita nombres de clase que choquen
(`.brand` es un modificador de badge; el logo es `.marca`).

## Movimiento (mismo vocabulario que el landing)
- Entrada de vistas: `rise` (automático en `.view > *`); listas: `.stagger` + `style="--i:n"`; héroes: `.in1`…`.in4`.
- Flotar: `.float1` / `.float2`; vivo: `.pulse` / `.dot-live`; destellos: `.spark`; barras: `grow`; estado: `.blink`.
- Hover: tarjetas suben 6 px con sombra morada, el `.tile` gira −4°; botón primario con brillo que cruza (`::after`).
- Landing: `lp-reveal` usa `animation-timeline: view()` (si el navegador no lo soporta, el contenido se ve sin animar).
- `prefers-reduced-motion` apaga todas las animaciones.

## Reglas
1. Estados siempre: cargando (`.skel`), vacío (`.empty` con ilustración lavanda + CTA), error (`.error-text` / toast), ocupado (`.is-busy`).
2. Español neutro, tuteo, verbos en botones ("Agendar cita", "Emitir receta").
3. Móvil primero (390 px): la navegación pasa a `.tabbar`; columnas secundarias con `.hide-m`.
4. Accesibilidad: foco visible, `aria-label`/`title` en botones de solo icono, contraste AA.
5. Iconos: sprite SVG de `index.html` (`<svg class="i"><use href="#i-nombre"/></svg>`), trazo lineal 1.9.
6. Sin dependencias nuevas sin necesidad real (solo Alpine.js vendorizado).
7. La lógica de negocio vive en el servidor (`web/api_*.py` sobre PostgreSQL), no en el frontend.
