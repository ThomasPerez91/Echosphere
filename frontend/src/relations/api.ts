import { ApiError } from "../colony/api";
export { ApiError };

export type Empire = { id: string; name: string };
export type RelationAction = "propose" | "withdraw" | "accept" | "refuse" | "terminate";
/** Oriented own contact: how and when this Empire learned of the other; presence is dated. */
export type Contact = {
  first_source: "combat" | "presence" | "diplomacy";
  first_seen_at: string;
  last_seen_at: string;
  presence: { planet_id: string; planet_name: string | null; system_id: string | null; system_name: string | null; observed_at: string } | null;
};
export type Relation = {
  empire: Empire;
  contact: Contact | null;
  state: "NO_AGREEMENT" | "PACT";
  pact: { accepted_at: string; notice: { by: "self" | "counterpart"; at: string; ends_at: string } | null } | null;
  proposal: { direction: "sent" | "received"; proposed_at: string; expires_at: string } | null;
  cooldown_until: string | null;
  /** Hostility is a dated fact per side, never a relation state (Q18). */
  hostility: { by_self_at: string | null; by_counterpart_at: string | null };
  actions: RelationAction[];
};
export type HistoryEntry = {
  id: string; at: string; kind: "proposed" | "withdrawn" | "accepted" | "refused" | "notice";
  actor: "self" | "counterpart"; counterpart_id: string;
  expires_at?: string; cooldown_until?: string; ends_at?: string; pact_id?: string;
};
export type RelationsProjection = {
  at: string;
  terms: { proposal_ttl_seconds: number; refusal_cooldown_seconds: number; notice_seconds: number };
  relations: Relation[];
  history: HistoryEntry[];
  can_negotiate: boolean;
};

type Value = Record<string, unknown>;
const object = (v: unknown): v is Value => !!v && typeof v === "object" && !Array.isArray(v);
const id = (v: unknown): v is string =>
  typeof v === "string" && /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(v);
const date = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
const optionalDate = (v: unknown) => v === null || date(v);
const integer = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v) && v > 0;
const list = (v: unknown, item: (x: unknown) => boolean) => Array.isArray(v) && v.every(item);
const exactKeys = (v: Value, keys: string[]) => Object.keys(v).sort().join() === [...keys].sort().join();
const nullableText = (v: unknown) => v === null || typeof v === "string";
const ACTIONS = ["propose", "withdraw", "accept", "refuse", "terminate"];

// A presence reveals the Empire, the planet and the date only: any extra field is a fog leak.
const presence = (v: unknown) =>
  v === null || (object(v) && exactKeys(v, ["planet_id", "planet_name", "system_id", "system_name", "observed_at"]) &&
    id(v.planet_id) && nullableText(v.planet_name) && (v.system_id === null || id(v.system_id)) &&
    nullableText(v.system_name) && date(v.observed_at));
// A diplomatic introduction reveals identity and date only; a place only ever comes from a
// later own presence observation of the same Empire.
const contact = (v: unknown) =>
  v === null || (object(v) && exactKeys(v, ["first_source", "first_seen_at", "last_seen_at", "presence"]) &&
    ["combat", "presence", "diplomacy"].includes(String(v.first_source)) && date(v.first_seen_at) && date(v.last_seen_at) &&
    presence(v.presence));
const pact = (v: unknown) =>
  v === null || (object(v) && date(v.accepted_at) &&
    (v.notice === null || (object(v.notice) && ["self", "counterpart"].includes(String(v.notice.by)) &&
      date(v.notice.at) && date(v.notice.ends_at))));
const proposal = (v: unknown) =>
  v === null || (object(v) && ["sent", "received"].includes(String(v.direction)) && date(v.proposed_at) && date(v.expires_at));
const relation = (v: unknown) =>
  object(v) && object(v.empire) && id(v.empire.id) && typeof v.empire.name === "string" && contact(v.contact) &&
  ["NO_AGREEMENT", "PACT"].includes(String(v.state)) && pact(v.pact) && (v.state === "PACT") === (v.pact !== null) &&
  proposal(v.proposal) && optionalDate(v.cooldown_until) && object(v.hostility) &&
  optionalDate(v.hostility.by_self_at) && optionalDate(v.hostility.by_counterpart_at) &&
  list(v.actions, (a) => ACTIONS.includes(String(a)));
const entry = (v: unknown) =>
  object(v) && id(v.id) && date(v.at) && ["proposed", "withdrawn", "accepted", "refused", "notice"].includes(String(v.kind)) &&
  ["self", "counterpart"].includes(String(v.actor)) && id(v.counterpart_id);

export function validRelations(value: unknown): value is RelationsProjection {
  return object(value) && date(value.at) && object(value.terms) && integer(value.terms.proposal_ttl_seconds) &&
    integer(value.terms.refusal_cooldown_seconds) && integer(value.terms.notice_seconds) &&
    list(value.relations, relation) && list(value.history, entry) && typeof value.can_negotiate === "boolean" &&
    // Without the negotiate right no action is ever offered.
    (value.can_negotiate || (value.relations as Relation[]).every((r) => r.actions.length === 0));
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

export async function listRelationEmpires(universe: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/relations`, bootstrap, signal);
  if (!object(body) || typeof body.available !== "boolean" ||
    !list(body.empires, (e) => object(e) && id(e.id) && typeof e.name === "string"))
    throw new ApiError("invalid_response", 0);
  return { available: body.available, empires: body.empires as Empire[] };
}

export async function readRelations(universe: string, empire: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/relations/${empire}`, bootstrap, signal);
  if (!validRelations(body)) throw new ApiError("invalid_response", 0);
  return body;
}

/** One negotiation command; the server answers its receipt and the fresh projection. */
export async function relationCommand(universe: string, empire: string, counterpart: string, action: RelationAction,
  csrf: string, key: string, signal: AbortSignal) {
  const reply = await request(`/api/game/${universe}/relations/${empire}/${counterpart}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify({ idempotency_key: key }),
  }, signal);
  if (!object(reply) || !object(reply.result) || !validRelations(reply.relations))
    throw new ApiError("invalid_response", 0);
  return { result: reply.result, relations: reply.relations };
}
