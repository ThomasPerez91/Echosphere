import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import type { MissionView } from "../fleet/api";
import { missionPosition, point, stationed, systemName } from "./model";
import type { Point, World } from "./model";

export type RoutePreview = { from: string; to: string; path?: string[] };
export type MapFilter = "all" | "known" | "own" | "fleets" | "signals";
type View = { x: number; y: number; w: number; h: number };

/** Deterministic decorative starfield (no game meaning): same picture on every render. */
function starfield(box: View, count: number) {
  let seed = 1337;
  const next = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  return Array.from({ length: count }, () => ({
    x: box.x + next() * box.w, y: box.y + next() * box.h, r: 0.3 + next() ** 3 * 2.2, o: 0.2 + next() * 0.7,
  }));
}

const stateLabel = { DETECTED: "Détecté", MAPPED: "Cartographié", MONITORED: "Surveillé" } as const;

/**
 * Galaxy command map (look of docs/visual-reference/galaxy-map.png): starfield, glowing systems
 * coloured by Knowledge state, own systems ringed, hyperspace routes, own fleets and missions, the
 * planned route; overlays for legend, zoom and minimap. Only this Empire's Knowledge is drawn:
 * the mockup's regions, influence and distances have no game data and are not reproduced.
 * Every system is a real button (Tab, Enter/Space); nothing depends on hover.
 */
