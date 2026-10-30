import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { RecoveryForm, ResetRequestForm, SensitiveSettings } from './SecurityForms';
import { consumeSecurityFragment } from './security-links';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); history.replaceState(null, '', '/'); });

test('sensitive password change obtains an action-bound proof and requests normal login', async () => {
  const signedOut = vi.fn();
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ proof: 'once' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'password_changed' }) });
  vi.stubGlobal('fetch', fetcher);
  render(<SensitiveSettings csrf="session-csrf" onSignedOut={signedOut} />);
  fireEvent.change(screen.getByLabelText('Mot de passe actuel'), { target: { value: 'Current test password !' } });
  fireEvent.change(screen.getByLabelText('Nouveau mot de passe'), { target: { value: 'Replacement test password !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Changer mon mot de passe' }));
  await waitFor(() => expect(signedOut).toHaveBeenCalledOnce());
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ action: 'password_change', current_password: 'Current test password !', new_password: 'Replacement test password !' });
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ proof: 'once', new_password: 'Replacement test password !' });
  expect(fetcher.mock.calls[1][1].headers['X-CSRF-Token']).toBe('session-csrf');
  expect(localStorage.length + sessionStorage.length).toBe(0);
});

test('email request keeps account connected until two confirmations and does not claim delivery', async () => {
  const signedOut = vi.fn();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ proof: 'once' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'confirmation_required' }) }));
  render(<SensitiveSettings csrf="session-csrf" onSignedOut={signedOut} />);
  fireEvent.change(screen.getByLabelText('Opération de sécurité'), { target: { value: 'email_change' } });
  fireEvent.change(screen.getByLabelText('Mot de passe actuel'), { target: { value: 'Current test password !' } });
  fireEvent.change(screen.getByLabelText('Nouvelle adresse email'), { target: { value: 'new@example.org' } });
  fireEvent.click(screen.getByRole('button', { name: 'Demander le changement d’email' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Confirmez l’ancienne et la nouvelle adresse');
  expect(signedOut).not.toHaveBeenCalled();
});

test('reset token is removed from URL and success never calls login', async () => {
  const token = 'a'.repeat(43);
  history.replaceState(null, '', '/#reset-password=' + token);
  const link = consumeSecurityFragment();
  expect(location.hash).toBe('');
  expect(consumeSecurityFragment()).toBeNull();
  if (!link) throw new Error('expected link');
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'password_reset' }) });
  vi.stubGlobal('fetch', fetcher);
  render(<RecoveryForm link={link} onBack={vi.fn()} />);
  for (const name of ['Nouveau mot de passe', 'Confirmer le nouveau mot de passe']) {
    fireEvent.change(screen.getByLabelText(name), { target: { value: 'Replacement test password !' } });
  }
  fireEvent.click(screen.getByRole('button', { name: 'Réinitialiser mon mot de passe' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Connectez-vous à nouveau');
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0][0]).toBe('/api/security/password/reset/confirm');
  expect(document.body.textContent).not.toContain(token);
});

test('unknown reset requests show a generic acknowledgement and malformed private errors are hidden', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'request_received' }) })
    .mockResolvedValueOnce({ ok: false, json: async () => { throw new SyntaxError('private response must not leak'); } });
  vi.stubGlobal('fetch', fetcher);
  render(<ResetRequestForm onBack={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'unknown@example.org' } });
  fireEvent.click(screen.getByRole('button', { name: 'Demander un lien de récupération' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Si les conditions sont remplies');
  fireEvent.click(screen.getByRole('button', { name: 'Demander un lien de récupération' }));
  expect(await screen.findByRole('alert')).not.toHaveTextContent('private response');
});
