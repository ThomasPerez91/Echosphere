/**
 * UX03 prototype data: implements the production `MissionApi` seam with fixtures (no network).
 * `launch`/`recall` apply a local DEMO ECHO to the fixture world (what the server's re-read would
 * show); production never does this — it re-reads the real projections after an accepted command.
 */
import type { FleetProjection, FleetView, MissionView } from "../fleet/api";
import type { World } from "../command/model";
import type { CommandQuote, MissionApi } from "../command/types";
import { quoteFixture } from "./fixtures";

export class MissionRefused extends Error {
  constructor(public code: string) { super(code); }
}

const delay = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("aborted", "AbortError")); });
});
const id = (prefix: string, n: number) => `${prefix}-0000-4000-8000-${String(n).padStart(12, "0")}`;

export function fixtureApi(world: () => World, update: (w: World) => void, now: () => number,
  options: { latencyMs?: number; withPath?: () => boolean } = {}): MissionApi {
  const latency = options.latencyMs ?? 350;
  let sequence = 0;
  const write = (fleets: FleetProjection) => update({ ...world(), fleets: { ...fleets, server_time: new Date(now()).toISOString() } });
  return {
    async preview(plan, signal) {
      await delay(latency, signal);
      const w = world();
      const fleet = w.fleets.fleets?.find((f) => f.id === plan.fleet_id);
      const destination = plan.destination_id ?? w.fleets.systems?.find((s) => s.planets?.some((p) => p.id === plan.target_planet_id))?.id;
      if (!fleet?.system || !destination) throw new MissionRefused("invalid_request");
      const answer = quoteFixture(fleet.system.id, plan.kind, destination, plan.units, plan.target_planet_id ?? null, new Date(now()).toISOString());
      if ("error" in answer) throw new MissionRefused(answer.error);
      if (options.withPath && !options.withPath()) { const rest: CommandQuote = { ...answer }; delete rest.path; return rest; }
      return answer;
    },
    async launch(plan, quote) {
      await delay(latency);
      const w = world();
      const source = w.fleets.fleets!.find((f) => f.id === plan.fleet_id)!;
      sequence += 1;
      const started = new Date(now()).toISOString();
      const arrival = new Date(Date.parse(started) + Number(BigInt(quote.travel_us) / 1000n)).toISOString();
      const ref = (sid: string) => w.fleets.systems!.find((s) => s.id === sid) ?? null;
      const whole = source.kind === "TASK" && Object.entries(source.stacks).every(([c, n]) => (plan.units[c] ?? 0) === n);
      const fleetId = whole ? source.id : id("62000000", sequence);
      const missionId = id("61000000", sequence);
      const mission: MissionView = {
        id: missionId, fleet_id: fleetId, kind: plan.kind, status: "active", origin: source.system, destination: ref(quote.destination_id),
        hops: quote.hops, stacks: plan.units, cargo: { alloys: "0", flux: "0", data: "0" }, cost: quote.cost,
        started_at: started, travel_arrival_at: arrival, due_at: quote.kind === "ATTACK" && quote.battle_at ? quote.battle_at : quote.due_at,
        recalled_at: null, return_at: null, completed_at: null, payer_colony_id: quote.payer_colony_id, target_planet: null, report: null,
        ...(plan.kind === "ATTACK" && quote.battle_at ? { attack: { engagement_id: id("63000000", sequence), battle_at: quote.battle_at, state: "pending" as const } } : {}),
      };
      const moving: FleetView = { ...source, id: fleetId, kind: "TASK", status: "MOVING", system: null, mission_id: missionId, stacks: plan.units,
        name: whole ? source.name : `Détachement ${sequence}` };
      const rest = Object.fromEntries(Object.entries(source.stacks).map(([c, n]) => [c, n - (plan.units[c] ?? 0)]).filter(([, n]) => (n as number) > 0));
      const fleets = whole ? w.fleets.fleets!.map((f) => (f.id === source.id ? moving : f))
        : [...w.fleets.fleets!.map((f) => (f.id === source.id ? { ...f, stacks: rest } : f)), moving];
      write({ ...w.fleets, fleets, missions: [mission, ...(w.fleets.missions ?? [])] });
      return { missionId };
    },
    async recall(m) {
      await delay(latency);
      const w = world();
      const at = now();
      const back = new Date(at + (at - Date.parse(m.started_at))).toISOString();
      write({ ...w.fleets, missions: (w.fleets.missions ?? []).map((x) => (x.id === m.id
        ? { ...x, status: "returning" as const, recalled_at: new Date(at).toISOString(), return_at: back } : x)) });
      return true;
    },
  };
}
