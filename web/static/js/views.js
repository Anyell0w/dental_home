/* Componentes Alpine de cada vista. La lógica de negocio vive en el servidor
   (web/api_*.py sobre PostgreSQL); aquí solo estado de pantalla y llamadas a la API. */
document.addEventListener('alpine:init', () => {
  const ui = () => Alpine.store('ui');
  const app = () => Alpine.store('app');
  const HORAS = [];
  for (let h = 7; h < 21; h++) for (const m of ['00', '30']) HORAS.push(`${String(h).padStart(2, '0')}:${m}`);
  const DURACIONES = [15, 30, 45, 60, 90, 120];
  const guardarCodigo = (c) => { try { localStorage.setItem('dh-clinica', c); } catch (e) { /* privado */ } };
  const codigoGuardado = () => { try { return localStorage.getItem('dh-clinica') || ''; } catch (e) { return ''; } };

  // Ejecuta una acción con estado "ocupado" y error visible en el formulario
  async function run(vm, fn) {
    vm.busy = true; vm.error = '';
    try { return await fn(); } catch (e) { vm.error = e.message; return undefined; } finally { vm.busy = false; }
  }

  /* ------------------------------ landing ------------------------------ */
  Alpine.data('landing', () => {
    const A = { bg: '#FFFFFF', fg: '#4A2E80' }, B = { bg: '#B39DDB', fg: '#1E1433' }, C = { bg: 'rgba(255,255,255,0.12)', fg: '#E1D5E7' };
    const s = (t, h, k) => ({ t, h, bg: k.bg, fg: k.fg });
    const teeth = (marks) => marks.map((m) => (m === 1 ? { bg: '#7B1FA2', ring: '#7B1FA2' } : m === 2 ? { bg: '#B39DDB', ring: '#B39DDB' } : { bg: '#F4F1F8', ring: '#E1D5E7' }));
    const marquee = ['Agenda', 'Odontograma', 'Historia clínica', 'Recordatorios por WhatsApp', 'Yape y Plin', 'Presupuestos', 'Reportes', 'Multiusuario', 'En la nube'];
    return {
      openFaq: 0, planes: [],
      nav: [['funciones', 'Funciones'], ['como-funciona', 'Cómo funciona'], ['planes', 'Planes'], ['nosotros', 'Quiénes somos'], ['preguntas', 'Preguntas']],
      appts: [
        { time: '09:00', name: 'Rosa M.', proc: 'Limpieza y profilaxis', status: 'Confirmada', color: '#7B1FA2', bg: '#F4F1F8' },
        { time: '10:30', name: 'Jorge Q.', proc: 'Endodoncia · 2.ª sesión', status: 'En sala', color: '#1E7A46', bg: '#FFFFFF' },
        { time: '12:00', name: 'Lucía C.', proc: 'Control de ortodoncia', status: 'Recordada', color: '#4A2E80', bg: '#FFFFFF' },
        { time: '15:30', name: 'Mario A.', proc: 'Evaluación inicial', status: 'Nueva', color: '#7B1FA2', bg: '#FFFFFF' },
      ],
      marquee: marquee.concat(marquee),
      week: [
        { day: 'LUN', slots: [s('Limpieza', '56px', A), s('Resina', '80px', B), s('', '40px', C)] },
        { day: 'MAR', slots: [s('', '30px', C), s('Endodoncia', '100px', A), s('Control', '50px', B)] },
        { day: 'MIÉ', slots: [s('Ortodoncia', '70px', B), s('', '40px', C), s('Extracción', '64px', A)] },
        { day: 'JUE', slots: [s('Evaluación', '50px', A), s('Blanqueamiento', '96px', B)] },
        { day: 'VIE', slots: [s('', '44px', C), s('Profilaxis', '60px', A), s('Corona', '70px', B)] },
      ],
      teethTop: teeth([0, 0, 2, 0, 1, 0, 0, 0]), teethBottom: teeth([0, 1, 0, 0, 0, 2, 2, 0]),
      steps: [
        { n: '01', title: 'Crea tu consultorio', text: 'Regístrate en un minuto y prueba 14 días gratis, con datos de ejemplo para explorar.' },
        { n: '02', title: 'Configuramos contigo', text: 'Registramos tus odontólogos, horarios y pacientes, y te acompañamos en la primera semana.' },
        { n: '03', title: 'Atiende y crece', text: 'Usa Dental Home desde cualquier computadora o celular, con soporte cuando lo necesites.' },
      ],
      cities: ['Puno', 'Juliaca', 'Ilave', 'Azángaro', 'Ayaviri', 'Todo el Perú'],
      faqs: [
        { q: '¿Necesito instalar algo en mi computadora?', a: 'No. Dental Home funciona desde el navegador de tu computadora, tablet o celular. Solo necesitas conexión a internet.' },
        { q: '¿Funciona si el internet de mi consultorio es lento?', a: 'Sí. El sistema está optimizado para cargar rápido y consumir pocos datos, pensando en la conectividad de la región.' },
        { q: '¿Pueden pasar mis pacientes de Excel o de mi cuaderno?', a: 'Sí. Durante la configuración te ayudamos a migrar tu lista de pacientes para que no empieces desde cero.' },
        { q: '¿Mis datos y los de mis pacientes están seguros?', a: 'Cada consultorio está aislado en la base de datos, cada usuario ingresa con su propia cuenta y todas las acciones quedan registradas en la auditoría.' },
        { q: '¿Puedo cambiar de plan o cancelar cuando quiera?', a: 'Sí. Puedes subir o bajar de plan según crezca tu consultorio, sin contratos de permanencia.' },
      ],
      get plans() {
        const who = { esencial: 'Para el odontólogo independiente', profesional: 'Para consultorios en crecimiento', clinica: 'Para clínicas medianas' };
        return this.planes.map((p) => {
          const hot = p.codigo === 'profesional';
          const feats = [p.max_usuarios ? `Hasta ${p.max_usuarios} usuarios` : 'Usuarios ilimitados',
            p.max_pacientes ? `Hasta ${p.max_pacientes.toLocaleString('es-PE')} pacientes activos` : 'Pacientes ilimitados',
            'Agenda, historia clínica y odontograma', 'Recetas en PDF y recordatorios',
            p.permite_excel ? 'Reportes en PDF y Excel' : 'Reportes en PDF'];
          if (p.permite_respaldos) feats.push('Copias de seguridad automáticas');
          return {
            ...p, featured: hot, who: who[p.codigo] || '', feats,
            cta: hot ? `Elegir ${p.nombre}` : `Empezar con ${p.nombre}`,
            btn: hot ? 'lp-btn-light' : 'lp-btn-ghost', bg: hot ? '#4A2E80' : '#F4F1F8', fg: hot ? '#FFFFFF' : '#1E1433',
            muted: hot ? '#E1D5E7' : '#5B5070', line: hot ? 'rgba(255,255,255,0.2)' : '#E1D5E7', check: hot ? '#B39DDB' : '#7B1FA2',
            shadow: hot ? '0 40px 80px -30px rgba(74,46,128,0.7)' : 'none',
          };
        });
      },
      async init() { try { this.planes = await api.get('/api/planes'); } catch (e) { /* sin planes */ } },
    };
  });

  /* ------------------------------ acceso ------------------------------ */
  Alpine.data('loginView', () => ({
    f: { clinica: codigoGuardado(), usuario: '', password: '' }, busy: false, error: '',
    async submit() {
      await run(this, async () => {
        const codigo = this.f.clinica.trim().toLowerCase();
        await api.post('/api/login', { ...this.f, clinica: codigo });
        guardarCodigo(codigo);
        await app().load(); location.hash = '#/inicio';
      });
    },
  }));

  Alpine.data('olvideView', () => ({
    f: { clinica: codigoGuardado(), correo: '' }, busy: false, error: '', enviado: '',
    async submit() { await run(this, async () => { this.enviado = (await api.post('/api/recuperar', this.f)).mensaje; }); },
  }));

  Alpine.data('restablecerView', () => ({
    f: { password: '', repetir: '' }, busy: false, error: '', listo: false,
    async submit() {
      if (this.f.password !== this.f.repetir) { this.error = 'Las contraseñas no coinciden.'; return; }
      const q = Alpine.store('router').query;
      await run(this, async () => { await api.post('/api/restablecer', { c: q.c, t: q.t, password: this.f.password }); this.listo = true; });
    },
  }));

  Alpine.data('registroView', () => ({
    planes: [], busy: false, error: '',
    f: { clinica: '', correo: '', usuario: 'admin', password: '', demo: true, plan: 'profesional', atiende: true, colegiatura: '' },
    async init() {
      try { this.planes = await api.get('/api/planes'); } catch (e) { /* ok */ }
      const p = Alpine.store('router').query.plan; if (p) this.f.plan = p;
    },
    async submit() {
      await run(this, async () => {
        const r = await api.post('/api/registro', this.f);
        guardarCodigo(r.codigo);
        await app().load(); location.hash = '#/inicio';
        ui().toast(`¡Listo! El código de tu clínica es "${r.codigo}".`);
      });
    },
  }));

  /* ------------------------------ inicio ------------------------------ */
  Alpine.data('inicioView', () => ({
    d: null, circ: 2 * Math.PI * 40,
    async init() { try { this.d = await api.get('/api/dashboard'); } catch (e) { ui().error(e); } },
    get maxSemana() { return Math.max(1, ...this.d.semana.map((s) => s.citas)); },
    get progreso() { return this.d.stats.citas_hoy ? this.d.stats.completadas_hoy / this.d.stats.citas_hoy : 0; },
    get pendientesInicio() { return this.d.inicio.filter((t) => !t.hecho); },
    enCurso(c) { const n = new Date(), m = n.getHours() * 60 + n.getMinutes(); return c.estado === 'pendiente' && c.fecha === fmt.today() && fmt.min(c.hora) <= m && m < fmt.min(c.horaFin); },
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
    nuevo() { this.error = ''; this.form = { tipoDocumento: 'DNI', numeroDocumento: '', nombres: '', apellidos: '', sexo: '', fechaNacimiento: '', telefono: '', correo: '', direccion: '' }; },
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
      if (!(await ui().confirm({ title: 'Dar de baja', text: `${p.nombreCompleto} dejará de aparecer entre los pacientes activos y se cancelarán sus citas futuras. Su historial se conserva.`, ok: 'Dar de baja', danger: true }))) return;
      try {
        const r = await api.post(`/api/pacientes/${p.id}/baja`);
        ui().toast(r.citasCanceladas ? `Paciente dado de baja · ${r.citasCanceladas} citas canceladas` : 'Paciente dado de baja');
        await this.cargar(); app().refresh();
      } catch (e) { ui().error(e); }
    },
    async reactivar(p) {
      try { await api.post(`/api/pacientes/${p.id}/reactivar`); ui().toast('Paciente reactivado'); await this.cargar(); app().refresh(); } catch (e) { ui().error(e); }
    },
  }));

  /* ------------------------------ agenda ------------------------------ */
  Alpine.data('citasView', () => ({
    HORAS, DURACIONES, periodo: 'dia', fecha: fmt.today(), doctor: '', doctores: [], citas: [], rango: null, cargando: true,
    form: null, rep: null, canc: null, ocupadas: [], busy: false, error: '',
    async init() {
      try { this.doctores = await api.get('/api/doctores'); } catch (e) { /* ok */ }
      const q = Alpine.store('router').query;
      if (q.fecha) this.fecha = q.fecha;
      await this.cargar();
      if (q.nueva) this.nueva(q.paciente ? Number(q.paciente) : null);
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
      const p = this.citas.filter((c) => c.estado === 'pendiente').length;
      return `${this.citas.length} ${this.citas.length === 1 ? 'cita' : 'citas'} · ${p} pendientes`;
    },
    get soyDoctor() { return app().is('doctor'); },
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
    enCurso(c) { const n = new Date(), m = n.getHours() * 60 + n.getMinutes(); return c.estado === 'pendiente' && c.fecha === fmt.today() && fmt.min(c.hora) <= m && m < fmt.min(c.horaFin); },
    // disponibilidad: un horario está libre si [inicio, inicio + duración) no se cruza con otra cita del doctor
    libre(h, fecha, dur) {
      const a = fmt.min(h), b = a + Number(dur);
      if (fecha === fmt.today()) { const n = new Date(); if (a < n.getHours() * 60 + n.getMinutes() - 5) return false; }
      if (fecha < fmt.today()) return false;
      return !this.ocupadas.some(([x, y]) => a < y && b > x);
    },
    async cargarOcupadas(doctorId, fecha, excluir) {
      if (!doctorId || !fecha) { this.ocupadas = []; return; }
      try {
        const r = await api.get(`/api/citas?fecha=${fecha}&periodo=dia&doctor=${doctorId}`);
        this.ocupadas = r.citas.filter((c) => c.estado !== 'cancelada' && c.id !== excluir).map((c) => [fmt.min(c.hora), fmt.min(c.horaFin)]);
      } catch (e) { /* ok */ }
    },
    // ----- nueva cita
    async nueva(pacienteId) {
      this.error = ''; this.ocupadas = [];
      const doctorId = this.soyDoctor ? app().user.id : (this.doctor || (this.doctores.length === 1 ? this.doctores[0].id : ''));
      this.form = { q: '', res: [], paciente: null, doctorId, fecha: this.fecha < fmt.today() ? fmt.today() : this.fecha, hora: '', minutos: 30 };
      if (pacienteId) {
        try { const lista = await api.get('/api/pacientes'); this.form.paciente = lista.find((p) => p.id === pacienteId) || null; } catch (e) { /* ok */ }
      }
      this.libres();
    },
    async buscarPaciente() {
      if (this.form.q.trim().length < 2) { this.form.res = []; return; }
      try { this.form.res = (await api.get('/api/pacientes?q=' + encodeURIComponent(this.form.q))).slice(0, 8); } catch (e) { /* ok */ }
    },
    async libres() {
      await this.cargarOcupadas(this.form.doctorId, this.form.fecha);
      if (this.form.hora && !this.libre(this.form.hora, this.form.fecha, this.form.minutos)) this.form.hora = '';
    },
    async guardar() {
      await run(this, async () => {
        const f = this.form;
        await api.post('/api/citas', { pacienteId: f.paciente.id, doctorId: Number(f.doctorId) || null, fecha: f.fecha, hora: f.hora, minutos: Number(f.minutos) });
        ui().toast('Cita agendada · recordatorio programado'); this.form = null;
        this.fecha = f.fecha; await this.cargar();
      });
    },
    // ----- acciones
    async completar(c) {
      try { await api.post(`/api/citas/${c.id}/completar`); ui().toast('Cita completada'); await this.cargar(); } catch (e) { ui().error(e); }
    },
    reprogramar(c) { this.error = ''; this.rep = { c, fecha: c.fecha < fmt.today() ? fmt.today() : c.fecha, hora: '', minutos: c.minutos }; this.libresRep(); },
    async libresRep() {
      await this.cargarOcupadas(this.rep.c.doctorId, this.rep.fecha, this.rep.c.id);
      if (this.rep.hora && !this.libre(this.rep.hora, this.rep.fecha, this.rep.minutos)) this.rep.hora = '';
    },
    async guardarRep() {
      await run(this, async () => {
        await api.post(`/api/citas/${this.rep.c.id}/reprogramar`, { fecha: this.rep.fecha, hora: this.rep.hora, minutos: Number(this.rep.minutos) });
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
    pid: null, det: null, tab: 'consultas', q: '', pacientes: [], cargando: false, doctores: [],
    notas: '', cf: null, rf: null, sugeridos: [], busy: false, error: '',
    async init() {
      const r = Alpine.store('router');
      this.pid = r.params[0] ? Number(r.params[0]) : null;
      if (this.pid) {
        await this.cargar();
        try { this.doctores = await api.get('/api/doctores'); } catch (e) { /* ok */ }
        if (r.query.cita && this.det?.citasAtendibles.some((c) => c.id === Number(r.query.cita))) this.nuevaConsulta(Number(r.query.cita));
      }
    },
    async buscar() {
      this.cargando = true;
      try { this.pacientes = await api.get('/api/pacientes?q=' + encodeURIComponent(this.q)); } catch (e) { ui().error(e); }
      this.cargando = false;
    },
    async cargar() {
      try { this.det = await api.get(`/api/pacientes/${this.pid}/historial`); this.notas = this.det.historial.observaciones; }
      catch (e) { ui().error(e); location.hash = '#/historial'; }
    },
    get puedeAtender() { return this.det.paciente.activo && (app().user.esDoctor || app().is('administrador')); },
    nuevaConsulta(citaId) {
      this.error = '';
      const id = citaId || this.det.citasAtendibles[0]?.id || 'sin';
      this.cf = { citaId: String(id), doctorId: app().user.esDoctor ? '' : String(this.doctores[0]?.id || ''), diagnostico: '', tratamiento: '', observaciones: '' };
    },
    editarConsulta(r) { this.error = ''; this.cf = { id: r.id, diagnostico: r.diagnostico, tratamiento: r.tratamiento, observaciones: r.observaciones }; },
    async guardarConsulta() {
      await run(this, async () => {
        const f = this.cf;
        if (f.id) await api.put('/api/registros/' + f.id, f);
        else if (f.citaId === 'sin') await api.post(`/api/pacientes/${this.pid}/atencion`, { ...f, doctorId: Number(f.doctorId) || null });
        else await api.post(`/api/citas/${f.citaId}/registro`, f);
        ui().toast('Consulta guardada'); this.cf = null; await this.cargar();
      });
    },
    nuevaReceta(r) { this.error = ''; this.rf = { registroId: r.id, indicaciones: '', meds: [{ nombre: '', presentacion: '', cantidad: 1, indicaciones: '' }] }; },
    async sugerir(m) {
      const q = m.nombre.trim();
      if (q.length < 2) return;
      try {
        this.sugeridos = await api.get('/api/medicamentos?q=' + encodeURIComponent(q));
        const hit = this.sugeridos.find((s) => s.nombre.toLowerCase() === q.toLowerCase());
        if (hit && !m.presentacion) m.presentacion = hit.presentacion || '';
      } catch (e) { /* opcional */ }
    },
    async guardarReceta() {
      await run(this, async () => {
        await api.post(`/api/registros/${this.rf.registroId}/receta`, { indicaciones: this.rf.indicaciones, medicamentos: this.rf.meds });
        ui().toast('Receta emitida'); this.rf = null; await this.cargar();
      });
    },
    async guardarNotas() {
      await run(this, async () => {
        await api.put(`/api/historiales/${this.det.historial.id}/observaciones`, { texto: this.notas });
        ui().toast('Antecedentes guardados'); await this.cargar();
      });
    },
  }));

  /* ------------------------------ reportes ------------------------------ */
  Alpine.data('reportesView', () => {
    const hoy = fmt.today();
    return {
      TIPOS: [['citas', 'Citas'], ['pacientes', 'Pacientes'], ['actividad', 'Actividad']], lista: [], busy: false, error: '',
      f: { tipo: 'citas', formato: 'pdf', inicio: fmt.add(hoy, -29), fin: hoy },
      rapido(dias) { this.f.fin = fmt.today(); this.f.inicio = fmt.add(this.f.fin, -(dias - 1)); },
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
    get permitido() { return app().sub.plan?.permite_respaldos; },
    get ultima() { return this.lista.find((c) => c.estado === 'exitoso'); },
    async init() { try { this.lista = await api.get('/api/copias'); } catch (e) { ui().error(e); } },
    async crear() {
      this.busy = true;
      try {
        const c = await api.post('/api/copias');
        ui().toast(c.estado === 'exitoso' ? 'Copia creada' : 'La copia falló', c.estado === 'exitoso' ? 'ok' : 'error');
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
    nuevo() { this.error = ''; this.form = { rol: 'doctor', usuario: '', correo: '', password: '', colegiatura: '', turno: 'tiempo_completo', atiende: false }; },
    editar(u) { this.error = ''; this.form = { id: u.id, usuario: u.usuario, correo: u.correo, rol: u.rol, colegiatura: u.colegiatura, turno: u.turno, atiende: u.esDoctor }; },
    get pideColegiatura() { return this.form.rol === 'doctor' || (this.form.rol === 'administrador' && this.form.atiende); },
    async guardar() {
      await run(this, async () => {
        const f = { ...this.form };
        if (!this.pideColegiatura) f.colegiatura = '';
        if (f.id) await api.put('/api/usuarios/' + f.id, f); else await api.post('/api/usuarios', f);
        ui().toast(f.id ? 'Usuario actualizado' : 'Miembro agregado'); this.form = null; await this.cargar();
      });
    },
    async resetear() {
      await run(this, async () => {
        await api.post(`/api/usuarios/${this.clave.u.id}/password`, { nueva: this.clave.nueva });
        ui().toast('Contraseña actualizada'); this.clave = null; await this.cargar();
      });
    },
    async alternar(u) {
      if (u.activo && !(await ui().confirm({ title: 'Desactivar usuario', text: `${u.usuario} ya no podrá iniciar sesión y se cerrarán sus sesiones. Podrás reactivarlo cuando quieras.`, ok: 'Desactivar', danger: true }))) return;
      try { await api.post(`/api/usuarios/${u.id}/estado`, { activo: !u.activo }); await this.cargar(); } catch (e) { ui().error(e); }
    },
    async desbloquear(u) {
      try { await api.post(`/api/usuarios/${u.id}/desbloquear`); ui().toast(`${u.usuario} desbloqueado`); await this.cargar(); } catch (e) { ui().error(e); }
    },
    async copiar() {
      try { await navigator.clipboard.writeText(app().clinica.codigo); ui().toast('Código copiado'); } catch (e) { ui().toast(app().clinica.codigo); }
    },
  }));

  /* ------------------------------ auditoría ------------------------------ */
  const ACCIONES = {
    login: 'Inicio de sesión', logout: 'Cierre de sesión', login_fallido: 'Intento fallido de acceso', usuario_bloqueado: 'Usuario bloqueado',
    usuario_desbloqueado: 'Usuario desbloqueado', registro: 'Registro de la clínica', clinica_creada: 'Clínica creada',
    password_cambiada: 'Contraseña cambiada', password_restablecida: 'Contraseña restablecida', recuperacion_solicitada: 'Recuperación solicitada',
    paciente_creado: 'Paciente registrado', paciente_editado: 'Paciente editado', paciente_baja: 'Paciente dado de baja', paciente_reactivado: 'Paciente reactivado',
    cita_creada: 'Cita agendada', cita_reprogramada: 'Cita reprogramada', cita_cancelada: 'Cita cancelada', cita_completada: 'Cita completada',
    consulta_registrada: 'Consulta registrada', consulta_editada: 'Consulta editada', receta_emitida: 'Receta emitida',
    odontograma_actualizado: 'Odontograma actualizado', historial_notas: 'Antecedentes actualizados',
    usuario_creado: 'Usuario creado', usuario_editado: 'Usuario editado', usuario_activado: 'Usuario activado', usuario_desactivado: 'Usuario desactivado',
    reporte_generado: 'Reporte generado', copia_creada: 'Copia de seguridad', copia_descargada: 'Copia descargada',
    pago_iniciado: 'Pago iniciado', pago_pagado: 'Pago aprobado', pago_fallido: 'Pago rechazado', prueba_extendida: 'Prueba extendida',
    clinica_suspendida: 'Clínica suspendida', clinica_activada: 'Clínica activada',
  };
  Alpine.data('auditoriaView', () => ({
    d: null, f: { desde: fmt.add(fmt.today(), -6), hasta: fmt.today(), usuario: '', accion: '' }, pagina: 1, cargando: false,
    etiqueta: (a) => ACCIONES[a] || a,
    async init() { await this.cargar(); },
    async cargar(p = 1) {
      this.cargando = true; this.pagina = p;
      const qs = new URLSearchParams({ ...this.f, pagina: p });
      try { this.d = await api.get('/api/auditoria?' + qs); } catch (e) { ui().error(e); }
      this.cargando = false;
    },
    detalle(x) {
      if (!x.detalle) return '';
      return Object.entries(x.detalle).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') || '—' : v}`).join(' · ');
    },
  }));

  /* ------------------------------ suscripción y pago ------------------------------ */
  Alpine.data('suscripcionView', () => ({
    d: null, busy: false,
    get sub() { return this.d.suscripcion; },
    pct(k) { const m = this.sub.plan && this.sub.plan['max_' + k]; return m ? Math.min(100, Math.round((this.d.uso[k] / m) * 100)) : 0; },
    actual(p) { return this.sub.plan && this.sub.plan.id === p.id && this.sub.estado === 'activa'; },
    async init() { try { this.d = await api.get('/api/suscripcion'); } catch (e) { ui().error(e); } },
    async pagar(p) {
      const renueva = this.actual(p);
      if (!(await ui().confirm({ title: renueva ? `Renovar ${p.nombre}` : `Cambiar a ${p.nombre}`, text: `Pagarás ${fmt.soles(p.precio)} por un mes. El plan se activa en cuanto la pasarela confirme el pago.`, ok: 'Ir a pagar' }))) return;
      this.busy = true;
      try { const r = await api.post('/api/suscripcion/pagar', { plan: p.codigo }); location.hash = r.url; } catch (e) { ui().error(e); }
      this.busy = false;
    },
  }));

  Alpine.data('pagoView', () => ({
    ref: '', c: null, error: '', busy: false, resultado: '',
    async init() {
      this.ref = Alpine.store('router').params[0] || '';
      try { this.c = await api.get('/api/pasarela/simulada/' + this.ref); } catch (e) { this.error = e.message; }
    },
    async pagar(resultado) {
      await run(this, async () => {
        const r = await api.post('/api/pasarela/simulada/' + this.ref, { resultado });
        this.resultado = r.resultado; this.c.estado = r.resultado === 'pagado' ? 'pagado' : this.c.estado;
        if (app().user) await app().refresh();
      });
    },
  }));

  /* ------------------------------ consola de plataforma ------------------------------ */
  Alpine.data('plataformaView', () => ({
    admin: null, d: null, f: { correo: '', password: '' }, editando: null, busy: false, error: '', cargado: false,
    async init() {
      try { this.admin = (await api.get('/api/plataforma/me')).admin; } catch (e) { /* ok */ }
      if (this.admin) await this.cargar();
      this.cargado = true;
    },
    async cargar() { try { this.d = await api.get('/api/plataforma/resumen'); } catch (e) { ui().error(e); } },
    async login() {
      await run(this, async () => { await api.post('/api/plataforma/login', this.f); this.admin = { correo: this.f.correo }; await this.cargar(); });
    },
    async salir() { await api.post('/api/plataforma/logout'); this.admin = null; this.d = null; },
    cuenta(e) { return this.d.clinicas.filter((c) => c.estado === e && c.activa).length; },
    async estado(c) {
      if (c.activa && !(await ui().confirm({ title: 'Suspender clínica', text: `${c.nombre} no podrá iniciar sesión hasta que la reactives.`, ok: 'Suspender', danger: true }))) return;
      try { await api.post(`/api/plataforma/clinicas/${c.id}/estado`, { activa: !c.activa }); await this.cargar(); } catch (e) { ui().error(e); }
    },
    async extender(c) {
      try { const r = await api.post(`/api/plataforma/clinicas/${c.id}/prueba`, { dias: 7 }); ui().toast(`Prueba extendida hasta ${fmt.short(r.vence)}`); await this.cargar(); } catch (e) { ui().error(e); }
    },
    editar(p) { this.error = ''; this.editando = { ...p, max_usuarios: p.max_usuarios ?? '', max_pacientes: p.max_pacientes ?? '' }; },
    async guardarPlan() {
      await run(this, async () => { await api.put(`/api/plataforma/planes/${this.editando.id}`, this.editando); this.editando = null; ui().toast('Plan actualizado'); await this.cargar(); });
    },
  }));
});
