import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { SystemView } from './components/SystemView';
import { validSystemDetail } from './galaxy/api';
import { detail, empire, origin, otherEmpire, near, universe, withoutColonyRead } from '../tests/systemFixture';
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
  expect(await screen.findByRole('heading', { name: 'Système d’origine' })).toBeVisible();
  // The own world is third in server order, yet opens selected so its action is not hidden.
  expect(screen.getByRole('heading', { name: 'Nouvelle Aube' })).toBeVisible();
  expect(screen.getByRole('button', { name: /3 · Nouvelle Aube/ })).toHaveAttribute('aria-pressed', 'true');
  const target = `#universe/${universe}/colony/overview/${detail().colony_links![0].colony_id}`;
  expect(screen.getByRole('link', { name: 'Voir ma colonie' })).toHaveAttribute('href', target);
  expect(screen.getByRole('link', { name: 'Ouvrir la colonie Nouvelle Aube →' })).toHaveAttribute('href', target);
  expect(screen.getByText(/Présence propre observée : Nouvelle Aube/)).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Mondes connus' })).toBeVisible();
  expect(screen.getByText(/Cartographié/)).toBeVisible();
  expect(fetcher.mock.calls.every(call => call.length > 0)).toBe(true);
  // The System View also reads the Galaxy and Fleet projections (actions); every read is a GET.
  for (const call of fetcher.mock.calls as unknown as [string, RequestInit][]) {
    expect(call[1]?.method).toBeUndefined();
  }
  const reads = (fetcher.mock.calls as unknown as [string, RequestInit][]).filter(call => call[0].includes('/systems/'));
  expect(reads.length).toBeGreaterThan(0);
  for (const call of reads) {
    expect(call[0]).toBe(`/api/game/${universe}/galaxy/${empire}/systems/${origin}`);
    expect(call[1].method).toBeUndefined();
    expect(call[1].headers).toEqual({ 'X-Game-Request': 'bootstrap' });
  }
});

test('MAPPED shows durable structure and says presence information unavailable', async () => {
  setup(detail('MAPPED'));
  await screen.findByRole('heading', { name: 'Système d’origine' });
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
  setup(withoutColonyRead());
  expect(await screen.findByText('Présence propre observée')).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Voir ma colonie' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Ouvrir la colonie/ })).not.toBeInTheDocument();
});

test('a response carrying Colony identifiers without colony.read is refused, not hidden', async () => {
  const leaked = withoutColonyRead(); leaked.observation = { own_colony_ids: [detail().colony_links![0].colony_id] };
  expect(validSystemDetail(withoutColonyRead(), empire, origin)).toBe(true);
  expect(validSystemDetail(leaked, empire, origin)).toBe(false);
  setup(leaked);
  expect(await screen.findByRole('alert')).toHaveTextContent('momentanément indisponible');
  expect(screen.queryByText('Nouvelle Aube')).not.toBeInTheDocument();
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
  expect(await screen.findByRole('heading', { name: 'Current scope' })).toBeVisible();
  resolveOld(json(detail()));
  await waitFor(() => expect(screen.queryByRole('heading', { name: 'Système d’origine' })).not.toBeInTheDocument());
});

test('detail validator refuses hidden DETECTED structure and foreign scope', () => {
  expect(validSystemDetail(detail(), empire, origin)).toBe(true);
  expect(validSystemDetail(detail(), otherEmpire, origin)).toBe(false);
  expect(validSystemDetail({ ...projection().systems[1], routes: [] }, empire, near)).toBe(false);
  const bad = detail(); bad.permissions = ['galaxy.read'];
  expect(validSystemDetail(bad, empire, origin)).toBe(false);
});

test('v0.5: a world without own colony offers "Coloniser…" into the Fleet flow, never "Libre"', async () => {
  const body = { ...detail(), colonization: true, permissions: ['galaxy.read', 'colony.read', 'fleet.command', 'colony.expand'] };
  setup(body);
  // The own world opens first: its colony link, no colonization offer.
  expect(await screen.findByRole('link', { name: 'Voir ma colonie' })).toBeVisible();
  expect(screen.queryByRole('link', { name: 'Coloniser…' })).not.toBeInTheDocument();
  screen.getByRole('button', { name: /1 · Rocher Pâle/ }).click();
  const link = await screen.findByRole('link', { name: 'Coloniser…' });
  expect(link).toHaveAttribute('href', `#universe/${universe}/fleets/colonize/${empire}/${origin}/0aaaaaaa-0000-4000-8000-000000000001`);
  expect(screen.getByText(/Occupation actuelle inconnue/)).toBeVisible();
  expect(screen.queryByText(/\bLibre\b/)).not.toBeInTheDocument();
});

