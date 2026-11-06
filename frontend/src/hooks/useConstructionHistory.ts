import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, readConstructionHistory } from '../colony/api';
import type { HistoryEntry } from '../colony/api';

/** Per colony: loaded pages, next cursor and whether the server offers the history at all. */
export type ColonyHistory = { entries: HistoryEntry[]; next: string | null; status: 'loading' | 'ready' | 'unavailable' | 'error' };

/**
 * Completed constructions of every own colony (W-UX-05). Reads only: no activity, no catch-up. A
 * Game server without the route (or a colony no longer readable) answers 404: that colony's history
 * is shown as unavailable while the rest of the reports keep working. Refreshing restarts at page 1.
 */
export function useConstructionHistory(universe: string | null, colonies: { id: string }[], enabled: boolean, onSessionLost: () => void) {
  const [history, setHistory] = useState<Record<string, ColonyHistory>>({});
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const lost = useRef(onSessionLost); lost.current = onSessionLost;
  const current = useRef(history); current.current = history;
  const ids = colonies.map(c => c.id).join(',');

  const load = useCallback(async (targets: { id: string; before: string | null }[], reset: boolean) => {
    if (!universe || !targets.length) return;
    controller.current?.abort(); const signal = (controller.current = new AbortController()).signal;
    const observed = ++generation.current;
    setBusy(true);
    if (reset) setHistory(Object.fromEntries(targets.map(t => [t.id, { entries: [], next: null, status: 'loading' as const }])));
    const results = await Promise.all(targets.map(async t => {
      try { return { id: t.id, page: await readConstructionHistory(universe, t.id, t.before, signal), error: null }; }
      catch (error) { return { id: t.id, page: null, error }; }
    }));
    if (observed !== generation.current) return;
    setBusy(false);
    if (results.some(r => r.error instanceof ApiError && r.error.status === 401)) lost.current();
    setHistory(old => {
      const next = { ...old };
      for (const { id, page, error } of results) {
        const previous = reset ? [] : old[id]?.entries ?? [];
        if (!page) {
          const unavailable = error instanceof ApiError && error.status === 404;
          next[id] = { entries: previous, next: reset ? null : old[id]?.next ?? null, status: unavailable ? 'unavailable' : 'error' };
        } else {
          // Exclusive cursor: a later page never repeats an entry; ids guard against a replayed page.
          const seen = new Set(previous.map(e => e.id));
          next[id] = { entries: [...previous, ...page.entries.filter(e => !seen.has(e.id))], next: page.next_before_sequence, status: 'ready' };
        }
      }
      return next;
    });
  }, [universe]);

  const refresh = useCallback(() => { void load(ids ? ids.split(',').map(id => ({ id, before: null })) : [], true); }, [ids, load]);
  const more = useCallback(() => {
    const targets = Object.entries(current.current).filter(([, h]) => h.status === 'ready' && h.next).map(([id, h]) => ({ id, before: h.next }));
    void load(targets, false);
  }, [load]);

  useEffect(() => {
    if (enabled && universe && ids) refresh();
    // Counter and controller refs, not DOM nodes: invalidating the latest read on cleanup is intended.
    const counter = generation, reads = controller;
    return () => { counter.current++; reads.current?.abort(); };
  }, [enabled, universe, ids, refresh]);

  const values = Object.values(history);
  return {
    history, busy, refresh, more,
    hasMore: values.some(h => h.status === 'ready' && !!h.next),
    unavailable: values.filter(h => h.status === 'unavailable').length,
    failed: values.filter(h => h.status === 'error').length,
  };
}
