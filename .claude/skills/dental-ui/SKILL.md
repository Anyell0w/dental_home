---
name: dental-ui
description: Reglas del sistema de diseño de Dental Home (web). Úsalo al crear o modificar cualquier pantalla, componente, animación o estilo de web/static.
---

# Dental Home — guía de interfaz

Filosofía: **minimalista, moderna, con micro-interacciones que dan ganas de seguir usándola**. Una sola
acento (teal→azul), mucho aire, jerarquía por tamaño/peso, nunca por decoración.

## Reglas
1. **Tokens, no colores sueltos.** Todo color/radio/sombra sale de las variables de `web/static/css/app.css`
   (`--brand`, `--surface`, `--line`, `--r`, `--shadow`…). Siempre probar claro **y** oscuro (`data-theme`).
2. **Componentes existentes primero:** `.btn(.primary/.ghost/.danger/.sm/.lg/.icon)`, `.card(.hover)`, `.badge(.ok/.warn/.bad/.brand)`,
   `.seg`, `.input`, `.field`, `.overlay + .modal/.drawer`, `.empty`, `.skel`, `.table`, `.toolbar`, `.page-head`.
3. **Movimiento sutil y con propósito** (150–500 ms, `--ease` o `--spring`):
   - entrada de vista: `.view > *` (automático); listas: `.stagger` + `style="--i:n"`;
   - números: `x-count`; secciones de landing: `x-reveal`; éxito: `.burst`, anillo de progreso, check animado.
   - Respetar `prefers-reduced-motion` (ya global; no añadir animaciones largas ni en bucle salvo decorativas lentas).
4. **Estados siempre:** cargando (`.skel`), vacío (`.empty` con ilustración + CTA), error (`.error-text` / toast), ocupado (`.is-busy`).
5. **Texto:** español neutro, tuteo, frases cortas. Verbos en botones ("Agendar cita", no "Enviar").
6. **Móvil primero:** probar a 390 px. La navegación se vuelve `.tabbar`; tablas con `.hide-m` en columnas secundarias.
7. **Accesibilidad:** foco visible (ya global), `aria-label` en botones solo-icono, contraste AA, no depender solo del color.
8. **Iconos:** sprite SVG de `index.html` (`<svg class="i"><use href="#i-nombre"/></svg>`), trazo lineal 1.7. Añadir ahí si falta.
9. **Sin dependencias nuevas** salvo necesidad real: Alpine.js + three.js vendorizados en `web/static/vendor`
   (la CSP no permite scripts inline ni CDN).
10. La lógica de negocio NO va en el frontend: vive en `controllers/` y se expone en `web/app.py`.

## Estructura
- `web/static/index.html` shell + sprite · `css/app.css` sistema · `js/core.js` API/stores/router/directivas
- `js/views.js` componentes por vista · `views/*.html` plantillas · `js/odontograma.js` · `js/tooth3d.js` (landing)
