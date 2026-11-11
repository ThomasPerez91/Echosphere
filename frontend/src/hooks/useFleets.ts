import { useCallback, useEffect, useRef, useState } from "react";
import { onSandboxChange } from "../sandbox/api";
import { ApiError, fleetCommand, listFleetEmpires, readFleets } from "../fleet/api";
import type { Empire, FleetProjection } from "../fleet/api";

type Phase = "idle" | "loading" | "ready" | "empty" | "error";
export type Feedback = { tone: "success" | "error" | "unknown"; code: string } | null;
type State = { phase: Phase; empires: Empire[]; projection: FleetProjection | null; receivedAt: number; error: string | null };

const LATE_RETRIES = [3000, 10000, 30000];

/** Next server deadline worth a passive reread: production, arrival, analysis end or return. */
export function nextDeadline(p: FleetProjection | null) {
  if (!p?.available) return undefined;
  const dates = [
    ...p.colonies!.flatMap((c) => c.orders.map((o) => o.due_at)),
    ...p.missions!.filter((m) => m.status !== "completed").map((m) => (m.status === "returning" ? m.return_at : m.due_at)),
  ].filter((d): d is string => !!d);
  return dates.sort((a, b) => Date.parse(a) - Date.parse(b))[0];
}

/**
 * Same discipline as Galaxy/Research: reads are never activity and never progress the game (the
 * worker does), one command at a time, an unknown outcome keeps its key so a retry cannot pay
 * twice, and a late answer for another Universe/Empire/command generation is ignored.
 */
export function useFleets(universe: string | null, enabled: boolean, csrf: string | undefined, onSessionLost: () => void,
  preferredEmpire?: string) {
  const [state, setState] = useState<State>({ phase: "idle", empires: [], projection: null, receivedAt: 0, error: null });
  const [selectedEmpire, setSelectedEmpire] = useState("");
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [awaiting, setAwaiting] = useState(false);
  const selected = useRef<string | null>(null);
  const active = useRef(false);
  const generation = useRef(0);
  const reads = useRef<AbortController | null>(null);
  const current = useRef(state);
  current.current = state;
  const intent = useRef<{ signature: string; key: string } | null>(null);
  const busy = useRef(false);
  const late = useRef(0);
  const lost = useRef(onSessionLost);
  lost.current = onSessionLost;
  const preferred = useRef(preferredEmpire);
  preferred.current = preferredEmpire;

  const accept = useCallback((projection: FleetProjection) => {
    const previous = current.current.projection;
    if (previous && previous.empire.id === projection.empire.id &&
      Date.parse(projection.server_time) < Date.parse(previous.server_time))
      return;
    setState((old) => ({ ...old, phase: "ready", projection, receivedAt: Date.now(), error: null }));
  }, []);

  const fail = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) lost.current();
    const code = error instanceof ApiError ? error.code : "unavailable";
    if (error instanceof ApiError && [401, 403, 404, 409].includes(error.status)) {
      setState((old) => ({ ...old, phase: "error", projection: null, error: code }));
      return;
    }
    setState((old) => (old.projection ? { ...old, error: code } : { ...old, phase: "error", error: code }));
  }, []);

  const read = useCallback(async (empire?: string) => {
    if (!universe) return;
    reads.current?.abort();
    const controller = new AbortController();
    reads.current = controller;
    const observed = generation.current;
    const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      let target = empire ?? selected.current ?? current.current.projection?.empire.id;
      if (!target) {
        const empires = await listFleetEmpires(universe, controller.signal);
        if (!active.current || observed !== generation.current) return;
        if (!empires.length) {
          setState((old) => ({ ...old, phase: "empty", empires, projection: null, error: null }));
          return;
        }
        setState((old) => ({ ...old, empires }));
        // A shortcut's Empire is read first when accessible; otherwise the first readable one.
        target = empires.find((e) => e.id === preferred.current)?.id ?? empires[0].id;
      }
      selected.current = target;
      setSelectedEmpire(target);
      const projection = await readFleets(universe, target, controller.signal);
      if (active.current && observed === generation.current) accept(projection);
    } catch (error) {
      if (active.current && observed === generation.current && reads.current === controller) fail(error);
    } finally {
      window.clearTimeout(timer);
    }
  }, [universe, accept, fail]);

  useEffect(() => {
    active.current = true;
    generation.current += 1;
    late.current = 0;
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
    const projection = state.projection;
    const due = nextDeadline(projection);
    if (!projection || !due || state.phase !== "ready") {
      setAwaiting(false);
      return;
    }
    const remaining = Date.parse(due) - Date.parse(projection.server_time) - (Date.now() - state.receivedAt);
    if (remaining <= 0 && late.current >= LATE_RETRIES.length) {
      setAwaiting(true);
      return;
    }
    const delay = remaining > 0 ? remaining + 1500 : LATE_RETRIES[late.current];
    const timer = window.setTimeout(() => {
      if (remaining <= 0) late.current += 1;
      else late.current = 0;
      void read();
    }, delay);
    return () => window.clearTimeout(timer);
  }, [state.projection, state.phase, state.receivedAt, read]);

  /** Send one command. `signature` identifies the intention: same signature → same key. */
  const run = useCallback(async (path: string, body: object, signature: string) => {
    const projection = current.current.projection;
    if (!universe || !projection || !csrf || busy.current) return null;
    const empire = projection.empire.id;
    const fingerprint = JSON.stringify([empire, path, signature]);
    if (intent.current?.signature !== fingerprint)
      intent.current = { signature: fingerprint, key: globalThis.crypto.randomUUID().replaceAll("-", "") };
    generation.current += 1;
    reads.current?.abort();
    busy.current = true;
    setPending(true);
    setFeedback(null);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 15000);
    const observed = generation.current;
    try {
      const reply = await fleetCommand(universe, empire, csrf, path,
        { ...body, idempotency_key: intent.current.key }, controller.signal);
      intent.current = null;
      if (!active.current || observed !== generation.current) return reply.result;
      late.current = 0;
      accept(reply.fleets);
      setFeedback({ tone: "success", code: "accepted" });
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
  }, [universe, csrf, accept, read]);

  const select = useCallback((empire: string) => {
    generation.current += 1;
    intent.current = null;
    late.current = 0;
    setFeedback(null);
    setState((old) => ({ ...old, phase: "loading", projection: null }));
    void read(empire);
  }, [read]);

  // Test game: a sandbox grant or completion rereads every open view at once.
  useEffect(() => onSandboxChange(() => { late.current = 0; void read(); }), [read]);
  return {
    ...state, selectedEmpire, pending, feedback, awaiting,
    refresh: () => { late.current = 0; void read(); },
    run, select, dismiss: () => setFeedback(null),
  };
}
