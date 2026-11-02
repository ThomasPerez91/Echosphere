import { ApiError } from "../colony/api";
import type { Amounts } from "../colony/api";
export { ApiError };

export type Empire = { id: string; name: string };
/** Knowledge structure only; `colony_id` names an own Colony and requires colony.read. */
export type KnownPlanet = { id: string; name: string; sector_capacity: number; orbital_capacity: number; colony_id: string | null };
export type SystemRef = { id: string; state: "DETECTED" | "MAPPED" | "MONITORED"; name?: string; planets?: KnownPlanet[] };
export type ShipClass = {
  name: string;
  cost: Amounts;
  build_us: string;
  hop_seconds: number;
  flux_per_hop: number;
  cargo: string;
  survey: boolean;
};
export type ShipOrder = {
  id: string;
  ship_class: string;
  quantity: number;
  status: "queued" | "active";
  accepted_at: string;
  started_at: string | null;
  due_at: string | null;
  cost: Amounts;
  cancel: { theoretical: Amounts; recoverable: Amounts; lost: Amounts } | null;
};
export type ColonyView = { id: string; name: string; system_id: string; orders: ShipOrder[] };
export type FleetView = {
  id: string;
  name: string;
  kind: "GARRISON" | "TASK";
  status: "STATIONED" | "MOVING";
  home_colony_id: string | null;
  system: SystemRef | null;
  stacks: Record<string, number>;
  cargo: Amounts;
  capacity: string;
  mission_id: string | null;
  /** Every own Colony of this system (colony.read only): load/unload always name one. */
  colonies_here: { id: string; name: string; unload: { credited: Amounts; kept: Amounts } | null }[];
  /** 13B (v0.9): first-contact protocol of a stationed task Fleet; absent before v0.9. */
  protocol?: Protocol | null;
};
export type Protocol = "SURVEILLANCE" | "AMBUSH" | "INTERCEPTION" | "FRIENDLY_CONTACT";
/** One side of a detection: system, instant, anonymous signature; the Empire only if identified. */
export type FrontierDetection = {
  id: string; system: SystemRef | null; detected_at: string; role: "watch" | "transit"; friendly: boolean; empire: Empire | null;
};
export type FrontierEngagement = {
  id: string; kind: "engagement"; at: string; system: SystemRef | null; role: "watcher" | "mover"; protocol: Protocol | null;
  outcome: string; opponent: Empire; own: CombatSide; opponent_forces: CombatSide; destroyed: boolean; rounds: number;
};
export type FrontierRetreat = {
  id: string; kind: "retreat"; at: string; system: SystemRef | null;
  outcome: "retreated" | "retreat_failed" | "retreat_impossible" | "void"; reason: string | null; destination: SystemRef | null;
};
export type Frontier = { protocols: Protocol[]; detections: FrontierDetection[]; encounters: (FrontierEngagement | FrontierRetreat)[] };
export type MissionKind = "DEPLOY" | "SURVEY" | "RETURN" | "COLONIZE" | "ATTACK";
/** Own engagement only: battle instant and state; the defender is never projected. */
export type AttackState = { engagement_id: string; battle_at: string; state: "pending" | "resolved" | "cancelled" };
export type MissionView = {
  id: string;
  fleet_id: string;
  kind: MissionKind;
  status: "active" | "returning" | "completed";
  origin: SystemRef | null;
  destination: SystemRef | null;
  hops: number;
  stacks: Record<string, number>;
  cargo: Amounts;
  cost: Amounts;
  started_at: string;
  travel_arrival_at: string;
  due_at: string;
  recalled_at: string | null;
  return_at: string | null;
  completed_at: string | null;
  payer_colony_id: string | null;
  target_planet: { id: string; name: string } | null;
  attack?: AttackState | null;
  report: { observed_at: string; processed_at: string; result: { kind: string; outcome?: string; reason?: string; colony_id?: string | null; destroyed?: boolean } } | null;
};
/** Defender view before a battle: target and instant only, never the attacker or its force. */
export type CombatAlert = { id: string; planet_id: string; system_id: string; battle_at: string; state: "pending" | "cancelled" };
export type CombatSide = { initial: Record<string, number>; losses: Record<string, number>; survivors: Record<string, number> };
export type CombatOutcome = "attacker_win" | "defender_win" | "mutual_destruction" | "unopposed" | "target_unavailable" | "voided_by_pact";
/** Dated observation written by the resolution; military compositions only. */
export type CombatReport = {
  engagement_id: string; role: "attacker" | "defender"; battle_at: string; processed_at: string; outcome: CombatOutcome;
  target: { planet_id: string; system_id: string };
  opponent_empire_id?: string; own?: CombatSide; opponent?: CombatSide; rounds?: unknown[];
  /** v0.8: the pact that voided the battle (no composition is ever reported then). */
  pact_id?: string;
};
export type Combat = { classes: string[]; min_warning_seconds: number; alerts: CombatAlert[] | null; reports: CombatReport[] | null };
export type Colonization = {
  colonizer_class: string;
  package_minimum: Amounts;
  max_colonies: number;
  max_active_missions: number;
  colonizer_quote: { rank: number; multiplier_bps: number; cost: Amounts } | null;
};
export type FleetProjection = {
  server_time: string;
  empire: Empire;
  permissions: string[];
  available: boolean;
  catalogue?: Record<string, ShipClass>;
  queue_limit?: number;
  max_quantity?: number;
  colonies?: ColonyView[];
  fleets?: FleetView[];
  missions?: MissionView[];
  colonization?: Colonization | null;
  combat?: Combat | null;
  frontier?: Frontier | null;
  systems?: SystemRef[];
};
export type Quote = {
  kind: MissionKind;
  destination_id: string;
  hops: number;
  cost: Amounts;
  travel_us: string;
  survey_us: string;
  travel_arrival_at: string;
  due_at: string;
  payer_colony_id: string | null;
  affordable: boolean;
  target_planet_id: string | null;
  package_minimum: Amounts | null;
  battle_at?: string;
  units?: Record<string, number>;
};

