import type { FleetProjection, MissionView } from "../src/fleet/api";
import { amounts, colony, empire, near, origin, otherEmpire, session } from "./galaxyFixture";
export { colony, empire, near, origin, session, universe, otherEmpire } from "./galaxyFixture";
// Intercepted UI data only: shapes follow the Game API; values are test placeholders, not rules.
export const garrison = "66666666-6666-4666-8666-666666666666";
export const task = "77777777-7777-4777-8777-777777777777";
export const order = "88888888-8888-4888-8888-888888888888";
export const mission = "99999999-9999-4999-8999-999999999999";
export const done = "aaaaaaaa-0000-4000-8000-000000000009";

export function surveying(at = "2099-01-01T00:00:00Z"): MissionView {
  return {
    id: mission, fleet_id: task, kind: "SURVEY", status: "active",
    origin: { id: origin, state: "MONITORED", name: "Système d’origine" },
    destination: { id: near, state: "DETECTED" }, hops: 1, stacks: { probe: 1 },
    cargo: amounts(0, 0, 0), cost: amounts(0, 4, 20), started_at: at,
    travel_arrival_at: "2099-01-01T00:10:00Z", due_at: "2099-01-01T00:25:00Z",
    recalled_at: null, return_at: null, completed_at: null, payer_colony_id: colony, report: null,
  };
}

export function fleets(missions: MissionView[] = [surveying()], permissions?: string[]): FleetProjection {
  return {
    server_time: session.server_time,
    empire: { id: empire, name: "Empire test" },
    permissions: permissions ?? ["colony.read", "galaxy.read", "fleet.read", "fleet.build", "fleet.command"],
    available: true,
    catalogue: {
      probe: { name: "Sonde", cost: amounts(80, 40, 40), build_us: String(1200e6), hop_seconds: 600, flux_per_hop: 4, cargo: "0", survey: true },
      freighter: { name: "Cargo léger", cost: amounts(200, 60, 20), build_us: String(2400e6), hop_seconds: 1200, flux_per_hop: 8, cargo: String(500e6), survey: false },
    },
    queue_limit: 3,
    max_quantity: 20,
    colonies: [{
      id: colony, name: "Nouvelle Aube", system_id: origin,
      orders: [{
        id: order, ship_class: "probe", quantity: 2, status: "active", accepted_at: session.server_time,
        started_at: session.server_time, due_at: "2099-01-01T00:40:00Z", cost: amounts(160, 80, 80),
        cancel: { theoretical: amounts(128, 64, 64), recoverable: amounts(100, 64, 64), lost: amounts(28, 0, 0) },
      }],
    }],
    fleets: [
      {
        id: garrison, name: "Garnison Nouvelle Aube", kind: "GARRISON", status: "STATIONED", home_colony_id: colony,
        system: { id: origin, state: "MONITORED", name: "Système d’origine" }, stacks: { probe: 2, freighter: 1 },
        cargo: amounts(300, 0, 0), capacity: String(500e6), mission_id: null, colony_here: colony,
        unload: { credited: amounts(100, 0, 0), kept: amounts(200, 0, 0) },
      },
      {
        id: task, name: "Flotte 2", kind: "TASK", status: "MOVING", home_colony_id: colony, system: null,
        stacks: { probe: 1 }, cargo: amounts(0, 0, 0), capacity: "0", mission_id: mission, colony_here: null, unload: null,
      },
    ],
    missions: [...missions, {
      ...surveying("2098-12-31T22:00:00Z"), id: done, status: "completed", kind: "DEPLOY",
      destination: { id: origin, state: "MONITORED", name: "Système d’origine" },
      travel_arrival_at: "2098-12-31T22:20:00Z", due_at: "2098-12-31T22:20:00Z", completed_at: "2098-12-31T22:20:00Z",
      report: { observed_at: "2098-12-31T22:20:00Z", processed_at: "2098-12-31T22:20:01Z", result: { kind: "DEPLOY" } },
    }],
    systems: [
      { id: origin, state: "MONITORED", name: "Système d’origine" },
      { id: near, state: "DETECTED" },
    ],
  };
}

/** A second readable Empire without colony.read: its own garrison only, nothing from Empire A. */
export function otherFleets(): FleetProjection {
  const p = fleets([], ["galaxy.read", "fleet.read", "fleet.build", "fleet.command"]);
  return {
    ...p, empire: { id: otherEmpire, name: "Empire B" }, colonies: [], missions: [],
    fleets: [{ ...p.fleets![0], name: "Garnison Bastion B", home_colony_id: null, colony_here: null, unload: null, cargo: amounts(0, 0, 0) }],
  };
}
