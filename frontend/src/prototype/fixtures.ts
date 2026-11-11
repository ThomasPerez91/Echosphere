/**
 * UX03 PROTOTYPE FIXTURES — never imported by the production app (src/main.tsx).
 *
 * Shapes are the real Game API types (galaxy and fleet projections, mission preview), so the
 * TypeScript build proves the prototype stays contract-compatible. Values are illustrative
 * placeholders written by hand for one Empire: they are not computed by any game rule, and they
 * contain only what the server would send to this Empire (Fog of War: DETECTED systems carry no
 * name nor structure, no foreign fleet is listed, no hidden route is present).
 */
import type { Projection as GalaxyProjection } from "../galaxy/api";
import type { FleetProjection, MissionKind } from "../fleet/api";
import type { CommandQuote } from "../command/types";

export const SERVER_TIME = "2099-01-01T12:00:00Z";
const EMPIRE = { id: "10000000-0000-4000-8000-000000000001", name: "Concorde d’Aube" };
const zero = { alloys: "0", flux: "0", data: "0" };
const M = (n: number) => String(n * 1_000_000);

// Systems (ids are readable on purpose: s-<n>). Coordinates are Knowledge positions.
export const ids = {
  home: "20000000-0000-4000-8000-000000000001",
  vesta: "20000000-0000-4000-8000-000000000002",
  orion: "20000000-0000-4000-8000-000000000003",
  lyra: "20000000-0000-4000-8000-000000000004",
  cygne: "20000000-0000-4000-8000-000000000005",
  draco: "20000000-0000-4000-8000-000000000006",
  signalA: "20000000-0000-4000-8000-000000000007",
  signalB: "20000000-0000-4000-8000-000000000008",
  signalC: "20000000-0000-4000-8000-000000000009",
  colony: "30000000-0000-4000-8000-000000000001",
  planetHome: "40000000-0000-4000-8000-000000000001",
  planetVesta: "40000000-0000-4000-8000-000000000002",
  planetOrion: "40000000-0000-4000-8000-000000000003",
  planetLyra: "40000000-0000-4000-8000-000000000004",
  planetCygne: "40000000-0000-4000-8000-000000000005",
  garrison: "50000000-0000-4000-8000-000000000001",
  escadre: "50000000-0000-4000-8000-000000000002",
  kepler: "50000000-0000-4000-8000-000000000003",
  pionnier: "50000000-0000-4000-8000-000000000004",
  scout: "50000000-0000-4000-8000-000000000005",
  surveyMission: "60000000-0000-4000-8000-000000000001",
} as const;

const planet = (id: string, name: string, sectors: number, orbital: number, colony: string | null = null) =>
  ({ id, name, sector_capacity: sectors, orbital_capacity: orbital, colony_id: colony });

