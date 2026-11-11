import { ApiError } from "../colony/api";
import type { Amounts } from "../colony/api";
import { validLayout } from "./shape";
import type { Layout } from "./shape";
export { ApiError };

export type Empire = { id: string; name: string };
export type KnowledgeState = "DETECTED" | "MAPPED" | "MONITORED";
export type KnownPlanet = {
  id: string;
  name: string;
  sector_capacity: number;
  orbital_capacity: number;
};
/** DETECTED carries only an opaque id and an approximate position; never a name or structure. */
export type KnownSystem = {
  id: string;
  state: KnowledgeState;
  x: number;
  y: number;
  discovered_at: string;
  name?: string;
  mapped_at?: string;
  last_seen_at?: string | null;
  observation?: { own_colony_ids: string[] } | null;
  planets?: KnownPlanet[];
  /** EXP-01 (v0.10): signatures not prospected yet, and the dated details of those that were. */
  opportunities?: { signatures: number; known: KnownOpportunity[] };
};
export type KnownOpportunity = {
  id: string; family: "deposit" | "curiosity"; kind: string; tier: "common" | "remarkable"; observed_at: string;
  resource?: "alloys" | "flux" | "data"; reserve?: string; throughput_per_hour?: string;
  study_seconds?: number; data?: string; dossier?: number; clue?: number;
  /** EXP-02a: this Empire already studied this curiosity (one study per Empire). */
  studied?: boolean;
};
export type Route = { id: string; a_id: string; b_id: string };
export type Report = {
  observed_at: string;
  processed_at: string;
  discoveries: {
    system: KnownSystem;
    neighbors: { id: string; x: number; y: number; new: boolean }[];
    routes: Route[];
    path: string[];
  };
};
export type Mission = {
  id: string;
  destination_id: string;
  colony_id: string | null;
  status: "active" | "completed";
  started_at: string;
  due_at: string;
  cost: Amounts;
  report: Report | null;
};
export type Option = {
  colony_id: string;
  destination_id: string;
  hops: number;
  cost: Amounts;
  duration_us: string;
  reason: string | null;
};
export type Presence = { empire: number; system_id: string; planet_id: string };
/** v0.12 map: a foreign Colony this Empire legitimately knows (own MONITORED system, own attack report). */
export type Relation = "ally" | "neutral" | "hostile" | "unknown";
export type ForeignPresence = { planet_id: string; system_id: string; observed_at: string; source: "monitoring" | "combat";
  relation: Relation; empire?: { id: string; name: string | null } };
export type Projection = {
  server_time: string;
  /** Pinned exploration means: abstract expedition (v0.3) or probe Fleet SURVEY (v0.4+). */
  exploration?: "abstract-expedition-v1" | "fleet-survey-v1";
  empire: Empire;
  permissions: string[];
  systems: KnownSystem[];
  routes: Route[];
  /** Every star of the galaxy as a bare position (decision 09/11/2026): no identity, no route. */
  stars?: [number, number][];
  /** Test game only: every foreign Colony with an anonymous Empire number (never a name). */
  sandbox?: { presences: Presence[] };
  /** Shaped galaxy (v0.12): the density of the backdrop, decorative only. */
  layout?: Layout;
  /** v0.12: known foreign Colonies, classed ally/neutral/hostile (absent before v0.12 or without relations.read). */
  foreign?: ForeignPresence[];
  sources: { id: string; name: string; stocks: Amounts }[];
  options: Option[];
  missions: Mission[];
};

type Value = Record<string, unknown>;
const object = (v: unknown): v is Value => !!v && typeof v === "object" && !Array.isArray(v);
const id = (v: unknown): v is string =>
  typeof v === "string" && /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(v);
const date = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const integer = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v);
const micro = (v: unknown) => typeof v === "string" && /^\d{1,20}$/.test(v);
const amounts = (v: unknown) => object(v) && ["alloys", "flux", "data"].every((k) => micro(v[k]));
const list = (v: unknown, item: (x: unknown) => boolean) => Array.isArray(v) && v.every(item);
const route = (v: unknown) => object(v) && id(v.id) && id(v.a_id) && id(v.b_id);
const STRUCTURE = ["name", "mapped_at", "last_seen_at", "observation", "planets", "opportunities"];
const opportunity = (o: unknown) => object(o) && id(o.id) && typeof o.kind === "string" && date(o.observed_at)
  && (o.tier === "common" || o.tier === "remarkable")
  && (o.family === "deposit"
    ? ["alloys", "flux", "data"].includes(String(o.resource)) && micro(o.reserve) && micro(o.throughput_per_hour) && !("data" in o)
    : o.family === "curiosity" && integer(o.study_seconds) && micro(o.data) && !("reserve" in o)
      && (o.studied === undefined || typeof o.studied === "boolean"));
