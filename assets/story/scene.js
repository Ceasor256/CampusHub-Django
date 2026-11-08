/**
 * CampusHub scroll story: a WebGL scene driven by scroll position.
 *
 * Source file. It is bundled (with only the parts of Three.js it uses) into
 * static/js/story-scene.js by `npm run story`. Loaded on demand by
 * static/js/story.js, never on pages without a story section.
 *
 * Chapters (one per screen of scrolling):
 *   0 The hub    – the CampusHub logo, in 3D, assembles and slowly turns
 *   1 Buy & sell – a phone, laptop and textbook orbit the hub
 *   2 Gigs       – task cards fan out in front of the hub
 *   3 Deals      – golden discount tickets fall and spin
 *   4 Join       – the hub faces you and pulses outward
 *
 * The hub turns half a turn per chapter as you scroll (the logo is on both
 * faces), so it is face-on at every chapter.
 */
import {
  ACESFilmicToneMapping,
  AmbientLight,
  BoxGeometry,
  BufferGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  ExtrudeGeometry,
  Float32BufferAttribute,
  FogExp2,
  Group,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  PointLight,
  Points,
  PointsMaterial,
  Scene,
  Shape,
  SphereGeometry,
  SRGBColorSpace,
  TorusGeometry,
  Vector3,
  WebGLRenderer,
} from "three";

// Brand palette (matches assets/app.css).
const COLOR = {
  brand: 0x6633d1,
  brandLight: 0xb9a0f6,
  night: 0x22104a,
  accent: 0xfbbd2e,
  white: 0xffffff,
  ink: 0x17131f,
  paper: 0xf5f1fe,
};

const CHAPTERS = 5;
const TAU = Math.PI * 2;
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const smooth = (v) => {
  const x = clamp01(v);
  return x * x * (3 - 2 * x);
};

// ------------------------------------------------------------------ geometry helpers
function roundedRect(w, h, r) {
  const s = new Shape();
  const x = -w / 2;
  const y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y);
  s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r);
  s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h);
  s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r);
  s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

function slab(w, h, depth, radius, material) {
  const geo = new ExtrudeGeometry(roundedRect(w, h, radius), {
    depth,
    bevelEnabled: true,
    bevelThickness: Math.min(0.04, depth / 3),
    bevelSize: Math.min(0.04, radius / 2),
    bevelSegments: 3,
    curveSegments: 10,
  });
  geo.center();
  return new Mesh(geo, material);
}

function fadeable(params) {
  return new MeshStandardMaterial({ transparent: true, ...params });
}

// ------------------------------------------------------------------ objects
function buildHub() {
  const hub = new Group();
  const plate = slab(2.6, 2.6, 0.35, 0.7, new MeshStandardMaterial({ color: COLOR.brand, metalness: 0.35, roughness: 0.32 }));
  hub.add(plate);

  // The logo is on both faces, so the hub always shows it while it turns.
  const barMat = new MeshStandardMaterial({ color: COLOR.brandLight, metalness: 0.2, roughness: 0.4 });
  const coreMat = new MeshStandardMaterial({ color: COLOR.accent, emissive: COLOR.accent, emissiveIntensity: 0.55, metalness: 0.1, roughness: 0.3 });
  const nodeMat = new MeshStandardMaterial({ color: COLOR.white, metalness: 0.05, roughness: 0.25 });
  const nodes = [];
  for (const side of [1, -1]) {
    for (const angle of [Math.PI / 4, -Math.PI / 4]) {
      const bar = new Mesh(new CylinderGeometry(0.06, 0.06, 2.1, 16), barMat);
      bar.rotation.z = angle;
      bar.position.z = 0.24 * side;
      hub.add(bar);
    }
    const core = new Mesh(new SphereGeometry(0.42, 40, 40), coreMat);
    core.position.z = 0.32 * side;
    hub.add(core);
    for (const [x, y] of [[-0.75, 0.75], [0.75, 0.75], [-0.75, -0.75], [0.75, -0.75]]) {
      const node = new Mesh(new SphereGeometry(0.26, 32, 32), nodeMat);
      node.userData.home = new Vector3(x, y, 0.3 * side);
      node.userData.start = new Vector3(x * 6, y * 6, 3 * side);
      node.position.copy(node.userData.start);
      hub.add(node);
      nodes.push(node);
    }
  }
  const core = { material: coreMat };
  return { hub, core, nodes };
}