export function galaxyFixture(): GalaxyProjection {
  const mapped = (id: string, name: string, x: number, y: number, planets: ReturnType<typeof planet>[]) => ({
    id, state: "MAPPED" as const, x, y, discovered_at: "2098-12-30T08:00:00Z", name,
    mapped_at: "2098-12-30T10:00:00Z", last_seen_at: null, observation: null,
    // Galaxy Knowledge carries planet structure only (no colony link): same as the real API.
    planets: planets.map((p) => ({ id: p.id, name: p.name, sector_capacity: p.sector_capacity, orbital_capacity: p.orbital_capacity })),
  });
  const detected = (id: string, x: number, y: number) => ({ id, state: "DETECTED" as const, x, y, discovered_at: "2098-12-31T08:00:00Z" });
  return {
    server_time: SERVER_TIME,
    exploration: "fleet-survey-v1",
    empire: EMPIRE,
    permissions: ["galaxy.read", "fleet.read", "fleet.command", "colony.read", "colony.expand", "combat.read", "combat.attack"],
    systems: [
      { ...mapped(ids.home, "Aube", 0, 0, [planet(ids.planetHome, "Aube Prime", 12, 2, ids.colony)]),
        state: "MONITORED", last_seen_at: SERVER_TIME, observation: { own_colony_ids: [ids.colony] } },
      { ...mapped(ids.vesta, "Vesta", 120, -60, [planet(ids.planetVesta, "Vesta II", 10, 2)]),
        // EXP-01 (v0.10): one prospected deposit, one signature still unexplained.
        opportunities: { signatures: 1, known: [{ id: "80000000-0000-4000-8000-000000000001", family: "deposit" as const,
          kind: "metal_belt", tier: "common" as const, observed_at: "2098-12-31T09:00:00Z", resource: "alloys" as const,
          reserve: "4200000000", throughput_per_hour: "90000000" },
          { id: "80000000-0000-4000-8000-000000000002", family: "curiosity" as const, kind: "anomaly",
            tier: "common" as const, observed_at: "2098-12-31T09:00:00Z", study_seconds: 600, data: "300000000",
            studied: false }] } },
      mapped(ids.orion, "Orion", 80, 110, [planet(ids.planetOrion, "Orion Rift", 9, 1)]),
      mapped(ids.lyra, "Lyra", 240, -20, [planet(ids.planetLyra, "Lyra Bastion", 11, 2)]),
      mapped(ids.cygne, "Cygne", 210, 120, [planet(ids.planetCygne, "Cygne Halo", 8, 1)]),
      mapped(ids.draco, "Draco", -110, 70, []),
      detected(ids.signalA, 350, 40),
      detected(ids.signalB, -150, -90),
      detected(ids.signalC, 320, 190),
    ],
    routes: [
      { id: "70000000-0000-4000-8000-000000000001", a_id: ids.home, b_id: ids.vesta },
      { id: "70000000-0000-4000-8000-000000000002", a_id: ids.home, b_id: ids.orion },
      { id: "70000000-0000-4000-8000-000000000003", a_id: ids.vesta, b_id: ids.lyra },
      { id: "70000000-0000-4000-8000-000000000004", a_id: ids.orion, b_id: ids.cygne },
      { id: "70000000-0000-4000-8000-000000000005", a_id: ids.home, b_id: ids.draco },
      { id: "70000000-0000-4000-8000-000000000006", a_id: ids.lyra, b_id: ids.signalA },
      { id: "70000000-0000-4000-8000-000000000007", a_id: ids.draco, b_id: ids.signalB },
      { id: "70000000-0000-4000-8000-000000000008", a_id: ids.cygne, b_id: ids.signalC },
      { id: "70000000-0000-4000-8000-000000000009", a_id: ids.lyra, b_id: ids.cygne },
    ],
    sources: [],
    options: [],
    missions: [],
  };
}

const ref = (id: string) => {
  const s = galaxyFixture().systems.find((x) => x.id === id)!;
  return s.state === "DETECTED" ? { id, state: s.state } : {
    id, state: s.state, name: s.name,
    planets: (s.planets ?? []).map((p) => ({ ...p, colony_id: p.id === ids.planetHome ? ids.colony : null })),
  };
};

const fleet = (id: string, name: string, kind: "GARRISON" | "TASK", system: string | null, stacks: Record<string, number>,
  extra: Partial<NonNullable<FleetProjection["fleets"]>[number]> = {}) => ({
  id, name, kind, status: system ? "STATIONED" as const : "MOVING" as const, home_colony_id: ids.colony,
  system: system ? ref(system) : null, stacks, cargo: zero, capacity: "0", mission_id: null, colonies_here: [], protocol: null, ...extra,
});

const ship = (name: string, survey = false, cargo = "0") =>
  ({ name, cost: zero, build_us: "0", hop_seconds: 0, flux_per_hop: 0, cargo, survey });

export function fleetFixture(): FleetProjection {
  return {
    server_time: SERVER_TIME,
    empire: EMPIRE,
    permissions: ["fleet.read", "fleet.build", "fleet.command", "colony.read", "colony.expand", "galaxy.read", "combat.read", "combat.attack"],
    available: true,
    catalogue: {
      probe: ship("Sonde", true), freighter: ship("Cargo léger", false, M(500)), colonizer: ship("Colonisateur", false, M(300)),
      interceptor: ship("Intercepteur"), frigate: ship("Frégate"), cruiser: ship("Croiseur"),
    },
    queue_limit: 3,
    max_quantity: 10,
    colonies: [{ id: ids.colony, name: "Aube Prime", system_id: ids.home, orders: [] }],
    fleets: [
      fleet(ids.garrison, "Garnison Aube Prime", "GARRISON", ids.home, { interceptor: 3, probe: 1 }),
      fleet(ids.escadre, "Escadre Héliade", "TASK", ids.home, { frigate: 2, interceptor: 2 }),
      fleet(ids.pionnier, "Pionnier", "TASK", ids.home, { colonizer: 1 }, {
        cargo: { alloys: M(300), flux: M(200), data: M(100) }, capacity: M(300) }),
      fleet(ids.kepler, "Sonde Kepler", "TASK", ids.vesta, { probe: 1 }),
      fleet(ids.scout, "Éclaireur Draco", "TASK", null, { probe: 1 }, { mission_id: ids.surveyMission }),
    ],
    missions: [{
      id: ids.surveyMission, fleet_id: ids.scout, kind: "SURVEY", status: "active",
      origin: ref(ids.draco), destination: ref(ids.signalB), hops: 1, path: [ids.draco, ids.signalB], stacks: { probe: 1 }, cargo: zero,
      cost: { alloys: "0", flux: M(4), data: M(20) },
      started_at: "2099-01-01T11:40:00Z", travel_arrival_at: "2099-01-01T12:20:00Z", due_at: "2099-01-01T12:35:00Z",
      recalled_at: null, return_at: null, completed_at: null, payer_colony_id: ids.colony, target_planet: null, report: null,
    }],
    colonization: { colonizer_class: "colonizer", package_minimum: { alloys: M(200), flux: M(150), data: M(50) },
      max_colonies: 4, max_active_missions: 1, colonizer_quote: null },
    combat: { classes: ["interceptor", "frigate", "cruiser"], min_warning_seconds: 86400, alerts: [], reports: [] },
    frontier: null,
    systems: [ids.home, ids.vesta, ids.orion, ids.lyra, ids.cygne, ids.draco, ids.signalA, ids.signalB, ids.signalC].map(ref),
  };
}

