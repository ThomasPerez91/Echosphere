import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, listRelationEmpires, readRelations, relationCommand } from "../relations/api";
import type { Empire, RelationAction, RelationsProjection } from "../relations/api";

type Phase = "idle" | "loading" | "ready" | "empty" | "unavailable" | "error";
export type Feedback = { tone: "success" | "error" | "unknown"; code: string } | null;
type State = { phase: Phase; empires: Empire[]; projection: RelationsProjection | null; receivedAt: number; error: string | null };

/** Next server instant that changes what is shown: a proposal expiry, a notice end, a cooldown end. */
export function nextRelationDeadline(p: RelationsProjection | null) {
  if (!p) return undefined;
  const now = Date.parse(p.at);
  return p.relations
    .flatMap((r) => [r.proposal?.expires_at, r.pact?.notice?.ends_at, r.cooldown_until])
    .filter((d): d is string => !!d && Date.parse(d) > now)
    .sort((a, b) => Date.parse(a) - Date.parse(b))[0];
}

/**
 * Same discipline as Fleets: reads are never activity, one command at a time, an unknown outcome
 * keeps its key so a retry cannot act twice, and a late answer for another Universe, Empire or
 * command generation is ignored.
 */
export function useRelations(universe: string | null, enabled: boolean, csrf: string | undefined, onSessionLost: () => void) {
  const [state, setState] = useState<State>({ phase: "idle", empires: [], projection: null, receivedAt: 0, error: null });
  const [selectedEmpire, setSelectedEmpire] = useState("");
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const selected = useRef<string | null>(null);
  const active = useRef(false);
  const generation = useRef(0);
  const reads = useRef<AbortController | null>(null);
  const intent = useRef<{ signature: string; key: string } | null>(null);
  const busy = useRef(false);
  const lost = useRef(onSessionLost);
  lost.current = onSessionLost;

  const fail = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) lost.current();
    const code = error instanceof ApiError ? error.code : "unavailable";
    if (code === "relations_unavailable") {
      setState((old) => ({ ...old, phase: "unavailable", projection: null, error: null }));
      return;
    }
    setState((old) => (old.projection && !(error instanceof ApiError && [401, 403, 404].includes(error.status))
      ? { ...old, error: code } : { ...old, phase: "error", projection: null, error: code }));
  }, []);

  const read = useCallback(async (empire?: string) => {
    if (!universe) return;
    reads.current?.abort();
    const controller = new AbortController();
    reads.current = controller;
    const observed = generation.current;
    const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      let target = empire ?? selected.current;
      if (!target) {
        const listing = await listRelationEmpires(universe, controller.signal);
        if (!active.current || observed !== generation.current) return;
        if (!listing.available) {
          setState((old) => ({ ...old, phase: "unavailable", empires: listing.empires, projection: null, error: null }));
          return;
        }
        if (!listing.empires.length) {
          setState((old) => ({ ...old, phase: "empty", empires: [], projection: null, error: null }));
          return;
        }
        setState((old) => ({ ...old, empires: listing.empires }));
        target = listing.empires[0].id;
      }
      selected.current = target;
      setSelectedEmpire(target);
      const projection = await readRelations(universe, target, controller.signal);
      if (active.current && observed === generation.current)
        setState((old) => ({ ...old, phase: "ready", projection, receivedAt: Date.now(), error: null }));
    } catch (error) {
      if (active.current && observed === generation.current && reads.current === controller) fail(error);
    } finally {
      window.clearTimeout(timer);
    }
  }, [universe, fail]);

  useEffect(() => {
    active.current = true;
    generation.current += 1;
    selected.current = null;
    intent.current = null;
    setSelectedEmpire("");
    setFeedback(null);
    if (universe && enabled) {
      setState({ phase: "loading", empires: [], projection: null, receivedAt: 0, error: null });
      void read();
    }
    return () => {
      active.current = false;
      generation.current += 1;
      reads.current?.abort();
    };
  }, [universe, enabled, read]);

  useEffect(() => {
    const due = nextRelationDeadline(state.projection);
    if (!state.projection || !due || state.phase !== "ready") return;
    const remaining = Date.parse(due) - Date.parse(state.projection.at) - (Date.now() - state.receivedAt);
    const timer = window.setTimeout(() => void read(), Math.max(1500, remaining + 1500));
    return () => window.clearTimeout(timer);
  }, [state.projection, state.phase, state.receivedAt, read]);

  const run = useCallback(async (counterpart: string, action: RelationAction) => {
    const empire = selected.current;
    if (!universe || !empire || !csrf || busy.current) return null;
    const signature = JSON.stringify([empire, counterpart, action]);
    if (intent.current?.signature !== signature)
      intent.current = { signature, key: globalThis.crypto.randomUUID().replaceAll("-", "") };
    generation.current += 1;
    reads.current?.abort();
    busy.current = true;
    setPending(true);
    setFeedback(null);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 15000);
    const observed = generation.current;
    try {
      const reply = await relationCommand(universe, empire, counterpart, action, csrf, intent.current.key, controller.signal);
      intent.current = null;
      if (!active.current || observed !== generation.current) return reply.result;
      setState((old) => ({ ...old, phase: "ready", projection: reply.relations, receivedAt: Date.now(), error: null }));
      setFeedback({ tone: "success", code: action });
      return reply.result;
    } catch (error) {
      if (!active.current || observed !== generation.current) return null;
      if (error instanceof ApiError && error.status > 0 && error.status < 500) {
        intent.current = null; // Definitive refusal: a later click is a new intention.
        if (error.status === 401) lost.current();
        setFeedback({ tone: "error", code: error.code });
        if (error.status !== 401) void read();
      } else {
        setFeedback({ tone: "unknown", code: error instanceof ApiError ? error.code : "unavailable" });
      }
      return null;
    } finally {
      window.clearTimeout(timer);
      busy.current = false;
      if (active.current && observed === generation.current) setPending(false);
    }
  }, [universe, csrf, read]);

  const select = useCallback((empire: string) => {
    generation.current += 1;
    intent.current = null;
    setFeedback(null);
    setState((old) => ({ ...old, phase: "loading", projection: null }));
    void read(empire);
  }, [read]);

  return {
    ...state, selectedEmpire, pending, feedback,
    refresh: () => void read(), run, select, dismiss: () => setFeedback(null),
  };
}
