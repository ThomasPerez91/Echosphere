/*
 * Galaxy rendering of the Echosphere mockup (js/galaxy-view.js), driven by real Knowledge only:
 * nebula and star dust as decoration, own territory glow, fog of war away from known systems,
 * known routes, glowing stars by state (no radar sweep: removed after the 09/11/2026 test).
 * Textures are built once in world coordinates, then every frame only transforms them, so pan
 * and zoom stay cheap. Nothing here has a game meaning beyond what the projection says.
 */
export type SceneSystem = { id: string; x: number; y: number; state: 'DETECTED' | 'MAPPED' | 'MONITORED'; own: boolean; capital?: boolean; name?: string };
export type SceneRoute = { a: string; b: string };
export type SceneFleet = { x: number; y: number; angle: number };
export type Scene = { systems: SceneSystem[]; routes: SceneRoute[]; fleets?: SceneFleet[]; extent?: View };
export type View = { x: number; y: number; w: number; h: number };

type RGB = [number, number, number];
const C = { own: [59, 227, 255] as RGB, ownDeep: [30, 120, 255] as RGB, gold: [255, 200, 110] as RGB, known: [150, 195, 245] as RGB,
  mapped: [255, 196, 92] as RGB, monitored: [61, 220, 151] as RGB, detected: [80, 170, 255] as RGB, arm: [165, 190, 255] as RGB,
  outer: [60, 90, 200] as RGB, core: [255, 228, 180] as RGB };
const rgba = (c: RGB, a: number) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mix = (a: RGB, b: RGB, t: number): RGB => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const clamp = (v: number, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
const smooth = (a: number, b: number, v: number) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
function hash2(x: number, y: number, s: number) {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(s + 1, 1442695041);
  h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16; return (h >>> 0) / 4294967296;
}
function vnoise(x: number, y: number, s: number) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi, s), b = hash2(xi + 1, yi, s), c = hash2(xi, yi + 1, s), d = hash2(xi + 1, yi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x: number, y: number, s = 0, o = 4) {
  let sum = 0, amp = 0.5, f = 1, n = 0;
  for (let i = 0; i < o; i++) { sum += amp * vnoise(x * f, y * f, s + i * 17); n += amp; amp *= 0.5; f *= 2.03; }
  return sum / n;
}
function mulberry(a: number) {
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const canvas = (w: number, h: number) => { const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; };
const glows = new Map<string, HTMLCanvasElement>();
function glow(c: RGB) {
  const key = c.join();
  const cached = glows.get(key); if (cached) return cached;
  const g = canvas(128, 128), x = g.getContext('2d')!, gr = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, rgba(c, 1)); gr.addColorStop(0.1, rgba(c, 0.8)); gr.addColorStop(0.3, rgba(c, 0.24)); gr.addColorStop(0.6, rgba(c, 0.06)); gr.addColorStop(1, rgba(c, 0));
  x.fillStyle = gr; x.fillRect(0, 0, 128, 128); glows.set(key, g); return g;
}

/** Typical distance between neighbouring systems (world units), the scale of glows and blobs. */
function spacing(scene: Scene) {
  const routes = scene.routes.map(r => {
    const a = scene.systems.find(s => s.id === r.a), b = scene.systems.find(s => s.id === r.b);
    return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
  }).filter(Boolean).sort((p, q) => p - q);
  if (routes.length) return routes[Math.floor(routes.length / 2)];
  const xs = scene.systems.map(s => s.x), ys = scene.systems.map(s => s.y);
  return Math.max(40, Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) / Math.max(2, Math.sqrt(scene.systems.length)));
}

export type Textures = { box: View; px: number; nebula: HTMLCanvasElement; territory: HTMLCanvasElement; fog: HTMLCanvasElement; s: number };