function buildMarketItems() {
  const items = [];

  // Phone
  const phoneMat = fadeable({ color: COLOR.ink, metalness: 0.6, roughness: 0.3 });
  const screenMat = new MeshBasicMaterial({ color: COLOR.brandLight, transparent: true });
  const phone = new Group();
  phone.add(slab(0.56, 1.12, 0.08, 0.1, phoneMat));
  const screen = new Mesh(new PlaneGeometry(0.46, 0.96), screenMat);
  screen.position.z = 0.07;
  phone.add(screen);
  items.push({ obj: phone, mats: [phoneMat, screenMat] });

  // Laptop
  const bodyMat = fadeable({ color: 0xc9c3d6, metalness: 0.7, roughness: 0.35 });
  const lapScreenMat = new MeshBasicMaterial({ color: COLOR.brand, transparent: true });
  const laptop = new Group();
  const base = new Mesh(new BoxGeometry(1.3, 0.06, 0.9), bodyMat);
  laptop.add(base);
  const lid = new Group();
  lid.position.set(0, 0.03, -0.45);
  const lidShell = new Mesh(new BoxGeometry(1.3, 0.85, 0.05), bodyMat);
  lidShell.position.y = 0.425;
  const lidScreen = new Mesh(new PlaneGeometry(1.16, 0.72), lapScreenMat);
  lidScreen.position.set(0, 0.425, 0.03);
  lid.add(lidShell, lidScreen);
  lid.rotation.x = -0.25;
  laptop.add(lid);
  items.push({ obj: laptop, mats: [bodyMat, lapScreenMat] });

  // Textbook
  const coverMat = fadeable({ color: COLOR.accent, roughness: 0.6 });
  const pageMat = fadeable({ color: COLOR.paper, roughness: 0.9 });
  const book = new Group();
  book.add(new Mesh(new BoxGeometry(0.82, 1.08, 0.2), coverMat));
  const pages = new Mesh(new BoxGeometry(0.76, 1.02, 0.21), pageMat);
  pages.position.x = 0.04;
  book.add(pages);
  items.push({ obj: book, mats: [coverMat, pageMat] });

  return items;
}

function buildGigCards() {
  const cards = [];
  for (let i = 0; i < 5; i++) {
    const cardMat = fadeable({ color: COLOR.white, roughness: 0.5 });
    const stripeMat = new MeshBasicMaterial({ color: i % 2 ? COLOR.accent : COLOR.brand, transparent: true });
    const lineMat = new MeshBasicMaterial({ color: 0xd7c8fb, transparent: true });
    const card = new Group();
    card.add(slab(1.15, 0.72, 0.04, 0.08, cardMat));
    const stripe = new Mesh(new PlaneGeometry(1.0, 0.12), stripeMat);
    stripe.position.set(0, 0.22, 0.03);
    const line1 = new Mesh(new PlaneGeometry(0.8, 0.06), lineMat);
    line1.position.set(-0.1, 0.0, 0.03);
    const line2 = new Mesh(new PlaneGeometry(0.55, 0.06), lineMat);
    line2.position.set(-0.22, -0.14, 0.03);
    card.add(stripe, line1, line2);
    cards.push({ obj: card, mats: [cardMat, stripeMat, lineMat] });
  }
  return cards;
}

function buildTickets() {
  const tickets = [];
  for (let i = 0; i < 8; i++) {
    const mat = fadeable({ color: COLOR.accent, metalness: 0.45, roughness: 0.3, emissive: 0x6b3d0a, emissiveIntensity: 0.4 });
    const perfMat = new MeshBasicMaterial({ color: COLOR.white, transparent: true });
    const ticket = new Group();
    ticket.add(slab(0.92, 0.46, 0.05, 0.08, mat));
    const perf = new Mesh(new PlaneGeometry(0.03, 0.36), perfMat);
    perf.position.set(0.22, 0, 0.04);
    ticket.add(perf);
    ticket.userData.seed = i;
    tickets.push({ obj: ticket, mats: [mat, perfMat] });
  }
  return tickets;
}

function buildParticles(count) {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const r = 6 + Math.random() * 18;
    const theta = Math.random() * TAU;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi) - 6;
  }
  const geo = new BufferGeometry();
  geo.setAttribute("position", new Float32BufferAttribute(positions, 3));
  return new Points(geo, new PointsMaterial({ color: COLOR.brandLight, size: 0.06, transparent: true, opacity: 0.7, depthWrite: false }));
}

function setOpacity(entry, value) {
  entry.obj.visible = value > 0.01;
  for (const m of entry.mats) m.opacity = value;
}

