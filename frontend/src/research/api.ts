import { ApiError } from '../colony/api';
import type { Amounts } from '../colony/api';
export { ApiError };
export type Empire = { id: string; name: string };
export type Technology = { id: string; name: string; domain: string; tier: number; requires: string[]; effect: string; reduction_bps: number; cost: Amounts; base_duration_us: string; duration_us: string; available: boolean; reason: string | null };
export type Refund = { colony_id: string; colony_name: string; theoretical: Amounts; recoverable: Amounts; lost: Amounts };
export type Order = { id: string; technology_id: string; name: string; status: string; colony_id: string | null; cost: Amounts; duration_us: string; started_at: string | null; due_at: string | null; blocked_reason: string | null; cancel: { available: boolean; refunds: Refund[]; also_cancels: string[] } };
export type Projection = { server_time: string; ruleset_version: string; empire: Empire; permissions: string[]; acquired: { technology_id: string; acquired_at: string; effect: string; reduction_bps: number }[]; bonuses: Record<string, number>; queue: Order[]; technologies: Technology[]; sources: { id: string; name: string; stocks: Amounts }[] };
export type Command = { kind: 'start'; technology_id: string; colony_id: string } | { kind: 'cancel'; order_id: string };
const amount = (v: unknown) => typeof v === 'string' && /^\d{1,20}$/.test(v);
const amounts = (v: unknown): v is Amounts => !!v && typeof v === 'object' && ['alloys', 'flux', 'data'].every(k => amount((v as Record<string, unknown>)[k]));
const date = (v: unknown) => typeof v === 'string' && Number.isFinite(Date.parse(v));
export function validProjection(value: unknown, empire: string): value is Projection {
  if (!value || typeof value !== 'object') return false;
  const p = value as Projection;
  return p.empire?.id === empire && typeof p.empire.name === 'string' && date(p.server_time)
    && Array.isArray(p.permissions) && Array.isArray(p.acquired) && Array.isArray(p.technologies)
    && p.technologies.every(t => typeof t.id === 'string' && typeof t.name === 'string' && amounts(t.cost) && amount(t.duration_us) && Array.isArray(t.requires))
    && Array.isArray(p.sources) && p.sources.every(s => typeof s.id === 'string' && amounts(s.stocks))
    && Array.isArray(p.queue) && p.queue.every(o => typeof o.id === 'string' && amounts(o.cost) && amount(o.duration_us)
      && (o.due_at === null || date(o.due_at)) && Array.isArray(o.cancel?.refunds) && Array.isArray(o.cancel.also_cancels)
      && o.cancel.refunds.every(r => amounts(r.theoretical) && amounts(r.recoverable) && amounts(r.lost)));
}
async function request(url: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { ...init, signal });
  let body: unknown;
  try { body = await response.json(); } catch { throw new ApiError('invalid_response', response.ok ? 0 : response.status); }
  if (!response.ok) {
    const error = body as { error?: { code?: string } };
    throw new ApiError(error.error?.code ?? 'unavailable', response.status);
  }
  return body;
}
export async function listEmpires(universe: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/research`, { headers: { 'X-Game-Request': 'bootstrap' } }, signal) as { empires?: Empire[] };
  if (!Array.isArray(body.empires) || body.empires.some(e => typeof e.id !== 'string' || typeof e.name !== 'string')) throw new ApiError('invalid_response', 0);
  return body.empires;
}
export async function readResearch(universe: string, empire: string, signal: AbortSignal) {
  const body = await request(`/api/game/${universe}/research/${empire}`, { headers: { 'X-Game-Request': 'bootstrap' } }, signal);
  if (!validProjection(body, empire)) throw new ApiError('invalid_response', 0);
  return body;
}
export async function sendCommand(universe: string, empire: string, csrf: string, command: Command, key: string, signal: AbortSignal) {
  const root = `/api/game/${universe}/research/${empire}/orders`;
  const [url, payload] = command.kind === 'start' ? [root, { idempotency_key: key, technology_id: command.technology_id, colony_id: command.colony_id }] : [`${root}/${command.order_id}/cancel`, {}];
  const body = await request(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload) }, signal) as { research?: unknown };
  if (!validProjection(body.research, empire)) throw new ApiError('invalid_response', 0);
  return body.research;
}