const opportunities = (v: unknown) => v === undefined
  || (object(v) && integer(v.signatures) && v.signatures >= 0 && list(v.known, opportunity));

export function validKnownSystem(v: unknown): v is KnownSystem {
  if (!object(v) || !id(v.id) || !integer(v.x) || !integer(v.y) || !date(v.discovered_at))
    return false;
  // A DETECTED payload with structure would be a fog leak: refuse it instead of hiding it.
  if (v.state === "DETECTED") return STRUCTURE.every((k) => !(k in v));
  if (v.state !== "MAPPED" && v.state !== "MONITORED") return false;
  return (
    typeof v.name === "string" &&
    opportunities(v.opportunities) &&
    date(v.mapped_at) &&
    (v.last_seen_at === null || date(v.last_seen_at)) &&
    (v.observation === null ||
      (object(v.observation) && list(v.observation.own_colony_ids, id))) &&
    list(
      v.planets,
      (p) =>
        object(p) &&
        id(p.id) &&
        typeof p.name === "string" &&
        integer(p.sector_capacity) &&
        integer(p.orbital_capacity),
    )
  );
}

function report(v: unknown) {
  if (v === null) return true;
  if (!object(v) || !date(v.observed_at) || !date(v.processed_at)) return false;
  const d = v.discoveries;
  return (
    object(d) &&
    validKnownSystem(d.system) &&
    list(d.neighbors, (n) => object(n) && id(n.id) && integer(n.x) && integer(n.y)) &&
    list(d.routes, route) &&
    list(d.path, id)
  );
}

function mission(v: unknown) {
  return (
    object(v) &&
    id(v.id) &&
    id(v.destination_id) &&
    (v.colony_id === null || id(v.colony_id)) &&
    (v.status === "active" || v.status === "completed") &&
    date(v.started_at) &&
    date(v.due_at) &&
    amounts(v.cost) &&
    report(v.report)
  );
}

export function validProjection(value: unknown, empire: string): value is Projection {
  if (
    !object(value) ||
    !date(value.server_time) ||
    !object(value.empire) ||
    value.empire.id !== empire ||
    typeof value.empire.name !== "string" ||
    !list(value.permissions, (p) => typeof p === "string") ||
    !list(value.systems, validKnownSystem) ||
    // Colony identifiers belong to colony.read: refuse them instead of hiding them.
    (!(value.permissions as string[]).includes("colony.read") && (value.systems as KnownSystem[]).some((s) => s.observation)) ||
    !list(value.routes, route) ||
    ("stars" in value && !list(value.stars, (p) => Array.isArray(p) && p.length === 2 && p.every((c) => typeof c === "number" && Number.isFinite(c)))) ||
    ("layout" in value && !validLayout(value.layout)) ||
    ("foreign" in value && !list(value.foreign, (p) => object(p) && id(p.planet_id) && id(p.system_id) && date(p.observed_at)
      && (p.source === "monitoring" || p.source === "combat") && ["ally", "neutral", "hostile", "unknown"].includes(String(p.relation))
      && (p.empire === undefined ? p.relation === "unknown" : object(p.empire) && id(p.empire.id) && (p.empire.name === null || typeof p.empire.name === "string")))) ||
    ("sandbox" in value && !(object(value.sandbox) && list(value.sandbox.presences, (p) => object(p) && integer(p.empire) && id(p.system_id) && id(p.planet_id)))) ||
    !list(value.sources, (s) => object(s) && id(s.id) && typeof s.name === "string" && amounts(s.stocks)) ||
    !list(
      value.options,
      (o) =>
        object(o) &&
        id(o.colony_id) &&
        id(o.destination_id) &&
        integer(o.hops) &&
        o.hops > 0 &&
        amounts(o.cost) &&
        micro(o.duration_us) &&
        (o.reason === null || typeof o.reason === "string"),
    ) ||
    !list(value.missions, mission)
  )
    return false;
  const p = value as Projection;
  const known = new Set(p.systems.map((s) => s.id));
  // Every route and destination must reference a system this projection legitimately shows.
  return (
    known.size === p.systems.length &&
    p.routes.every((r) => known.has(r.a_id) && known.has(r.b_id)) &&
    p.options.every((o) => known.has(o.destination_id)) &&
    p.missions.every((m) => known.has(m.destination_id))
  );
}

