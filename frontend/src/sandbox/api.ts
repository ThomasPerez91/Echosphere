import { ApiError } from '../colony/api';

/** Test game (sandbox, recette 10/11/2026): Game answers 404 `sandbox_unavailable` elsewhere. */
export type SandboxStatus = {
  sandbox: true; server_time: string; ship_classes: string[];
  colonies: { id: string; name: string; capacity: string }[];
};
export type SandboxCommand =
  | { kind: 'resources'; colony_id: string; alloys?: number; flux?: number; data?: number }
  | { kind: 'ships'; colony_id: string; ships: Record<string, number> }
  | { kind: 'finish' };
export type Finished = { constructions: number; research: number; ships: number };

const EVENT = 'echosphere:sandbox';

/** Every open view rereads its projection after a grant or an instant completion. */
export function onSandboxChange(listener: () => void) {
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}
export const sandboxChanged = () => window.dispatchEvent(new Event(EVENT));

export function validStatus(value: unknown): value is SandboxStatus {
  if (!value || typeof value !== 'object') return false;
  const v = value as Partial<SandboxStatus>;
  return v.sandbox === true && typeof v.server_time === 'string' && Array.isArray(v.ship_classes)
    && v.ship_classes.every(c => typeof c === 'string') && Array.isArray(v.colonies)
    && v.colonies.every(c => !!c && typeof c.id === 'string' && typeof c.name === 'string'
      && typeof c.capacity === 'string' && /^\d{1,19}$/.test(c.capacity));
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

/** Null when this universe is not a test game. */
export async function readSandbox(universe: string, empire: string, signal: AbortSignal) {
  try {
    const body = await request(`/api/game/${universe}/sandbox/${empire}`, { headers: { 'X-Game-Request': 'bootstrap' } }, signal);
    if (!validStatus(body)) throw new ApiError('invalid_response', 0);
    return body;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function sandboxCommand(universe: string, empire: string, csrf: string, command: SandboxCommand, signal: AbortSignal) {
  const { kind, ...payload } = command;
  const body = await request(`/api/game/${universe}/sandbox/${empire}/${kind}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(payload),
  }, signal);
  if (!validStatus(body)) throw new ApiError('invalid_response', 0);
  return body as SandboxStatus & { result: unknown };
}
