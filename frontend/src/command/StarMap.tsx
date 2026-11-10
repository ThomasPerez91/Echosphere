import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";
import { GalaxyCanvas } from "../galaxy/GalaxyCanvas";
import type { Scene } from "../galaxy/render";
import type { MissionView } from "../fleet/api";
import { missionPosition, missionRoute, missionRouteLabel, point, stationed, systemName } from "./model";
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
export function StarMap({ world, selected, onSelect, preview, missions, now, filter = "all", showRoutes = true, showNames = true, focus, backdrop = true, menu, onFleets, picking = false, onCancelPick, overlay }: {
  world: World; selected: string | null; onSelect: (id: string) => void; preview: RoutePreview | null;
  missions: MissionView[]; now: number;
  filter?: MapFilter; showRoutes?: boolean; showNames?: boolean;
  /** "Localiser": centre the view on this point (keeps the zoom); `key` makes a repeat request count. */
  focus?: { x: number; y: number; key: number } | null;
  /** Animated canvas of the visual pack behind the interactive SVG (nebula, territory, fog, radar). */
  backdrop?: boolean;
  /** Context menu anchored next to the selected system (desktop); null keeps it closed. */
  menu?: ReactNode;
  /** The fleet symbol above a system opens the window of the fleets stationed there. */
  onFleets?: (system: string) => void;
  /** Destination picking: watermark on the map; right click (or Escape, handled by the caller) cancels. */
  picking?: boolean;
  onCancelPick?: () => void;
  /** Floating windows drawn over the map (fleet window, destination bar). */
  overlay?: ReactNode;
}) {
  const systems = world.galaxy.systems;
  const xs = systems.map((s) => s.x), ys = systems.map((s) => s.y);
  // Room for the legend overlay (top left) and labels (right of each star).
  const pad = { left: 150, right: 180, y: 60 };
  // Known space (first view, "Recentrer") and the whole galaxy (every star is visible as a point,
  // decision 09/11/2026; identities and routes stay behind the fog of war).
  const full: View = { x: Math.min(...xs) - pad.left, y: Math.min(...ys) - pad.y,
    w: Math.max(...xs) - Math.min(...xs) + pad.left + pad.right, h: Math.max(...ys) - Math.min(...ys) + 2 * pad.y };
  const far = useMemo(() => {
    const known = new Set(systems.map((s) => `${s.x},${s.y}`));
    return (world.galaxy.stars ?? []).filter(([x, y]) => !known.has(`${x},${y}`));
  }, [systems, world.galaxy.stars]);
  // Test game: foreign Colonies per system, by anonymous Empire number (still unknown Empires).
  const foreign = useMemo(() => {
    const map = new Map<string, number[]>();
    for (const p of world.galaxy.presences ?? []) {
      const list = map.get(p.system_id) ?? [];
      if (!list.includes(p.empire)) map.set(p.system_id, [...list, p.empire]);
    }
    return map;
  }, [world.galaxy.presences]);
  const galaxy: View = useMemo(() => {
    if (!far.length) return full;
    const ax = [...xs, ...far.map((p) => p[0])], ay = [...ys, ...far.map((p) => p[1])];
    const x = Math.min(...ax) - pad.left, y = Math.min(...ay) - pad.y;
    const w = Math.max(...ax) - x + pad.right, h = Math.max(...ay) - y + pad.y;
    // Same aspect as the known-space view, so zooming out keeps the frame proportions.
    const ratio = full.h / full.w, cw = Math.max(w, h / ratio), ch = cw * ratio;
    return { x: x - (cw - w) / 2, y: y - (ch - h) / 2, w: cw, h: ch };
  }, [far, full.x, full.y, full.w, full.h]); // eslint-disable-line react-hooks/exhaustive-deps
  const [view, setView] = useState<View>(full);
  const drag = useRef<{ x: number; y: number; view: View } | null>(null);
  useEffect(() => {
    if (focus) setView((v) => ({ ...v, x: focus.x - v.w / 2, y: focus.y - v.h / 2 }));
  }, [focus]);
  const svg = useRef<SVGSVGElement>(null);
  const stars = useMemo(() => starfield({ x: full.x - full.w, y: full.y - full.h, w: full.w * 3, h: full.h * 3 }, 900),
    [full.x, full.y, full.w, full.h]);

  const capital = systems.find((s) => s.observation?.own_colony_ids.length)?.id;
  const scene: Scene = useMemo(() => ({
    systems: systems.map((s) => ({ id: s.id, x: s.x, y: s.y, state: s.state, own: !!s.observation?.own_colony_ids.length, capital: s.id === capital })),
    routes: world.galaxy.routes.map((r) => ({ a: r.a_id, b: r.b_id })),
    ...(far.length ? { extent: galaxy } : {}),
  }), [systems, world.galaxy.routes, capital, far.length, galaxy]);
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
    const w = Math.min(Math.max(full.w * 1.5, galaxy.w * 1.1), Math.max(full.w / 4, v.w * factor)), h = w * (full.h / full.w);
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
  // No upper bound: zoomed out over the whole galaxy, markers keep their on-screen size.
  const scale = Math.max(0.35, fitted);
  const down = (e: PointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest(".cmd-system")) return;
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
    else if (e.key === "9") setView(galaxy);
  };

  const target = selected ? systems.find((s) => s.id === selected) : undefined;
  const anchor = target && rendered?.width ? (() => {
    const k = Math.min(rendered.width / view.w, rendered.height / view.h);
    const ox = (rendered.width - view.w * k) / 2, oy = (rendered.height - view.h * k) / 2;
    const left = ox + (target.x - view.x) * k, top = oy + (target.y - view.y) * k;
    return { left, top, flip: left > rendered.width * 0.6, up: top > rendered.height * 0.5 };
  })() : null;

  return <div className={`cmd-map-frame${backdrop ? " has-backdrop" : ""}${picking ? " is-picking" : ""}`}
    onContextMenu={picking ? (e) => { e.preventDefault(); onCancelPick?.(); } : undefined}>
    {picking && <div className="cmd-pick-watermark" aria-hidden="true">Choisir une destination</div>}
    {overlay}
    {backdrop && <GalaxyCanvas className="cmd-backdrop" scene={scene} view={view} labels={false} routes={false} selected={selected} />}
    <svg ref={svg} className="cmd-map" viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} role="group" tabIndex={0}
      aria-label="Carte de commandement : systèmes connus, vos flottes et vos missions. Flèches pour déplacer, plus et moins pour zoomer, zéro pour recentrer."
      preserveAspectRatio="xMidYMid meet" onPointerDown={down} onPointerMove={move}
      onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onKeyDown={mapKeys}>
      <defs>
        <radialGradient id="cmd-glow"><stop offset="0" stopColor="currentColor" stopOpacity=".55" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></radialGradient>
        <radialGradient id="cmd-nebula-a"><stop offset="0" stopColor="var(--map-nebula-a)" stopOpacity=".35" /><stop offset="1" stopColor="var(--map-nebula-a)" stopOpacity="0" /></radialGradient>
        <radialGradient id="cmd-nebula-b"><stop offset="0" stopColor="var(--map-nebula-b)" stopOpacity=".28" /><stop offset="1" stopColor="var(--map-nebula-b)" stopOpacity="0" /></radialGradient>
        <marker id="cmd-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" className="cmd-arrow" />
        </marker>
      </defs>
      {!backdrop && <g aria-hidden="true" className="cmd-decor">
        <ellipse cx={full.x + full.w * .3} cy={full.y + full.h * .35} rx={full.w * .45} ry={full.h * .5} fill="url(#cmd-nebula-a)" />
        <ellipse cx={full.x + full.w * .75} cy={full.y + full.h * .7} rx={full.w * .4} ry={full.h * .45} fill="url(#cmd-nebula-b)" />
        {stars.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r * scale} opacity={s.o} className="cmd-dust" />)}
      </g>}
      <g aria-hidden="true" className="cmd-far">
        {far.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={2.2 * scale} className="cmd-far-star" />)}
      </g>
      {showRoutes && world.galaxy.routes.map((r) => {
        const a = point(world, r.a_id)!, b = point(world, r.b_id)!;
        const partial = [r.a_id, r.b_id].some((id) => systems.find((s) => s.id === id)?.state === "DETECTED");
        const dim = !visible(r.a_id) && !visible(r.b_id);
        return <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} strokeWidth={1.5 * scale}
          strokeDasharray={partial ? `${6 * scale} ${5 * scale}` : undefined}
          className={`cmd-route${partial ? " cmd-route--partial" : ""}${dim ? " is-dimmed" : ""}`} />;
      })}
      {planned.length > 1 && <polyline points={planned.map((p) => `${p.x},${p.y}`).join(" ")} strokeWidth={3 * scale}
        strokeDasharray={preview?.path?.length ? undefined : `${8 * scale} ${6 * scale}`}
        className={`cmd-plan${preview?.path?.length ? "" : " cmd-plan--estimate"}`} markerEnd="url(#cmd-arrow)">
        <title>{preview?.path?.length ? "Trajet calculé par le serveur" : "Représentation indicative : départ et destination reliés directement, pas le trajet réel"}</title>
      </polyline>}
      {missions.map((m) => {
        const route = missionRoute(world, m);
        const ends = route?.points ?? [];
        const at = missionPosition(world, m, now);
        return <g key={m.id} className="cmd-mission">
          {ends.length > 1 && <polyline points={ends.map((p) => `${p.x},${p.y}`).join(" ")} strokeWidth={2 * scale}
            strokeDasharray={`${2 * scale} ${6 * scale}`} className={`cmd-mission-path${route?.kind === "estimated" ? " cmd-mission-path--estimate" : ""}`}>
            <title>{missionRouteLabel(m, route!)}</title></polyline>}
          {at && <g transform={`translate(${at.x} ${at.y}) scale(${scale})`}><title>{`Mission vers ${systemName(world, m.destination?.id)} — position estimée, non transmise par le serveur`}</title>
            <circle r={9} className="cmd-mission-halo" /><path d="M -5 4 L 0 -6 L 5 4 L 0 1 Z" className="cmd-mission-ship" /></g>}
        </g>;
      })}
      {systems.map((s) => {
        const name = systemName(world, s.id);
        const count = here.get(s.id) ?? 0;
        const others = foreign.get(s.id) ?? [];
        const label = `${name}${s.state === "DETECTED" ? " (position approximative)" : ""}${own.has(s.id) ? ", votre colonie" : ""}${others.length ? `, ${others.map((n) => `Empire inconnu ${n}`).join(", ")}` : ""}${count ? `, ${count} flotte(s) stationnée(s)` : ""}`;
        const state = own.has(s.id) ? "own" : s.state.toLowerCase();
        const big = selected === s.id || own.has(s.id);
        return <g key={s.id} role="button" tabIndex={0} aria-pressed={selected === s.id} aria-label={label}
          className={`cmd-system cmd-system--${state}${selected === s.id ? " is-selected" : ""}${visible(s.id) ? "" : " is-dimmed"}`}
          onClick={() => onSelect(s.id)} onKeyDown={key(s.id)}>
          <g transform={`translate(${s.x} ${s.y}) scale(${scale})`}>
            <circle r={26} className="cmd-hit" />
            <circle r={big ? 36 : 22} fill="url(#cmd-glow)" className="cmd-halo" />
            {selected === s.id && <circle r={18} className="cmd-selection" />}
            {own.has(s.id) && <><circle r={13} className="cmd-own" /><circle r={9.5} className="cmd-own cmd-own--inner" /></>}
            {others.map((n, i) => <circle key={n} r={13 + i * 4} className="cmd-foreign" style={{ stroke: foreignColor(n) }}>
              <title>{`Empire inconnu ${n}`}</title></circle>)}
            <circle r={s.state === "DETECTED" ? 4.5 : 6.5} className="cmd-star" />
            {(showNames || selected === s.id) && <text x={15} y={5} className={`cmd-label${big ? " cmd-label--strong" : ""}`}>{name}</text>}
            {count > 0 && (onFleets
              ? <g className="cmd-fleet-pin is-button" transform="translate(-14 -46)" role="button" tabIndex={0}
                aria-label={`Flottes à ${name} : ${count}`}
                onClick={(e) => { e.stopPropagation(); onFleets(s.id); }}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); onFleets(s.id); } }}>
                <rect width={28} height={18} rx={5} />
                <path d="M5 13 L10 5 L15 13 L10 10.5 Z" className="cmd-fleet-glyph" />
                <text x={21} y={13} textAnchor="middle">{count}</text></g>
              : <g className="cmd-fleet-pin" transform="translate(-24 -26)">
                <rect width={18} height={14} rx={4} /><text x={9} y={10.5} textAnchor="middle">{count}</text></g>)}
          </g>
        </g>;
      })}
    </svg>

    <div className="cmd-overlay cmd-overlay--legend" aria-label="Légende des systèmes" role="group">
      <p>Légende des systèmes</p>
      <ul>
        <li><span className="cmd-swatch cmd-swatch--unknown" />Inconnu (brouillard)</li>
        <li><span className="cmd-swatch cmd-swatch--detected" />{stateLabel.DETECTED}</li>
        <li><span className="cmd-swatch cmd-swatch--mapped" />{stateLabel.MAPPED}</li>
        <li><span className="cmd-swatch cmd-swatch--monitored" />{stateLabel.MONITORED}</li>
        <li><span className="cmd-swatch cmd-swatch--own" />Votre colonie</li>
        {foreign.size > 0 && <li><span className="cmd-swatch cmd-swatch--foreign" />Empire inconnu (partie de test)</li>}
        <li><span className="cmd-swatch cmd-swatch--fleet" />Vos flottes</li>
        <li><span className="cmd-swatch cmd-swatch--mission" />Mission en cours</li>
        <li><span className="cmd-swatch cmd-swatch--route" />Route hyperespace</li>
        <li className="cmd-legend-pending" title="Implémentation backend nécessaire"><span className="cmd-swatch cmd-swatch--hostile" />Système hostile <small>(à venir)</small></li>
      </ul>
    </div>

    <svg className="cmd-overlay cmd-minimap" viewBox={`${galaxy.x} ${galaxy.y} ${galaxy.w} ${galaxy.h}`} aria-hidden="true">
      {far.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={galaxy.w / 160} className="cmd-mini-far" />)}
      {world.galaxy.routes.map((r) => { const a = point(world, r.a_id)!, b = point(world, r.b_id)!;
        return <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="cmd-mini-route" />; })}
      {systems.map((s) => <circle key={s.id} cx={s.x} cy={s.y} r={Math.max(8, galaxy.w / 120)} className={`cmd-mini-star cmd-system--${own.has(s.id) ? "own" : s.state.toLowerCase()}`} />)}
      <rect x={view.x} y={view.y} width={view.w} height={view.h} className="cmd-mini-view" />
    </svg>

    {menu && (anchor ? <div className={`cmd-ctx${anchor.flip ? " is-flipped" : ""}${anchor.up ? " is-up" : ""}`} style={{ left: anchor.left, top: anchor.top }}>{menu}</div>
      : <div className="cmd-ctx is-docked">{menu}</div>)}

    <div className="cmd-overlay cmd-zoom" role="group" aria-label="Commandes de la carte">
      <button type="button" className="button" aria-label="Recentrer la carte" onClick={() => setView(full)}>⌖</button>
      {far.length > 0 && <button type="button" className="button" aria-label="Voir toute la galaxie" title="Toute la galaxie" onClick={() => setView(galaxy)}>◎</button>}
      <button type="button" className="button" aria-label="Zoom arrière" onClick={() => zoom(1.25)}>−</button>
      <button type="button" className="button" aria-label="Zoom avant" onClick={() => zoom(1 / 1.25)}>+</button>
    </div>
  </div>;
}

/** Distinct, stable hue per anonymous Empire number (test game). */
export function foreignColor(n: number) {
  return `hsl(${(n * 67 + 8) % 360} 85% 62%)`;
}
