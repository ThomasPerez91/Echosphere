import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

test('reports Portal readiness without a gameplay action', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ready', service: 'portal' }) }));
  render(<App />);
  expect(await screen.findByText('Portal disponible')).toBeVisible();
  expect(screen.queryByRole('button', { name: /^jouer$/i })).not.toBeInTheDocument();
});

test('rejects a Game response and recovers on explicit retry', async () => {
  let calls = 0;
  const fetcher = vi.fn((url: string) => url.includes('/auth/')
    ? Promise.resolve({ ok: false, status: 401, json: async () => ({}) })
    : Promise.resolve({ ok: true, json: async () => (++calls === 1 ? { status: 'ready' } : { status: 'ready', service: 'portal' }) }));
  vi.stubGlobal('fetch', fetcher);
  render(<App />);
  expect(await screen.findByText('Portal indisponible')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier à nouveau' }));
  expect(await screen.findByText('Portal disponible')).toBeVisible();
  expect(fetcher.mock.calls.filter(call => call[0] === '/api/ready')).toHaveLength(2);
});

test('network error allows retry instead of reporting readiness', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
  render(<App />);
  expect(await screen.findByText('Portal indisponible')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Vérifier à nouveau' })).toBeEnabled();
});

test('aborts an outstanding request on unmount', () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal('fetch', vi.fn((_url, options) => {
    signal = options.signal;
    return new Promise(() => {});
  }));
  const { unmount } = render(<App />);
  unmount();
  expect(signal?.aborted).toBe(true);
});

test('public home: login and registration are separate pages reached from the header', async () => {
  vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url === '/api/ready'
    ? { ok: true, json: async () => ({ status: 'ready', service: 'portal' }) }
    : { ok: false, status: 401, json: async () => ({ error: { code: 'authentication_required' } }) })));
  render(<App />);
  expect(screen.getByRole('heading', { level: 1, name: /Conquérez les étoiles/ })).toBeVisible();
  expect(screen.queryByLabelText('Adresse email')).toBeNull(); // forms live on their own pages
  expect(screen.getAllByText('Implémentation backend nécessaire').length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('link', { name: 'Connexion' }));
  expect(window.location.pathname).toBe('/connexion');
  expect(await screen.findByRole('button', { name: 'Ouvrir ma session' })).toBeVisible();
  expect(screen.getByRole('heading', { level: 1, name: 'Connexion' })).toBeVisible();
  fireEvent.click(screen.getByRole('link', { name: 'Inscription' }));
  expect(window.location.pathname).toBe('/inscription');
  expect(await screen.findByRole('button', { name: 'Créer le compte' })).toBeVisible();
  window.history.replaceState(null, '', '/');
});
