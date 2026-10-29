import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

test('reports Portal readiness and provides no account or gameplay action', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ready', service: 'portal' }) }));
  render(<App />);
  expect(await screen.findByText('Portal disponible')).toBeVisible();
  expect(screen.queryByRole('button', { name: /connexion|inscription|jouer/i })).not.toBeInTheDocument();
});

test('rejects a Game response and recovers on explicit retry', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ready' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ready', service: 'portal' }) });
  vi.stubGlobal('fetch', fetcher);
  render(<App />);
  expect(await screen.findByText('Portal indisponible')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier à nouveau' }));
  expect(await screen.findByText('Portal disponible')).toBeVisible();
  expect(fetcher).toHaveBeenCalledTimes(2);
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
