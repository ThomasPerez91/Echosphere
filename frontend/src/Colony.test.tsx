import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';
import type { Projection } from './colony/api';

const universe = '052d4535-79c7-413b-ace3-47c732561fbd';
const colonyId = '7d1c56a0-3c52-4e8e-9d6b-2b1f4b0f8a11';
const M = (value: number) => String(value * 1_000_000);
const amounts = (alloys: number, flux: number, data: number) => ({ alloys: M(alloys), flux: M(flux), data: M(data) });
const session = { universe_id: universe, universe_name: 'Mon univers', csrf_token: 'a'.repeat(64),
  expires_at: '2099-01-01T08:00:00Z', idle_expires_at: '2099-01-01T02:00:00Z', access_valid_until: '2099-01-01T08:00:00Z',
  server_time: '2099-01-01T00:00:00Z', portal_url: 'https://portal.example.org' };

function projection(changes: Partial<Projection> = {}): Projection {
  const option = (kind: string, sector: number | null, available = true, reason: string | null = null) => ({
    action: 'build' as const, infrastructure_type: kind, sector_index: sector, target_level: 1, cost: amounts(250, 120, 0),
    base_duration_us: String(120e6), estimated_duration_us: String(109090910), production_per_hour: amounts(120, 0, 0),
    construction_bonus_bps: 0, capacity: null, available, reason });
  return {
    server_time: '2099-01-01T00:00:00+00:00', settled_at: '2099-01-01T00:00:00+00:00', ruleset_version: 'v0.1',
    permissions: ['colony.cancel', 'colony.construct', 'colony.read'],
    colony: { id: colonyId, name: 'Kepler Test', planet: { name: 'Kepler Test', sector_capacity: 12, orbital_capacity: 2 },
      system: { name: 'Système Test' }, empire: { id: 'e', name: 'Empire Test' }, universe: { id: universe, name: 'Mon univers' } },
    sectors: { capacity: 12, built: 4, reserved: 0, free: 8, free_indices: [5, 6, 7, 8, 9, 10, 11, 12] },
    resources: [
      { resource: 'alloys', stock: M(2000), capacity: M(10000), rate_per_hour: M(120) },
      { resource: 'flux', stock: M(1500), capacity: M(10000), rate_per_hour: M(100) },
      { resource: 'data', stock: M(750), capacity: M(10000), rate_per_hour: M(60) },
    ],
    infrastructures: [{ sector_index: 1, infrastructure_type: 'extraction_complex', level: 1, cost: amounts(250, 120, 0),
      base_duration_us: String(120e6), production_per_hour: amounts(120, 0, 0), construction_bonus_bps: 0, capacity: null }],
    queue: [], queue_limit: 3,
    options: [option('data_node', 5), option('industrial_complex', 5, false, 'unique_limit')],
    ...changes,
  };
}

type Reply = { status?: number; body: unknown } | Error;
function setup(route: string, replies: { colony?: Reply[]; command?: Reply[] } = {}, strict = false) {
  const queues = { colony: [...(replies.colony ?? [])], command: [...(replies.command ?? [])] };
  const reply = (value: Reply | undefined, fallback: unknown) => {
    if (value instanceof Error) return Promise.reject(value);
    const status = value?.status ?? 200;
    return Promise.resolve({ ok: status < 400, status, json: async () => value ? value.body : fallback });
  };
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (url === '/api/ready') return reply(undefined, { status: 'ready' });
    if (url.endsWith('/session')) return reply(undefined, session);
    if (url.endsWith('/colonies')) return reply(undefined, { server_time: session.server_time, colonies: [{ id: colonyId, name: 'Kepler Test', empire: { id: 'e', name: 'Empire Test' } }] });
    if (options?.method === 'POST' && url.includes('/construction-orders')) return reply(queues.command.shift(), { order: { id: 'o', status: 'active' }, colony: projection() });
    if (url.includes(`/colonies/${colonyId}`)) return reply(queues.colony.length > 1 ? queues.colony.shift() : queues.colony[0], projection());
    return reply(undefined, session);
  });
  vi.stubGlobal('fetch', fetcher);
  window.history.replaceState(null, '', `#universe/${universe}/${route}`);
  render(strict ? <StrictMode><App /></StrictMode> : <App />);
  return fetcher;
}
const posts = (fetcher: ReturnType<typeof setup>) => fetcher.mock.calls.filter(call => call[1]?.method === 'POST' && String(call[0]).includes('construction-orders'));
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });

test('real server projection renders without any mutation, even under StrictMode', async () => {
  const fetcher = setup('colony/infrastructure', {}, true);
  expect(await screen.findByRole('heading', { name: 'Kepler Test' })).toBeVisible();
  expect(screen.getByLabelText('Stocks de la colonie')).toHaveTextContent('2 000');
  expect(screen.getAllByText('+120/h').length).toBeGreaterThan(0);
  expect(screen.getByRole('button', { name: 'Construire Nœud de données' })).toBeEnabled();
  expect(screen.getByRole('button', { name: 'Construire Complexe industriel' })).toBeDisabled();
  expect(screen.getByText('Cette infrastructure est limitée à un exemplaire par colonie.')).toBeVisible();
  expect(posts(fetcher)).toHaveLength(0);
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0);
});

