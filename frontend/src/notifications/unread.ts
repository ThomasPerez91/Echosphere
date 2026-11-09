import type { ReportEvent } from '../reports/events';

/** Keys the viewer has already seen, kept per universe and Empire in this browser only. */
export type Seen = { keys: string[] };
const LIMIT = 300;

export const storageKey = (universe: string, empire: string) => `echosphere.notifications.${universe}.${empire}`;

export function readSeen(key: string): Seen | null {
  try {
    const raw = window.localStorage.getItem(key);
    const value: unknown = raw ? JSON.parse(raw) : null;
    return value && typeof value === 'object' && Array.isArray((value as Seen).keys) && (value as Seen).keys.every(k => typeof k === 'string')
      ? value as Seen : null;
  } catch { return null; }
}

export function writeSeen(key: string, seen: Seen) {
  try { window.localStorage.setItem(key, JSON.stringify({ keys: seen.keys.slice(-LIMIT) })); } catch { /* storage unavailable: unread state lives in memory */ }
}

/**
 * The first time a browser opens a game, its past is not news: everything already reported is
 * marked as seen, except an attack still pending, which always needs attention.
 */
export const initialSeen = (events: ReportEvent[]): Seen => ({ keys: events.filter(e => !e.key.startsWith('alert-')).map(e => e.key) });

export const unread = (events: ReportEvent[], seen: Seen) => {
  const known = new Set(seen.keys);
  return events.filter(e => !known.has(e.key));
};

export const markAll = (events: ReportEvent[], seen: Seen): Seen => {
  const keys = [...seen.keys.filter(k => !events.some(e => e.key === k)), ...events.map(e => e.key)];
  return { keys: keys.slice(-LIMIT) };
};
