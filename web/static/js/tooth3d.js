/* Diente 3D del landing (three.js). Malla procedural, sin assets externos.
   - Reacciona al puntero (parallax suave) y a la gestualidad de arrastrar
   - Click = "boing" elástico + destello
   - Se pausa fuera de pantalla / pestaña oculta; respeta prefers-reduced-motion */
import * as THREE from '/static/vendor/three/three.module.js';
import { RoomEnvironment } from '/static/vendor/three/RoomEnvironment.js';

function toothShape() {
  const s = new THREE.Shape();
  s.moveTo(0, 0.78);
  s.bezierCurveTo(0.25, 1.05, 0.7, 1.28, 1.0, 1.12);
  s.bezierCurveTo(1.38, 0.92, 1.48, 0.42, 1.32, -0.02);
  s.bezierCurveTo(1.2, -0.4, 1.14, -0.85, 1.02, -1.3);
  s.bezierCurveTo(0.92, -1.78, 0.56, -1.82, 0.5, -1.36);
  s.bezierCurveTo(0.44, -0.95, 0.32, -0.62, 0, -0.62);
  s.bezierCurveTo(-0.32, -0.62, -0.44, -0.95, -0.5, -1.36);
  s.bezierCurveTo(-0.56, -1.82, -0.92, -1.78, -1.02, -1.3);
  s.bezierCurveTo(-1.14, -0.85, -1.2, -0.4, -1.32, -0.02);
  s.bezierCurveTo(-1.48, 0.42, -1.38, 0.92, -1.0, 1.12);
  s.bezierCurveTo(-0.7, 1.28, -0.25, 1.05, 0, 0.78);
  return s;
}

function glow() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const g = c.getContext('2d'), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(0.25, 'rgba(255,255,255,.8)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export function mountTooth(host) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
  camera.position.set(0, 0.1, 10.6);

  const geo = new THREE.ExtrudeGeometry(toothShape(), {
    depth: 0.55, steps: 1, curveSegments: 56,
    bevelEnabled: true, bevelThickness: 0.5, bevelSize: 0.34, bevelSegments: 14,
  });
  geo.center();
  const mat = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, roughness: 0.16, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.08,
    sheen: 0.6, sheenColor: new THREE.Color(0xbff3ec), sheenRoughness: 0.5, envMapIntensity: 1.1,
  });
  const tooth = new THREE.Mesh(geo, mat);
  const rig = new THREE.Group();
  rig.add(tooth);
  scene.add(rig);

  // Luces: relleno suave + contraluz de marca
  scene.add(new THREE.HemisphereLight(0xffffff, 0xaee8e2, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(3, 4, 5); scene.add(key);
  const rim = new THREE.PointLight(0x2fd6c4, 28, 16); rim.position.set(-4, 1, -2); scene.add(rim);
  const rim2 = new THREE.PointLight(0x4cb4f7, 22, 16); rim2.position.set(4, -2, -2); scene.add(rim2);

  // Destellos flotantes
  const N = 46, pos = new Float32Array(N * 3), seed = [];
  for (let i = 0; i < N; i++) {
    const a = Math.random() * Math.PI * 2, r = 2.2 + Math.random() * 1.8;
    pos.set([Math.cos(a) * r, (Math.random() - 0.5) * 5, Math.sin(a) * r * 0.5 - 0.5], i * 3);
    seed.push({ s: 0.3 + Math.random() * 0.7, p: Math.random() * 6.28 });
  }
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const pts = new THREE.Points(pg, new THREE.PointsMaterial({
    map: glow(), size: 0.22, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, color: 0x7ff0e2, opacity: 0.85,
  }));
  scene.add(pts);

  // Destello de esmalte (estrella) sobre el diente
  const star = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow(), color: 0xffffff, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0 }));
  star.position.set(0.85, 1.25, 1.2); star.scale.setScalar(0.1);
  rig.add(star);

  function resize() {
    const w = host.clientWidth || 1, h = host.clientHeight || 1;
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host); resize();

  // Interacción
  const target = { x: 0, y: 0 }, cur = { x: 0, y: 0 };
  let spin = 0, spinV = 0, dragging = false, lastX = 0, boing = -10, glint = 0;
  const onMove = (e) => {
    const r = host.getBoundingClientRect();
    target.x = ((e.clientX - r.left) / r.width - 0.5) * 2;
    target.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
    if (dragging) { spinV = (e.clientX - lastX) * 0.012; lastX = e.clientX; }
  };
  host.addEventListener('pointermove', onMove);
  host.addEventListener('pointerdown', (e) => { dragging = true; lastX = e.clientX; host.setPointerCapture(e.pointerId); });
  host.addEventListener('pointerup', () => { dragging = false; });
  host.addEventListener('click', () => { boing = now(); glint = boing; });
  host.addEventListener('pointerleave', () => { target.x = target.y = 0; });

  const t0 = performance.now(), now = () => (performance.now() - t0) / 1000;
  let visible = true, running = false;
  new IntersectionObserver((es) => { visible = es[0].isIntersecting; kick(); }).observe(host);
  document.addEventListener('visibilitychange', kick);
  const themeSync = () => { renderer.toneMappingExposure = document.documentElement.dataset.theme === 'dark' ? 0.9 : 1.05; };
  window.addEventListener('themechange', themeSync); themeSync();

  function frame() {
    if (!visible || document.hidden) { running = false; return; }
    const t = now();
    cur.x += (target.x - cur.x) * 0.06; cur.y += (target.y - cur.y) * 0.06;
    spin += spinV; spinV *= 0.94;
    const idle = reduce ? 0 : Math.sin(t * 0.6) * 0.35;
    rig.rotation.y = idle + cur.x * 0.55 + spin;
    rig.rotation.x = cur.y * 0.28 + (reduce ? 0 : Math.sin(t * 0.8) * 0.04);
    rig.rotation.z = reduce ? 0 : Math.sin(t * 0.5) * 0.04;
    rig.position.y = reduce ? 0 : Math.sin(t * 1.1) * 0.1;
    // boing elástico (oscilación amortiguada de escala)
    const dt = t - boing, e = dt < 2 ? Math.exp(-dt * 3.2) * Math.sin(dt * 14) : 0;
    rig.scale.set(1 - e * 0.12, 1 + e * 0.16, 1 - e * 0.12);
    // destello: automático cada ~5s y al hacer click
    const gp = ((t + 1.5) % 5.5) / 5.5, gl = Math.max(0, 1 - Math.abs(gp * 2 - 0.12) * 5.5);
    const gc = Math.max(0, 1 - (t - glint) * 1.6);
    const gi = Math.max(gl, gc);
    star.material.opacity = gi; star.scale.setScalar(0.1 + gi * 1.1); star.material.rotation = t * 1.5;
    // partículas
    const a = pg.attributes.position;
    for (let i = 0; i < N; i++) {
      a.array[i * 3 + 1] += 0.004 * seed[i].s;
      if (a.array[i * 3 + 1] > 2.8) a.array[i * 3 + 1] = -2.8;
      a.array[i * 3] += Math.sin(t * seed[i].s + seed[i].p) * 0.0016;
    }
    a.needsUpdate = true;
    pts.rotation.y = t * 0.05;
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  function kick() { if (!running && visible && !document.hidden) { running = true; requestAnimationFrame(frame); } }
  kick();

  return () => {
    visible = false;
    renderer.dispose(); geo.dispose(); mat.dispose(); pmrem.dispose();
    window.removeEventListener('themechange', themeSync);
    host.replaceChildren();
  };
}