/**
 * Hand-written preview answers (what `POST …/missions/preview` would return), keyed by the
 * destination. `path` is NOT part of today's Quote contract: it is the API extension proposed
 * by UX-API-01 (the server already computes this path on the Empire's known routes). The
 * prototype draws it only in the "extension proposée" mode, never in the "contrat actuel" mode.
 */
const table: Record<string, { hops: number; travel_min: number; flux: number; path: string[] }> = {
  [ids.vesta]: { hops: 1, travel_min: 18, flux: 6, path: [ids.home, ids.vesta] },
  [ids.orion]: { hops: 1, travel_min: 18, flux: 6, path: [ids.home, ids.orion] },
  [ids.draco]: { hops: 1, travel_min: 18, flux: 6, path: [ids.home, ids.draco] },
  [ids.lyra]: { hops: 2, travel_min: 36, flux: 12, path: [ids.home, ids.vesta, ids.lyra] },
  [ids.cygne]: { hops: 2, travel_min: 36, flux: 12, path: [ids.home, ids.orion, ids.cygne] },
  [ids.signalA]: { hops: 3, travel_min: 54, flux: 18, path: [ids.home, ids.vesta, ids.lyra, ids.signalA] },
  [ids.signalB]: { hops: 2, travel_min: 36, flux: 12, path: [ids.home, ids.draco, ids.signalB] },
  [ids.signalC]: { hops: 3, travel_min: 54, flux: 18, path: [ids.home, ids.orion, ids.cygne, ids.signalC] },
};
const fromVesta: typeof table = {
  [ids.lyra]: { hops: 1, travel_min: 10, flux: 2, path: [ids.vesta, ids.lyra] },
  [ids.signalA]: { hops: 2, travel_min: 20, flux: 4, path: [ids.vesta, ids.lyra, ids.signalA] },
  [ids.home]: { hops: 1, travel_min: 10, flux: 2, path: [ids.vesta, ids.home] },
  [ids.signalB]: { hops: 3, travel_min: 30, flux: 6, path: [ids.vesta, ids.home, ids.draco, ids.signalB] },
  [ids.signalC]: { hops: 4, travel_min: 40, flux: 8, path: [ids.vesta, ids.lyra, ids.cygne, ids.signalC] },
};

export type FixtureQuote = CommandQuote;

export function quoteFixture(from: string, kind: MissionKind, destination: string, units: Record<string, number>,
  planet: string | null, at: string): FixtureQuote | { error: string } {
  const row = (from === ids.vesta ? fromVesta : table)[destination];
  if (!row) return { error: "destination_unreachable" };
  const start = Date.parse(at);
  const arrival = new Date(start + row.travel_min * 60_000).toISOString();
  const attack = kind === "ATTACK";
  return {
    kind, destination_id: destination, hops: row.hops,
    cost: { alloys: "0", flux: M(row.flux * (attack ? 2 : 1)), data: kind === "SURVEY" ? M(20) : "0" },
    travel_us: String(row.travel_min * 60_000_000), survey_us: kind === "SURVEY" ? String(15 * 60_000_000) : "0",
    travel_arrival_at: arrival,
    due_at: kind === "SURVEY" ? new Date(start + (row.travel_min + 15) * 60_000).toISOString() : arrival,
    payer_colony_id: ids.colony, affordable: true, target_planet_id: planet,
    package_minimum: kind === "COLONIZE" ? { alloys: M(200), flux: M(150), data: M(50) } : null,
    ...(attack ? { battle_at: new Date(start + 86_400_000).toISOString(), units } : {}),
    path: row.path,
  };
}
