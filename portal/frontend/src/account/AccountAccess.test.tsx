import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { AccountAccess } from './AccountAccess';

const snapshot = {
  status: 'authenticated', user: { email: 'player@example.org', email_verified: true },
  csrf_token: 'session-proof', session_id: 'one', sessions: [{ id: 'one', current: true }],
};
function installFetcher(fetcher: (url: string, options?: RequestInit) => unknown) {
  vi.stubGlobal('fetch', (url: string, options?: RequestInit) => url === '/api/auth/revocation-status'
    ? Promise.resolve({ ok: false, status: 404, json: async () => ({ error: { code: 'receipt_expired' } }) })
    : url === '/api/lobby/memberships'
    ? Promise.resolve({ ok: true, json: async () => ({ memberships: [], revocations: [] }) })
    : url === '/api/mfa/status'
    ? Promise.resolve({ ok: true, json: async () => ({ enabled: false, totp: false, credentials: [] }) })
    : fetcher(url, options));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('automatic bootstrap is a read and explicit refresh is a CSRF protected action', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => snapshot });
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} page="account" />);
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
  render(<AccountAccess verificationToken={null} page="login" />);
  fireEvent.change(await screen.findByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'Test password for C03 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir ma session' }));
  expect(await screen.findByRole('heading', { name: 'Mes parties' })).toBeVisible();
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
  render(<AccountAccess verificationToken={null} page="account" />);
  fireEvent.click(await screen.findByRole('button', { name: /^Se déconnecter$/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Déconnexion des parties en attente');
  expect(screen.queryByText('player@example.org')).not.toBeInTheDocument();
});

test('device cap refusal is actionable and does not expose server response content', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(url.endsWith('/sessions')
    ? { ok: false, status: 401, json: async () => ({}) }
    : url.endsWith('/challenge') ? { ok: true, json: async () => ({ csrf_token: 'login-proof' }) }
    : { ok: false, status: 409, json: async () => ({ error: { code: 'device_limit_reached', private: 'never display this' } }) }));
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} page="login" />);
  fireEvent.change(await screen.findByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
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
  render(<AccountAccess verificationToken={null} page="account" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Actualiser mes connexions' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Vérifiez son état puis réessayez');
  expect(fetcher).toHaveBeenCalledTimes(3);
  expect(fetcher.mock.calls.filter(item => item[1].method === 'POST')).toHaveLength(1);
});

test('a delayed bootstrap is aborted on unmount and cannot restore stale UI', async () => {
  let finish: (value: unknown) => void = () => {};
  let signal: AbortSignal | undefined;
  const delayed = new Promise(resolve => { finish = resolve; });
  installFetcher((_url, options) => { signal = options?.signal as AbortSignal; return delayed; });
  const { unmount } = render(<AccountAccess verificationToken={null} />);
  expect(screen.getByText('Vérification de votre compte…')).toBeVisible();
  unmount();
  expect(signal?.aborted).toBe(true);
  await act(async () => { finish({ ok: true, json: async () => snapshot }); await delayed; });
  expect(screen.queryByText('player@example.org')).not.toBeInTheDocument();
});

test('a failed bootstrap offers read-only retry instead of a false signed-out state', async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce({ ok: true, json: async () => snapshot });
  installFetcher(fetcher); render(<AccountAccess verificationToken={null} page="account" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Vérifier mon compte' }));
  expect(await screen.findByText('player@example.org')).toBeVisible();
  expect(fetcher.mock.calls.every(call => call[1].method === undefined)).toBe(true);
});

test('StrictMode aborted first bootstrap never overrides the current successful request', async () => {
  const { StrictMode } = await import('react');
  let calls = 0;
  installFetcher((_url, options) => ++calls === 1 ? new Promise((_resolve, reject) => {
    options?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
  }) : Promise.resolve({ ok: false, status: 401, json: async () => ({}) }));
  render(<StrictMode><AccountAccess verificationToken={null} /></StrictMode>);
  expect(await screen.findByRole('button', { name: 'Se connecter à mon compte' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'Compte indisponible' })).not.toBeInTheDocument();
});

test('a normal login drops the previous revocation receipt status from the screen', async () => {
  let loggedIn = false;
  vi.stubGlobal('fetch', (url: string) => Promise.resolve(url === '/api/auth/revocation-status'
    ? loggedIn ? { ok: false, status: 404, json: async () => ({ error: { code: 'receipt_expired' } }) }
      : { ok: true, status: 200, json: async () => ({ state: 'pending', scope: 'device', expires_at: '2026-10-30T12:15:00+00:00' }) }
    : url === '/api/lobby/memberships' ? { ok: true, json: async () => ({ memberships: [], revocations: [] }) }
    : url === '/api/mfa/status' ? { ok: true, json: async () => ({ enabled: false, totp: false, credentials: [] }) }
    : url.endsWith('/sessions') ? { ok: false, status: 401, json: async () => ({}) }
    : url.endsWith('/challenge') ? { ok: true, json: async () => ({ csrf_token: 'login-proof' }) }
    : (loggedIn = true, { ok: true, json: async () => snapshot })));
  render(<AccountAccess verificationToken={null} page="account" />);
  expect(await screen.findByText('Déconnexion encore en attente sur certains services Game.')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'Test password for C03 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir ma session' }));
  expect(await screen.findByText('player@example.org')).toBeVisible();
  await waitFor(() => expect(screen.queryByText('Déconnexion encore en attente sur certains services Game.')).toBeNull());
});