type Value = Record<string, unknown>;
const object = (v: unknown): v is Value => !!v && typeof v === "object" && !Array.isArray(v);
const id = (v: unknown): v is string =>
  typeof v === "string" && /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(v);
const date = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const optionalDate = (v: unknown) => v === null || date(v);
const integer = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v);
const micro = (v: unknown) => typeof v === "string" && /^\d{1,20}$/.test(v);
const amounts = (v: unknown) => object(v) && ["alloys", "flux", "data"].every((k) => micro(v[k]));
const list = (v: unknown, item: (x: unknown) => boolean) => Array.isArray(v) && v.every(item);
const counts = (v: unknown) => object(v) && Object.values(v).every((n) => integer(n) && n > 0);
// A DETECTED signal never carries a name: that would be a fog leak, refused instead of hidden.
const systemRef = (v: unknown) =>
  object(v) && id(v.id) &&
  (v.state === "DETECTED" ? !("name" in v) : ["MAPPED", "MONITORED"].includes(String(v.state)) && typeof v.name === "string");
const nullableRef = (v: unknown) => v === null || systemRef(v);
const planet = (v: unknown) =>
  object(v) && id(v.id) && typeof v.name === "string" && integer(v.sector_capacity) && integer(v.orbital_capacity) &&
  (v.colony_id === null || id(v.colony_id));
// Planets belong to MAPPED+ structure only; a DETECTED signal never carries them.
const knownSystem = (v: unknown) =>
  systemRef(v) && (!("planets" in (v as Value)) || ((v as Value).state !== "DETECTED" && list((v as Value).planets, planet)));

