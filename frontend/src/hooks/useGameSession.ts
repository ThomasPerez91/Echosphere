import { useCallback, useEffect, useRef, useState } from 'react';

export type GameSession = { universe_id: string; universe_name: string; csrf_token: string;
  expires_at: string; idle_expires_at: string; access_valid_until: string; server_time: string; portal_url: string };
type Snapshot = { phase: 'loading' | 'active' | 'expired' | 'unavailable' | 'signed-out'; session: GameSession | null; portal: string | null };
export function safePortal(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash && url.pathname === '/'; }
  catch { return false; }
}
function valid(value: unknown, universe: string): value is GameSession {
  if (!value || typeof value !== 'object') return false;
  const row = value as Partial<GameSession>;
  return row.universe_id === universe && typeof row.universe_name === 'string' && row.universe_name.length <= 120
    && typeof row.csrf_token === 'string' && /^[a-f0-9]{64}$/.test(row.csrf_token)
    && [row.expires_at, row.idle_expires_at, row.access_valid_until, row.server_time].every(v => typeof v === 'string' && Number.isFinite(Date.parse(v)))
    && safePortal(row.portal_url);
}

export function useGameSession(universe: string | null) {
  const [snapshot, setSnapshot] = useState<Snapshot>({ phase: 'loading', session: null, portal: null });
  const [busy, setBusy] = useState(false);
  const active = useRef(false); const generation = useRef(0); const flight = useRef<AbortController | null>(null);
  const current = useRef(snapshot); current.current = snapshot;
  const perform = useCallback(async (action: 'read' | 'navigation' | 'logout') => {
    if (!universe) return;
    flight.current?.abort(); const controller = new AbortController(); flight.current = controller;
    const observed = ++generation.current; const timer = window.setTimeout(() => controller.abort(), 10000);
    setBusy(true);
    try {
      const session = current.current.session;
      const response = await fetch(`/api/game/${universe}/${action === 'read' ? 'session' : action}`, {
        method: action === 'read' ? 'GET' : 'POST', signal: controller.signal,
        headers: action === 'read' ? { 'X-Game-Request': 'bootstrap' }
          : { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf_token ?? '' },
        ...(action === 'read' ? {} : { body: '{}' }),
      });
      const body: unknown = await response.json();
      if (!active.current || observed !== generation.current || controller.signal.aborted) return;
      const link = body && typeof body === 'object' && 'portal_url' in body && safePortal(body.portal_url) ? body.portal_url : current.current.portal;
      if (response.status === 401) setSnapshot({ phase: 'expired', session: null, portal: link });
      else if (action === 'logout' && response.ok && body && typeof body === 'object' && 'status' in body && body.status === 'game_logged_out') {
        setSnapshot({ phase: 'signed-out', session: null, portal: link });
      } else if (response.ok && valid(body, universe)) setSnapshot({ phase: 'active', session: body, portal: body.portal_url });
      else setSnapshot({ phase: 'unavailable', session: null, portal: link });
    } catch { if (active.current && observed === generation.current) setSnapshot(old => ({ phase: 'unavailable', session: null, portal: old.portal })); }
    finally { window.clearTimeout(timer); if (active.current && observed === generation.current) setBusy(false); }
  }, [universe]);
  useEffect(() => {
    active.current = true;
    if (universe) { setSnapshot({ phase: 'loading', session: null, portal: null }); void perform('read'); }
    return () => { active.current = false; generation.current++; flight.current?.abort(); };
  }, [universe, perform]);
  useEffect(() => {
    if (snapshot.phase !== 'active' || !snapshot.session) return;
    const session = snapshot.session;
    const deadline = Math.min(...[session.expires_at, session.idle_expires_at, session.access_valid_until].map(Date.parse));
    // Timer only asks the server again. It never sends an activity event or renews access.
    const timer = window.setTimeout(() => { void perform('read'); }, Math.max(0, deadline - Date.parse(session.server_time)) + 100);
    return () => window.clearTimeout(timer);
  }, [snapshot, perform]);
  const visible: Snapshot = snapshot.session && snapshot.session.universe_id !== universe
    ? { phase: 'loading', session: null, portal: null } : snapshot;
  return { ...visible, busy, refresh: () => perform('navigation'), retry: () => perform('read'), logout: () => perform('logout') };
}