test('a double click sends one command with CSRF and an idempotency key', async () => {
  const fetcher = setup('colony/infrastructure', { command: [{ body: { order: { id: 'o', status: 'active' }, colony: projection() } }] });
  const button = await screen.findByRole('button', { name: 'Construire Nœud de données' });
  fireEvent.click(button); fireEvent.click(button);
  expect(await screen.findByText('Ordre de construction accepté par le serveur.')).toBeVisible();
  expect(posts(fetcher)).toHaveLength(1);
  const [url, init] = posts(fetcher)[0] as unknown as [string, RequestInit];
  expect(url).toBe(`/api/game/${universe}/colonies/${colonyId}/construction-orders`);
  expect(init.headers).toMatchObject({ 'X-CSRF-Token': 'a'.repeat(64), 'Content-Type': 'application/json' });
  const body = JSON.parse(init.body as string);
  expect(body).toMatchObject({ infrastructure_type: 'data_node', sector_index: 5, target_level: 1 });
  expect(body.idempotency_key).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
  expect(Object.keys(body).sort()).toEqual(['idempotency_key', 'infrastructure_type', 'sector_index', 'target_level']);
});

test('a retry after an unknown outcome reuses the same key; a refusal starts a new intent', async () => {
  const fetcher = setup('colony/infrastructure', { command: [new TypeError('network'),
    { body: { order: { id: 'o', status: 'active' }, colony: projection() } }] });
  fireEvent.click(await screen.findByRole('button', { name: 'Construire Nœud de données' }));
  expect(await screen.findByText(/Résultat non confirmé/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Construire Nœud de données' }));
  await screen.findByText('Ordre de construction accepté par le serveur.');
  const keys = posts(fetcher).map(call => JSON.parse((call[1] as RequestInit).body as string).idempotency_key);
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test('a server refusal is explained and the colony is re-read without activity', async () => {
  const fetcher = setup('colony/infrastructure', { command: [{ status: 409, body: { error: { code: 'insufficient_resources' } } }] });
  fireEvent.click(await screen.findByRole('button', { name: 'Construire Nœud de données' }));
  expect(await screen.findByText('Ressources insuffisantes pour cette construction.')).toBeVisible();
  await waitFor(() => expect(fetcher.mock.calls.filter(call => String(call[0]).endsWith(colonyId)).length).toBeGreaterThan(1));
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST' && String(call[0]).endsWith('/navigation'))).toHaveLength(0);
});

test('cancellation needs an explicit confirmation and shows the refund; Q39 refusal blocks it', async () => {
  const order = { id: 'order-1', sequence: 1, status: 'active' as const, infrastructure_type: 'data_node', sector_index: 5, target_level: 1,
    cost: amounts(250, 120, 0), base_duration_us: String(120e6), applied_bonus_bps: 1000,
    started_at: '2099-01-01T00:00:00+00:00', due_at: '2099-01-01T00:01:49+00:00',
    cancel: { available: true, reason: null, refund: amounts(200, 96, 0), also_cancels: [] } };
  const blocked = { ...order, id: 'order-2', status: 'queued' as const, started_at: null, due_at: null,
    cancel: { available: false, reason: 'refund_exceeds_capacity', refund: amounts(250, 120, 0), also_cancels: [] } };
  const fetcher = setup('colony/infrastructure', { colony: [{ body: projection({ queue: [order, blocked] }) }] });
  const refused = await screen.findByRole('button', { name: 'Annuler Nœud de données', description: /remboursement dépasserait la capacité/ });
  expect(refused).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Annuler Nœud de données', description: '' }));
  expect(screen.getByText(/Remboursement : 200 Alliages, 96 Flux/)).toBeVisible();
  expect(posts(fetcher)).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer l’annulation' }));
  await waitFor(() => expect(posts(fetcher)).toHaveLength(1));
  expect(String(posts(fetcher)[0][0])).toContain('/construction-orders/order-1/cancel');
  expect(JSON.parse((posts(fetcher)[0][1] as RequestInit).body as string)).toEqual({});
});

test('read-only access shows the colony but no command buttons', async () => {
  const fetcher = setup('colony/infrastructure', { colony: [{ body: projection({ permissions: ['colony.read'],
    options: projection().options.map(o => ({ ...o, available: false, reason: 'permission_denied' })) }) }] });
  expect(await screen.findByRole('heading', { name: 'Kepler Test' })).toBeVisible();
  expect(screen.queryByRole('button', { name: /^Construire|^Améliorer|^Annuler/ })).not.toBeInTheDocument();
  expect(posts(fetcher)).toHaveLength(0);
});

test('an expired session on a command re-reads the session and shows the lobby path', async () => {
  const fetcher = setup('colony/infrastructure', { command: [{ status: 401, body: { error: { code: 'authentication_required' } } }] });
  fireEvent.click(await screen.findByRole('button', { name: 'Construire Nœud de données' }));
  await waitFor(() => expect(fetcher.mock.calls.filter(call => String(call[0]).endsWith('/session')).length).toBeGreaterThan(1));
});

test('reaching the server deadline triggers a read, never a command or activity', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
  vi.setSystemTime(new Date('2099-01-01T00:00:00Z'));
  const order = { id: 'order-1', sequence: 1, status: 'active' as const, infrastructure_type: 'data_node', sector_index: 5, target_level: 1,
    cost: amounts(250, 120, 0), base_duration_us: String(120e6), applied_bonus_bps: 1000,
    started_at: '2099-01-01T00:00:00+00:00', due_at: '2099-01-01T00:00:10+00:00',
    cancel: { available: true, reason: null, refund: amounts(200, 96, 0), also_cancels: [] } };
  const fetcher = setup('colony/overview', { colony: [{ body: projection({ queue: [order] }) }, { body: projection() }] });
  await act(() => vi.advanceTimersByTimeAsync(100));
  const reads = () => fetcher.mock.calls.filter(call => String(call[0]).endsWith(colonyId)).length;
  const before = reads();
  await act(() => vi.advanceTimersByTimeAsync(12000));
  expect(reads()).toBeGreaterThan(before);
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0);
});
