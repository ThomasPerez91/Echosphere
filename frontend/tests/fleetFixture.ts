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
    recalled_at: null, return_at: null, completed_at: null, payer_colony_id: colony, target_planet: null, report: null,
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
        cargo: amounts(300, 0, 0), capacity: String(500e6), mission_id: null,
        colonies_here: [{ id: colony, name: "Nouvelle Aube", unload: { credited: amounts(100, 0, 0), kept: amounts(200, 0, 0) } }],
      },
      {
        id: task, name: "Flotte 2", kind: "TASK", status: "MOVING", home_colony_id: colony, system: null,
        stacks: { probe: 1 }, cargo: amounts(0, 0, 0), capacity: "0", mission_id: mission, colonies_here: [],
      },
    ],
    missions: [...missions, {
      ...surveying("2098-12-31T22:00:00Z"), id: done, status: "completed", kind: "DEPLOY",
      destination: { id: origin, state: "MONITORED", name: "Système d’origine" },
      travel_arrival_at: "2098-12-31T22:20:00Z", due_at: "2098-12-31T22:20:00Z", completed_at: "2098-12-31T22:20:00Z",
      report: { observed_at: "2098-12-31T22:20:00Z", processed_at: "2098-12-31T22:20:01Z", result: { kind: "DEPLOY" } },
    }],
    colonization: null,
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
    fleets: [{ ...p.fleets![0], name: "Garnison Bastion B", home_colony_id: null, colonies_here: [], cargo: amounts(0, 0, 0) }],
  };
}

export const freeWorld = "cccccccc-0000-4000-8000-000000000001";
export const ownWorld = "cccccccc-0000-4000-8000-000000000002";
export const secondColony = "cccccccc-0000-4000-8000-000000000003";
/** v0.5 projection: a colonizer in the garrison, two known worlds of the home system. */
export function colonizing(permissions?: string[]): FleetProjection {
  const p = fleets([], permissions ?? ["colony.read", "galaxy.read", "fleet.read", "fleet.build", "fleet.command", "colony.expand"]);
  const colonyRead = p.permissions.includes("colony.read");
  return {
    ...p,
    colonies: colonyRead ? p.colonies : [],
    catalogue: { ...p.catalogue, colonizer: { name: "Colonisateur", cost: amounts(1200, 600, 300), build_us: String(10800e6), hop_seconds: 1800, flux_per_hop: 20, cargo: String(1000e6), survey: false } },
    fleets: [{ ...p.fleets![0], stacks: { colonizer: 1 }, capacity: String(1000e6), cargo: amounts(600, 300, 100),
      home_colony_id: colonyRead ? p.fleets![0].home_colony_id : null,
      colonies_here: colonyRead ? [
        { id: colony, name: "Nouvelle Aube", unload: { credited: amounts(600, 300, 100), kept: amounts(0, 0, 0) } },
        { id: secondColony, name: "Seconde Aube", unload: { credited: amounts(500, 300, 100), kept: amounts(100, 0, 0) } },
      ] : [] }],
    missions: [],
    colonization: { colonizer_class: "colonizer", package_minimum: amounts(500, 250, 50), max_colonies: 12, max_active_missions: 1,
      colonizer_quote: colonyRead ? { rank: 3, multiplier_bps: 20000, cost: amounts(2400, 1200, 600) } : null },
    systems: [
      { id: origin, state: "MONITORED", name: "Système d’origine", planets: [
        { id: ownWorld, name: "Nouvelle Aube", sector_capacity: 12, orbital_capacity: 2, colony_id: colonyRead ? colony : null },
        { id: freeWorld, name: "Monde libre ?", sector_capacity: 9, orbital_capacity: 1, colony_id: null },
      ] },
      { id: near, state: "DETECTED" },
    ],
  };
}

export const rivalWorld = "dddddddd-0000-4000-8000-000000000001";
export const engagement = "dddddddd-0000-4000-8000-000000000002";
export const attacking = "dddddddd-0000-4000-8000-000000000003";
export const COMBAT_RIGHTS = ["colony.read", "galaxy.read", "fleet.read", "fleet.build", "fleet.command", "combat.read", "combat.attack"];
/** v0.7 projection: military classes in the garrison, a known foreign-candidate world, an attack in approach. */
export function fighting(permissions: string[] = COMBAT_RIGHTS): FleetProjection {
  const p = fleets([], permissions);
  const readable = permissions.includes("combat.read");
  const attack: MissionView = {
    ...surveying("2098-12-31T12:00:00Z"), id: attacking, kind: "ATTACK", fleet_id: task,
    destination: { id: near, state: "MAPPED", name: "Système voisin" }, stacks: { frigate: 2 },
    travel_arrival_at: "2098-12-31T12:18:00Z", due_at: "2099-01-01T12:00:00Z", cost: amounts(0, 48, 0),
    target_planet: { id: rivalWorld, name: "Monde rival" },
    attack: { engagement_id: engagement, battle_at: "2099-01-01T12:00:00Z", state: "pending" },
  };
  return {
    ...p,
    catalogue: {
      ...p.catalogue,
      interceptor: { name: "Intercepteur", cost: amounts(180, 90, 30), build_us: String(1800e6), hop_seconds: 720, flux_per_hop: 6, cargo: "0", survey: false },
      frigate: { name: "Frégate", cost: amounts(450, 200, 80), build_us: String(3600e6), hop_seconds: 1080, flux_per_hop: 12, cargo: "0", survey: false },
      cruiser: { name: "Croiseur", cost: amounts(1000, 450, 180), build_us: String(7200e6), hop_seconds: 1500, flux_per_hop: 25, cargo: "0", survey: false },
    },
    fleets: [
      { ...p.fleets![0], stacks: { interceptor: 3, probe: 1 } },
      { ...p.fleets![1], stacks: { frigate: 2 }, mission_id: attacking },
    ],
    missions: [attack],
    combat: {
      classes: ["interceptor", "frigate", "cruiser"], min_warning_seconds: 86400,
      alerts: readable ? [{ id: engagement, planet_id: rivalWorld, system_id: near, battle_at: "2099-01-02T00:00:00Z", state: "pending" }] : null,
      reports: readable ? [{
        engagement_id: done, role: "defender", battle_at: "2098-12-31T00:00:00Z", processed_at: "2098-12-31T00:00:05Z",
        outcome: "defender_win", target: { planet_id: rivalWorld, system_id: near }, opponent_empire_id: otherEmpire,
        own: { initial: { interceptor: 3 }, losses: { interceptor: 1 }, survivors: { interceptor: 2 } },
        opponent: { initial: { cruiser: 1 }, losses: { cruiser: 1 }, survivors: { cruiser: 0 } },
        rounds: [{}, {}],
      }] : null,
    },
    systems: [
      { id: origin, state: "MONITORED", name: "Système d’origine" },
      { id: near, state: "MAPPED", name: "Système voisin", planets: [
        { id: rivalWorld, name: "Monde rival", sector_capacity: 12, orbital_capacity: 2, colony_id: null },
      ] },
    ],
  };
}
