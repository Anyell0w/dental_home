/* Núcleo: cliente API, stores globales (app/ui/router), directivas y utilidades. */
(() => {
  class ApiError extends Error {
    constructor(msg, status, code) { super(msg); this.status = status; this.code = code; }
  }

  async function req(method, url, body) {
    const opt = { method, headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' };
    if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    let r;
    try { r = await fetch(url, opt); } catch (e) { throw new ApiError('Sin conexión con el servidor.', 0); }
    let data = null;
    try { data = await r.json(); } catch (e) { /* sin cuerpo */ }
    if (!r.ok) {
      const err = new ApiError((data && data.error) || 'Ocurrió un error inesperado.', r.status, data && data.codigo);
      const app = Alpine.store('app');
      if (r.status === 401 && app.user) app.expire();
      if (r.status === 402 && err.code === 'suscripcion') location.hash = '#/suscripcion';
      throw err;
    }
    return data;
  }
  window.api = {
    get: (u) => req('GET', u), post: (u, b) => req('POST', u, b === undefined ? {} : b),
    put: (u, b) => req('PUT', u, b),
  };

  /* ---------- formato ---------- */
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  const parse = (iso) => { const [y, m, d] = iso.slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d); };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  window.fmt = {
    MESES, DIAS, parse, iso, today: () => iso(new Date()),
    initials: (s) => (s || '?').split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase(),
    long: (i) => { const d = parse(i); return `${DIAS[d.getDay()]} ${d.getDate()} de ${MESES[d.getMonth()]}`; },
    short: (i) => { const d = parse(i); return `${d.getDate()} ${MESES[d.getMonth()].slice(0, 3)} ${d.getFullYear()}`; },
    add: (i, n) => { const d = parse(i); d.setDate(d.getDate() + n); return iso(d); },
    ago: (s) => {
      if (!s) return '';
      const t = new Date(s.length <= 10 ? s + 'T00:00:00' : s), m = Math.round((Date.now() - t) / 60000);
      if (m < 1) return 'justo ahora'; if (m < 60) return `hace ${m} min`;
      if (m < 1440) return `hace ${Math.round(m / 60)} h`;
      const d = Math.round(m / 1440); return d === 1 ? 'ayer' : d < 30 ? `hace ${d} días` : fmt.short(s);
    },
    saludo: () => { const h = new Date().getHours(); return h < 12 ? 'Buenos días' : h < 19 ? 'Buenas tardes' : 'Buenas noches'; },
    cap: (s) => (s ? s[0].toUpperCase() + s.slice(1) : ''),
  };

  document.addEventListener('alpine:init', () => {
    /* ---------- UI global ---------- */
    Alpine.store('ui', {
      toasts: [], cmdk: false, dialog: null, _res: null,
      toast(msg, type = 'ok') {
        const id = Math.random();
        this.toasts.push({ id, msg, type });
        setTimeout(() => { this.toasts = this.toasts.filter((t) => t.id !== id); }, type === 'error' ? 5200 : 3200);
      },
      error(e) { this.toast(e && e.message ? e.message : String(e), 'error'); },
      confirm(opts) { this.dialog = opts; return new Promise((r) => { this._res = r; }); },
      answer(v) { this.dialog = null; if (this._res) this._res(v); this._res = null; },
    });

    /* ---------- sesión / tema ---------- */
    Alpine.store('app', {
      user: null, clinica: null, sub: null, uso: null, ready: false,
      theme: document.documentElement.dataset.theme || 'light',
      async load() {
        try { const d = await api.get('/api/me'); if (d.usuario) this.set(d); else this.user = null; } catch (e) { this.user = null; }
        this.ready = true;
      },
      set(d) { this.user = d.usuario; this.clinica = d.clinica; this.sub = d.suscripcion; this.uso = d.uso; },
      async refresh() { try { this.set(await api.get('/api/me')); } catch (e) { /* 401 gestionado */ } },
      async logout() {
        try { await api.post('/api/logout'); } catch (e) { /* ya cerrada */ }
        this.user = null; location.hash = '#/';
      },
      expire() { this.user = null; Alpine.store('ui').toast('Tu sesión expiró. Inicia sesión de nuevo.', 'error'); location.hash = '#/login'; },
      is(...roles) { return !!this.user && roles.includes(this.user.rol); },
      toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = this.theme;
        try { localStorage.setItem('dh-theme', this.theme); } catch (e) { /* modo privado */ }
        window.dispatchEvent(new CustomEvent('themechange'));
      },
    });

    /* ---------- router por hash ---------- */
    const CLIN = ['Doctor', 'Administrador'], ADM = ['Administrador'];
    const ROUTES = {
      '': { v: 'landing', pub: 1 }, login: { v: 'login', pub: 1 }, registro: { v: 'registro', pub: 1 },
      inicio: { v: 'inicio' }, pacientes: { v: 'pacientes' }, citas: { v: 'citas' },
      historial: { v: 'historial', roles: CLIN }, reportes: { v: 'reportes', roles: ADM },
      copias: { v: 'copias', roles: ADM }, equipo: { v: 'equipo', roles: ADM }, suscripcion: { v: 'suscripcion', roles: ADM },
    };
    const cache = {};
    Alpine.store('router', {
      html: '', name: '', params: [], query: {}, pub: true,
      async go() {
        const app = Alpine.store('app');
        const raw = location.hash.replace(/^#\/?/, '');
        const [path, qs] = raw.split('?');
        const [name, ...params] = path.split('/');
        let route = ROUTES[name];
        let target = name;
        if (!route) { target = app.user ? 'inicio' : ''; route = ROUTES[target]; }
        if (!route.pub && !app.user) { target = 'login'; route = ROUTES.login; }
        else if (app.user && (target === 'login' || target === 'registro')) { target = 'inicio'; route = ROUTES.inicio; }
        else if (route.roles && !route.roles.includes(app.user.rol)) { target = 'inicio'; route = ROUTES.inicio; }
        if (target !== name) { history.replaceState(null, '', '#/' + target); }
        this.query = Object.fromEntries(new URLSearchParams(qs || ''));
        this.params = target === name ? params : [];
        const changed = this.name !== target || this.pub !== !!route.pub;
        this.name = target; this.pub = !!route.pub;
        if (!cache[route.v]) {
          const r = await fetch(`/static/views/${route.v}.html`);
          cache[route.v] = await r.text();
        }
        this.html = '';
        await Alpine.nextTick();
        this.html = cache[route.v];
        document.title = (target ? fmt.cap(target) + ' · ' : '') + 'Dental Home';
        if (changed || true) window.scrollTo({ top: 0 });
      },
    });

    /* ---------- directivas ---------- */
    // x-count="valor": anima números hacia el valor
    Alpine.directive('count', (el, { expression }, { evaluateLater, effect }) => {
      const get = evaluateLater(expression);
      let from = 0, raf;
      effect(() => get((v) => {
        const to = Number(v) || 0;
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) { el.textContent = to.toLocaleString('es-PE'); from = to; return; }
        const t0 = performance.now(), dur = 900, a = from;
        cancelAnimationFrame(raf);
        const tick = (t) => {
          const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 4);
          el.textContent = Math.round(a + (to - a) * e).toLocaleString('es-PE');
          if (p < 1) raf = requestAnimationFrame(tick); else from = to;
        };
        raf = requestAnimationFrame(tick);
      }));
    });
    // x-reveal: aparece al entrar en pantalla
    Alpine.directive('reveal', (el) => {
      el.classList.add('reveal');
      const io = new IntersectionObserver((es) => es.forEach((e) => {
        if (e.isIntersecting) { el.classList.add('in'); io.disconnect(); }
      }), { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
      io.observe(el);
    });
  });

  window.scrollToId = (id) => {
    if (location.hash.replace('#/', '').split('?')[0] !== '') { location.hash = '#/'; }
    setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
  };

  document.addEventListener('alpine:initialized', async () => {
    await Alpine.store('app').load();
    window.addEventListener('hashchange', () => Alpine.store('router').go());
    Alpine.store('router').go();
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k' && Alpine.store('app').user) {
        e.preventDefault(); Alpine.store('ui').cmdk = !Alpine.store('ui').cmdk;
      }
    });
  });
})();
