import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, previewMission } from "../fleet/api";
import { message } from "../fleet/messages";
import { time } from "../colony/format";
import { useFleets } from "../hooks/useFleets";
import { useGalaxy } from "../hooks/useGalaxy";
import { Button, Panel } from "../components/ui";
import { CommandMap } from "./CommandMap";
import type { World } from "./model";
import type { MissionApi } from "./types";

/**
 * Production container of the command map (UX04). Reads the real Galaxy and Fleet projections of
 * ONE Empire of the current Universe, joins them only when both concern that Empire, and wires the
 * MissionApi to the existing Game API: `previewMission` for the server summary, `useFleets().run`
 * for launch/recall (session CSRF, idempotency key per intention, one command at a time, re-read
 * on refusal). After an accepted command both projections are re-read: no mission is invented.
 */
export function LiveCommandMap({ universe, enabled, csrf, onSessionLost, onEconomyChanged, initialEmpire, onEmpireChange, toolbar: extra, subtitle, systemHref }: {
  universe: string; enabled: boolean; csrf: string | undefined; onSessionLost: () => void;
  onEconomyChanged?: () => void; initialEmpire?: string; onEmpireChange?: (empire: string) => void;
  /** Extra controls shown in the page header (e.g. the classic-map switch). */
  toolbar?: ReactNode; subtitle?: string;
  systemHref?: (empire: string, system: string) => string;
}) {
  const galaxy = useGalaxy(universe, enabled, csrf, onSessionLost, initialEmpire);
  const fleets = useFleets(universe, enabled, csrf, onSessionLost, galaxy.selectedEmpire || initialEmpire);
  const g = galaxy.projection;
  const f = fleets.projection;
  const empire = g?.empire.id ?? null;

  // The Fleet projection follows the Empire chosen for the map (never the other way round).
  const synced = useRef<string | null>(null);
  useEffect(() => {
    if (!empire || fleets.phase === "loading" || fleets.phase === "idle") return;
    if (f?.empire.id === empire) { synced.current = empire; return; }
    if (synced.current === empire) return; // already asked: an error stays visible, no loop
    synced.current = empire;
    fleets.select(empire);
    // fleets.select is stable (useCallback); the hook object itself changes every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [empire, f?.empire.id, fleets.phase]);
  useEffect(() => { if (empire) onEmpireChange?.(empire); }, [empire, onEmpireChange]);

  const world: World | null = useMemo(() => (g && f && f.available && f.empire.id === g.empire.id
    ? { galaxy: { systems: g.systems, routes: g.routes, stars: g.stars }, fleets: f } : null), [g, f]);

  // Server clock: the Fleet projection's server_time advanced by the local time since reception.
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => { const t = window.setInterval(() => setTick(Date.now()), 1000); return () => window.clearInterval(t); }, []);
  const now = f ? Date.parse(f.server_time) + Math.max(0, tick - fleets.receivedAt) : tick;

  const latest = useRef({ galaxy, fleets, csrf, onEconomyChanged, onSessionLost });
  latest.current = { galaxy, fleets, csrf, onEconomyChanged, onSessionLost };
  const api: MissionApi = useMemo(() => ({
    async preview(plan, signal) {
      const { fleets: fl, csrf: token } = latest.current;
      const p = fl.projection;
      if (!p || !token) throw new ApiError("authentication_required", 401);
      try {
        return await previewMission(universe, p.empire.id, token, plan, p.permissions.includes("colony.read"), signal);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) latest.current.onSessionLost();
        throw error;
      }
    },
    async launch(plan) {
      const { fleets: fl, galaxy: ga } = latest.current;
      // Same plan → same signature → same idempotency key: a retry after an unknown outcome never pays twice.
      const result = await fl.run("/missions", plan, JSON.stringify(plan));
      if (!result) return null;
      ga.refresh(); // the fleet's new position and any revealed knowledge come from the server
      latest.current.onEconomyChanged?.();
      return { missionId: typeof result.mission_id === "string" ? result.mission_id : null };
    },
    async recall(m) {
      const result = await latest.current.fleets.run(`/missions/${m.id}/recall`, {}, m.id);
      return !!result;
    },
    // Same endpoint and idempotency signature as the Fleets screen (13B protocols).
    async protocol(fleetId, protocol) {
      const result = await latest.current.fleets.run(`/${fleetId}/protocol`, { protocol }, JSON.stringify([fleetId, protocol]));
      return !!result;
    },
  }), [universe]);

  if (!enabled) return null;
  // Until the map is drawn, the page keeps its heading and the switch to the classic map.
  const head = <header className="cmd-page-head"><div><h1 className="cmd-page-title" tabIndex={-1}>Galaxie</h1>
    <p><strong>Carte stratégique</strong> {subtitle ?? "des systèmes connus de votre Empire"}.</p></div>{extra}</header>;
  if (galaxy.phase === "loading" || galaxy.phase === "idle")
    return <div className="cmd-root cmd-live">{head}<p className="panel" role="status">Chargement des connaissances de l’Empire…</p></div>;
  if (galaxy.phase === "empty")
    return <div className="cmd-root cmd-live">{head}<Panel title="Aucune galaxie accessible"><p>Aucun Empire ne vous donne accès à la galaxie dans cet univers.</p></Panel></div>;
  if (!g) return <div className="cmd-root cmd-live">{head}<Panel title="Galaxie indisponible">
    <p role="alert">{galaxy.error === "galaxy_unavailable" ? "La galaxie n’est pas disponible pour cet Empire dans cet univers." : message(galaxy.error ?? "unavailable")}</p>
    <Button onClick={galaxy.refresh}>Réessayer</Button></Panel></div>;

  const controls = <>
    {galaxy.empires.length > 1 ? <label className="galaxy-field">Empire
      <select value={galaxy.selectedEmpire} disabled={galaxy.pending || fleets.pending} onChange={(e) => galaxy.select(e.target.value)}>
        {galaxy.empires.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
      </select></label> : <span className="panel-meta">Empire : {g.empire.name}</span>}
    <span className="panel-meta">Connaissances au {time(g.server_time)}</span>
    <Button onClick={() => { galaxy.refresh(); fleets.refresh(); }} disabled={fleets.pending}>Actualiser</Button>
  </>;
  const toolbar = <div className="cmd-toolbar">{extra}{controls}</div>;

  if (!world) {
    const loadingFleets = fleets.phase === "loading" || fleets.phase === "idle" || (f && f.empire.id !== g.empire.id && !fleets.error);
    return <div className="cmd-root cmd-live">{head}<div className="cmd-toolbar cmd-toolbar--solo">{controls}</div>
      {loadingFleets ? <p className="panel" role="status">Chargement des flottes de l’Empire…</p>
        : <Panel title="Flottes indisponibles">
          <p role="alert">{f && !f.available ? "Les flottes ne sont pas disponibles pour cet Empire dans cet univers."
            : message(fleets.error ?? "unavailable")}</p>
          <p className="cmd-help">La carte de commandement a besoin de la galaxie et des flottes du même Empire. La carte classique reste disponible.</p>
          <Button onClick={() => { synced.current = null; fleets.select(g.empire.id); }}>Réessayer</Button></Panel>}
    </div>;
  }

  return <div className="cmd-root cmd-live">
    {fleets.awaiting && <p className="cmd-help" role="status">Une échéance est passée : en attente de la confirmation du serveur.</p>}
    <CommandMap world={world} now={now} api={api} pending={fleets.pending} feedback={fleets.feedback} toolbar={toolbar}
      subtitle={subtitle} systemHref={systemHref ? (id) => systemHref(g.empire.id, id) : undefined} />
  </div>;
}
