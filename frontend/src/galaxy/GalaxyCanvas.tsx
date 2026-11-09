import { useEffect, useMemo, useRef } from 'react';
import { buildTextures, drawFrame, frame } from './render';
import type { Scene, View } from './render';

const jsdom = typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent);

/**
 * Animated canvas of the mockup over real Knowledge. Decorative for assistive technologies: the
 * same information is always available as text or buttons next to it. Animation stops when the
 * canvas is off-screen, when the tab is hidden and with prefers-reduced-motion.
 */
export function GalaxyCanvas({ scene, view, labels = true, routes = true, selected = null, drift = false, stars = true, className, label }: {
  scene: Scene; view?: View; labels?: boolean; routes?: boolean; selected?: string | null; drift?: boolean; stars?: boolean;
  className?: string; label?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const key = useMemo(() => JSON.stringify([scene.systems.map(s => [s.id, s.x, s.y, s.state, s.own, s.capital]), scene.routes, scene.extent]), [scene]);
  // Textures depend on the Knowledge only (not on fleets, labels or the view).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const textures = useMemo(() => (jsdom ? null : buildTextures(scene)), [key]);
  const latest = useRef({ scene, view, labels, routes, selected, drift, stars });
  latest.current = { scene, view, labels, routes, selected, drift, stars };

  useEffect(() => {
    const el = ref.current;
    const ctx = el && !jsdom ? el.getContext('2d') : null;
    if (!el || !ctx || !textures) return;
    let raf = 0, running = false, visible = true, w = 0, h = 0, dpr = 1;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    const paint = (now: number) => {
      const o = latest.current;
      const v = o.view ?? frame(o.scene.systems, textures.s * 0.8);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawFrame(ctx, w, h, v, o.scene, textures, now, { labels: o.labels, routes: o.routes, selected: o.selected, drift: o.drift && !reduce, stars: o.stars });
    };
    const loop = (now: number) => { paint(now); if (running) raf = requestAnimationFrame(loop); };
    const start = () => { if (running || !visible || reduce || document.hidden) return; running = true; raf = requestAnimationFrame(loop); };
    const stop = () => { running = false; cancelAnimationFrame(raf); };
    const resize = () => {
      const r = el.getBoundingClientRect(); if (!r.width || !r.height) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2); w = r.width; h = r.height;
      el.width = Math.round(w * dpr); el.height = Math.round(h * dpr);
      paint(performance.now());
    };
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    ro?.observe(el); resize();
    const io = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(entries => {
      visible = entries[0]?.isIntersecting ?? true; if (visible) start(); else stop();
    }) : null;
    io?.observe(el);
    const onVisibility = () => (document.hidden ? stop() : start());
    document.addEventListener('visibilitychange', onVisibility);
    start();
    return () => { stop(); ro?.disconnect(); io?.disconnect(); document.removeEventListener('visibilitychange', onVisibility); };
  }, [textures]);

  // Static repaint when inputs change and the loop is not running (reduced motion).
  useEffect(() => {
    const el = ref.current;
    if (!el || jsdom || !textures) return;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      const ctx = el.getContext('2d'); if (!ctx) return;
      const r = el.getBoundingClientRect(); const dpr = Math.min(window.devicePixelRatio || 1, 2);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawFrame(ctx, r.width, r.height, view ?? frame(scene.systems, textures.s * 0.8), scene, textures, 0, { labels, routes, selected, drift: false, stars });
    }
  }, [scene, view, labels, routes, selected, stars, textures]);

  return <canvas ref={ref} className={className} role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true} />;
}
