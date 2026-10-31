import type { Projection, Order } from '../src/research/api';
export const universe = '052d4535-79c7-413b-ace3-47c732561fbd';
export const empire = '8c315025-a146-4510-9347-475838286851';
export const colony = '7d1c56a0-3c52-4e8e-9d6b-2b1f4b0f8a11';
export const amounts = (n: number) => ({ alloys: String(n * 1e6), flux: String(n * 1e6), data: String(n * 1e6) });
export const session = { universe_id: universe, universe_name: 'Research test', csrf_token: 'a'.repeat(64), expires_at: '2099-01-01T08:00:00Z', idle_expires_at: '2099-01-01T02:00:00Z', access_valid_until: '2099-01-01T08:00:00Z', server_time: '2099-01-01T00:00:00Z', portal_url: 'https://portal.example.org' };
export function order(): Order { return { id: 'first', technology_id: 'engineering_1', name: 'Fabrication modulaire I', status: 'active', colony_id: colony, cost: amounts(100), duration_us: '120000000', started_at: session.server_time, due_at: '2099-01-01T00:02:00Z', blocked_reason: null, cancel: { available: true, refunds: [{ colony_id: colony, colony_name: 'Nouvelle Aube', theoretical: amounts(80), recoverable: amounts(3), lost: amounts(77) }], also_cancels: [] } }; }
export function projection(queue: Order[] = []): Projection {
  return { server_time: session.server_time, ruleset_version: 'v0.2', empire: { id: empire, name: 'Empire test' }, permissions: ['research.read', 'research.start', 'research.cancel', 'colony.read'], acquired: [], bonuses: {}, queue, sources: [{ id: colony, name: 'Nouvelle Aube', stocks: amounts(500) }], technologies: [
    { id: 'engineering_1', name: 'Fabrication modulaire I', domain: 'engineering', tier: 1, requires: [], effect: 'colony_alloys', reduction_bps: 500, cost: amounts(100), base_duration_us: '120000000', duration_us: '120000000', available: !queue.length, reason: queue.length ? 'technology_duplicate' : null },
    { id: 'engineering_2', name: 'Fabrication modulaire II', domain: 'engineering', tier: 2, requires: ['engineering_1'], effect: 'colony_alloys', reduction_bps: 1000, cost: amounts(200), base_duration_us: '300000000', duration_us: '300000000', available: queue.length > 0, reason: queue.length ? null : 'prerequisites_unmet' },
  ] };
}
