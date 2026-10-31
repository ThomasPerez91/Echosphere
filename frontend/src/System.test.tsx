import { StrictMode } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { SystemView } from './components/SystemView';
import { validSystemDetail } from './galaxy/api';
import { detail, empire, origin, otherEmpire, near, universe } from '../tests/systemFixture';
import { projection } from '../tests/galaxyFixture';

const json = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(body: unknown = detail(), status = 200) {
  const fetcher = vi.fn(async () => json(body, status));
  vi.stubGlobal('fetch', fetcher);
  const lost = vi.fn();
  render(<StrictMode><SystemView universe={universe} empire={empire} system={origin} onSessionLost={lost} /></StrictMode>);
  return { fetcher, lost };
}

test('MONITORED shows dated actual presence and authorized Colony link; StrictMode sends GET only', async () => {
  const { fetcher } = setup();
  expect(await screen.findByRole('heading', { name: 'Système Système d’origine' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Voir ma colonie' })).toHaveAttribute('href',
    `#universe/${universe}/colony/overview/${detail().colony_links![0].colony_id}`);
  expect(screen.getByText(/Présence propre observée : Nouvelle Aube/)).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Mondes connus' })).toBeVisible();
  expect(screen.getByText(/Cartographié/)).toBeVisible();
  expect(fetcher.mock.calls.every(call => call.length > 0)).toBe(true);
  for (const call of fetcher.mock.calls as unknown as [string, RequestInit][]) {
    expect(call[0]).toBe(`/api/game/${universe}/galaxy/${empire}/systems/${origin}`);
    expect(call[1].method).toBeUndefined();
    expect(call[1].headers).toEqual({ 'X-Game-Request': 'bootstrap' });
  }
});

test('MAPPED shows durable structure and says presence information unavailable', async () => {
  setup(detail('MAPPED'));
  await screen.findByRole('heading', { name: 'Système Système d’origine' });
  expect(screen.getByText('Aucune donnée de présence disponible.')).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Voir ma colonie' })).not.toBeInTheDocument();
  expect(screen.queryByText('Aucune présence dans ce système')).not.toBeInTheDocument();
  expect(screen.getByText(/Dernière observation, ancienne/)).toBeVisible();
});

test('old observations stay explicitly old and never provide a Colony action', async () => {
  const value = detail('MAPPED');
  value.presences = [{ kind: 'own_colony', current: false, observed_at: value.last_seen_at!, colony: null }];
  setup(value);
  expect(await screen.findByText('Ancienne présence propre observée')).toBeVisible();
  expect(screen.getByText(/Cette observation ancienne/)).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Voir ma colonie' })).not.toBeInTheDocument();
});

test('without colony.read presence is generic and protected links are absent', async () => {
  const value = detail(); value.permissions = ['galaxy.read']; value.colony_links = [];
  value.presences![0].colony = null;
  setup(value);
  expect(await screen.findByText('Présence propre observée')).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Voir ma colonie' })).not.toBeInTheDocument();
});

test('DETECTED is limited and never displays full structure', async () => {
  const limited = projection().systems.find(s => s.id === near)!;
  vi.stubGlobal('fetch', vi.fn(async () => json(limited)));
  render(<SystemView universe={universe} empire={empire} system={near} onSessionLost={vi.fn()} />);
  expect(await screen.findByRole('heading', { name: 'Structure encore inconnue' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'Mondes connus' })).not.toBeInTheDocument();
  expect(screen.queryByText('Nouvelle Aube')).not.toBeInTheDocument();
});

test.each([404, 403, 401])('refusal %s reveals no structure', async status => {
  const { lost } = setup({ error: { code: status === 401 ? 'authentication_required' : 'system_not_found' } }, status);
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(screen.queryByText('Nouvelle Aube')).not.toBeInTheDocument();
  if (status === 401) expect(lost).toHaveBeenCalled();
});

test.each(['empire', 'universe'])('late response from another %s never replaces current scope', async changed => {
  let resolveOld!: (reply: ReturnType<typeof json>) => void;
  const next = detail(); next.name = 'Current scope';
  if (changed === 'empire') next.empire_id = otherEmpire;
  const fetcher = vi.fn().mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
    .mockResolvedValue(json(next));
  vi.stubGlobal('fetch', fetcher);
  const lost = vi.fn();
  const view = render(<SystemView universe={universe} empire={empire} system={origin} onSessionLost={lost} />);
  view.rerender(<SystemView universe={changed === 'universe' ? otherEmpire : universe}
    empire={changed === 'empire' ? otherEmpire : empire} system={origin} onSessionLost={lost} />);
  expect(await screen.findByRole('heading', { name: 'Système Current scope' })).toBeVisible();
  resolveOld(json(detail()));
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Système Système d’origine' })).not.toBeInTheDocument());
});

test('detail validator refuses hidden DETECTED structure and foreign scope', () => {
  expect(validSystemDetail(detail(), empire, origin)).toBe(true);
  expect(validSystemDetail(detail(), otherEmpire, origin)).toBe(false);
  expect(validSystemDetail({ ...projection().systems[1], routes: [] }, empire, near)).toBe(false);
  const bad = detail(); bad.permissions = ['galaxy.read'];
  expect(validSystemDetail(bad, empire, origin)).toBe(false);
});
