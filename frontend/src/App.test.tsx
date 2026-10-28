import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('shows readiness and the development heading', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ready' }) }));
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Echosphere' })).toBeInTheDocument();
  expect(await screen.findByText('connected')).toBeInTheDocument();
});

test('can retry after a failed request', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ready' }) });
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  expect(await screen.findByText('unavailable')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier la connexion' }));
  expect(await screen.findByText('connected')).toBeInTheDocument();
});

test('does not report connected when PostgreSQL is unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Database unavailable' }) }));
  render(<App />);
  expect(await screen.findByText('unavailable')).toBeInTheDocument();
});
