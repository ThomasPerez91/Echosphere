/**
 * The only seam between the prototype UI and data. The UI calls `MissionApi`; the prototype
 * provides `fixtureApi` (local, no network). Wiring the real Game API later means implementing
 * the same two calls with `previewMission` and `fleetCommand(… "/missions" …)` from fleet/api.ts.
 */
import type { MissionView, Plan } from "../fleet/api";
import { quoteFixture } from "./fixtures";
import type { FixtureQuote } from "./fixtures";
import type { World } from "./model";

export class MissionRefused extends Error {
  constructor(public code: string) { super(code); }
}

export type MissionApi = {
  preview(plan: Plan, signal?: AbortSignal): Promise<FixtureQuote>;
  launch(plan: Plan, quote: FixtureQuote): Promise<MissionView>;
};

const delay = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("aborted", "AbortError")); });
});

/** Fixture answers with a short artificial latency so loading states are visible. */
export function fixtureApi(world: () => World, now: () => number, latencyMs = 350): MissionApi {
  let sequence = 0;
  return {
    async preview(plan, signal) {
      await delay(latencyMs, signal);
      const w = world();
      const fleet = w.fleets.fleets?.find((f) => f.id === plan.fleet_id);
      const destination = plan.destination_id ?? w.fleets.systems?.find((s) => s.planets?.some((p) => p.id === plan.target_planet_id))?.id;
      if (!fleet?.system || !destination) throw new MissionRefused("invalid_request");
      const answer = quoteFixture(fleet.system.id, plan.kind, destination, plan.units, plan.target_planet_id ?? null, new Date(now()).toISOString());
      if ("error" in answer) throw new MissionRefused(answer.error);
      return answer;
    },
    async launch(plan, quote) {
      await delay(latencyMs);
      const w = world();
      const fleet = w.fleets.fleets!.find((f) => f.id === plan.fleet_id)!;
      sequence += 1;
      const started = new Date(now()).toISOString();
      const travel = Number(BigInt(quote.travel_us) / 1000n);
      const arrival = new Date(Date.parse(started) + travel).toISOString();
      const ref = (id: string) => w.fleets.systems!.find((s) => s.id === id) ?? null;
      return {
        id: `61000000-0000-4000-8000-${String(sequence).padStart(12, "0")}`,
        fleet_id: fleet.id, kind: plan.kind, status: "active", origin: fleet.system, destination: ref(quote.destination_id),
        hops: quote.hops, stacks: plan.units, cargo: { alloys: "0", flux: "0", data: "0" }, cost: quote.cost,
        started_at: started, travel_arrival_at: arrival, due_at: quote.kind === "ATTACK" && quote.battle_at ? quote.battle_at : arrival,
        recalled_at: null, return_at: null, completed_at: null, payer_colony_id: quote.payer_colony_id,
        target_planet: null, report: null,
      };
    },
  };
}