/** World-space textures (one pixel = `px` world units), rebuilt only when the Knowledge changes. */
export function buildTextures(scene: Scene, margin = 1.6): Textures | null {
  if (!scene.systems.length || typeof document === 'undefined') return null;
  const s = spacing(scene);
  const xs = scene.systems.map(p => p.x), ys = scene.systems.map(p => p.y);
  const box = { x: Math.min(...xs) - s * margin * 2, y: Math.min(...ys) - s * margin * 2, w: 0, h: 0 };
  box.w = Math.max(...xs) + s * margin * 2 - box.x; box.h = Math.max(...ys) + s * margin * 2 - box.y;
  if (scene.extent) { // the whole galaxy (every star visible): the backdrop covers it too
    const e = scene.extent, x2 = Math.max(box.x + box.w, e.x + e.w), y2 = Math.max(box.y + box.h, e.y + e.h);
    box.x = Math.min(box.x, e.x); box.y = Math.min(box.y, e.y); box.w = x2 - box.x; box.h = y2 - box.y;
  }
  const px = Math.max(box.w, box.h) / 900; // ~900 px on the long side
  const W = Math.ceil(box.w / px), H = Math.ceil(box.h / px);
  // Nebula: decorative noise brighter around known space.
  const k = 0.5, lw = Math.ceil(W * k), lh = Math.ceil(H * k);
  const lo = canvas(lw, lh), lx = lo.getContext('2d')!;
  const img = lx.createImageData(lw, lh), d = img.data;
  const near = (wx: number, wy: number) => {
    let best = Infinity;
    for (const p of scene.systems) { const dd = (p.x - wx) ** 2 + (p.y - wy) ** 2; if (dd < best) best = dd; }
    return Math.sqrt(best) / s;
  };
  for (let y = 0; y < lh; y++) for (let x = 0; x < lw; x++) {
    const wx = box.x + (x / k) * px, wy = box.y + (y / k) * px, u = wx / (s * 6), v = wy / (s * 6);
    const dd = Math.exp(-((near(wx, wy) / 2.4) ** 2));
    const t1 = fbm(u * 1.4 + 3, v * 1.4, 1, 4), t2 = fbm(u * 4.2, v * 4.2 + 7, 2, 3);
    let I = (dd * 0.7 + 0.12) * (0.3 + 1.6 * t1 * t2 * 1.3);
    I *= 1 - 0.55 * smooth(0.55, 0.7, fbm(u * 2.6 + 3, v * 2.6, 3, 3));
    const col = mix(C.outer, C.arm, clamp(dd * 1.1));
    let r = 3 + col[0] * I * 0.75, g = 6 + col[1] * I * 0.75, b = 16 + col[2] * I * 0.8;
    const h = smooth(0.64, 0.78, t2) * dd; r += 255 * h * 0.18; g += 70 * h * 0.18; b += 170 * h * 0.25;
    const q = (y * lw + x) * 4; d[q] = r; d[q + 1] = g; d[q + 2] = b; d[q + 3] = 255;
  }
  lx.putImageData(img, 0, 0);
  const nebula = canvas(W, H), ng = nebula.getContext('2d')!;
  ng.filter = 'blur(3px)'; ng.drawImage(lo, 0, 0, W, H); ng.filter = 'none';
  const rnd = mulberry(4242), dust = Math.round(W * H / 260);
  for (let i = 0; i < dust; i++) {
    const x = rnd() * W, y = rnd() * H, a = 0.15 + rnd() * 0.55, t = rnd();
    ng.fillStyle = t < 0.6 ? `rgba(225,235,255,${a})` : t < 0.88 ? `rgba(150,195,255,${a})` : `rgba(255,210,180,${a})`;
    ng.beginPath(); ng.arc(x, y, 0.3 + rnd() * 0.7, 0, 6.283); ng.fill();
  }
  // Territory: glow around own systems and along routes between them.
  const territory = canvas(W, H), tg = territory.getContext('2d')!;
  const own = new Set(scene.systems.filter(p => p.own).map(p => p.id));
  const at = (id: string) => scene.systems.find(p => p.id === id)!;
  const blob = (col: RGB, k2: number) => {
    tg.save(); tg.filter = `blur(${Math.max(6, (s / px) * 0.35)}px)`; tg.globalCompositeOperation = 'lighter';
    for (const p of scene.systems) {
      if (!own.has(p.id)) continue;
      const x = (p.x - box.x) / px, y = (p.y - box.y) / px, rad = (s / px) * (p.capital ? 1.05 : 0.8) * k2;
      const gr = tg.createRadialGradient(x, y, 0, x, y, rad);
      gr.addColorStop(0, rgba(col, 0.42)); gr.addColorStop(0.7, rgba(col, 0.22)); gr.addColorStop(1, rgba(col, 0));
      tg.fillStyle = gr; tg.beginPath(); tg.arc(x, y, rad, 0, 6.283); tg.fill();
    }
    tg.lineCap = 'round'; tg.strokeStyle = rgba(col, 0.22); tg.lineWidth = (s / px) * 0.9 * k2;
    for (const r of scene.routes) if (own.has(r.a) && own.has(r.b)) {
      const a = at(r.a), b = at(r.b);
      tg.beginPath(); tg.moveTo((a.x - box.x) / px, (a.y - box.y) / px); tg.lineTo((b.x - box.x) / px, (b.y - box.y) / px); tg.stroke();
    }
    tg.restore();
  };
  blob(C.ownDeep, 1); blob(C.own, 0.55);
  // Fog of war: dark away from every known system (signals included, faintly).
  const fog = canvas(W, H), fg = fog.getContext('2d')!;
  fg.fillStyle = 'rgba(3,6,14,.62)'; fg.fillRect(0, 0, W, H);
  fg.globalCompositeOperation = 'destination-out'; fg.filter = `blur(${Math.max(8, (s / px) * 0.5)}px)`;
  for (const p of scene.systems) {
    const x = (p.x - box.x) / px, y = (p.y - box.y) / px, rad = (s / px) * (p.own ? 1.9 : p.state === 'DETECTED' ? 0.9 : 1.3);
    const gr = fg.createRadialGradient(x, y, 0, x, y, rad);
    gr.addColorStop(0, 'rgba(0,0,0,1)'); gr.addColorStop(0.6, 'rgba(0,0,0,.85)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    fg.fillStyle = gr; fg.beginPath(); fg.arc(x, y, rad, 0, 6.283); fg.fill();
  }
  return { box, px, nebula, territory, fog, s };
}

export type DrawOptions = { labels: boolean; routes: boolean; selected?: string | null; drift?: boolean; stars?: boolean };

/** One frame: textures transformed to the current view, then routes, fleets and stars. */
export function drawFrame(ctx: CanvasRenderingContext2D, cw: number, ch: number, view: View, scene: Scene, tex: Textures, now: number, o: DrawOptions) {
  const t = now / 1000;
  const scale = Math.min(cw / view.w, ch / view.h);
  const ox = (cw - view.w * scale) / 2 - view.x * scale, oy = (ch - view.h * scale) / 2 - view.y * scale;
  const dx = o.drift ? Math.sin(t * 0.09) * 8 : 0, dy = o.drift ? Math.cos(t * 0.07) * 5 : 0;
  const W2S = (x: number, y: number): [number, number] => [x * scale + ox - dx, y * scale + oy - dy];
  ctx.fillStyle = '#02050d'; ctx.fillRect(0, 0, cw, ch);
  const [bx, by] = W2S(tex.box.x, tex.box.y), bw = tex.box.w * scale, bh = tex.box.h * scale;
  ctx.drawImage(tex.nebula, bx + dx * 0.6, by + dy * 0.6, bw, bh);
  ctx.globalCompositeOperation = 'screen'; ctx.globalAlpha = 0.85 + 0.15 * Math.sin(t * 0.8);
  ctx.drawImage(tex.territory, bx, by, bw, bh); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  ctx.drawImage(tex.fog, bx, by, bw, bh);
  const s = tex.s * scale, kz = clamp(s / 46, 0.7, 1.4);
  const byId = new Map(scene.systems.map(p => [p.id, p]));
  if (o.routes) {
    ctx.lineCap = 'round';
    for (const r of scene.routes) {
      const a = byId.get(r.a), b = byId.get(r.b); if (!a || !b) continue;
      const [ax, ay] = W2S(a.x, a.y), [bx2, by2] = W2S(b.x, b.y);
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx2, by2);
      if (a.own && b.own) { ctx.setLineDash([]); ctx.strokeStyle = rgba(C.own, 0.16); ctx.lineWidth = 5; ctx.stroke(); ctx.strokeStyle = rgba(C.own, 0.75); ctx.lineWidth = 1.4; ctx.stroke(); }
      else { ctx.setLineDash([4, 5]); ctx.lineDashOffset = -t * 7; ctx.strokeStyle = rgba(C.known, a.state !== 'DETECTED' && b.state !== 'DETECTED' ? 0.5 : 0.28); ctx.lineWidth = 1; ctx.stroke(); }
    }
    ctx.setLineDash([]); ctx.lineDashOffset = 0;
  }
  for (const f of scene.fleets ?? []) {
    const [fx, fy] = W2S(f.x, f.y);
    ctx.globalCompositeOperation = 'lighter'; ctx.drawImage(glow([120, 255, 190]), fx - 14, fy - 14, 28, 28); ctx.globalCompositeOperation = 'source-over';
    ctx.save(); ctx.translate(fx, fy); ctx.rotate(f.angle); ctx.fillStyle = '#d8fff0';
    ctx.beginPath(); ctx.moveTo(6, 0); ctx.lineTo(-4, 3.5); ctx.lineTo(-2, 0); ctx.lineTo(-4, -3.5); ctx.closePath(); ctx.fill(); ctx.restore();
  }
  if (o.stars !== false) for (const p of scene.systems) {
    const [x, y] = W2S(p.x, p.y); if (x < -30 || y < -30 || x > cw + 30 || y > ch + 30) continue;
    const col: RGB = p.capital ? [255, 214, 130] : p.own ? [170, 240, 255] : p.state === 'MONITORED' ? C.monitored : p.state === 'MAPPED' ? C.mapped : C.detected;
    const tw = 1 + 0.14 * Math.sin(t * 1.7 + x * 0.01) + 0.08 * Math.sin(t * 3.3 + y * 0.01);
    const r = (p.capital ? 4.6 : p.own ? 2.9 : p.state === 'DETECTED' ? 2 : 2.4) * kz;
    ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = p.state === 'DETECTED' ? 0.6 : 0.9;
    const gr = r * (p.capital ? 9 : 5.5) * tw; ctx.drawImage(glow(col), x - gr, y - gr, gr * 2, gr * 2);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    ctx.fillStyle = rgba(mix(col, [255, 255, 255], 0.45), 1); ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
    ctx.fillStyle = rgba(mix(col, [255, 255, 255], 0.88), 1); ctx.beginPath(); ctx.arc(x, y, r * 0.5, 0, 6.283); ctx.fill();
    if (p.capital) {
      ctx.strokeStyle = rgba(C.gold, 0.95); ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(x, y, r + 6, 0, 6.283); ctx.stroke();
      ctx.save(); ctx.translate(x, y); ctx.rotate(t * 0.35); ctx.setLineDash([3, 5]); ctx.strokeStyle = rgba(C.gold, 0.5); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(0, 0, r + 13, 0, 6.283); ctx.stroke(); ctx.restore(); ctx.setLineDash([]);
    } else if (p.own) { ctx.strokeStyle = rgba(C.own, 0.9); ctx.lineWidth = 1.3; ctx.beginPath(); ctx.arc(x, y, r + 4, 0, 6.283); ctx.stroke(); }
    else if (p.state !== 'DETECTED') { ctx.strokeStyle = rgba(col, 0.55); ctx.lineWidth = 0.9; ctx.beginPath(); ctx.arc(x, y, r + 3.5, 0, 6.283); ctx.stroke(); }
    if (o.selected === p.id) { ctx.strokeStyle = rgba(C.own, 0.9); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, r + 10, 0, 6.283); ctx.stroke(); }
  }
  if (o.labels) {
    ctx.textBaseline = 'middle';
    for (const p of scene.systems) {
      if (!p.name) continue;
      const [x, y] = W2S(p.x, p.y); if (x < -60 || y < -30 || x > cw + 60 || y > ch + 30) continue;
      const fs = Math.round(clamp(12 * kz, 11, 15) * (p.capital ? 1.1 : 1));
      ctx.font = `${p.capital ? 700 : 600} ${fs}px Inter, system-ui, sans-serif`;
      const w = ctx.measureText(p.name).width, off = (p.capital ? 30 : 12) * Math.min(kz, 1.1);
      let lx = x + off; ctx.textAlign = 'left';
      if (lx + w > cw - 6) { lx = x - off; ctx.textAlign = 'right'; }
      ctx.shadowColor = 'rgba(0,0,0,.95)'; ctx.shadowBlur = 6;
      ctx.fillStyle = p.capital ? '#ffe7b8' : '#eef4ff'; ctx.fillText(p.name, lx, y); ctx.shadowBlur = 0;
    }
  }
}

/** View that frames the given systems with a margin (in world units). */
export function frame(systems: { x: number; y: number }[], margin: number): View {
  const xs = systems.map(p => p.x), ys = systems.map(p => p.y);
  const x0 = Math.min(...xs) - margin, y0 = Math.min(...ys) - margin;
  return { x: x0, y: y0, w: Math.max(...xs) + margin - x0, h: Math.max(...ys) + margin - y0 };
}