test('no colonization offer without the ruleset or without colony.expand', async () => {
  setup({ ...detail(), colonization: false, permissions: ['galaxy.read', 'colony.read', 'fleet.command', 'colony.expand'] });
  (await screen.findByRole('button', { name: /1 · Rocher Pâle/ })).click();
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Rocher Pâle' })).toBeVisible());
  expect(screen.queryByRole('link', { name: 'Coloniser…' })).not.toBeInTheDocument();
  cleanup();
  setup({ ...detail(), colonization: true, permissions: ['galaxy.read', 'colony.read', 'fleet.command'] });
  (await screen.findByRole('button', { name: /1 · Rocher Pâle/ })).click();
  await waitFor(() => expect(screen.getByText(/Occupation actuelle inconnue/)).toBeVisible());
  expect(screen.queryByRole('link', { name: 'Coloniser…' })).not.toBeInTheDocument();
});

test('v0.7: "Attaquer…" opens the Fleet ATTACK flow and never states occupation or defence', async () => {
  setup({ ...detail(), colonization: true, combat: true,
    permissions: ['galaxy.read', 'colony.read', 'fleet.command', 'combat.read', 'combat.attack'] });
  (await screen.findByRole('button', { name: /1 · Rocher Pâle/ })).click();
  const link = await screen.findByRole('link', { name: 'Attaquer…' });
  expect(link).toHaveAttribute('href', `#universe/${universe}/fleets/attack/${empire}/${origin}/0aaaaaaa-0000-4000-8000-000000000001`);
  expect(screen.getByText('Occupation et défense non confirmées.')).toBeVisible();
  cleanup();
  setup({ ...detail(), colonization: true, combat: true, permissions: ['galaxy.read', 'colony.read', 'fleet.command', 'combat.read'] });
  (await screen.findByRole('button', { name: /1 · Rocher Pâle/ })).click();
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Rocher Pâle' })).toBeVisible());
  expect(screen.queryByRole('link', { name: 'Attaquer…' })).not.toBeInTheDocument();
});

// Refonte du 11/11/2026: with the Galaxy and Fleet projections of the same Empire, every action
// of the system is launched here through the command map's planner (prototype fixtures).
test('the System View launches the actions of a world, an opportunity or the system through the shared planner', async () => {
  const { fleetFixture, galaxyFixture, ids } = await import('./prototype/fixtures');
  const g = galaxyFixture(), f = fleetFixture(), id = g.empire.id, u = '90000000-0000-4000-8000-000000000001';
  const vesta = g.systems.find(s => s.id === ids.vesta)!;
  const body = { ...vesta, server_time: g.server_time, empire_id: id, permissions: g.permissions, colonization: true, combat: true,
    routes: [{ id: '70000000-0000-4000-8000-000000000001', neighbor: { id: ids.home, state: 'MONITORED', name: 'Aube' } }],
    presences: [], colony_links: [] };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url.includes('/systems/') ? json(body)
    : url.endsWith('/galaxy') || url.endsWith('/fleets') ? json({ empires: [g.empire] })
    : url.endsWith(`/galaxy/${id}`) ? json(g) : url.endsWith(`/fleets/${id}`) ? json(f) : json({ error: { code: 'unavailable' } }, 503)));
  render(<SystemView universe={u} empire={id} system={ids.vesta} onSessionLost={vi.fn()} csrf={'c'.repeat(64)} />);
  expect(await screen.findByRole('heading', { level: 1, name: 'Vesta' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Vesta II' })).toBeVisible();
  expect(await screen.findByRole('button', { name: 'Coloniser Vesta II' })).toBeVisible();
  expect(screen.getByText(/Occupation actuelle inconnue/)).toBeVisible();
  expect(screen.queryByText(/\bLibre\b/)).not.toBeInTheDocument();
  // An opportunity marker selects the deposit and offers its extraction.
  fireEvent.click(screen.getByRole('button', { name: 'Ceinture métallique (gisement)' }));
  expect(screen.getByRole('heading', { name: 'Ceinture métallique' })).toBeVisible();
  expect(screen.getByRole('button', { name: /Extraire : Ceinture métallique/ })).toBeInTheDocument();
  // System-wide action: the same planner as the map, nothing sent before the confirmation.
  fireEvent.click(screen.getByRole('button', { name: 'Déplacer une flotte' }));
  expect(await screen.findByRole('heading', { name: 'Déplacer une flotte' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Annuler' }));
  expect(await screen.findByRole('button', { name: 'Déplacer une flotte' })).toBeVisible();
});
