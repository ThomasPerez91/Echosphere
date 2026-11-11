/*
 * Galaxy shapes (v0.12, recette 11/11/2026): the density the server drew a shaped galaxy from
 * (`layout` of the galaxy projection, app/galaxy/shapes.py), painted as the map backdrop like the
 * reference carte-galaxie.html (buildBackground): arms, core, dust lanes, HII regions, clusters.
 * Decorative only: every star is already visible as a point, the layout says nothing more.
 */
import { clamp, fbm, mix, mulberry, smooth } from './noise';
import type { RGB } from './noise';

export type Shape = 'elliptical' | 'spiral2' | 'spiral4' | 'irregular' | 'clusters';
export const SHAPES: Shape[] = ['elliptical', 'spiral2', 'spiral4', 'irregular', 'clusters'];
export type Layout = {
  shape: Shape; cx: number; cy: number; radius: number; squash: number;
  params: { ns: number; e?: number; rot?: number; ox?: number; oy?: number; sx?: number; clusters?: [number, number, number][] };
};

export const SHAPE_NAMES: Record<Shape | 'random', string> = {
  random: 'Au hasard', elliptical: 'Elliptique', spiral2: 'Spirale à 2 bras', spiral4: 'Spirale à 4 bras',
  irregular: 'Irrégulière', clusters: 'Amas d’étoiles',
};

const integer = (v: unknown) => typeof v === 'number' && Number.isInteger(v);
export function validLayout(v: unknown): v is Layout {
  if (typeof v !== 'object' || v === null) return false;
  const l = v as Record<string, unknown>, p = l.params as Record<string, unknown> | undefined;
  return SHAPES.includes(l.shape as Shape) && [l.cx, l.cy, l.radius, l.squash].every(integer) && (l.radius as number) > 0
    && typeof p === 'object' && p !== null && integer(p.ns)
    && (p.clusters === undefined || (Array.isArray(p.clusters) && p.clusters.every(c => Array.isArray(c) && c.length === 3 && c.every(integer))));
}