const order = (v: unknown) =>
  object(v) && id(v.id) && typeof v.ship_class === "string" && integer(v.quantity) &&
  ["queued", "active"].includes(String(v.status)) && date(v.accepted_at) &&
  optionalDate(v.started_at) && optionalDate(v.due_at) && amounts(v.cost) &&
  (v.cancel === null || (object(v.cancel) && ["theoretical", "recoverable", "lost"].every((k) => amounts((v.cancel as Value)[k]))));
const fleet = (v: unknown) =>
  object(v) && id(v.id) && typeof v.name === "string" && ["GARRISON", "TASK"].includes(String(v.kind)) &&
  ["STATIONED", "MOVING"].includes(String(v.status)) && (v.home_colony_id === null || id(v.home_colony_id)) &&
  (v.status === "STATIONED" ? systemRef(v.system) : v.system === null) && counts(v.stacks) &&
  amounts(v.cargo) && micro(v.capacity) && (v.mission_id === null || id(v.mission_id)) &&
  list(v.colonies_here, (c) => object(c) && id(c.id) && typeof c.name === "string" &&
    (c.unload === null || (object(c.unload) && amounts(c.unload.credited) && amounts(c.unload.kept))));
const exactKeys = (v: Value, keys: string[]) => Object.keys(v).sort().join() === [...keys].sort().join();
const attackState = (v: unknown) =>
  object(v) && exactKeys(v, ["engagement_id", "battle_at", "state"]) && id(v.engagement_id) && date(v.battle_at) &&
  ["pending", "resolved", "cancelled"].includes(String(v.state));
const mission = (v: unknown) =>
  object(v) && id(v.id) && id(v.fleet_id) && ["DEPLOY", "SURVEY", "RETURN", "COLONIZE", "ATTACK"].includes(String(v.kind)) &&
  (["COLONIZE", "ATTACK"].includes(String(v.kind)) ? object(v.target_planet) && id(v.target_planet.id) && typeof v.target_planet.name === "string" : v.target_planet === null) &&
  (v.kind === "ATTACK" ? attackState(v.attack) : v.attack === null || v.attack === undefined) &&
  ["active", "returning", "completed"].includes(String(v.status)) && nullableRef(v.origin) &&
  nullableRef(v.destination) && integer(v.hops) && counts(v.stacks) && amounts(v.cargo) && amounts(v.cost) &&
  date(v.started_at) && date(v.travel_arrival_at) && date(v.due_at) && optionalDate(v.recalled_at) &&
  optionalDate(v.return_at) && optionalDate(v.completed_at) &&
  (v.payer_colony_id === null || id(v.payer_colony_id)) &&
  (v.report === null || (object(v.report) && date(v.report.observed_at) && date(v.report.processed_at) && object(v.report.result)));

const tally = (v: unknown) => object(v) && Object.values(v).every((n) => integer(n) && n >= 0);
const side = (v: unknown) => object(v) && tally(v.initial) && tally(v.losses) && tally(v.survivors);
// An alert carrying anything beyond target, instant and state would leak the attacker: refused.
const alert = (v: unknown) =>
  object(v) && exactKeys(v, ["id", "planet_id", "system_id", "battle_at", "state"]) && id(v.id) && id(v.planet_id) &&
  id(v.system_id) && date(v.battle_at) && ["pending", "cancelled"].includes(String(v.state));
const OUTCOMES = ["attacker_win", "defender_win", "mutual_destruction", "unopposed", "target_unavailable", "voided_by_pact"];
const combatReport = (v: unknown) =>
  object(v) && id(v.engagement_id) && ["attacker", "defender"].includes(String(v.role)) && date(v.battle_at) &&
  date(v.processed_at) && OUTCOMES.includes(String(v.outcome)) && object(v.target) && id(v.target.planet_id) &&
  id(v.target.system_id) &&
  (v.outcome === "target_unavailable" ? !("opponent_empire_id" in v) && !("opponent" in v)
    // A battle voided by a pact never carries a composition: refused rather than hidden.
    : v.outcome === "voided_by_pact" ? id(v.opponent_empire_id) && id(v.pact_id) && !("own" in v) && !("opponent" in v) && !("rounds" in v)
    : id(v.opponent_empire_id) && side(v.own) && side(v.opponent) && Array.isArray(v.rounds));
