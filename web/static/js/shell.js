/* Shell de la app (navegación por rol) y paleta de comandos (Ctrl/⌘ K). */
document.addEventListener('alpine:init', () => {
  const NAV = [
    { r: 'inicio', t: 'Inicio', i: 'home' },
    { r: 'pacientes', t: 'Pacientes', i: 'users' },
    { r: 'citas', t: 'Citas', i: 'calendar' },
    { r: 'historial', t: 'Historial', i: 'file', roles: ['Doctor', 'Administrador'] },
    { r: 'reportes', t: 'Reportes', i: 'chart', roles: ['Administrador'] },
    { r: 'copias', t: 'Copias', i: 'database', roles: ['Administrador'] },
    { r: 'equipo', t: 'Equipo', i: 'shield', roles: ['Administrador'] },
    { r: 'suscripcion', t: 'Suscripción', i: 'card', roles: ['Administrador'] },
  ];
  const navFor = (rol) => NAV.filter((n) => !n.roles || n.roles.includes(rol));

  Alpine.data('shell', () => ({
    get nav() { return navFor(Alpine.store('app').user.rol); },
    pct(k) {
      const max = Alpine.store('app').sub.plan['max_' + k];
      return max ? Math.min(100, Math.round((Alpine.store('app').uso[k] / max) * 100)) : 0;
    },
  }));

  Alpine.data('cmdk', () => ({
    q: '', sel: 0, pacientes: [],
    get items() {
      const app = Alpine.store('app');
      const needle = this.q.trim().toLowerCase();
      const pages = navFor(app.user.rol);
      const pg = pages.filter((n) => !needle || n.t.toLowerCase().includes(needle))
        .map((n) => ({ k: 'p' + n.r, t: n.t, i: n.i, s: 'Ir a', run: () => (location.hash = '#/' + n.r) }));
      const pa = this.pacientes.map((p) => ({
        k: 'a' + p.id, t: p.nombreCompleto, i: 'users', s: 'DNI ' + p.dni,
        run: () => (location.hash = app.is('Doctor', 'Administrador') ? '#/historial/' + p.id : '#/pacientes?q=' + p.dni),
      }));
      const out = [];
      if (pa.length) out.push({ k: 'g1', grp: 1, t: 'Pacientes' }, ...pa);
      if (pg.length) out.push({ k: 'g2', grp: 1, t: 'Secciones' }, ...pg);
      return out;
    },
    init() { this.$watch('items', () => { if (this.items[this.sel]?.grp || !this.items[this.sel]) this.sel = this.items.findIndex((i) => !i.grp); }); this.sel = this.items.findIndex((i) => !i.grp); },
    async search() {
      const q = this.q.trim();
      if (q.length < 2) { this.pacientes = []; return; }
      try { this.pacientes = (await api.get('/api/pacientes?q=' + encodeURIComponent(q))).slice(0, 5); } catch (e) { /* sin resultados */ }
    },
    move(d) {
      const idx = this.items.map((it, i) => (it.grp ? -1 : i)).filter((i) => i >= 0);
      if (!idx.length) return;
      const cur = idx.indexOf(this.sel);
      this.sel = idx[(cur + d + idx.length) % idx.length];
    },
    go(i = this.sel) {
      const it = this.items[i];
      if (!it || it.grp) return;
      Alpine.store('ui').cmdk = false;
      it.run();
    },
  }));
});