test('the account page keeps the optional second factor folded away, explained in plain words', async () => {
  installFetcher(vi.fn().mockResolvedValue({ ok: true, json: async () => snapshot }));
  render(<AccountAccess verificationToken={null} page="account" />);
  expect(await screen.findByText('player@example.org')).toBeVisible();
  const advanced = screen.getByText('Sécurité avancée').closest('details')!;
  expect(advanced).not.toHaveAttribute('open');
  expect(screen.getByText(/Vous pouvez jouer sans l’activer/)).not.toBeVisible();
});

test('login asks for a second factor only when the account uses one', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(url.endsWith('/sessions')
    ? { ok: false, status: 401, json: async () => ({}) }
    : url.endsWith('/challenge') ? { ok: true, json: async () => ({ csrf_token: 'login-proof' }) }
    : { ok: false, status: 401, json: async () => ({ error: { code: 'mfa_required' } }) }));
  installFetcher(fetcher);
  render(<AccountAccess verificationToken={null} page="login" />);
  fireEvent.change(await screen.findByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  expect(screen.queryByLabelText('Preuve MFA')).toBeNull();
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'Test password for C03 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir ma session' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('double vérification');
  expect(screen.getByLabelText('Preuve MFA')).toBeVisible();
});

test('signed in, a new SOLO game is created once with the chosen opponents, then the games page opens', async () => {
  const posted: RequestInit[] = [];
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (url === '/api/lobby/universes') { posted.push(options!); return Promise.resolve({ ok: true, status: 200, json: async () => ({ universe_id: 'u', status: 'starting' }) }); }
    return Promise.resolve({ ok: true, json: async () => snapshot });
  });
  installFetcher(fetcher);
  const onNavigate = vi.fn();
  render(<AccountAccess verificationToken={null} page="new-game" onNavigate={onNavigate} />);
  expect(await screen.findByRole('heading', { name: 'Nouvelle partie' })).toBeVisible();
  fireEvent.change(screen.getByLabelText('Nom de l’univers'), { target: { value: '  Frontière d’Orion ' } });
  // 100 systems hold 4 Empires: one player + 3 AI at most.
  fireEvent.change(screen.getByLabelText('IA expansionnistes'), { target: { value: '5' } });
  expect(screen.getByLabelText('IA expansionnistes')).toHaveValue(2);
  fireEvent.click(screen.getByRole('button', { name: 'Créer la partie' }));
  await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('/parties'));
  expect(posted).toHaveLength(1);
  expect(posted[0].headers).toMatchObject({ 'X-CSRF-Token': 'session-proof' });
  const body = JSON.parse(posted[0].body as string);
  expect(body).toMatchObject({ name: 'Frontière d’Orion', family: 'solo', profiles: ['economic_cautious', 'expansionist', 'expansionist'] });
  expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(body.size).toBe(100);
  expect(Object.keys(body).sort()).toEqual(['family', 'name', 'profiles', 'request_id', 'size']); // never a seed from the browser
});

