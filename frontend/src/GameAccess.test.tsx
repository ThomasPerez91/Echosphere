import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';
const universe = '052d4535-79c7-413b-ace3-47c732561fbd';
const current = { universe_id: universe, universe_name: 'Mon univers', csrf_token: 'a'.repeat(64),
  expires_at: '2099-01-01T08:00:00Z', idle_expires_at: '2099-01-01T02:00:00Z',
  access_valid_until: '2099-01-01T08:00:00Z', server_time: '2099-01-01T00:00:00Z', portal_url: 'https://portal.example.org' };
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/'); });
function setup(response: unknown = current, status = 200) {
  const fetcher = vi.fn((url: string, options?: RequestInit) => Promise.resolve({
    ok: url === '/api/ready' || status === 200, status: url === '/api/ready' ? 200 : status,
    json: async () => url === '/api/ready' ? { status: 'ready' } : options?.method === 'POST' && url.endsWith('/logout') ? { status: 'game_logged_out' } : response,
  }));
  vi.stubGlobal('fetch', fetcher); window.history.replaceState(null, '', `#universe/${universe}/empire`);
  render(<App />); return fetcher;
}
test('session context is in the existing shell and only explicit navigation posts activity', async () => {
  const fetcher = setup();
  expect((await screen.findAllByText('Mon univers')).length).toBeGreaterThan(0);
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0);
  expect(screen.getByRole('link', { name: 'Colonie' })).toHaveAttribute('href', `#universe/${universe}/colony`);
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser mon accès' }));
  await waitFor(() => expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(1));
  expect(fetcher.mock.calls.at(-1)?.[1]?.headers).toMatchObject({ 'X-CSRF-Token': 'a'.repeat(64) });
  expect(localStorage.length + sessionStorage.length).toBe(0);
});
test('an expired session hides context and offers a fresh lobby entry, without auto-renewal', async () => {
  const fetcher = setup({ portal_url: current.portal_url }, 401);
  expect(await screen.findByRole('alert')).toHaveTextContent('a expiré');
  expect(screen.getByRole('link', { name: 'Retour au lobby' })).toHaveAttribute('href', current.portal_url);
  expect(screen.queryByRole('button', { name: 'Déconnecter cette partie' })).not.toBeInTheDocument();
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0);
});
test('logout closes only the current Game view and keeps the Portal link', async () => {
  setup(); fireEvent.click(await screen.findByRole('button', { name: 'Déconnecter cette partie' }));
  expect(await screen.findByText(/Partie déconnectée/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'Retour au lobby' })).toBeVisible();
});
test('a malformed private context is hidden and a retry remains read-only', async () => {
  const fetcher = setup({ universe_name: 'private field' });
  expect(await screen.findByRole('alert')).toHaveTextContent('non confirmé');
  expect(document.body.textContent).not.toContain('private field');
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier mon accès' }));
  expect(fetcher.mock.calls.filter(call => call[1]?.method === 'POST')).toHaveLength(0);
});

test('the deadline timer verifies the server without extending activity', async () => {
  vi.useFakeTimers();
  let reads = 0;
  const near = { ...current, idle_expires_at: '2099-01-01T00:00:01Z' };
  const fetcher = vi.fn((url: string) => Promise.resolve({
    ok: url === '/api/ready' || ++reads === 1, status: url === '/api/ready' || reads === 1 ? 200 : 401,
    json: async () => url === '/api/ready' ? { status: 'ready' } : reads === 1 ? near : { portal_url: current.portal_url },
  }));
  vi.stubGlobal('fetch', fetcher); window.history.replaceState(null, '', `#universe/${universe}/empire`);
  const { act } = await import('@testing-library/react');
  await act(async () => { render(<App />); });
  await act(() => vi.advanceTimersByTimeAsync(1101));
  expect(screen.getByRole('alert')).toHaveTextContent('a expiré');
  expect(reads).toBe(2);
  expect(fetcher.mock.calls.every(call => (call as unknown as [string, RequestInit])[1]?.method !== 'POST')).toBe(true);
  vi.useRealTimers();
});
