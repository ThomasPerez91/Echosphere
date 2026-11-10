import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { SandboxPanel } from './sandbox/SandboxPanel';
import { onSandboxChange } from './sandbox/api';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const universe = '00000000-0000-4000-8000-0000000000aa';
const empire = '00000000-0000-4000-8000-0000000000bb';
const colony = '00000000-0000-4000-8000-0000000000cc';
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
const status = { sandbox: true, server_time: '2099-01-01T00:00:00Z', ship_classes: ['probe', 'frigate'],
  colonies: [{ id: colony, name: 'Nouvelle Aube', capacity: '768867' }] };

function setup(sandbox = true) {
  const fetch = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url, init) =>
    !sandbox ? json({ error: { code: 'sandbox_unavailable' } }, 404)
    : init?.method === 'POST' && url.endsWith('/finish') ? json({ ...status, result: { constructions: 2, research: 1, ships: 0 } })
    : init?.method === 'POST' ? json({ ...status, result: { colony_id: colony } })
    : json(status));
  vi.stubGlobal('fetch', fetch);
  let open = false;
  const view = () => <SandboxPanel universe={universe} empire={empire} csrf="csrf" open={open}
    onToggle={value => { open = value; rerender(view()); }} />;
  const { rerender } = render(view());
  return fetch;
}

test('a normal game shows no test tools', async () => {
  const fetch = setup(false);
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole('button', { name: 'Outils de la partie de test' })).toBeNull();
});

test('a test game grants resources, adds ships and completes every queue, then views reread', async () => {
  const fetch = setup();
  const changed = vi.fn();
  const stop = onSandboxChange(changed);
  fireEvent.click(await screen.findByRole('button', { name: 'Outils de la partie de test' }));
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Alliages' }), { target: { value: '5000' } });
  fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }));
  expect(await screen.findByText(/Stocks de Nouvelle Aube mis à jour/)).toBeInTheDocument();
  const grant = fetch.mock.calls.find(([url]) => url.endsWith('/resources'))!;
  expect(JSON.parse(String(grant[1]!.body))).toEqual({ colony_id: colony, alloys: 5000 });
  fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }));
  expect(await screen.findByText(/10 × Sonde ajoutés/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Tout terminer maintenant' }));
  expect(await screen.findByText('Terminé maintenant : 2 constructions, 1 recherche.')).toBeInTheDocument();
  expect(changed).toHaveBeenCalledTimes(3);
  stop();
});
