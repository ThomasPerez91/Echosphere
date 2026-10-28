import { cleanup, render, screen, fireEvent, act } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from './App';

const ready = { ok: true, json: async () => ({ status: 'ready' }) };
beforeEach(() => { window.history.replaceState(null, '', '/'); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function navigate(hash: string) {
  act(() => {
    window.history.pushState(null, '', hash);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

test('shows real service readiness and explicitly unavailable stocks', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ready));
  render(<App />);
  expect(screen.getByRole('heading', { level: 1, name: 'Votre horizon commence ici.' })).toBeInTheDocument();
  expect(await screen.findByRole('status')).toHaveTextContent('Services disponibles');
  expect(screen.getAllByText('Stocks non disponibles')).toHaveLength(3);
  expect(screen.getByRole('link', { name: 'Empire' })).toHaveAttribute('aria-current', 'page');
});

test('can retry after a failed request without losing the current destination', async () => {
  const fetch = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(ready);
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  expect(await screen.findByRole('status')).toHaveTextContent('Connexion indisponible');
  fireEvent.click(screen.getByRole('button', { name: 'Vérifier la connexion' }));
  expect(await screen.findByText('Services disponibles', { selector: '[role="status"]' })).toBeInTheDocument();
  navigate('#research');
  expect(screen.getByRole('link', { name: 'Recherche' })).toHaveAttribute('aria-current', 'page');
  expect(fetch).toHaveBeenCalledTimes(2);
});

test.each([
  { ok: false, json: async () => ({ detail: 'Database unavailable' }) },
  { ok: true, json: async () => ({ status: 'unexpected' }) },
  { ok: true, json: async () => { throw new Error('invalid json'); } },
])('rejects unsuccessful or malformed readiness responses', async response => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
  render(<App />);
  expect(await screen.findByText('Connexion indisponible', { selector: '[role="status"]' })).toBeInTheDocument();
});

test('times out, enables retry and ignores a late successful response', async () => {
  vi.useFakeTimers();
  let resolve: (value: typeof ready) => void = () => {};
  const fetch = vi.fn(() => new Promise(r => { resolve = r; }));
  vi.stubGlobal('fetch', fetch);
  render(<App />);
  expect(screen.getByRole('button', { name: 'Vérification…' })).toBeDisabled();
  await act(() => vi.advanceTimersByTimeAsync(5000));
  expect(screen.getByRole('status')).toHaveTextContent('Connexion indisponible');
  await act(async () => { resolve(ready); });
  expect(screen.getByRole('status')).toHaveTextContent('Connexion indisponible');
  expect(screen.getByRole('button', { name: 'Vérifier la connexion' })).toBeEnabled();
});

test('aborts an in-flight request when unmounted', () => {
  const fetch = vi.fn(() => new Promise(() => {}));
  vi.stubGlobal('fetch', fetch);
  const { unmount } = render(<App />);
  const signal = (fetch.mock.calls as unknown as [string, RequestInit][])[0][1].signal;
  unmount();
  expect(signal?.aborted).toBe(true);
});

test('supports deep links, route changes, focus and browser history events', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ready));
  window.history.replaceState(null, '', '#galaxy');
  render(<App />);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Au-delà du connu.');
  navigate('#colony');
  expect(screen.getByRole('heading', { level: 1 })).toHaveFocus();
  expect(screen.getByRole('link', { name: 'Colonie' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByText('Colonie : espace en préparation')).toBeInTheDocument();
  expect(screen.getByText(/Aucun ordre de jeu/)).toBeInTheDocument();
  navigate('#galaxy');
  expect(screen.getByRole('link', { name: 'Galaxie' })).toHaveAttribute('aria-current', 'page');
  await screen.findByText('Services disponibles', { selector: '[role="status"]' });
});

test('more navigation closes after selection and skip link focuses content', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ready));
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Plus' }));
  expect(screen.getByRole('button', { name: 'Plus' })).toHaveAttribute('aria-expanded', 'true');
  navigate('#reports');
  expect(screen.getByRole('button', { name: 'Plus' })).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(screen.getByRole('link', { name: 'Aller au contenu' }));
  expect(screen.getByRole('main')).toHaveFocus();
  await screen.findByText('Services disponibles', { selector: '[role="status"]' });
});

test('unknown destinations give a route back to Empire', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ready));
  window.history.replaceState(null, '', '#missing');
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Page introuvable' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Revenir à l’Empire' })).toHaveAttribute('href', '#empire');
  await screen.findByText('Services disponibles', { selector: '[role="status"]' });
});
