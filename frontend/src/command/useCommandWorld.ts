import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, previewMission } from "../fleet/api";
import { useFleets } from "../hooks/useFleets";
import { useGalaxy } from "../hooks/useGalaxy";
import type { World } from "./model";
import type { MissionApi } from "./types";

/**
 * Galaxy and Fleet projections of ONE Empire of the current Universe, joined only when both
 * concern that Empire, with the MissionApi wired to the Game API: `previewMission` for the server
 * summary, `useFleets().run` for launch/recall (session CSRF, idempotency key per intention, one
 * command at a time, re-read on refusal). After an accepted command both projections are re-read:
 * no mission is invented. Shared by the command map and the System View.
 */
export function useCommandWorld(universe: string, enabled: boolean, csrf: string | undefined, onSessionLost: () => void,
  onEconomyChanged?: () => void, initialEmpire?: string, onEmpireChange?: (empire: string) => void) {
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
    ? { galaxy: { systems: g.systems, routes: g.routes, stars: g.stars, presences: g.sandbox?.presences, layout: g.layout }, fleets: f } : null), [g, f]);

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

  return { galaxy, fleets, g, f, world, now, api, synced };
}