// ------------------------------------------------------------------ camera path
// One key per chapter: [camera position, look-at target].
const CAMERA_KEYS = [
  [new Vector3(0, 0.2, 8.6), new Vector3(0, 0, 0)],
  [new Vector3(1.6, 1.6, 7.4), new Vector3(0, 0.1, 0)],
  [new Vector3(-1.3, -0.9, 7.6), new Vector3(0, 0.3, 0)],
  [new Vector3(0.6, 2.6, 8.4), new Vector3(0, 0, 0)],
  [new Vector3(0, 0, 6.9), new Vector3(0, 0, 0)],
];

function cameraAt(t, outPos, outTarget) {
  const i = Math.min(CHAPTERS - 2, Math.floor(t));
  const f = smooth(t - i);
  outPos.lerpVectors(CAMERA_KEYS[i][0], CAMERA_KEYS[i + 1][0], f);
  outTarget.lerpVectors(CAMERA_KEYS[i][1], CAMERA_KEYS[i + 1][1], f);
}

// ------------------------------------------------------------------ main
export function start(root, host) {
  const chapters = Array.from(root.querySelectorAll("[data-chapter]"));
  const lowPower = (navigator.hardwareConcurrency || 4) <= 4 || (navigator.deviceMemory || 4) <= 2;

  const renderer = new WebGLRenderer({ antialias: !lowPower, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, lowPower ? 1 : 1.75));
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  host.appendChild(renderer.domElement);
  renderer.domElement.setAttribute("aria-hidden", "true");

  const scene = new Scene();
  scene.background = new Color(COLOR.night);
  scene.fog = new FogExp2(COLOR.night, 0.045);
  const camera = new PerspectiveCamera(40, 1, 0.1, 100);

  // Lighting: soft fill, white key, purple rim, warm core glow.
  scene.add(new AmbientLight(0xffffff, 0.35));
  const key = new DirectionalLight(0xffffff, 2.2);
  key.position.set(5, 6, 8);
  const rim = new DirectionalLight(COLOR.brandLight, 2.6);
  rim.position.set(-6, 2, -4);
  const glow = new PointLight(COLOR.accent, 1.5, 12, 2);
  glow.position.set(0, 0, 1.4);
  scene.add(key, rim, glow);

  const world = new Group(); // shifted to make room for the text column
  scene.add(world);

  const { hub, core, nodes } = buildHub();
  world.add(hub);
  const market = buildMarketItems();
  const cards = buildGigCards();
  const tickets = buildTickets();
  for (const e of [...market, ...cards, ...tickets]) world.add(e.obj);

  const ringMat = new MeshBasicMaterial({ color: COLOR.accent, transparent: true, opacity: 0 });
  const ring = new Mesh(new TorusGeometry(1.9, 0.025, 12, 96), ringMat);
  ring.position.z = 0.1;
  world.add(ring);

  const particles = buildParticles(lowPower ? 350 : 900);
  scene.add(particles);

  // ---------------------------------------------------------------- state
  const camPos = new Vector3();
  const camTarget = new Vector3();
  const lookAt = new Vector3();
  const pointer = { x: 0, y: 0, sx: 0, sy: 0 };
  let progress = 0;
  let running = false;
  let lastTime = performance.now();
  const startTime = lastTime;
  let layout = { x: 0, y: 0, scale: 1 };

  function measure() {
    const w = host.clientWidth || window.innerWidth;
    const h = host.clientHeight || window.innerHeight;
    renderer.setSize(w, h, true);
    camera.aspect = w / h;
    camera.fov = w < 640 ? 52 : 40;
    camera.updateProjectionMatrix();
    // Desktop: text on the left, so move the scene right. Phones: text at the bottom, so lift the scene.
    layout = w >= 1024 ? { x: 2.1, y: 0, scale: 1 } : { x: 0, y: 1.2, scale: w < 640 ? 0.7 : 0.8 };
  }

  function readScroll() {
    const rect = root.getBoundingClientRect();
    const total = rect.height - window.innerHeight;
    progress = total > 0 ? clamp01(-rect.top / total) : 0;
  }

  function frame(now) {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastTime) / 1000);
    lastTime = now;
    const time = (now - startTime) / 1000;
    const t = progress * (CHAPTERS - 1);
    const w = (i) => smooth(1 - Math.min(1, Math.abs(t - i)));
    const [wHub, wMarket, wGigs, wDeals, wJoin] = [0, 1, 2, 3, 4].map(w);

    // Highlight the chapter text in view.
    const active = Math.round(t);
    chapters.forEach((el, i) => el.classList.toggle("is-active", i === active));

    // World offset for the text column.
    world.position.set(layout.x, layout.y, 0);
    particles.position.set(layout.x * 0.5, layout.y * 0.5, 0);
    particles.rotation.y = time * 0.02 + progress * 1.2;

    // Hub: the four nodes fly in on load; scrolling turns the hub (see above).
    const assemble = smooth((time - 0.2) / 1.6);
    nodes.forEach((n) => n.position.lerpVectors(n.userData.start, n.userData.home, assemble));
    // Scroll turns the hub half a turn per chapter, so it faces you at each chapter.
    hub.rotation.y = progress * (CHAPTERS - 1) * Math.PI + Math.sin(time * 0.5) * 0.3 * (1 - wJoin);
    hub.rotation.x = 0.22 * (1 - wJoin) + Math.sin(time * 0.6) * 0.04;
    hub.scale.setScalar(layout.scale * (1 + 0.15 * wJoin + 0.08 * wHub));
    core.material.emissiveIntensity = 0.5 + 0.6 * wDeals + 0.4 * wJoin + Math.sin(time * 2.4) * 0.1;
    glow.intensity = 1.5 + 6 * wDeals + 2 * wJoin;

    // Buy & sell: items orbit in from far away.
    market.forEach((e, k) => {
      const a = time * 0.35 + (k * TAU) / 3;
      const r = MathUtils.lerp(9, 3.3, wMarket);
      e.obj.position.set(Math.cos(a) * r, Math.sin(a * 1.3 + k) * 0.35 + (k - 1) * 0.25, Math.sin(a) * r * 0.55);
      e.obj.rotation.set(0.35, time * 0.6 + k, Math.sin(time + k) * 0.1);
      e.obj.scale.setScalar(0.4 + 0.8 * wMarket);
      setOpacity(e, wMarket);
    });

    // Gigs: cards rise into a fan in front of the hub.
    cards.forEach((e, j) => {
      const a = (j - 2) * 0.42;
      const tx = Math.sin(a) * 3.1;
      const ty = Math.cos(a) * 1.15 - 0.35 + Math.sin(time * 1.4 + j) * 0.07;
      const tz = 1.2 + j * 0.06;
      e.obj.position.set(MathUtils.lerp(0, tx, wGigs), MathUtils.lerp(-6, ty, wGigs), tz);
      e.obj.rotation.set(-0.15, a * -0.35, -a * 0.6);
      e.obj.scale.setScalar(Math.max(0.01, wGigs));
      setOpacity(e, wGigs);
    });

    // Deals: tickets fall and spin, lit by the warm glow.
    tickets.forEach((e) => {
      const s = e.obj.userData.seed;
      const fall = (time * 0.7 + s * 0.95) % 8;
      e.obj.position.set((s / 7 - 0.5) * 7.5 + Math.sin(time * 0.5 + s) * 0.3, 4 - fall, Math.cos(s * 1.7) * 1.4 + 0.6);
      e.obj.rotation.set(time * (0.6 + s * 0.07), time * (0.9 + s * 0.05), s);
      setOpacity(e, wDeals);
    });

    // Join: a ring pulses outward from the hub.
    const pulse = (time * 0.55) % 1;
    ring.scale.setScalar(1 + pulse * 2.2);
    ringMat.opacity = (1 - pulse) * 0.8 * wJoin;
    ring.visible = wJoin > 0.01;

    // Camera follows the chapter path, with a little pointer parallax.
    pointer.sx += (pointer.x - pointer.sx) * Math.min(1, dt * 3);
    pointer.sy += (pointer.y - pointer.sy) * Math.min(1, dt * 3);
    cameraAt(t, camPos, camTarget);
    // (The camera stays on its path; only the world is offset, so the hub sits beside the text.)
    camera.position.set(camPos.x + pointer.sx * 0.45, camPos.y + pointer.sy * 0.3, camPos.z);
    lookAt.copy(camTarget);
    camera.lookAt(lookAt);

    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }

  function setRunning(on) {
    if (on === running) return;
    running = on;
    if (on) {
      lastTime = performance.now();
      requestAnimationFrame(frame);
    }
  }

  // Only animate while the story is on screen (saves battery and data).
  new IntersectionObserver((entries) => setRunning(entries.some((e) => e.isIntersecting))).observe(root);
  window.addEventListener("scroll", readScroll, { passive: true });
  window.addEventListener("resize", () => { measure(); readScroll(); }, { passive: true });
  window.addEventListener("pointermove", (e) => {
    pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
    pointer.y = -((e.clientY / window.innerHeight) * 2 - 1);
  }, { passive: true });
  document.addEventListener("visibilitychange", () => setRunning(!document.hidden && root.getBoundingClientRect().bottom > 0));

  measure();
  readScroll();
  root.classList.add("story-live");
  measure(); // the stage only has its full size once live
  setRunning(true);
}