const combat = (v: unknown, readable: boolean) =>
  v === null || v === undefined || (object(v) && list(v.classes, (c) => typeof c === "string") &&
    integer(v.min_warning_seconds) &&
    (readable ? list(v.alerts, alert) && list(v.reports, combatReport) : v.alerts === null && v.reports === null));

const PROTOCOLS = ["SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"];
const empireRef = (v: unknown) => object(v) && exactKeys(v, ["id", "name"]) && id(v.id) && (v.name === null || typeof v.name === "string");
// D3: a detection carries system, instant and an anonymous signature only. Any composition,
// origin, destination, route or direction is a leak, refused rather than hidden.
const detection = (v: unknown) =>
  object(v) && exactKeys(v, ["id", "system", "detected_at", "role", "friendly", "empire"]) && id(v.id) && nullableRef(v.system) &&
  date(v.detected_at) && ["watch", "transit"].includes(String(v.role)) && typeof v.friendly === "boolean" &&
  (v.empire === null || empireRef(v.empire));
const encounter = (v: unknown) => {
  if (!object(v) || !id(v.id) || !date(v.at) || !nullableRef(v.system)) return false;
  if (v.kind === "retreat")
    return exactKeys(v, ["id", "kind", "at", "system", "outcome", "reason", "destination"]) &&
      ["retreated", "retreat_failed", "retreat_impossible", "void"].includes(String(v.outcome)) &&
      (v.reason === null || typeof v.reason === "string") && nullableRef(v.destination);
  return v.kind === "engagement" &&
    exactKeys(v, ["id", "kind", "at", "system", "role", "protocol", "outcome", "opponent", "own", "opponent_forces", "destroyed", "rounds"]) &&
    ["watcher", "mover"].includes(String(v.role)) && (v.protocol === null || PROTOCOLS.includes(String(v.protocol))) &&
    // The moving side never learns the protocol that stopped it.
    (v.role === "watcher" || v.protocol === null) &&
    typeof v.outcome === "string" && empireRef(v.opponent) && side(v.own) && side(v.opponent_forces) &&
    typeof v.destroyed === "boolean" && Number.isSafeInteger(v.rounds);
};
const frontier = (v: unknown) =>
  v === null || v === undefined || (object(v) && list(v.protocols, (x) => PROTOCOLS.includes(String(x))) &&
    list(v.detections, detection) && list(v.encounters, encounter));

