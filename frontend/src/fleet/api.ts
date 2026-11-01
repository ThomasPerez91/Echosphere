import { ApiError } from "../colony/api";
import type { Amounts } from "../colony/api";
export { ApiError };

export type Empire = { id: string; name: string };
export type SystemRef = { id: string; state: "DETECTED" | "MAPPED" | "MONITORED"; name?: string };
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
  colony_here: string | null;
  unload: { credited: Amounts; kept: Amounts } | null;
};
export type MissionKind = "DEPLOY" | "SURVEY" | "RETURN";
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
  report: { observed_at: string; processed_at: string; result: { kind: string } } | null;
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
  (v.colony_here === null || id(v.colony_here)) &&
  (v.unload === null || (object(v.unload) && amounts(v.unload.credited) && amounts(v.unload.kept)));
const mission = (v: unknown) =>
  object(v) && id(v.id) && id(v.fleet_id) && ["DEPLOY", "SURVEY", "RETURN"].includes(String(v.kind)) &&
  ["active", "returning", "completed"].includes(String(v.status)) && nullableRef(v.origin) &&
  nullableRef(v.destination) && integer(v.hops) && counts(v.stacks) && amounts(v.cargo) && amounts(v.cost) &&
  date(v.started_at) && date(v.travel_arrival_at) && date(v.due_at) && optionalDate(v.recalled_at) &&
  optionalDate(v.return_at) && optionalDate(v.completed_at) &&
  (v.payer_colony_id === null || id(v.payer_colony_id)) &&
  (v.report === null || (object(v.report) && date(v.report.observed_at) && date(v.report.processed_at) && object(v.report.result)));

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
    list(value.fleets, fleet) && list(value.missions, mission) && list(value.systems, systemRef);
  if (!shapes) return false;
  // Colony data belongs to colony.read: present without it is a leak, refused rather than hidden.
  if (!v.permissions.includes("colony.read") && (v.colonies!.length || v.fleets!.some((f) =>
    f.home_colony_id || f.colony_here || f.unload) || v.missions!.some((m) => m.payer_colony_id)))
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

export type Plan = { fleet_id: string; kind: MissionKind; destination_id?: string; units: Record<string, number> };

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
