import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { ReportsScreen } from './reports/ReportsScreen';
import { validHistory } from './colony/api';
import type { useColony } from './hooks/useColony';
import type { useGameSession } from './hooks/useGameSession';

const universe = '11111111-1111-4111-8111-111111111111';
const colonyId = '22222222-2222-4222-8222-222222222222';
const empireId = '33333333-3333-4333-8333-333333333333';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const entry = (n: number, type = 'extraction_complex', level = 1) => ({
  id: `order-${n}`, sequence: String(n), infrastructure_type: type, sector_index: n % 12, target_level: level,
  completed_at: new Date(Date.UTC(2026, 10, 5, 8, 0) + n * 60000).toISOString(),
});
const page = (entries: ReturnType<typeof entry>[], next: string | null) => ({
  server_time: '2026-11-06T09:00:00+00:00', colony_id: colonyId, empire_id: empireId, entries, next_before_sequence: next,
});
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
const missing = () => json({ error: { code: 'not_found' } }, 404);

function setup(history: (url: string) => Promise<Response>) {
  // Typed with the RequestInit argument so the assertions can read headers and methods.
  const fetch = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) => url.includes('/construction-history') ? history(url) : missing());
  vi.stubGlobal('fetch', fetch);
  const access = { phase: 'active', session: { csrf_token: 'csrf' }, retry: vi.fn() } as unknown as ReturnType<typeof useGameSession>;
  const colony = { colonies: [{ id: colonyId, name: 'Aube Prime', empire: { id: empireId, name: 'Concorde' } }], projection: null, refresh: vi.fn() } as unknown as ReturnType<typeof useColony>;
  render(<ReportsScreen universe={universe} access={access} colony={colony} />);
  return fetch;
}

test('completed constructions are listed from the server, older pages follow the exclusive cursor', async () => {
  const fetch = setup((url) => url.includes('before_sequence=3')
    ? json(page([entry(2, 'data_node', 2), entry(3, 'extraction_complex')], null)) // a replayed entry is not shown twice
    : json(page([entry(5, 'flux_reactor', 3), entry(4), entry(3, 'extraction_complex')], '3')));
  expect(await screen.findByText('Réacteur de Flux — niveau 3')).toBeVisible();
  expect(screen.getByRole('heading', { level: 1, name: 'La mémoire de votre empire.' })).toBeVisible();
  const reads = fetch.mock.calls.filter(([url]) => String(url).includes('/construction-history'));
  expect(reads[0][0]).toBe(`/api/game/${universe}/colonies/${colonyId}/construction-history`);
  expect(reads[0][1]?.headers).toEqual({ 'X-Game-Request': 'bootstrap' });
  fireEvent.click(screen.getByRole('button', { name: 'Afficher des constructions plus anciennes' }));
  expect(await screen.findByText('Nœud de données — niveau 2')).toBeVisible();
  expect(fetch.mock.calls.some(([url]) => String(url).endsWith('construction-history?before_sequence=3'))).toBe(true);
  expect(screen.getAllByText('Complexe d’extraction construit')).toHaveLength(2); // orders 3 and 4, no duplicate of 3
  expect(screen.queryByRole('button', { name: 'Afficher des constructions plus anciennes' })).toBeNull();
  // Reading never sends a command.
  expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});

test('filters keep one category; an older Game server without the route shows a partial unavailability', async () => {
  setup(missing);
  expect(await screen.findByText('Historique des constructions terminées : ce serveur Game ne le propose pas encore.')).toBeVisible();
  const filters = screen.getByRole('group', { name: 'Filtrer les rapports' });
  const constructions = within(filters).getByRole('button', { name: /Constructions/ });
  fireEvent.click(constructions);
  expect(constructions).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByText('Aucun rapport « Constructions » pour le moment.')).toBeVisible();
  await waitFor(() => expect(screen.getByText('Indisponible sur ce serveur')).toBeVisible());
});

test('the history contract is validated strictly (decimal text sequences, bounded page, same colony)', () => {
  expect(validHistory(page([entry(1)], null), colonyId)).toBe(true);
  expect(validHistory({ ...page([entry(1)], null), entries: [{ ...entry(1), sequence: 1 }] }, colonyId)).toBe(false);
  expect(validHistory(page([entry(1)], '0'), colonyId)).toBe(false);
  expect(validHistory(page([entry(1)], null), empireId)).toBe(false);
  expect(validHistory(page(Array.from({ length: 51 }, (_, i) => entry(i + 1)), null), colonyId)).toBe(false);
});
