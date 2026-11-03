import type { KeyboardEvent } from "react";
import type { MissionView } from "../fleet/api";
import { missionPosition, point, stationed, systemName } from "./model";
import type { Point, World } from "./model";

export type RoutePreview = { from: string; to: string; path?: string[] };

/**
 * Command map: known systems and routes (Knowledge only), own fleets where they stand, own
 * missions moving between their dates, and the route being planned. Every system is a real
 * button (Tab, Enter/Space); nothing is reachable by hover only.
 */
export function StarMap({ world, selected, onSelect, preview, missions, now, paths }: {
  world: World; selected: string | null; onSelect: (id: string) => void; preview: RoutePreview | null;
  missions: MissionView[]; now: number; paths: Record<string, string[] | undefined>;
}) {
  const systems = world.galaxy.systems;
  const xs = systems.map((s) => s.x), ys = systems.map((s) => s.y);
  // Labels sit right of each star: more room on the right than on the left.
  const pad = { left: 50, right: 150, y: 50 };
  const box = { x: Math.min(...xs) - pad.left, y: Math.min(...ys) - pad.y, w: Math.max(...xs) - Math.min(...xs) + pad.left + pad.right, h: Math.max(...ys) - Math.min(...ys) + 2 * pad.y };
  const here = new Map<string, number>();
  for (const f of stationed(world)) if (f.system) here.set(f.system.id, (here.get(f.system.id) ?? 0) + 1);
  const own = new Set(systems.filter((s) => s.observation?.own_colony_ids.length).map((s) => s.id));
  const planned = preview ? (preview.path?.length ? preview.path : [preview.from, preview.to]).map((id) => point(world, id)).filter((p): p is Point => !!p) : [];
  const key = (id: string) => (e: KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(id); } };

  return <svg className="proto-map" viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} role="group"
    aria-label="Carte de commandement : systèmes connus, vos flottes et vos missions" preserveAspectRatio="xMidYMid meet">
    <defs>
      <marker id="proto-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" className="proto-arrow" />
      </marker>
    </defs>
    {world.galaxy.routes.map((r) => {
      const a = point(world, r.a_id)!, b = point(world, r.b_id)!;
      const partial = [r.a_id, r.b_id].some((id) => systems.find((s) => s.id === id)?.state === "DETECTED");
      return <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`proto-route${partial ? " proto-route--partial" : ""}`} />;
    })}
    {planned.length > 1 && <polyline points={planned.map((p) => `${p.x},${p.y}`).join(" ")}
      className={`proto-plan${preview?.path?.length ? "" : " proto-plan--estimate"}`} markerEnd="url(#proto-arrow)" />}
    {missions.map((m) => {
      const ends = (paths[m.id]?.length ? paths[m.id]! : [m.origin?.id, m.destination?.id]).map((id) => (id ? point(world, id) : null)).filter((p): p is Point => !!p);
      const at = missionPosition(world, m, now, paths[m.id]);
      return <g key={m.id} className="proto-mission">
        {ends.length > 1 && <polyline points={ends.map((p) => `${p.x},${p.y}`).join(" ")} className="proto-mission-path" />}
        {at && <g transform={`translate(${at.x} ${at.y})`}><title>{`Mission vers ${systemName(world, m.destination?.id)} (position estimée)`}</title>
          <circle r={9} className="proto-mission-halo" /><path d="M -5 4 L 0 -6 L 5 4 L 0 1 Z" className="proto-mission-ship" /></g>}
      </g>;
    })}
    {systems.map((s) => {
      const name = systemName(world, s.id);
      const count = here.get(s.id) ?? 0;
      const label = `${name}${s.state === "DETECTED" ? " (position approximative)" : ""}${own.has(s.id) ? ", votre colonie" : ""}${count ? `, ${count} flotte(s) stationnée(s)` : ""}`;
      return <g key={s.id} role="button" tabIndex={0} aria-pressed={selected === s.id} aria-label={label}
        className={`proto-system proto-system--${s.state.toLowerCase()}${selected === s.id ? " is-selected" : ""}`}
        onClick={() => onSelect(s.id)} onKeyDown={key(s.id)}>
        <circle cx={s.x} cy={s.y} r={24} className="proto-hit" />
        {selected === s.id && <circle cx={s.x} cy={s.y} r={17} className="proto-selection" />}
        {own.has(s.id) && <circle cx={s.x} cy={s.y} r={12.5} className="proto-own" />}
        <circle cx={s.x} cy={s.y} r={s.state === "DETECTED" ? 5 : 7.5} className="proto-star" />
        <text x={s.x + 14} y={s.y + 4} className="proto-label">{name}</text>
        {count > 0 && <g className="proto-fleet-pin" transform={`translate(${s.x - 16} ${s.y - 18})`}>
          <rect width={18} height={14} rx={4} /><text x={9} y={10.5} textAnchor="middle">{count}</text></g>}
      </g>;
    })}
  </svg>;
}
