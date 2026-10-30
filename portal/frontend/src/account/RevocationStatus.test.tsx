import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { RevocationStatus } from './RevocationStatus';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test('pending changes to complete only after Game acknowledgement, with read-only refresh', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ state: 'pending' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ state: 'acknowledged' }) });
  vi.stubGlobal('fetch', fetcher); render(<RevocationStatus />);
  fireEvent.click(await screen.findByRole('button', { name: 'Vérifier la déconnexion des parties' }));
  expect(await screen.findByText(/Déconnexion terminée/)).toBeVisible();
  expect(fetcher.mock.calls.every(call => call[1].method === undefined)).toBe(true);
});
test('missing or expired capability never reports remote completion', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }));
  const { container } = render(<RevocationStatus />);
  expect(container).toBeEmptyDOMElement();
});
