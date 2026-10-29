/* Odontograma interactivo en SVG (FDI). El servidor guarda hallazgos fechados
   (pieza, superficie, condición); aquí se edita el estado vigente y se envían solo los cambios.
   Estado: { "16": { surf: { oclusal: "caries" }, whole: "corona" | null } } */
document.addEventListener('alpine:init', () => {
  const CELL = 42, GAP = 6, MID = 24, MX = 30, TOP_Y = 42, BOT_Y = TOP_Y + CELL + 70;
  const DENT = {
    permanente: { up: [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28], low: [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38] },
    temporal: { up: [55, 54, 53, 52, 51, 61, 62, 63, 64, 65], low: [85, 84, 83, 82, 81, 71, 72, 73, 74, 75] },
  };
  const W = MX * 2 + 16 * (CELL + GAP) - GAP + MID, H = BOT_Y + CELL + 34;
  const SUP = ['vestibular', 'lingual', 'mesial', 'distal', 'oclusal'];
  const CONDS = [
    { key: 'caries', color: '#e5484d', scope: 'surface' },
    { key: 'obturacion', color: '#3b82f6', scope: 'surface' },
    { key: 'sellante', color: '#10b981', scope: 'surface' },
    { key: 'fractura', color: '#f97316', scope: 'surface' },
    { key: 'endodoncia', color: '#f59e0b', scope: 'whole' },
    { key: 'corona', color: '#7b1fa2', scope: 'whole' },
    { key: 'implante', color: '#4a2e80', scope: 'whole' },
    { key: 'puente', color: '#9575cd', scope: 'whole' },
    { key: 'ausente', color: '#8e8aa0', scope: 'whole' },
    { key: 'extraccion_indicada', color: '#c2185b', scope: 'whole' },
    { key: 'sano', color: '#b39ddb', scope: 'erase' },
  ];
  const COLOR = Object.fromEntries(CONDS.map((c) => [c.key, c.color]));
  const clone = (o) => JSON.parse(JSON.stringify(o || {}));

  function layout(tipo) {
    const g = {}, d = DENT[tipo];
    [[d.up, TOP_Y], [d.low, BOT_Y]].forEach(([row, y]) => {
      const n = row.length, offset = (16 - n) / 2 * (CELL + GAP);
      row.forEach((p, i) => { g[p] = { x: MX + offset + i * (CELL + GAP) + (i >= n / 2 ? MID : 0), y }; });
    });
    return g;
  }
  // Cara del recuadro -> superficie anatómica según arcada y lado del paciente
  function caraA(p, cara) {
    const q = Math.floor(p / 10), sup = [1, 2, 5, 6].includes(q), der = [1, 4, 5, 8].includes(q);
    return { T: sup ? 'vestibular' : 'lingual', B: sup ? 'lingual' : 'vestibular', R: der ? 'mesial' : 'distal', L: der ? 'distal' : 'mesial', C: 'oclusal' }[cara];
  }
  function polys(x, y) {
    const x1 = x + CELL, y1 = y + CELL, cx = x + CELL / 2, cy = y + CELL / 2, k = CELL * 0.22;
    const [a0, b0, a1, b1] = [cx - k, cy - k, cx + k, cy + k];
    const P = (...p) => p.join(' ');
    return { T: P(x, y, x1, y, a1, b0, a0, b0), R: P(x1, y, x1, y1, a1, b1, a1, b0), B: P(x1, y1, x, y1, a0, b1, a1, b1), L: P(x, y1, x, y, a0, b0, a0, b1), C: P(a0, b0, a1, b0, a1, b1, a0, b1) };
  }

  Alpine.data('odo', () => ({
    CONDS, cur: 'caries', tipo: 'permanente', teeth: {}, orig: {}, nombres: {}, hid: null, registroId: '', notas: '',
    registros: [], historial: [], busy: false, fresh: null,
    cargar(det) {
      this.hid = det.historial.id;
      this.orig = clone(det.odontograma); this.teeth = clone(det.odontograma);
      this.nombres = Object.fromEntries((det.condiciones || []).map((c) => [c.codigo, c.nombre]));
      this.registros = det.registros;
      const hoy = det.registros.find((r) => r.fecha === fmt.today() && r.editable);
      this.registroId = hoy ? String(hoy.id) : '';
      if (Object.keys(this.orig).some((p) => Number(p) > 50)) this.tipo = Object.keys(this.orig).every((p) => Number(p) > 50) ? 'temporal' : this.tipo;
      this.cargarHistorial();
    },
    nombre(k) { return this.nombres[k] || fmt.cap(k.replace('_', ' ')); },
    async cargarHistorial() { try { this.historial = await api.get(`/api/historiales/${this.hid}/hallazgos`); } catch (e) { /* opcional */ } },
    get cambios() {
      const out = [], piezas = new Set([...Object.keys(this.orig), ...Object.keys(this.teeth)]);
      for (const p of piezas) {
        const o = this.orig[p] || { surf: {} }, c = this.teeth[p] || { surf: {} };
        for (const s of SUP) {
          const a = (o.surf || {})[s] || null, b = (c.surf || {})[s] || null;
          if (a !== b) out.push({ pieza: Number(p), superficie: s, condicion: b || 'sano' });
        }
        if ((o.whole || null) !== (c.whole || null)) out.push({ pieza: Number(p), superficie: null, condicion: c.whole || 'sano' });
      }
      return out;
    },
    get resumen() {
      const n = {};
      for (const t of Object.values(this.teeth)) {
        if (t.whole) n[t.whole] = (n[t.whole] || 0) + 1;
        for (const c of Object.values(t.surf || {})) n[c] = (n[c] || 0) + 1;
      }
      return n;
    },
    svg(exportar = false) {
      const P = exportar
        ? { face: '#ffffff', line: '#4a2e80', txt: '#5b5070', gap: '#b39ddb' }
        : { face: 'var(--surface)', line: 'var(--brand-2)', txt: 'var(--muted)', gap: 'var(--brand-2)' };
      const geo = layout(this.tipo);
      let s = `<svg class="odo" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="Manrope, system-ui, sans-serif">`;
      if (exportar) s += `<rect width="${W}" height="${H}" fill="#fff"/>`;
      const mid = W / 2;
      s += `<line x1="${mid}" y1="${TOP_Y - 14}" x2="${mid}" y2="${BOT_Y + CELL + 14}" stroke="${P.gap}" stroke-opacity=".6" stroke-dasharray="3 5"/>`;
      s += `<line x1="${MX - 6}" y1="${(TOP_Y + CELL + BOT_Y) / 2}" x2="${W - MX + 6}" y2="${(TOP_Y + CELL + BOT_Y) / 2}" stroke="${P.gap}" stroke-opacity=".6" stroke-dasharray="3 5"/>`;
      for (const [n, g] of Object.entries(geo)) {
        const t = this.teeth[n] || {}, surf = t.surf || {}, whole = t.whole, aus = whole === 'ausente';
        const poly = polys(g.x, g.y), x1 = g.x + CELL, y1 = g.y + CELL, cx = g.x + CELL / 2, cy = g.y + CELL / 2;
        s += `<g${!exportar && this.fresh === n ? ' class="fresh"' : ''}>`;
        for (const cara of ['T', 'R', 'B', 'L', 'C']) {
          const sup = caraA(Number(n), cara), c = surf[sup];
          const fill = aus ? '#ddd8e6' : (c ? COLOR[c] : P.face);
          s += `<polygon class="face" data-t="${n}" data-f="${sup}" points="${poly[cara]}" style="fill:${fill};stroke:${P.line}" stroke-width="1.2" stroke-linejoin="round"><title>${n} · ${sup}${c ? ' · ' + this.nombre(c) : ''}</title></polygon>`;
        }
        s += '<g class="mark" pointer-events="none">';
        if (aus) s += `<path d="M${g.x} ${g.y}L${x1} ${y1}M${x1} ${g.y}L${g.x} ${y1}" stroke="#6b5f80" stroke-width="3" stroke-linecap="round"/>`;
        if (whole === 'extraccion_indicada') s += `<path d="M${g.x} ${g.y}L${x1} ${y1}M${x1} ${g.y}L${g.x} ${y1}" stroke="${COLOR.extraccion_indicada}" stroke-width="3.4" stroke-linecap="round"/>`;
        if (whole === 'corona') s += `<circle cx="${cx}" cy="${cy}" r="${CELL * 0.62}" fill="none" stroke="${COLOR.corona}" stroke-width="2.6"/>`;
        if (whole === 'endodoncia') s += `<path d="M${cx} ${g.y - 4}V${y1 + 4}" stroke="${COLOR.endodoncia}" stroke-width="3.6" stroke-linecap="round"/>`;
        if (whole === 'implante') s += `<text x="${cx}" y="${cy + 8}" text-anchor="middle" font-size="22" font-weight="800" fill="${COLOR.implante}">I</text>`;
        if (whole === 'puente') s += `<path d="M${g.x - GAP / 2 - 1} ${cy}H${x1 + GAP / 2 + 1}" stroke="${COLOR.puente}" stroke-width="5" stroke-linecap="butt" opacity=".9"/>`;
        s += '</g>';
        const arriba = [1, 2, 5, 6].includes(Math.floor(Number(n) / 10));
        s += `<text x="${cx}" y="${arriba ? g.y - 10 : y1 + 17}" text-anchor="middle" font-size="10.5" font-weight="800" style="fill:${P.txt}">${n}</text></g>`;
      }
      return s + '</svg>';
    },
    locate(ev) {
      const el = ev.target.closest('[data-t]'); if (!el) return null;
      return { n: el.dataset.t, f: el.dataset.f };
    },
    click(ev) {
      const h = this.locate(ev); if (!h) return;
      const c = CONDS.find((x) => x.key === this.cur);
      const t = clone(this.teeth[h.n] || { surf: {}, whole: null }); t.surf ||= {};
      if (c.scope === 'erase') { t.surf = {}; t.whole = null; }
      else if (c.scope === 'surface') { if (t.surf[h.f] === c.key) delete t.surf[h.f]; else t.surf[h.f] = c.key; }
      else t.whole = t.whole === c.key ? null : c.key;
      const vacio = !Object.keys(t.surf).length && !t.whole;
      const next = { ...this.teeth }; if (vacio) delete next[h.n]; else next[h.n] = t;
      this.teeth = next; this.fresh = h.n;
    },
    borrar(ev) {
      const h = this.locate(ev); if (!h) return;
      const next = { ...this.teeth }; delete next[h.n]; this.teeth = next; this.fresh = h.n;
    },
    descartar() { this.teeth = clone(this.orig); this.fresh = null; },
    async guardar() {
      if (!this.cambios.length) return;
      this.busy = true;
      try {
        const r = await api.put(`/api/historiales/${this.hid}/odontograma`, { cambios: this.cambios, registroId: this.registroId || null, notas: this.notas });
        this.orig = clone(r.odontograma); this.teeth = clone(r.odontograma); this.notas = '';
        Alpine.store('ui').toast('Odontograma guardado'); this.cargarHistorial();
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