async function request(url: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    signal,
    credentials: "same-origin",
    cache: "no-store",
  });
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

export async function listEmpires(universe: string, signal: AbortSignal): Promise<Empire[]> {
  const body = await request(`/api/game/${universe}/galaxy`, bootstrap, signal);
  if (!object(body) || !list(body.empires, (e) => object(e) && id(e.id) && typeof e.name === "string"))
    throw new ApiError("invalid_response", 0);
  return body.empires as Empire[];
}

export async function readGalaxy(universe: string, empire: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/galaxy/${empire}`, bootstrap, signal);
  if (!validProjection(body, empire)) throw new ApiError("invalid_response", 0);
  return body;
}

export type Expedition = { colony_id: string; destination_id: string };

export async function startExpedition(
  universe: string,
  empire: string,
  csrf: string,
  expedition: Expedition,
  key: string,
  signal: AbortSignal,
) {
  const body = await request(
    `/api/game/${universe}/exploration/${empire}/missions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ idempotency_key: key, ...expedition }),
    },
    signal,
  );
  if (!object(body) || !id(body.mission_id) || !validProjection(body.galaxy, empire))
    throw new ApiError("invalid_response", 0);
  return { mission: body.mission_id, galaxy: body.galaxy };
}


export type ColonyLink = { colony_id: string; planet_id: string; name: string };
export type SystemDetail = KnownSystem & {
  server_time?: string; empire_id?: string; permissions?: string[];
  /** Pinned ruleset offers COLONIZE (v0.5+); says nothing about who occupies a world. */
  colonization?: boolean;
  /** Pinned ruleset offers ATTACK (v0.7+); says nothing about occupation or defence. */
  combat?: boolean;
  routes?: { id: string; neighbor: { id: string; state: KnowledgeState; name?: string } }[];
  presences?: { kind: "own_colony"; current: boolean; observed_at: string | null; colony: ColonyLink | null }[];
  colony_links?: ColonyLink[];
};
export function validSystemDetail(value: unknown, empire: string, systemId: string): value is SystemDetail {
  if (!validKnownSystem(value) || value.id !== systemId) return false;
  const v = value as SystemDetail;
  if (v.state === "DETECTED") return ["routes", "presences", "colony_links", "permissions", "server_time", "empire_id", "colonization", "combat"].every(k => !(k in v));
  const link = (c: unknown) => object(c) && id(c.colony_id) && typeof c.name === "string"
    && v.planets!.some(p => p.id === c.planet_id);
  return v.empire_id === empire && date(v.server_time) && typeof v.colonization === "boolean"
    && (v.combat === undefined || typeof v.combat === "boolean")
    && list(v.permissions, p => typeof p === "string") && v.permissions!.includes("galaxy.read")
    && (v.permissions!.includes("colony.read") || !v.observation)
    && list(v.routes, r => object(r) && id(r.id) && object(r.neighbor) && id(r.neighbor.id)
      && (r.neighbor.state === "DETECTED" ? !("name" in r.neighbor)
        : ["MAPPED", "MONITORED"].includes(String(r.neighbor.state)) && typeof r.neighbor.name === "string"))
    && list(v.presences, p => object(p) && p.kind === "own_colony" && typeof p.current === "boolean"
      && (p.observed_at === null || date(p.observed_at)) && (!p.current || v.state === "MONITORED")
      && (p.colony === null || p.current && v.permissions!.includes("colony.read") && link(p.colony)))
    && list(v.colony_links, c => v.permissions!.includes("colony.read") && link(c));
}
export async function readSystem(universe: string, empire: string, systemId: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/galaxy/${empire}/systems/${systemId}`, bootstrap, signal);
  if (!validSystemDetail(body, empire, systemId)) throw new ApiError("invalid_response", 0);
  return body;
}
