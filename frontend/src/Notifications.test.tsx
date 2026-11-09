import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { NotificationBell } from './notifications/NotificationBell';
import { initialSeen, markAll, unread } from './notifications/unread';
import type { ReportEvent } from './reports/events';
import type { useColony } from './hooks/useColony';
import type { useGameSession } from './hooks/useGameSession';
import { colony as colonyId, empire, fighting, universe } from '../tests/fleetFixture';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); try { window.localStorage.clear(); } catch { /* none */ } });

const event = (key: string, at = '2099-01-01T00:00:00Z'): ReportEvent =>
  ({ key, category: 'mission', tone: 'green', icon: 'x.svg', title: key, text: '', at });

test('first visit: past reports are not news, a pending attack always is; opening marks all as read', () => {
  const past = [event('mission-1'), event('research-a'), event('alert-1')];
  const seen = initialSeen(past);
  expect(unread(past, seen).map(e => e.key)).toEqual(['alert-1']);
  const later = [...past, event('construction-9')];
  expect(unread(later, seen).map(e => e.key)).toEqual(['alert-1', 'construction-9']);
  expect(unread(later, markAll(later, seen))).toEqual([]);
});

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));

function setup() {
  const fetch = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) =>
    url.endsWith('/fleets') ? json({ empires: [{ id: empire, name: 'Empire test' }] })
    : url.includes('/fleets/') ? json(fighting())
    : json({ error: { code: 'not_found' } }, 404));
  vi.stubGlobal('fetch', fetch);
  const access = { phase: 'active', session: { csrf_token: 'csrf' }, retry: vi.fn() } as unknown as ReturnType<typeof useGameSession>;
  const colony = { colonies: [{ id: colonyId, name: 'Nouvelle Aube', empire: { id: empire, name: 'Empire test' } }], projection: null,
    refresh: vi.fn() } as unknown as ReturnType<typeof useColony>;
  let open = false;
  const view = () => <NotificationBell universe={universe} access={access} colony={colony} open={open} href={s => `#${s}`} onNavigate={vi.fn()}
    onToggle={value => { open = value; rerender(view()); }} />;
  const { rerender } = render(view());
  return fetch;
}

test('the bell counts a pending attack, lists it, links to the fleets and never sends a command', async () => {
  const fetch = setup();
  const bell = await screen.findByRole('button', { name: 'Notifications : 1 non lue' });
  fireEvent.click(bell);
  const dialog = screen.getByRole('dialog', { name: 'Notifications' });
  expect(dialog).toHaveTextContent('Attaque annoncée');
  expect(screen.getByRole('link', { name: /Attaque annoncée/ })).toHaveAttribute('href', '#fleets');
  expect(screen.getByText('(nouveau)')).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Notifications' })).toBeVisible());
  expect(window.localStorage.length).toBe(1);
  expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
});
