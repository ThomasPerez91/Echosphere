import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, listColonies, readColony, sendCommand } from '../colony/api';
import type { ColonySummary, Command, Projection } from '../colony/api';

type Phase = 'idle' | 'loading' | 'ready' | 'empty' | 'error';
export type Feedback = { tone: 'success' | 'error' | 'unknown'; text: string; code?: string } | null;
type State = { phase: Phase; colonies: ColonySummary[]; projection: Projection | null; receivedAt: number; error: string | null };

const LATE_RETRIES = [3000, 10000, 30000];

function newKey() {
  return globalThis.crypto.randomUUID();
}

/**
 * Reads never count as activity and never renew the session. Commands run one at a time, are never
 * triggered by rendering, and reuse their idempotency key when retried after an unknown outcome.
 */
export function useColony(universe: string | null, enabled: boolean, csrf: string | undefined, onSessionLost: () => void) {
  const [state, setState] = useState<State>({ phase: 'idle', colonies: [], projection: null, receivedAt: 0, error: null });
  const [pending, setPending] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [awaiting, setAwaiting] = useState(false);
  const active = useRef(false); const generation = useRef(0); const reads = useRef<AbortController | null>(null);
  const current = useRef(state); current.current = state;
  const intent = useRef<{ signature: string; key: string } | null>(null);
  const busy = useRef(false); const late = useRef(0);
  const lost = useRef(onSessionLost); lost.current = onSessionLost;

  const accept = useCallback((projection: Projection) => {
    const previous = current.current.projection;
    // A slower, older response never replaces a newer server state.
    if (previous && previous.colony.id === projection.colony.id
      && Date.parse(projection.server_time) < Date.parse(previous.server_time)) return;
    setState(old => ({ ...old, phase: 'ready', projection, receivedAt: Date.now(), error: null }));
  }, []);

  const fail = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) lost.current();
    const code = error instanceof ApiError ? error.code : 'unavailable';
    setState(old => old.projection ? { ...old, error: code } : { ...old, phase: 'error', error: code });
  }, []);

  const read = useCallback(async (colony?: string) => {
    if (!universe) return;
    reads.current?.abort(); const controller = new AbortController(); reads.current = controller;
    const observed = generation.current; const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      let target = colony ?? current.current.projection?.colony.id;
      if (!target) {
        const colonies = await listColonies(universe, controller.signal);
        if (!active.current || observed !== generation.current) return;
        if (!colonies.length) { setState(old => ({ ...old, phase: 'empty', colonies, error: null })); return; }
        setState(old => ({ ...old, colonies }));
        target = colonies[0].id;
      }
      const projection = await readColony(universe, target, controller.signal);
      if (active.current && observed === generation.current) accept(projection);
    } catch (error) {
      // A read superseded by a newer one is silent; a timeout of the current read is an error.
      if (active.current && observed === generation.current && reads.current === controller) fail(error);
    } finally { window.clearTimeout(timer); }
  }, [universe, accept, fail]);

  useEffect(() => {
    active.current = true; generation.current += 1; late.current = 0;
    if (universe && enabled) {
      setState({ phase: 'loading', colonies: [], projection: null, receivedAt: 0, error: null });
      void read();
    }
    return () => { active.current = false; generation.current += 1; reads.current?.abort(); };
  }, [universe, enabled, read]);

  // Light refresh when the next server deadline is reached; the server alone completes orders.
  useEffect(() => {
    const projection = state.projection;
    const due = projection?.queue.find(order => order.status === 'active')?.due_at;
    if (!projection || !due || state.phase !== 'ready') { setAwaiting(false); return; }
    const remaining = Date.parse(due) - Date.parse(projection.server_time) - (Date.now() - state.receivedAt);
    if (remaining <= 0 && late.current >= LATE_RETRIES.length) { setAwaiting(true); return; }
    const delay = remaining > 0 ? remaining + 1500 : LATE_RETRIES[late.current];
    const timer = window.setTimeout(() => {
      if (remaining <= 0) late.current += 1; else late.current = 0;
      void read();
    }, delay);
    return () => window.clearTimeout(timer);
  }, [state.projection, state.phase, state.receivedAt, read]);

  const command = useCallback(async (value: Command) => {
    const projection = current.current.projection;
    if (!universe || !projection || !csrf || busy.current) return;
    const signature = JSON.stringify(value);
    if (intent.current?.signature !== signature) intent.current = { signature, key: newKey() };
    busy.current = true; setPending(signature); setFeedback(null);
    const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), 15000);
    const observed = generation.current;
    try {
      const result = await sendCommand(universe, projection.colony.id, csrf, value, intent.current.key, controller.signal);
      intent.current = null;
      if (!active.current || observed !== generation.current) return;
      late.current = 0; accept(result);
      setFeedback({ tone: 'success', text: value.kind === 'construct' ? 'Ordre de construction accepté par le serveur.' : 'Annulation enregistrée, remboursement crédité.' });
    } catch (error) {
      if (!active.current || observed !== generation.current) return;
      if (error instanceof ApiError && error.status > 0 && error.status < 500) {
        intent.current = null; // Definitive refusal: a later click is a new intent.
        if (error.status === 401) lost.current();
        setFeedback({ tone: 'error', text: '', code: error.code });
        if (error.status !== 401) void read();
      } else {
        // Unknown outcome (timeout, network, 5xx): keep the key so a retry cannot duplicate.
        setFeedback({ tone: 'unknown', text: '', code: error instanceof ApiError ? error.code : 'unavailable' });
      }
    } finally {
      window.clearTimeout(timer); busy.current = false;
      if (active.current && observed === generation.current) setPending(null);
    }
  }, [universe, csrf, accept, read]);

  const select = useCallback((colony: string) => {
    late.current = 0; setFeedback(null);
    setState(old => ({ ...old, phase: 'loading', projection: null, error: null }));
    void read(colony);
  }, [read]);

  return { ...state, pending, feedback, awaiting, refresh: () => { late.current = 0; void read(); }, command, select,
    dismiss: () => setFeedback(null) };
}