export function StarMap({ world, selected, onSelect, preview, missions, now, paths, filter = "all", showRoutes = true, showNames = true }: {
  world: World; selected: string | null; onSelect: (id: string) => void; preview: RoutePreview | null;
  missions: MissionView[]; now: number; paths: Record<string, string[] | undefined>;
  filter?: MapFilter; showRoutes?: boolean; showNames?: boolean;
}) {
  const systems = world.galaxy.systems;
  const xs = systems.map((s) => s.x), ys = systems.map((s) => s.y);
  // Room for the legend overlay (top left) and labels (right of each star).
  const pad = { left: 150, right: 180, y: 60 };
  const full: View = { x: Math.min(...xs) - pad.left, y: Math.min(...ys) - pad.y,
    w: Math.max(...xs) - Math.min(...xs) + pad.left + pad.right, h: Math.max(...ys) - Math.min(...ys) + 2 * pad.y };
  const [view, setView] = useState<View>(full);
  const drag = useRef<{ x: number; y: number; view: View } | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const stars = useMemo(() => starfield({ x: full.x - full.w, y: full.y - full.h, w: full.w * 3, h: full.h * 3 }, 900),
    [full.x, full.y, full.w, full.h]);

  const here = new Map<string, number>();
  for (const f of stationed(world)) if (f.system) here.set(f.system.id, (here.get(f.system.id) ?? 0) + 1);
  const own = new Set(systems.filter((s) => s.observation?.own_colony_ids.length).map((s) => s.id));
  const visible = (id: string) => {
    const s = systems.find((x) => x.id === id)!;
    return filter === "all" || (filter === "known" && s.state !== "DETECTED") || (filter === "own" && own.has(id))
      || (filter === "fleets" && here.has(id)) || (filter === "signals" && s.state === "DETECTED");
  };
  const planned = preview ? (preview.path?.length ? preview.path : [preview.from, preview.to]).map((id) => point(world, id)).filter((p): p is Point => !!p) : [];
  const key = (id: string) => (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(id); } };
  const zoom = (factor: number) => setView((v) => {
    const w = Math.min(full.w * 1.5, Math.max(full.w / 4, v.w * factor)), h = w * (full.h / full.w);
    return { x: v.x + (v.w - w) / 2, y: v.y + (v.h - h) / 2, w, h };
  });
  // Map units per screen pixel: markers, strokes and labels keep a constant on-screen size
  // whatever the zoom level or the screen width (the map content itself scales).
  const [pixels, setPixels] = useState(900);
  useEffect(() => {
    const node = svg.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => { if (entry.contentRect.width) setPixels(entry.contentRect.width); });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const rendered = svg.current?.getBoundingClientRect();
  const fitted = rendered?.height ? Math.max(view.w / pixels, view.h / rendered.height) : view.w / pixels;
  const scale = Math.min(1.6, Math.max(0.35, fitted));
  const down = (e: PointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest(".proto-system")) return;
    drag.current = { x: e.clientX, y: e.clientY, view };
    svg.current?.setPointerCapture?.(e.pointerId);
  };
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current, rect = svg.current?.getBoundingClientRect();
    if (!d || !rect?.width) return;
    const k = d.view.w / rect.width;
    setView({ ...d.view, x: d.view.x - (e.clientX - d.x) * k, y: d.view.y - (e.clientY - d.y) * k });
  };
  const mapKeys = (e: KeyboardEvent) => {
    if (e.target !== svg.current) return;
    const step = view.w / 10;
    const moves: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (moves[e.key]) { e.preventDefault(); setView((v) => ({ ...v, x: v.x + moves[e.key][0], y: v.y + moves[e.key][1] })); }
    else if (e.key === "+" || e.key === "=") zoom(1 / 1.25);
    else if (e.key === "-") zoom(1.25);
    else if (e.key === "0") setView(full);
  };

  return <div className="proto-map-frame">
    <svg ref={svg} className="proto-map" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} role="group" tabIndex={0}
      aria-label="Carte de commandement : systèmes connus, vos flottes et vos missions. Flèches pour déplacer, plus et moins pour zoomer, zéro pour recentrer."
      preserveAspectRatio="xMidYMid meet" onPointerDown={down} onPointerMove={move}
      onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onKeyDown={mapKeys}>
      <defs>
        <radialGradient id="proto-glow"><stop offset="0" stopColor="currentColor" stopOpacity=".55" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></radialGradient>
        <radialGradient id="proto-nebula-a"><stop offset="0" stopColor="var(--map-nebula-a)" stopOpacity=".35" /><stop offset="1" stopColor="var(--map-nebula-a)" stopOpacity="0" /></radialGradient>
        <radialGradient id="proto-nebula-b"><stop offset="0" stopColor="var(--map-nebula-b)" stopOpacity=".28" /><stop offset="1" stopColor="var(--map-nebula-b)" stopOpacity="0" /></radialGradient>
        <marker id="proto-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" className="proto-arrow" />
        </marker>
      </defs>
      <g aria-hidden="true" className="proto-decor">
        <ellipse cx={full.x + full.w * .3} cy={full.y + full.h * .35} rx={full.w * .45} ry={full.h * .5} fill="url(#proto-nebula-a)" />
        <ellipse cx={full.x + full.w * .75} cy={full.y + full.h * .7} rx={full.w * .4} ry={full.h * .45} fill="url(#proto-nebula-b)" />
        {stars.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r * scale} opacity={s.o} className="proto-dust" />)}
      </g>
      {showRoutes && world.galaxy.routes.map((r) => {
        const a = point(world, r.a_id)!, b = point(world, r.b_id)!;
        const partial = [r.a_id, r.b_id].some((id) => systems.find((s) => s.id === id)?.state === "DETECTED");
        const dim = !visible(r.a_id) && !visible(r.b_id);
        return <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} strokeWidth={1.5 * scale}
          strokeDasharray={partial ? `${6 * scale} ${5 * scale}` : undefined}
          className={`proto-route${partial ? " proto-route--partial" : ""}${dim ? " is-dimmed" : ""}`} />;
      })}
      {planned.length > 1 && <polyline points={planned.map((p) => `${p.x},${p.y}`).join(" ")} strokeWidth={3 * scale}
        strokeDasharray={preview?.path?.length ? undefined : `${8 * scale} ${6 * scale}`}
        className={`proto-plan${preview?.path?.length ? "" : " proto-plan--estimate"}`} markerEnd="url(#proto-arrow)" />}
      {missions.map((m) => {
        const ends = (paths[m.id]?.length ? paths[m.id]! : [m.origin?.id, m.destination?.id]).map((id) => (id ? point(world, id) : null)).filter((p): p is Point => !!p);
        const at = missionPosition(world, m, now, paths[m.id]);
        return <g key={m.id} className="proto-mission">
          {ends.length > 1 && <polyline points={ends.map((p) => `${p.x},${p.y}`).join(" ")} strokeWidth={2 * scale}
            strokeDasharray={`${2 * scale} ${6 * scale}`} className="proto-mission-path" />}
          {at && <g transform={`translate(${at.x} ${at.y}) scale(${scale})`}><title>{`Mission vers ${systemName(world, m.destination?.id)} (position estimée)`}</title>
            <circle r={9} className="proto-mission-halo" /><path d="M -5 4 L 0 -6 L 5 4 L 0 1 Z" className="proto-mission-ship" /></g>}
        </g>;
      })}
      {systems.map((s) => {
        const name = systemName(world, s.id);
        const count = here.get(s.id) ?? 0;
        const label = `${name}${s.state === "DETECTED" ? " (position approximative)" : ""}${own.has(s.id) ? ", votre colonie" : ""}${count ? `, ${count} flotte(s) stationnée(s)` : ""}`;
        const state = own.has(s.id) ? "own" : s.state.toLowerCase();
        const big = selected === s.id || own.has(s.id);
        return <g key={s.id} role="button" tabIndex={0} aria-pressed={selected === s.id} aria-label={label}
          className={`proto-system proto-system--${state}${selected === s.id ? " is-selected" : ""}${visible(s.id) ? "" : " is-dimmed"}`}
          onClick={() => onSelect(s.id)} onKeyDown={key(s.id)}>
          <g transform={`translate(${s.x} ${s.y}) scale(${scale})`}>
            <circle r={26} className="proto-hit" />
            <circle r={big ? 36 : 22} fill="url(#proto-glow)" className="proto-halo" />
            {selected === s.id && <circle r={18} className="proto-selection" />}
            {own.has(s.id) && <><circle r={13} className="proto-own" /><circle r={9.5} className="proto-own proto-own--inner" /></>}
            <circle r={s.state === "DETECTED" ? 4.5 : 6.5} className="proto-star" />
            {(showNames || selected === s.id) && <text x={15} y={5} className={`proto-label${big ? " proto-label--strong" : ""}`}>{name}</text>}
            {count > 0 && <g className="proto-fleet-pin" transform="translate(-24 -26)">
              <rect width={18} height={14} rx={4} /><text x={9} y={10.5} textAnchor="middle">{count}</text></g>}
          </g>
        </g>;
      })}
    </svg>

    <div className="proto-overlay proto-overlay--legend" aria-label="Légende des systèmes" role="group">
      <p>Légende des systèmes</p>
      <ul>
        <li><span className="proto-swatch proto-swatch--detected" />{stateLabel.DETECTED}</li>
        <li><span className="proto-swatch proto-swatch--mapped" />{stateLabel.MAPPED}</li>
        <li><span className="proto-swatch proto-swatch--monitored" />{stateLabel.MONITORED}</li>
        <li><span className="proto-swatch proto-swatch--own" />Votre colonie</li>
        <li><span className="proto-swatch proto-swatch--fleet" />Vos flottes</li>
        <li><span className="proto-swatch proto-swatch--mission" />Mission en cours</li>
        <li><span className="proto-swatch proto-swatch--route" />Route hyperespace</li>
      </ul>
    </div>

    <svg className="proto-overlay proto-minimap" viewBox={`${full.x} ${full.y} ${full.w} ${full.h}`} aria-hidden="true">
      {world.galaxy.routes.map((r) => { const a = point(world, r.a_id)!, b = point(world, r.b_id)!;
        return <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="proto-mini-route" />; })}
      {systems.map((s) => <circle key={s.id} cx={s.x} cy={s.y} r={8} className={`proto-mini-star proto-system--${own.has(s.id) ? "own" : s.state.toLowerCase()}`} />)}
      <rect x={view.x} y={view.y} width={view.w} height={view.h} className="proto-mini-view" />
    </svg>

    <div className="proto-overlay proto-zoom" role="group" aria-label="Commandes de la carte">
      <button type="button" className="button" aria-label="Recentrer la carte" onClick={() => setView(full)}>⌖</button>
      <button type="button" className="button" aria-label="Zoom arrière" onClick={() => zoom(1.25)}>−</button>
      <button type="button" className="button" aria-label="Zoom avant" onClick={() => zoom(1 / 1.25)}>+</button>
    </div>
  </div>;
}
