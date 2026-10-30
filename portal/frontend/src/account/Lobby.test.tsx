import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { Lobby } from './Lobby';

const member = { membership_id: 'membership', universe_id: 'universe', name: 'Ma partie', desired_status: 'active',
  applied_status: null, delivery_state: 'pending', expired: false, valid_until: '2026-10-30T20:00:00Z',
  last_checked_at: null, entry_available: false };
const ok = (value: unknown) => ({ ok: true, json: async () => value });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('empty lobby displays no invented participation and automatic reading has no POST', async () => {
  const fetcher = vi.fn().mockResolvedValue(ok({ memberships: [], revocations: [] }));
  vi.stubGlobal('fetch', fetcher); render(<Lobby csrf="csrf" />);
  expect(await screen.findByText(/Aucune participation/)).toBeVisible();
  expect(fetcher).toHaveBeenCalledOnce();
  expect(fetcher.mock.calls[0][1].method).toBeUndefined();
  expect(screen.queryByRole('button', { name: /Créer|Rejoindre|Entrer/ })).not.toBeInTheDocument();
});

test('explicit refresh distinguishes pending and confirmed without granting entry', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(ok({ memberships: [member], revocations: [{ scope: 'account', state: 'pending', created_at: 'now' }] }))
    .mockResolvedValueOnce(ok({})).mockResolvedValueOnce(ok({ memberships: [{ ...member, delivery_state: 'applied', applied_status: 'active' }],
      revocations: [{ scope: 'account', state: 'acknowledged', created_at: 'now' }] }));
  vi.stubGlobal('fetch', fetcher); render(<Lobby csrf="csrf" />);
  expect(await screen.findByText('Confirmation de Game en attente')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Actualiser mes parties' }));
  expect(await screen.findByText('Participation confirmée par Game')).toBeVisible();
  expect(screen.getByText(/révocation confirmée par les services Game/)).toBeVisible();
  expect(fetcher.mock.calls[1][0]).toBe('/api/auth/navigation');
  expect(fetcher.mock.calls[1][1].headers['X-CSRF-Token']).toBe('csrf');
  expect(fetcher.mock.calls[2][1].method).toBeUndefined();
  expect(screen.queryByRole('button', { name: /Entrer/ })).not.toBeInTheDocument();
});

test('malformed private responses are hidden and service failure does not invent a membership', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ memberships: [{ name: 'private payload' }], revocations: [] })));
  render(<Lobby csrf="csrf" />);
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('indisponible'));
  expect(document.body.textContent).not.toContain('private payload');
});