export function validFleets(value: unknown, empire: string): value is FleetProjection {
  if (!object(value) || !date(value.server_time) || !object(value.empire) || value.empire.id !== empire ||
    typeof value.empire.name !== "string" || !list(value.permissions, (p) => typeof p === "string") ||
    typeof value.available !== "boolean")
    return false;
  if (!value.available) return true;
  const v = value as FleetProjection;
  const shapes =
    object(value.catalogue) && Object.values(value.catalogue).every((c) => object(c) && typeof c.name === "string" &&
      amounts(c.cost) && micro(c.build_us) && integer(c.hop_seconds) && integer(c.flux_per_hop) && micro(c.cargo) &&
      typeof c.survey === "boolean") &&
    integer(value.queue_limit) && integer(value.max_quantity) &&
    list(value.colonies, (c) => object(c) && id(c.id) && typeof c.name === "string" && id(c.system_id) && list(c.orders, order)) &&
    list(value.fleets, fleet) && list(value.missions, mission) && list(value.systems, knownSystem) &&
    (value.colonization === null || (object(value.colonization) && typeof value.colonization.colonizer_class === "string" &&
      amounts(value.colonization.package_minimum) && integer(value.colonization.max_colonies) &&
      (value.colonization.colonizer_quote === null || (object(value.colonization.colonizer_quote) &&
        integer(value.colonization.colonizer_quote.rank) && amounts(value.colonization.colonizer_quote.cost)))));
  if (!shapes || !combat(value.combat, v.permissions.includes("combat.read")) || !frontier(value.frontier)) return false;
  // A protocol exists only on a stationed task Fleet, and only where the ruleset has frontiers.
  if (v.fleets!.some((f) => f.protocol !== undefined && f.protocol !== null &&
    (!PROTOCOLS.includes(f.protocol) || f.kind !== "TASK" || f.status !== "STATIONED" || !v.frontier)))
    return false;
  // Colony data belongs to colony.read: present without it is a leak, refused rather than hidden.
  if (!v.permissions.includes("colony.read") && (v.colonies!.length || v.fleets!.some((f) =>
    f.home_colony_id || f.colonies_here.length) || v.missions!.some((m) => m.payer_colony_id || m.report?.result.colony_id) ||
    v.systems!.some((s) => s.planets?.some((p) => p.colony_id)) || v.colonization?.colonizer_quote))
    return false;
  const known = new Set(v.systems!.map((s) => s.id));
  return v.fleets!.every((f) => !f.system || known.has(f.system.id));
}

async function request(url: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { ...init, signal, credentials: "same-origin", cache: "no-store" });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError("invalid_response", response.ok ? 0 : response.status);
  }
  if (!response.ok) {
    const error = body as { error?: { code?: string } };
    throw new ApiError(error.error?.code ?? "unavailable", response.status);
  }
  return body;
}

const bootstrap = { headers: { "X-Game-Request": "bootstrap" } };

export async function listFleetEmpires(universe: string, signal: AbortSignal): Promise<Empire[]> {
  const body = await request(`/api/game/${universe}/fleets`, bootstrap, signal);
  if (!object(body) || !list(body.empires, (e) => object(e) && id(e.id) && typeof e.name === "string"))
    throw new ApiError("invalid_response", 0);
  return body.empires as Empire[];
}

export async function readFleets(universe: string, empire: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/fleets/${empire}`, bootstrap, signal);
  if (!validFleets(body, empire)) throw new ApiError("invalid_response", 0);
  return body;
}

function post(universe: string, empire: string, path: string, csrf: string, body: object, signal: AbortSignal) {
  return request(`/api/game/${universe}/fleets/${empire}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(body),
  }, signal);
}

/** One command; the server answers its result and the fresh projection. */
export async function fleetCommand(universe: string, empire: string, csrf: string, path: string,
  body: object, signal: AbortSignal) {
  const reply = await post(universe, empire, path, csrf, body, signal);
  if (!object(reply) || !object(reply.result) || !validFleets(reply.fleets, empire))
    throw new ApiError("invalid_response", 0);
  return { result: reply.result, fleets: reply.fleets };
}

export type Plan = { fleet_id: string; kind: MissionKind; destination_id?: string; target_planet_id?: string; units: Record<string, number> };

/** Quote of a launch. A paying colony without colony.read is a leak, refused rather than hidden. */
export async function previewMission(universe: string, empire: string, csrf: string, plan: Plan, colonyRead: boolean,
  signal: AbortSignal) {
  const body = await post(universe, empire, "/missions/preview", csrf, plan, signal);
  if (!object(body) || !id(body.destination_id) || !integer(body.hops) || !amounts(body.cost) ||
    !micro(body.travel_us) || !micro(body.survey_us) || !date(body.travel_arrival_at) || !date(body.due_at) ||
    typeof body.affordable !== "boolean" ||
    !(body.payer_colony_id === null || (colonyRead && id(body.payer_colony_id))))
    throw new ApiError("invalid_response", 0);
  return body as Quote;
}