test('a lost creation answer is retried with the same request id', async () => {
  const ids: string[] = [];
  let first = true;
  installFetcher((url: string, options?: RequestInit) => {
    if (url === '/api/lobby/universes') {
      ids.push(JSON.parse(options!.body as string).request_id);
      if (first) { first = false; return Promise.reject(new TypeError('network')); }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ universe_id: 'u', status: 'starting' }) });
    }
    return Promise.resolve({ ok: true, json: async () => snapshot });
  });
  render(<AccountAccess verificationToken={null} page="new-game" />);
  fireEvent.change(await screen.findByLabelText('Nom de l’univers'), { target: { value: 'Orion' } });
  fireEvent.click(screen.getByRole('button', { name: 'Créer la partie' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('sans créer deux parties');
  fireEvent.click(screen.getByRole('button', { name: 'Créer la partie' }));
  await waitFor(() => expect(ids).toHaveLength(2));
  expect(ids[0]).toBe(ids[1]);
});

test('a multiplayer game sends humans, the galaxy size and the invitation mode, within its Empire cap', async () => {
  const posted: string[] = [];
  installFetcher((url: string, options?: RequestInit) => {
    if (url === '/api/lobby/universes') { posted.push(options!.body as string); return Promise.resolve({ ok: true, status: 200, json: async () => ({ universe_id: 'u', status: 'starting' }) }); }
    return Promise.resolve({ ok: true, json: async () => snapshot });
  });
  render(<AccountAccess verificationToken={null} page="new-game" />);
  fireEvent.change(await screen.findByLabelText('Nom de l’univers'), { target: { value: 'Coalition' } });
  fireEvent.click(screen.getByLabelText('Multijoueur'));
  fireEvent.change(screen.getByLabelText('Joueurs humains'), { target: { value: '3' } });
  // 3 humans on 100 systems (4 Empires): one AI left, the second profile drops to zero.
  expect(screen.getByLabelText('IA prudentes')).toHaveValue(1);
  expect(screen.getByLabelText('IA expansionnistes')).toHaveValue(0);
  expect(screen.queryByRole('option', { name: '5 joueurs' })).toBeNull();
  fireEvent.click(screen.getByLabelText(/1 000 systèmes/));
  expect(screen.getByRole('option', { name: '10 joueurs' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Joueurs humains'), { target: { value: '10' } });
  fireEvent.change(screen.getByLabelText('IA expansionnistes'), { target: { value: '29' } });
  fireEvent.click(screen.getByLabelText('Invitation par email'));
  fireEvent.click(screen.getByRole('button', { name: 'Créer la partie' }));
  await waitFor(() => expect(posted).toHaveLength(1));
  const body = JSON.parse(posted[0]);
  expect(body).toMatchObject({ family: 'private', humans: 10, invite: 'email', size: 1000 });
  expect(body.profiles).toHaveLength(30); // 1 cautious + 29 expansionists, 40 Empires
});

test('a received email invitation is accepted from the games page, then the lobby is re-read', async () => {
  let accepted = false;
  const lobbyReads: number[] = [];
  vi.stubGlobal('fetch', (url: string, options?: RequestInit) => Promise.resolve(
    url === '/api/auth/revocation-status' ? { ok: false, status: 404, json: async () => ({ error: { code: 'receipt_expired' } }) }
    : url === '/api/lobby/memberships' ? (lobbyReads.push(1), { ok: true, json: async () => ({ memberships: [], revocations: [], creations: [],
      invitations: accepted ? [] : [{ id: 'inv-1', universe_id: 'u', name: 'Coalition', expires_at: '2026-11-16T09:00:00Z' }] }) })
    : url === '/api/lobby/invitations/accept' ? (accepted = JSON.parse(options!.body as string).invitation_id === 'inv-1', { ok: true, status: 200, json: async () => ({ status: 'joined' }) })
    : { ok: true, json: async () => snapshot }));
  render(<AccountAccess verificationToken={null} page="games" />);
  expect(await screen.findByText('Coalition')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Accepter' }));
  await waitFor(() => expect(accepted).toBe(true));
  await waitFor(() => expect(screen.queryByText('Coalition')).toBeNull());
  expect(lobbyReads.length).toBeGreaterThanOrEqual(2);
});

test('the join page uses the link token once signed in and explains a replaced link', async () => {
  const bodies: string[] = [];
  let reply = { ok: false, status: 404, json: async () => ({ error: { code: 'invitation_not_found' } }) };
  installFetcher((url: string, options?: RequestInit) => {
    if (url === '/api/lobby/invitations/accept') { bodies.push(options!.body as string); return Promise.resolve(reply); }
    return Promise.resolve({ ok: true, json: async () => snapshot });
  });
  const onNavigate = vi.fn();
  const token = 'a'.repeat(43);
  render(<AccountAccess verificationToken={null} page="join" inviteToken={token} onNavigate={onNavigate} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Rejoindre la partie' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Ce lien n’est plus valable');
  reply = { ok: true, status: 200, json: async () => ({ status: 'joined' }) } as unknown as typeof reply;
  fireEvent.click(screen.getByRole('button', { name: 'Rejoindre la partie' }));
  await waitFor(() => expect(onNavigate).toHaveBeenCalledWith('/parties'));
  expect(JSON.parse(bodies[0])).toEqual({ token });
});

test('a delayed or refused creation says so instead of an endless "Création en cours"', async () => {
  vi.stubGlobal('fetch', (url: string) => Promise.resolve(
    url === '/api/auth/revocation-status' ? { ok: false, status: 404, json: async () => ({ error: { code: 'receipt_expired' } }) }
    : url === '/api/lobby/memberships' ? { ok: true, json: async () => ({ memberships: [], revocations: [], invitations: [], creations: [
      { universe_id: 'u1', name: 'Lente', created_at: '2026-11-09T09:00:00Z', state: 'delayed' },
      { universe_id: 'u2', name: 'Bloquée', created_at: '2026-11-09T09:00:00Z', state: 'refused' }] }) }
    : { ok: true, json: async () => snapshot }));
  render(<AccountAccess verificationToken={null} page="games" />);
  expect(await screen.findByText('Création retardée')).toBeVisible();
  expect(screen.getByText('Création bloquée')).toBeVisible();
  expect(screen.getByText(/renvoyée automatiquement/)).toBeVisible();
  expect(screen.getByText(/a refusé de démarrer cette partie/)).toBeVisible();
});
