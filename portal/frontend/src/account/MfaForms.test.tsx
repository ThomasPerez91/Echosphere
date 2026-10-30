import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { MfaSettings, MfaRecovery } from './MfaForms';

const ok = (value: unknown) => ({ ok: true, json: async () => value });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('TOTP is activated only after proving the new factor and codes are not stored', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(ok(url.endsWith('/status')
    ? { enabled: false, totp: false, credentials: [] } : url.endsWith('/step-up') ? { proof: 'once' }
    : url.endsWith('/begin') ? { challenge_id: 'enroll', secret: 'MANUAL-SECRET', uri: 'otpauth:private' }
    : { global_logout: true, backup_codes: ['BACKUP-ONLY-ONCE'] })));
  vi.stubGlobal('fetch', fetcher); const outcome = vi.fn();
  render(<MfaSettings csrf="session" onOutcome={outcome} />);
  fireEvent.change(screen.getByLabelText('Mot de passe pour la MFA'), { target: { value: 'Current password long !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Valider cette opération MFA' }));
  expect(await screen.findByText('MANUAL-SECRET')).toBeVisible();
  expect(outcome).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Code de la nouvelle application'), { target: { value: '123456' } });
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer le nouveau TOTP' }));
  await waitFor(() => expect(outcome).toHaveBeenCalledWith({ global_logout: true, backup_codes: ['BACKUP-ONLY-ONCE'] }));
  expect(screen.queryByText('MANUAL-SECRET')).not.toBeInTheDocument();
  const calls = fetcher.mock.calls as unknown as [string, RequestInit][];
  expect(JSON.parse(calls[2][1].body as string).kind).toBe('totp');
  expect(localStorage.length + sessionStorage.length).toBe(0);
});

test('voluntary code regeneration supplies an existing factor and preserves the session', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(ok(url.endsWith('/status')
    ? { enabled: true, totp: true, credentials: [] } : url.endsWith('/step-up') ? { proof: 'once' }
    : { global_logout: false, backup_codes: ['NEW-BACKUP'] })));
  vi.stubGlobal('fetch', fetcher); const outcome = vi.fn();
  render(<MfaSettings csrf="session" onOutcome={outcome} />);
  await screen.findByText(/MFA activée/);
  fireEvent.change(screen.getByLabelText('Opération MFA'), { target: { value: 'backup' } });
  fireEvent.change(screen.getByLabelText('Mot de passe pour la MFA'), { target: { value: 'Current password long !' } });
  fireEvent.change(screen.getByLabelText('Preuve MFA'), { target: { value: 'totp' } });
  fireEvent.change(screen.getByLabelText('Code du facteur enregistré'), { target: { value: '123456' } });
  fireEvent.click(screen.getByRole('button', { name: 'Valider cette opération MFA' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Vos connexions restent actives');
  const calls = fetcher.mock.calls as unknown as [string, RequestInit][];
  expect(JSON.parse(calls.find(([url]) => url.endsWith('/step-up'))![1].body as string).factor).toEqual({ totp: '123456' });
  expect(outcome).toHaveBeenCalledWith({ global_logout: false, backup_codes: ['NEW-BACKUP'] });
});

test('recovery uses its own CSRF context and never calls normal login', async () => {
  const fetcher = vi.fn((url: string) => Promise.resolve(ok(url.endsWith('/challenge') ? { csrf_token: 'preauth' }
    : url.endsWith('/start') ? { csrf_token: 'limited' } : { challenge_id: 'restore', secret: 'NEW-SECRET' })));
  vi.stubGlobal('fetch', fetcher);
  render(<MfaRecovery onBack={vi.fn()} onOutcome={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('Email du compte MFA'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe de récupération MFA'), { target: { value: 'Current password long !' } });
  fireEvent.change(screen.getByLabelText('Code de secours'), { target: { value: 'SECRET-BACKUP' } });
  fireEvent.click(screen.getByRole('button', { name: 'Ouvrir la récupération limitée' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Enregistrer le nouveau facteur' }));
  expect(await screen.findByText('NEW-SECRET')).toBeVisible();
  const calls = fetcher.mock.calls as unknown as [string, RequestInit][];
  expect(calls[2][0]).toBe('/api/mfa/recovery/enroll/begin');
  expect(calls[2][1].headers).toMatchObject({ 'X-CSRF-Token': 'limited' });
  expect(calls.some(([url]) => url.endsWith('/login'))).toBe(false);
});
