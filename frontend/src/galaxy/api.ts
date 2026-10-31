import type { Amounts } from '../colony/api';

export type KnownSystem = {
  id: string; state: 'DETECTED' | 'MAPPED' | 'MONITORED'; x: number; y: number;
  discovered_at: string; name?: string; last_seen_at?: string | null;
  planets?: { id: string; name: string; sector_capacity: number; orbital_capacity: number }[];
};
export type Mission = {
  id: string; destination_id: string; colony_id: string; status: 'active' | 'completed';
  started_at: string; due_at: string; cost: Amounts;
  report: { observed_at: string; processed_at: string; discoveries: { system: KnownSystem } } | null;
};
export type Projection = {
  server_time: string; empire: { id: string }; permissions: string[]; systems: KnownSystem[];
  routes: { id: string; a_id: string; b_id: string }[];
  sources: { id: string; name: string; stocks: Amounts }[];
  options: { colony_id: string; destination_id: string; hops: number; cost: Amounts;
    duration_us: string; reason: string | null }[]; missions: Mission[];
};
export class GalaxyError extends Error {
  constructor(public code: string, public status: number) { super(code); }
}
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object';
const identifier = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9-]{36}$/i.test(value);
const date = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value));
const integer = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value);
const micro = (value: unknown): value is string => typeof value === 'string' && /^\d+$/.test(value);
function amounts(value: unknown) {
  return object(value) && ['alloys', 'flux', 'data'].every(k => micro(value[k]));
}
function known(value: unknown) {
  if (!object(value) || !identifier(value.id) || !integer(value.x) || !integer(value.y)
    || !date(value.discovered_at) || !['DETECTED', 'MAPPED', 'MONITORED'].includes(String(value.state))) return false;
  if (value.state === 'DETECTED') return !('name' in value) && !('planets' in value);
  return typeof value.name === 'string' && Array.isArray(value.planets) && value.planets.every(p =>
    object(p) && identifier(p.id) && typeof p.name === 'string' && integer(p.sector_capacity)
    && integer(p.orbital_capacity)) && (value.last_seen_at === null || date(value.last_seen_at));
}
export function projection(value: unknown): Projection {
  if (!object(value) || !date(value.server_time) || !object(value.empire) || !identifier(value.empire.id)
    || !Array.isArray(value.permissions) || !value.permissions.every(p => typeof p === 'string')
    || !Array.isArray(value.systems) || !value.systems.every(known)
    || !Array.isArray(value.routes) || !value.routes.every(r => object(r) && identifier(r.id)
      && identifier(r.a_id) && identifier(r.b_id))
    || !Array.isArray(value.sources) || !value.sources.every(s => object(s) && identifier(s.id)
      && typeof s.name === 'string' && amounts(s.stocks))
    || !Array.isArray(value.options) || !value.options.every(o => object(o) && identifier(o.colony_id)
      && identifier(o.destination_id) && integer(o.hops) && o.hops > 0 && amounts(o.cost)
      && micro(o.duration_us) && (o.reason === null || typeof o.reason === 'string'))
    || !Array.isArray(value.missions) || !value.missions.every(m => object(m) && identifier(m.id)
      && identifier(m.destination_id) && identifier(m.colony_id) && ['active', 'completed'].includes(String(m.status))
      && date(m.started_at) && date(m.due_at) && amounts(m.cost) && (m.report === null
        || object(m.report) && date(m.report.observed_at) && date(m.report.processed_at)
        && object(m.report.discoveries) && known(m.report.discoveries.system)))) {
    throw new GalaxyError('invalid_response', 0);
  }
  const result = value as Projection;
  const ids = new Set(result.systems.map(s => s.id));
  if (ids.size !== result.systems.length || result.routes.some(r => !ids.has(r.a_id) || !ids.has(r.b_id))) {
    throw new GalaxyError('invalid_response', 0);
  }
  return result;
}
export async function request(path: string, signal: AbortSignal, body?: unknown, csrf?: string) {
  const response = await fetch(path, { signal, credentials: 'same-origin', cache: 'no-store',
    method: body === undefined ? 'GET' : 'POST', headers: body === undefined
      ? { 'X-Game-Request': 'bootstrap' } : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf ?? '' },
    body: body === undefined ? undefined : JSON.stringify(body) });
  const value: unknown = await response.json();
  if (!response.ok) throw new GalaxyError(object(value) && object(value.error)
    && typeof value.error.code === 'string' ? value.error.code : 'unavailable', response.status);
  return value;
}
export function empires(value: unknown): {id: string; name: string}[] {
  if (!object(value) || !Array.isArray(value.empires) || !value.empires.every(e => object(e)
    && identifier(e.id) && typeof e.name === 'string')) throw new GalaxyError('invalid_response', 0);
  return value.empires as {id: string; name: string}[];
}
