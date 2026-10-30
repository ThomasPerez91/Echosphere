import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { AccountAccess } from './AccountAccess';

const snapshot = {
  status: 'authenticated', user: { email: 'player@example.org', email_verified: true },
  csrf_token: 'session-proof', session_id: 'one', sessions: [{ id: 'one', current: true }],
};
function installFetcher(fetcher: (url: string, options?: RequestInit) => unknown) {
  vi.stubGlobal('fetch', (url: string, options?: RequestInit) => url === '/api/lobby/memberships'
    ? Promise.resolve({ ok: true, json: async () => ({ memberships: [], revocations: [] }) })
    : url === '/api/mfa/status'
    ? Promise.resolve({ ok: true, json: async () => ({ enabled: false, totp: false, credentials: [] }) })
    : fetcher(url, options));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('automatic bootstrap is a read and explicit refresh is a CSRF protected action', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => snapshot });
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} />);
  expect(await screen.findByText('player@example.org')).toBeVisible();
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe('/api/auth/sessions');
  expect(fetcher.mock.calls[0][1].method).toBeUndefined();
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser mes connexions' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
  expect(fetcher.mock.calls[1][0]).toBe('/api/auth/navigation');
  expect(fetcher.mock.calls[1][1].headers['X-CSRF-Token']).toBe('session-proof');
  expect(document.body.textContent).not.toContain('session-proof');
});

test('login obtains a bound challenge and never puts secrets in browser storage', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(url.endsWith('/sessions')
    ? { ok: false, status: 401, json: async () => ({}) }
    : url.endsWith('/challenge') ? { ok: true, json: async () => ({ csrf_token: 'login-proof' }) }
    : { ok: true, json: async () => snapshot }));
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} />);
  fireEvent.click(screen.getByRole('button', { name: 'Se connecter à mon compte' }));
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'Test password for C03 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir ma session' }));
  expect(await screen.findByText('player@example.org')).toBeVisible();
  const calls = vi.mocked(fetcher).mock.calls as unknown as [string, RequestInit][];
  const submitted = calls.find(item => item[0].endsWith('/login'));
  expect(submitted?.[1].headers).toMatchObject({ 'X-CSRF-Token': 'login-proof' });
  expect(JSON.parse(submitted?.[1].body as string)).toEqual({ email: 'player@example.org', password: 'Test password for C03 !' });
  expect(localStorage.length + sessionStorage.length).toBe(0);
});

test('logout reports pending remote revocation and does not claim universal disconnection', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => snapshot })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ current_session_closed: true, game_revocation: 'pending' }) });
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} />);
  fireEvent.click(await screen.findByRole('button', { name: /^Se déconnecter$/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Déconnexion des parties en attente');
  expect(screen.queryByText('player@example.org')).not.toBeInTheDocument();
});

test('device cap refusal is actionable and does not expose server response content', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(url.endsWith('/challenge')
    ? { ok: true, json: async () => ({ csrf_token: 'login-proof' }) }
    : { ok: false, status: 409, json: async () => ({ error: { code: 'device_limit_reached', private: 'never display this' } }) }));
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} />);
  fireEvent.click(screen.getByRole('button', { name: 'Se connecter à mon compte' }));
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'Test password for C03 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir ma session' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Fermez une connexion');
  expect(document.body.textContent).not.toContain('never display this');
});


test('another tab rotating authentication reloads proof without replaying the action', async () => {
  const changed = { ...snapshot, csrf_token: 'new-proof' };
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => snapshot })
    .mockResolvedValueOnce({ ok: false, status: 403, json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, json: async () => changed });
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Actualiser mes connexions' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Vérifiez son état puis réessayez');
  expect(fetcher).toHaveBeenCalledTimes(3);
  expect(fetcher.mock.calls.filter(item => item[1].method === 'POST')).toHaveLength(1);
});

test('a delayed automatic read cannot restore a session predating the login transition', async () => {
  let finish: (value: unknown) => void = () => {};
  const delayed = new Promise(resolve => { finish = resolve; });
  const fetcher = vi.fn((url: string) => url.endsWith('/sessions') ? delayed : Promise.resolve(
    url.endsWith('/challenge') ? { ok: true, json: async () => ({ csrf_token: 'login-proof' }) }
      : { ok: true, json: async () => snapshot }));
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} />);
  fireEvent.click(screen.getByRole('button', { name: 'Se connecter à mon compte' }));
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'Test password for C03 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir ma session' }));
  expect(await screen.findByText('player@example.org')).toBeVisible();
  await act(async () => {
    finish({ ok: true, json: async () => ({ ...snapshot, user: { email: 'obsolete@example.org', email_verified: true } }) });
    await delayed;
  });
  expect(screen.queryByText('obsolete@example.org')).not.toBeInTheDocument();
  expect(screen.getByText('player@example.org')).toBeVisible();
});
