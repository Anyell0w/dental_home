/* Odontograma interactivo en SVG (numeración FDI, 5 caras por pieza).
   Mismo modelo y JSON que el odontograma de escritorio:
   { "18": { "surf": { "V": "caries" }, "whole": ["corona"] } } */
document.addEventListener('alpine:init', () => {
  const CELL = 42, GAP = 6, MID = 24, MX = 30;
  const UPPER = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
  const LOWER = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
  const TOP_Y = 42, BOT_Y = TOP_Y + CELL + 70;
  const W = MX * 2 + 16 * (CELL + GAP) - GAP + MID, H = BOT_Y + CELL + 34;
  const CONDS = [
    { key: 'caries', label: 'Caries', color: '#e5484d', scope: 'surface' },
    { key: 'restauracion', label: 'Restauración', color: '#3aa7f0', scope: 'surface' },
    { key: 'sellante', label: 'Sellante', color: '#17a673', scope: 'surface' },
    { key: 'corona', label: 'Corona', color: '#8e5cf0', scope: 'whole' },
    { key: 'endodoncia', label: 'Endodoncia', color: '#f0a13a', scope: 'whole' },
    { key: 'extraccion', label: 'Extracción indicada', color: '#d32f2f', scope: 'whole' },
    { key: 'ausente', label: 'Ausente', color: '#757575', scope: 'whole' },
    { key: 'implante', label: 'Implante', color: '#00897b', scope: 'whole' },
    { key: 'erase', label: 'Borrar diente', color: '#9aa8ad', scope: 'erase' },
  ];
  const COLOR = Object.fromEntries(CONDS.map((c) => [c.key, c.color]));
  const geo = {};
  [[UPPER, TOP_Y], [LOWER, BOT_Y]].forEach(([row, y]) => row.forEach((n, i) => {
    geo[n] = { x: MX + i * (CELL + GAP) + (i >= 8 ? MID : 0), y };
  }));

  function faces(x, y) {
    const x1 = x + CELL, y1 = y + CELL, cx = x + CELL / 2, cy = y + CELL / 2, k = CELL * 0.22;
    const [a0, b0, a1, b1] = [cx - k, cy - k, cx + k, cy + k];
    const P = (...p) => p.join(' ');
    return {
      V: P(x, y, x1, y, a1, b0, a0, b0), D: P(x1, y, x1, y1, a1, b1, a1, b0),
      L: P(x1, y1, x, y1, a0, b1, a1, b1), M: P(x, y1, x, y, a0, b0, a0, b1), O: P(a0, b0, a1, b0, a1, b1, a0, b1),
    };
  }
  Alpine.data('odo', () => ({
    CONDS, cur: 'caries', teeth: {}, desc: '', dirty: false, busy: false, fresh: null, hid: null,
    cargar(h) {
      this.hid = h.id; this.desc = h.descripcionOdontograma || '';
      this.teeth = JSON.parse(JSON.stringify(h.odontograma || {})); this.dirty = false;
    },
    svg(exportar = false) {
      const P = exportar
        ? { face: '#ffffff', line: '#444444', txt: '#555555', gap: '#999999' }
        : { face: 'var(--surface)', line: 'var(--ink-2)', txt: 'var(--muted)', gap: 'var(--muted)' };
      let s = `<svg class="odo" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="Inter, system-ui, sans-serif">`;
      if (exportar) s += `<rect width="${W}" height="${H}" fill="#fff"/>`;
      const mid = MX + 8 * (CELL + GAP) - GAP / 2 + MID / 2;
      s += `<line x1="${mid}" y1="${TOP_Y - 14}" x2="${mid}" y2="${BOT_Y + CELL + 14}" stroke="${P.gap}" stroke-opacity=".35" stroke-dasharray="3 5"/>`;
      s += `<line x1="${MX - 6}" y1="${(TOP_Y + CELL + BOT_Y) / 2}" x2="${W - MX + 6}" y2="${(TOP_Y + CELL + BOT_Y) / 2}" stroke="${P.gap}" stroke-opacity=".35" stroke-dasharray="3 5"/>`;
      for (const [n, g] of Object.entries(geo)) {
        const t = this.teeth[n] || {}, surf = t.surf || {}, whole = t.whole || [], aus = whole.includes('ausente');
        const poly = faces(g.x, g.y), x1 = g.x + CELL, y1 = g.y + CELL, cx = g.x + CELL / 2, cy = g.y + CELL / 2;
        s += `<g data-tg="${n}"${!exportar && this.fresh === n ? ' class="fresh"' : ''}>`;
        for (const f of ['V', 'M', 'O', 'D', 'L']) {
          const fill = aus ? '#d9d9d9' : (surf[f] ? COLOR[surf[f]] : P.face);
          s += `<polygon class="face" data-t="${n}" data-f="${f}" points="${poly[f]}" style="fill:${fill};stroke:${P.line}" stroke-width="1" stroke-linejoin="round"/>`;
        }
        s += '<g class="mark">';
        if (aus) s += `<path d="M${g.x} ${g.y}L${x1} ${y1}M${x1} ${g.y}L${g.x} ${y1}" stroke="#616161" stroke-width="3" stroke-linecap="round" pointer-events="none"/>`;
        if (whole.includes('extraccion')) s += `<path d="M${g.x} ${g.y}L${x1} ${y1}M${x1} ${g.y}L${g.x} ${y1}" stroke="${COLOR.extraccion}" stroke-width="3" stroke-linecap="round" pointer-events="none"/>`;
        if (whole.includes('corona')) s += `<circle cx="${cx}" cy="${cy}" r="${CELL * 0.62}" fill="none" stroke="${COLOR.corona}" stroke-width="2.4" pointer-events="none"/>`;
        if (whole.includes('endodoncia')) s += `<path d="M${cx} ${g.y}V${y1}" stroke="${COLOR.endodoncia}" stroke-width="3.4" stroke-linecap="round" pointer-events="none"/>`;
        if (whole.includes('implante')) s += `<text x="${cx}" y="${cy + 8}" text-anchor="middle" font-size="22" font-weight="700" fill="${COLOR.implante}" pointer-events="none">I</text>`;
        s += '</g>';
        const ny = Number(n) < 30 && Number(n) > 20 || (Number(n) > 10 && Number(n) < 20) ? g.y - 10 : y1 + 16;
        s += `<text x="${cx}" y="${ny}" text-anchor="middle" font-size="10" font-weight="600" style="fill:${P.txt}">${n}</text></g>`;
      }
      return s + '</svg>';
    },
    locate(ev) {
      const el = ev.target.closest('[data-t]'); if (!el) return null;
      return { n: el.dataset.t, f: el.dataset.f };
    },
    click(ev) {
      const h = this.locate(ev); if (!h) return;
      const c = CONDS.find((x) => x.key === this.cur), t = (this.teeth[h.n] ||= { surf: {}, whole: [] });
      t.surf ||= {}; t.whole ||= [];
      if (c.scope === 'erase') delete this.teeth[h.n];
      else if (c.scope === 'surface') { if (t.surf[h.f] === c.key) delete t.surf[h.f]; else t.surf[h.f] = c.key; }
      else { const i = t.whole.indexOf(c.key); if (i >= 0) t.whole.splice(i, 1); else t.whole.push(c.key); }
      if (this.teeth[h.n] && !Object.keys(t.surf).length && !t.whole.length) delete this.teeth[h.n];
      this.fresh = h.n; this.dirty = true; this.teeth = { ...this.teeth };
    },
    borrar(ev) {
      const h = this.locate(ev); if (!h) return;
      delete this.teeth[h.n]; this.fresh = h.n; this.dirty = true; this.teeth = { ...this.teeth };
    },
    async limpiar() {
      if (!Object.keys(this.teeth).length) return;
      if (!(await Alpine.store('ui').confirm({ title: 'Limpiar odontograma', text: 'Se quitarán todas las marcas (podrás deshacerlo si no guardas).', ok: 'Limpiar', danger: true }))) return;
      this.teeth = {}; this.fresh = null; this.dirty = true;
    },
    async guardar() {
      this.busy = true;
      try {
        await api.put(`/api/historiales/${this.hid}/odontograma`, { estado: this.teeth, descripcion: this.desc });
        this.dirty = false; Alpine.store('ui').toast('Odontograma guardado');
      } catch (e) { Alpine.store('ui').error(e); }
      this.busy = false;
    },
    exportar() {
      const svg = this.svg(true), img = new Image(), sc = 3;
      img.onload = () => {
        const c = document.createElement('canvas'); c.width = W * sc; c.height = H * sc;
        const g = c.getContext('2d'); g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
        const a = document.createElement('a'); a.download = 'odontograma.png'; a.href = c.toDataURL('image/png'); a.click();
      };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    },
  }));
});