/** Same formulas as the server (and the reference makeShape), parameters in thousandths. */
export function density(layout: Layout): (u: number, v: number) => number {
  const p = layout.params, ns = p.ns;
  if (layout.shape === 'elliptical') {
    const e = (p.e ?? 850) / 1000, rot = (p.rot ?? 0) / 1000, c = Math.cos(rot), s = Math.sin(rot);
    return (u, v) => { const a = u * c + v * s, b = (-u * s + v * c) / e; return Math.min(1, Math.exp(-(a * a + b * b) / 0.32) * 1.25 * (0.8 + 0.4 * fbm(u * 2.4 + ns, v * 2.4, ns, 3))); };
  }
  if (layout.shape === 'spiral2' || layout.shape === 'spiral4') {
    const N = layout.shape === 'spiral2' ? 2 : 4, twist = N === 2 ? 5.4 : 4.2, w0 = N === 2 ? 0.075 : 0.058, rot = (p.rot ?? 0) / 1000;
    return (u, v) => {
      const r = Math.hypot(u, v); if (r > 1.3) return 0;
      const th = Math.atan2(v, u) + 0.45 * (fbm(u * 2.3 + ns, v * 2.3, ns, 3) - 0.5);
      let best = 9;
      for (let k = 0; k < N; k++) { let d = th - (r * twist + rot + k * 2 * Math.PI / N); d = ((d + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI; best = Math.min(best, Math.abs(d)); }
      const lin = best * Math.max(r, 0.1), w = w0 + 0.055 * r;
      const arm = Math.exp(-lin * lin / (2 * w * w)) * smooth(1.12, 0.68, r);
      return Math.min(1, Math.max(Math.exp(-((r / 0.15) ** 2)), arm * 0.95) + 0.07 * Math.exp(-((r / 0.75) ** 2)));
    };
  }
  if (layout.shape === 'irregular') {
    const ox = (p.ox ?? 0) / 1000, oy = (p.oy ?? 0) / 1000, sx = (p.sx ?? 1000) / 1000;
    return (u, v) => { const r = Math.hypot(u * sx, v), n = fbm(u * 1.3 + ox, v * 1.3 + oy, ns, 4); return smooth(0.46, 0.64, n + 0.32 * (0.68 - r)) * smooth(1.25, 0.82, r); };
  }
  const centres = (p.clusters ?? []).map(([x, y, sg]) => [x / 1000, y / 1000, sg / 1000]);
  return (u, v) => {
    let m = 0;
    for (const [x, y, sg] of centres) { const dx = u - x, dy = v - y; m = Math.max(m, Math.exp(-(dx * dx + dy * dy) / (2 * sg * sg))); }
    return Math.min(1, m * 1.15) + 0.012 * smooth(1.1, 0.4, Math.hypot(u, v));
  };
}

type Palette = { arm: RGB; outer: RGB; core: RGB; coreR: number; lanes: boolean; hii: boolean; amb: RGB };
const PALETTE: Record<Shape, Palette> = {
  elliptical: { arm: [255, 206, 160], outer: [150, 105, 90], core: [255, 236, 205], coreR: 0.24, lanes: false, hii: false, amb: [40, 30, 50] },
  spiral2: { arm: [165, 190, 255], outer: [60, 90, 200], core: [255, 228, 180], coreR: 0.13, lanes: true, hii: true, amb: [18, 38, 90] },
  spiral4: { arm: [165, 190, 255], outer: [60, 90, 200], core: [255, 228, 180], coreR: 0.12, lanes: true, hii: true, amb: [18, 38, 90] },
  irregular: { arm: [150, 180, 255], outer: [85, 80, 200], core: [230, 220, 255], coreR: 0.07, lanes: false, hii: true, amb: [30, 30, 90] },
  clusters: { arm: [180, 205, 255], outer: [70, 110, 220], core: [0, 0, 0], coreR: 0, lanes: false, hii: false, amb: [18, 34, 80] },
};

/** World extent of the drawn disc (with the halo), for the backdrop box. */
export function layoutExtent(l: Layout) {
  const rx = l.radius * 1.45, ry = rx * l.squash / 1000;
  return { x: l.cx - rx, y: l.cy - ry, w: 2 * rx, h: 2 * ry };
}

/**
 * Backdrop canvas of `W`×`H` pixels covering `box` (one pixel = `px` world units): the galaxy
 * nebula of the reference, then star dust concentrated where the galaxy is dense.
 */
export function shapeBackdrop(layout: Layout, box: { x: number; y: number }, px: number, W: number, H: number, make: (w: number, h: number) => HTMLCanvasElement) {
  const pal = PALETTE[layout.shape], dens = density(layout), R = layout.radius, Ry = R * layout.squash / 1000, ns = layout.params.ns % 911;
  const k = 0.5, lw = Math.ceil(W * k), lh = Math.ceil(H * k);
  const lo = make(lw, lh), lx = lo.getContext('2d')!, img = lx.createImageData(lw, lh), d = img.data;
  const base: RGB = [3, 6, 16];
  for (let y = 0; y < lh; y++) for (let x = 0; x < lw; x++) {
    const wx = box.x + (x / k) * px, wy = box.y + (y / k) * px, u = (wx - layout.cx) / R, v = (wy - layout.cy) / Ry, r = Math.hypot(u, v);
    const dd = Math.min(1, dens(u, v));
    const t1 = fbm(u * 5 + ns, v * 5, 1, 4), t2 = fbm(u * 15, v * 15 + ns, 2, 3);
    let I = (dd * 0.9 + 0.12 * Math.exp(-((r / 0.85) ** 2))) * (0.35 + 1.5 * t1 * t2 * 1.4);
    if (pal.lanes) I *= 1 - 0.6 * smooth(0.55, 0.68, fbm(u * 9 + 3, v * 9, 3, 3)) * smooth(0.12, 0.55, dd);
    const core = pal.coreR ? Math.exp(-((r / pal.coreR) ** 2)) : 0;
    const col = mix(pal.outer, pal.arm, clamp(dd * 1.25));
    let rr = base[0] + col[0] * I * 0.8 + pal.core[0] * core * 0.6, gg = base[1] + col[1] * I * 0.8 + pal.core[1] * core * 0.6, bb = base[2] + col[2] * I * 0.8 + pal.core[2] * core * 0.6;
    if (pal.hii) { const h = smooth(0.64, 0.76, t2) * dd * smooth(0.1, 0.4, r); rr += 255 * h * 0.3; gg += 70 * h * 0.3; bb += 170 * h * 0.3; }
    const amb = smooth(0.5, 0.8, fbm(u * 3, v * 3, 5, 4)) * 0.1 * Math.exp(-((r / 1.1) ** 2)) * (1 - clamp(dd * 2));
    rr += pal.amb[0] * amb; gg += pal.amb[1] * amb; bb += pal.amb[2] * amb;
    const q = (y * lw + x) * 4; d[q] = rr; d[q + 1] = gg; d[q + 2] = bb; d[q + 3] = 255;
  }
  lx.putImageData(img, 0, 0);
  const out = make(W, H), g = out.getContext('2d')!;
  g.imageSmoothingQuality = 'high'; g.filter = 'blur(2.5px)'; g.drawImage(lo, 0, 0, W, H); g.filter = 'none';
  const rnd = mulberry(layout.params.ns ^ 0x5bd1e995), dust = Math.round(clamp(W * H / 90, 4000, 22000));
  for (let i = 0; i < dust; i++) {
    const x = rnd() * W, y = rnd() * H, u = (box.x + x * px - layout.cx) / R, v = (box.y + y * px - layout.cy) / Ry, dd = Math.min(1, dens(u, v));
    if (rnd() > 0.08 + 0.92 * dd) continue;
    const rad = rnd() < 0.94 ? 0.35 + rnd() * 0.55 : 0.8 + rnd() * 0.6, a = 0.2 + rnd() * 0.7;
    const warm = pal.coreR ? Math.exp(-((Math.hypot(u, v) / 0.35) ** 2)) : 0, t = rnd();
    g.fillStyle = t < warm ? `rgba(255,226,190,${a})` : t < 0.65 ? `rgba(225,235,255,${a})` : t < 0.9 ? `rgba(150,195,255,${a})` : `rgba(255,210,180,${a})`;
    g.beginPath(); g.arc(x, y, rad, 0, 6.283); g.fill();
  }
  return out;
}
