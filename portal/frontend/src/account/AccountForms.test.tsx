import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { AccountForms } from './AccountForms';
import { consumeVerificationFragment } from './verification';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('registration posts credentials once, clears password and shows a non-enumerable result', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'request_received' }) });
  vi.stubGlobal('fetch', fetcher);
  render(<AccountForms verificationToken={null} />);
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'C02 strong test phrase 2026 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Créer le compte' }));
  expect(await screen.findByText(/Demande reçue/)).toBeVisible();
  expect(fetcher).toHaveBeenCalledOnce();
  expect(fetcher.mock.calls[0][0]).toBe('/api/accounts/register');
  expect(screen.getByLabelText('Mot de passe')).toHaveValue('');
});

test('verification uses an in-memory token without displaying it or creating a session', async () => {
  const token = 'a'.repeat(43);
  const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'verified' }) });
  vi.stubGlobal('fetch', fetcher);
  render(<AccountForms verificationToken={token} />);
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'C02 strong test phrase 2026 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer mon adresse' }));
  expect(await screen.findByText(/Votre adresse est confirmée/)).toBeVisible();
  expect(fetcher.mock.calls[0][0]).toBe('/api/accounts/email/verify');
  expect(JSON.parse(fetcher.mock.calls[0][1].body).token).toBe(token);
  expect(document.body.textContent).not.toContain(token);
});

test('fragment is consumed before React StrictMode renders', () => {
  const token = 'b'.repeat(43);
  window.history.replaceState(null, '', '/#verify-email=' + token);
  expect(consumeVerificationFragment()).toBe(token);
  expect(window.location.hash).toBe('');
  expect(consumeVerificationFragment()).toBeNull();
});

test('rate errors are shown without reflecting a backend secret', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429, json: async () => ({ detail: 'private-value' }) }));
  render(<AccountForms verificationToken={null} />);
  fireEvent.change(screen.getByLabelText('Adresse email'), { target: { value: 'player@example.org' } });
  fireEvent.change(screen.getByLabelText('Mot de passe'), { target: { value: 'C02 strong test phrase 2026 !' } });
  fireEvent.click(screen.getByRole('button', { name: 'Créer le compte' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Trop de demandes');
  expect(document.body.textContent).not.toContain('private-value');
});
