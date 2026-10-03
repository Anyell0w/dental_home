/* Componentes Alpine de cada vista. La lógica de negocio vive en el servidor
   (controladores Python); aquí solo estado de pantalla y llamadas a la API. */
document.addEventListener('alpine:init', () => {
  const ui = () => Alpine.store('ui');
  const app = () => Alpine.store('app');
  const HORAS = [];
  for (let h = 8; h < 20; h++) for (const m of ['00', '30']) HORAS.push(`${String(h).padStart(2, '0')}:${m}`);

  // Ejecuta una acción con estado "ocupado" y error visible en el formulario
  async function run(vm, fn) {
    vm.busy = true; vm.error = '';
    try { return await fn(); } catch (e) { vm.error = e.message; return undefined; } finally { vm.busy = false; }
  }

  /* ------------------------------ público ------------------------------ */
  Alpine.data('landing', () => ({
    ok: false, planes: [], dispose: null,
    feats: [
      { i: 'calendar', t: 'Agenda sin choques', d: 'Vista por día, semana y mes. Si un doctor ya tiene ese horario, te avisamos al instante.' },
      { i: 'users', t: 'Pacientes y fichas', d: 'Registro con DNI, búsqueda inmediata y toda su historia clínica a un clic.' },
      { i: 'tooth', t: 'Odontograma interactivo', d: '32 piezas, 5 caras por pieza y las condiciones que usas a diario. Se guarda por paciente.' },
      { i: 'pill', t: 'Recetas en PDF', d: 'Medicamentos e indicaciones con el membrete de tu consultorio, listas para imprimir.' },
      { i: 'chart', t: 'Reportes y respaldos', d: 'Exporta citas, pacientes y actividad en PDF o Excel. Descarga copias de seguridad cuando quieras.' },
      { i: 'shield', t: 'Equipo con permisos', d: 'Doctores, recepción y administración ven solo lo que necesitan. Datos aislados por consultorio.' },
    ],
    async init() {
      try { this.planes = await api.get('/api/planes'); } catch (e) { /* sin planes */ }
      try {
        const c = document.createElement('canvas');
        if (!(c.getContext('webgl2') || c.getContext('webgl'))) throw new Error('sin WebGL');
        const { mountTooth } = await import('/static/js/tooth3d.js');
        this.dispose = mountTooth(this.$refs.stage);
        this.ok = true;
      } catch (e) { this.ok = false; }
    },
    destroy() { if (this.dispose) this.dispose(); },
  }));

  Alpine.data('loginView', () => ({
    f: { clinica: (() => { try { return localStorage.getItem('dh-clinica') || ''; } catch (e) { return ''; } })(), usuario: '', password: '' },
    busy: false, error: '',
    async submit() {
      await run(this, async () => {
        const slug = this.f.clinica.trim().toLowerCase();
        await api.post('/api/login', { ...this.f, clinica: slug });
        try { localStorage.setItem('dh-clinica', slug); } catch (e) { /* privado */ }
        await app().load(); location.hash = '#/inicio';
      });
    },
  }));

  Alpine.data('registroView', () => ({
    planes: [], busy: false, error: '',
    f: { clinica: '', email: '', usuario: 'admin', password: '', demo: true, plan: 'profesional' },
    async init() {
      try { this.planes = await api.get('/api/planes'); } catch (e) { /* ok */ }
      const p = Alpine.store('router').query.plan; if (p) this.f.plan = p;
    },
    async submit() {
      await run(this, async () => {
        const r = await api.post('/api/registro', this.f);
        try { localStorage.setItem('dh-clinica', r.slug); } catch (e) { /* privado */ }
        await app().load(); location.hash = '#/inicio';
        ui().toast(`¡Listo! El código de tu clínica es "${r.slug}".`);
      });
    },
  }));

  /* ------------------------------ inicio ------------------------------ */
  Alpine.data('inicioView', () => ({
    d: null, circ: 2 * Math.PI * 38,
    async init() { try { this.d = await api.get('/api/dashboard'); } catch (e) { ui().error(e); } },
    get maxSemana() { return Math.max(1, ...this.d.semana.map((s) => s.citas)); },
    get progreso() { return this.d.stats.citas_hoy ? this.d.stats.citas_completadas / this.d.stats.citas_hoy : 0; },
    get pendientesInicio() { return this.d.inicio.filter((t) => !t.hecho); },
  }));

  /* ------------------------------ pacientes ------------------------------ */
  Alpine.data('pacientesView', () => ({
    lista: [], q: '', todos: false, cargando: true, form: null, busy: false, error: '',
    async init() {
      const qq = Alpine.store('router').query;
      if (qq.q) this.q = qq.q;
      await this.cargar();
      if (qq.nuevo) this.nuevo();
    },
    async cargar() {
      try { this.lista = await api.get(`/api/pacientes?q=${encodeURIComponent(this.q)}&todos=${this.todos ? 1 : 0}`); }
      catch (e) { ui().error(e); }
      this.cargando = false;
    },
    nuevo() { this.error = ''; this.form = { nombre: '', apellido: '', dni: '', telefono: '', fechaNacimiento: '', sexo: '', direccion: '' }; },
    editar(p) { this.error = ''; this.form = { ...p }; },
    async guardar() {
      await run(this, async () => {
        const f = this.form;
        if (f.id) await api.put('/api/pacientes/' + f.id, f); else await api.post('/api/pacientes', f);
        ui().toast(f.id ? 'Paciente actualizado' : 'Paciente registrado');
        this.form = null; await this.cargar(); app().refresh();
      });
    },
    async baja(p) {
      if (!(await ui().confirm({ title: 'Dar de baja', text: `${p.nombreCompleto} dejará de aparecer entre los pacientes activos y su historial quedará congelado.`, ok: 'Dar de baja', danger: true }))) return;
      try { await api.post(`/api/pacientes/${p.id}/baja`); ui().toast('Paciente dado de baja'); await this.cargar(); } catch (e) { ui().error(e); }
    },
  }));

  /* ------------------------------ citas ------------------------------ */
  Alpine.data('citasView', () => ({
    HORAS, periodo: 'dia', fecha: fmt.today(), doctor: '', doctores: [], citas: [], rango: null, cargando: true,
    form: null, rep: null, canc: null, ocupadas: [], busy: false, error: '',
    async init() {
      try { this.doctores = await api.get('/api/doctores'); } catch (e) { /* ok */ }
      await this.cargar();
      if (Alpine.store('router').query.nueva) this.nueva();
    },
    async cargar() {
      this.cargando = true;
      try {
        const r = await api.get(`/api/citas?fecha=${this.fecha}&periodo=${this.periodo}&doctor=${this.doctor}`);
        this.citas = r.citas; this.rango = r.rango;
      } catch (e) { ui().error(e); }
      this.cargando = false;
    },
    get titulo() {
      const d = fmt.parse(this.fecha);
      if (this.periodo === 'dia') return fmt.long(this.fecha);
      if (this.periodo === 'mes') return `${fmt.MESES[d.getMonth()]} ${d.getFullYear()}`;
      if (!this.rango) return '';
      const a = fmt.parse(this.rango.inicio), b = fmt.parse(this.rango.fin);
      return `${a.getDate()} ${fmt.MESES[a.getMonth()].slice(0, 3)} – ${b.getDate()} ${fmt.MESES[b.getMonth()].slice(0, 3)}`;
    },
    get resumen() {
      const p = this.citas.filter((c) => c.estado === 'Pendiente').length;
      return `${this.citas.length} citas · ${p} pendientes`;
    },
    mover(n) {
      const d = fmt.parse(this.fecha);
      if (this.periodo === 'dia') d.setDate(d.getDate() + n);
      else if (this.periodo === 'semana') d.setDate(d.getDate() + 7 * n);
      else d.setMonth(d.getMonth() + n, 1);
      this.fecha = fmt.iso(d); this.cargar();
    },
    hoy() { this.fecha = fmt.today(); this.cargar(); },
    irDia(f) { this.fecha = f; this.periodo = 'dia'; this.cargar(); },
    porDia(f) { return this.citas.filter((c) => c.fecha === f); },
    get diasSemana() { return this.rango ? Array.from({ length: 7 }, (_, i) => fmt.add(this.rango.inicio, i)) : []; },
    get celdasMes() {
      const d = fmt.parse(this.fecha); d.setDate(1);
      const lead = (d.getDay() + 6) % 7, start = fmt.add(fmt.iso(d), -lead), mes = d.getMonth();
      const out = [];
      for (let i = 0; i < 42; i++) { const f = fmt.add(start, i); out.push({ f, dentro: fmt.parse(f).getMonth() === mes }); }
      return out.slice(0, out.slice(35).some((c) => c.dentro) ? 42 : 35);
    },
    // ----- nueva cita
    nueva() {
      this.error = ''; this.ocupadas = [];
      this.form = { q: '', res: [], paciente: null, doctorId: app().is('Doctor') ? app().user.id : (this.doctor || (this.doctores.length === 1 ? this.doctores[0].id : '')), fecha: this.fecha, hora: '' };
      this.libres();
    },
    async buscarPaciente() {
      if (this.form.q.trim().length < 2) { this.form.res = []; return; }
      try { this.form.res = (await api.get('/api/pacientes?q=' + encodeURIComponent(this.form.q))).slice(0, 8); } catch (e) { /* ok */ }
    },
    async libresDe(doctorId, fecha, excluir) {
      if (!doctorId || !fecha) { this.ocupadas = []; return; }
      try {
        const r = await api.get(`/api/citas?fecha=${fecha}&periodo=dia&doctor=${doctorId}`);
        this.ocupadas = r.citas.filter((c) => c.estado === 'Pendiente' && c.id !== excluir).map((c) => c.hora);
      } catch (e) { /* ok */ }
    },
    async libres() { await this.libresDe(this.form.doctorId, this.form.fecha); if (this.ocupadas.includes(this.form.hora)) this.form.hora = ''; },
    async guardar() {
      await run(this, async () => {
        const f = this.form;
        await api.post('/api/citas', { pacienteId: f.paciente.id, doctorId: Number(f.doctorId) || null, fecha: f.fecha, hora: f.hora });
        ui().toast('Cita agendada'); this.form = null;
        this.fecha = f.fecha; if (this.periodo === 'mes') { /* se queda */ } await this.cargar();
      });
    },
    // ----- acciones
    async completar(c) {
      try {
        await api.post(`/api/citas/${c.id}/completar`);
        const b = document.getElementById('ok' + c.id); if (b) b.classList.add('burst');
        ui().toast('Cita completada ✓'); setTimeout(() => this.cargar(), 450);
      } catch (e) { ui().error(e); }
    },
    reprogramar(c) { this.error = ''; this.rep = { c, fecha: c.fecha, hora: '' }; this.libresRep(); },
    async libresRep() { await this.libresDe(this.rep.c.doctorId, this.rep.fecha, this.rep.c.id); if (this.ocupadas.includes(this.rep.hora)) this.rep.hora = ''; },
    async guardarRep() {
      await run(this, async () => {
        await api.post(`/api/citas/${this.rep.c.id}/reprogramar`, { fecha: this.rep.fecha, hora: this.rep.hora });
        ui().toast('Cita reprogramada'); this.rep = null; await this.cargar();
      });
    },
    cancelar(c) { this.error = ''; this.canc = { c, motivo: '' }; },
    async guardarCanc() {
      await run(this, async () => {
        await api.post(`/api/citas/${this.canc.c.id}/cancelar`, { motivo: this.canc.motivo });
        ui().toast('Cita cancelada'); this.canc = null; await this.cargar();
      });
    },
  }));

  /* ------------------------------ historial ------------------------------ */
  Alpine.data('historialView', () => ({
    pid: null, det: null, tab: 'consultas', q: '', pacientes: [], cargando: false, nota: '',
    cf: null, rf: null, busy: false, error: '',
    async init() {
      const r = Alpine.store('router');
      this.pid = r.params[0] ? Number(r.params[0]) : null;
      if (this.pid) { await this.cargar(); if (r.query.cita && this.det?.citasPendientes.some((c) => c.id === Number(r.query.cita))) this.nuevaConsulta(Number(r.query.cita)); }
    },
    async buscar() {
      this.cargando = true;
      try { this.pacientes = await api.get('/api/pacientes?q=' + encodeURIComponent(this.q)); } catch (e) { ui().error(e); }
      this.cargando = false;
    },
    async cargar() {
      try { this.det = await api.get(`/api/pacientes/${this.pid}/historial`); }
      catch (e) { ui().error(e); location.hash = '#/historial'; }
    },
    nuevaConsulta(citaId) {
      this.error = '';
      this.cf = { citaId: citaId || this.det.citasPendientes[0]?.id, diagnostico: '', tratamiento: '', observaciones: '' };
    },
    editarConsulta(r) { this.error = ''; this.cf = { id: r.id, diagnostico: r.diagnostico, tratamiento: r.tratamiento, observaciones: '' }; },
    async guardarConsulta() {
      await run(this, async () => {
        const f = this.cf;
        if (f.id) await api.put('/api/registros/' + f.id, f);
        else await api.post(`/api/citas/${f.citaId}/registro`, f);
        ui().toast('Consulta guardada'); this.cf = null; await this.cargar();
      });
    },
    nuevaReceta(r) { this.error = ''; this.rf = { registroId: r.id, indicaciones: '', meds: [{ nombre: '', cantidad: 1, indicaciones: '' }] }; },
    async guardarReceta() {
      await run(this, async () => {
        await api.post(`/api/registros/${this.rf.registroId}/receta`, { indicaciones: this.rf.indicaciones, medicamentos: this.rf.meds });
        ui().toast('Receta generada'); this.rf = null; await this.cargar();
      });
    },
    async agregarNota() {
      await run(this, async () => {
        await api.post(`/api/historiales/${this.det.historial.id}/observacion`, { texto: this.nota });
        this.nota = ''; ui().toast('Nota agregada'); await this.cargar();
      });
    },
  }));

  /* ------------------------------ reportes ------------------------------ */
  Alpine.data('reportesView', () => {
    const hoy = fmt.today(), y = hoy.slice(0, 4);
    return {
      TIPOS: ['Citas', 'Pacientes', 'Actividad'], lista: [], busy: false, error: '',
      f: { tipo: 'Citas', formato: 'PDF', inicio: `${y}-01-01`, fin: hoy },
      async init() { try { this.lista = await api.get('/api/reportes'); } catch (e) { ui().error(e); } },
      async generar() {
        await run(this, async () => {
          const r = await api.post('/api/reportes', this.f);
          ui().toast('Reporte generado'); this.lista = await api.get('/api/reportes');
          window.location.href = `/api/reportes/${r.id}/archivo`;
        });
      },
    };
  });

  /* ------------------------------ copias ------------------------------ */
  Alpine.data('copiasView', () => ({
    lista: [], busy: false,
    get ultima() { return this.lista.find((c) => c.estado === 'Exitoso'); },
    async init() { try { this.lista = await api.get('/api/copias'); } catch (e) { ui().error(e); } },
    async crear() {
      this.busy = true;
      try {
        const c = await api.post('/api/copias');
        ui().toast(c.estado === 'Exitoso' ? 'Copia creada' : 'La copia falló', c.estado === 'Exitoso' ? 'ok' : 'error');
        this.lista = await api.get('/api/copias');
      } catch (e) { ui().error(e); }
      this.busy = false;
    },
  }));

  /* ------------------------------ equipo ------------------------------ */
  Alpine.data('equipoView', () => ({
    lista: [], form: null, clave: null, busy: false, error: '',
    async init() { await this.cargar(); },
    async cargar() { try { this.lista = await api.get('/api/usuarios'); } catch (e) { ui().error(e); } app().refresh(); },
    nuevo() { this.error = ''; this.form = { rol: 'Doctor', usuario: '', password: '', colegiatura: '', turno: 'Tiempo Completo' }; },
    editar(u) { this.error = ''; this.form = { id: u.id, usuario: u.usuario, rol: u.rol, colegiatura: u.colegiatura || '', turno: u.turno || 'Tiempo Completo' }; },
    async guardar() {
      await run(this, async () => {
        const f = this.form;
        if (f.id) await api.put('/api/usuarios/' + f.id, { colegiatura: f.colegiatura, turno: f.turno });
        else await api.post('/api/usuarios', f);
        ui().toast(f.id ? 'Perfil actualizado' : 'Miembro agregado'); this.form = null; await this.cargar();
      });
    },
    async resetear() {
      await run(this, async () => {
        await api.post(`/api/usuarios/${this.clave.u.id}/password`, { nueva: this.clave.nueva });
        ui().toast('Contraseña actualizada'); this.clave = null;
      });
    },
    async alternar(u) {
      if (u.activo && !(await ui().confirm({ title: 'Desactivar usuario', text: `${u.usuario} ya no podrá iniciar sesión. Podrás reactivarlo cuando quieras.`, ok: 'Desactivar', danger: true }))) return;
      try { await api.post(`/api/usuarios/${u.id}/estado`, { activo: !u.activo }); await this.cargar(); } catch (e) { ui().error(e); }
    },
    async copiar() {
      try { await navigator.clipboard.writeText(app().clinica.slug); ui().toast('Código copiado'); } catch (e) { ui().toast(app().clinica.slug); }
    },
  }));

  /* ------------------------------ suscripción ------------------------------ */
  Alpine.data('suscripcionView', () => ({
    planes: [],
    get sub() { return app().sub; }, get uso() { return app().uso; },
    pct(k) { const m = this.sub.plan['max_' + k]; return m ? Math.min(100, Math.round((this.uso[k] / m) * 100)) : 0; },
    actual(p) { return this.sub.plan.id === p.id && this.sub.estado === 'activa'; },
    async init() { try { this.planes = await api.get('/api/planes'); } catch (e) { ui().error(e); } },
    async elegir(p) {
      if (!(await ui().confirm({ title: `Activar plan ${p.nombre}`, text: `S/ ${p.precio} al mes. En esta versión de demostración no se realiza ningún cobro.`, ok: 'Activar plan' }))) return;
      try { app().set(await api.post('/api/suscripcion/plan', { plan: p.id })); ui().toast(`Plan ${p.nombre} activado`); } catch (e) { ui().error(e); }
    },
    async cancelar() {
      if (!(await ui().confirm({ title: 'Cancelar suscripción', text: 'Podrás seguir consultando tu información, pero no registrar cambios nuevos.', ok: 'Cancelar suscripción', danger: true }))) return;
      try { app().set(await api.post('/api/suscripcion/cancelar')); ui().toast('Suscripción cancelada'); } catch (e) { ui().error(e); }
    },
  }));
});
