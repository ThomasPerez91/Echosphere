// Same-origin Colony API client. The server is authoritative; responses are validated, not trusted.

export type Amounts = { alloys: string; flux: string; data: string };
export type Resource = { resource: keyof Amounts; stock: string; capacity: string | null; rate_per_hour: string };
export type Infrastructure = {
  sector_index: number; infrastructure_type: string; level: number; cost: Amounts; base_duration_us: string;
  production_per_hour: Amounts; construction_bonus_bps: number; capacity: string | null;
};
export type Order = {
  id: string; sequence: number; status: 'active' | 'queued'; infrastructure_type: string; sector_index: number;
  target_level: number; cost: Amounts; base_duration_us: string; applied_bonus_bps: number | null;
  started_at: string | null; due_at: string | null;
  cancel: { available: boolean; reason: string | null; refund: Amounts; also_cancels: string[] };
};
export type Option = {
  action: 'build' | 'upgrade'; infrastructure_type: string; sector_index: number | null; target_level: number;
  cost: Amounts; base_duration_us: string; estimated_duration_us: string | null; production_per_hour: Amounts;
  construction_bonus_bps: number; capacity: string | null; available: boolean; reason: string | null;
};
export type Projection = {
  server_time: string; settled_at: string; ruleset_version: string; permissions: string[];
  colony: { id: string; name: string; planet: { name: string; sector_capacity: number; orbital_capacity: number };
    system: { name: string }; empire: { id: string; name: string }; universe: { id: string; name: string } };
  sectors: { capacity: number; built: number; reserved: number; free: number; free_indices: number[] };
  resources: Resource[]; infrastructures: Infrastructure[]; queue: Order[]; queue_limit: number; options: Option[];
};
export type ColonySummary = { id: string; name: string; empire: { id: string; name: string } };

export class ApiError extends Error {
  constructor(readonly code: string, readonly status: number) { super(code); }
}

const micro = (value: unknown) => typeof value === 'string' && /^\d{1,19}$/.test(value);
const amounts = (value: unknown) => !!value && typeof value === 'object'
  && ['alloys', 'flux', 'data'].every(key => micro((value as Record<string, unknown>)[key]));
const date = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value));

export function validProjection(value: unknown, colony?: string): value is Projection {
  if (!value || typeof value !== 'object') return false;
  const p = value as Projection;
  return date(p.server_time) && Array.isArray(p.permissions) && !!p.colony && typeof p.colony.name === 'string'
    && (!colony || p.colony.id === colony) && Array.isArray(p.resources) && p.resources.length === 3
    && p.resources.every(r => micro(r.stock) && micro(r.rate_per_hour) && (r.capacity === null || micro(r.capacity)))
    && Array.isArray(p.infrastructures) && p.infrastructures.every(i => Number.isInteger(i.level) && amounts(i.production_per_hour))
    && Array.isArray(p.queue) && p.queue.every(o => typeof o.id === 'string' && amounts(o.cost) && amounts(o.cancel?.refund)
      && (o.due_at === null || date(o.due_at)) && (o.started_at === null || date(o.started_at)))
    && Array.isArray(p.options) && p.options.every(o => amounts(o.cost) && micro(o.base_duration_us))
    && !!p.sectors && Array.isArray(p.sectors.free_indices) && Number.isInteger(p.queue_limit);
}

function validList(value: unknown): value is { colonies: ColonySummary[] } {
  return !!value && typeof value === 'object' && Array.isArray((value as { colonies?: unknown }).colonies)
    && (value as { colonies: ColonySummary[] }).colonies.every(c => typeof c.id === 'string' && typeof c.name === 'string');
}

async function request(url: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { ...init, signal });
  let body: unknown = null;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const code = body && typeof body === 'object' && 'error' in body && body.error && typeof body.error === 'object'
      && 'code' in body.error && typeof body.error.code === 'string' ? body.error.code : 'unavailable';
    throw new ApiError(code, response.status);
  }
  return body;
}

const read = { 'X-Game-Request': 'bootstrap' };

export async function listColonies(universe: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/colonies`, { headers: read }, signal);
  if (!validList(body)) throw new ApiError('invalid_response', 0);
  return body.colonies;
}

export async function readColony(universe: string, colony: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/colonies/${colony}`, { headers: read }, signal);
  if (!validProjection(body, colony)) throw new ApiError('invalid_response', 0);
  return body;
}

export type Command =
  | { kind: 'construct'; infrastructure_type: string; sector_index: number; target_level: number }
  | { kind: 'cancel'; order_id: string };

export async function sendCommand(universe: string, colony: string, csrf: string, command: Command,
  idempotencyKey: string, signal: AbortSignal) {
  const root = `/api/game/${universe}/colonies/${colony}/construction-orders`;
  const [url, payload] = command.kind === 'construct'
    ? [root, { idempotency_key: idempotencyKey, infrastructure_type: command.infrastructure_type,
      sector_index: command.sector_index, target_level: command.target_level }]
    : [`${root}/${command.order_id}/cancel`, {}];
  const body = await request(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(payload) }, signal);
  const colonyBody = body && typeof body === 'object' && 'colony' in body ? body.colony : null;
  if (!validProjection(colonyBody, colony)) throw new ApiError('invalid_response', 0);
  return colonyBody;
}
