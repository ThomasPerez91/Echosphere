import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, listEmpires, readGalaxy, startExpedition } from "../galaxy/api";
import type { Empire, Expedition, Projection } from "../galaxy/api";

type Phase = "idle" | "loading" | "ready" | "empty" | "error";
export type Feedback = { tone: "success" | "error" | "unknown"; code: string } | null;
type State = {
  phase: Phase;
  empires: Empire[];
  projection: Projection | null;
  receivedAt: number;
  error: string | null;
};

const LATE_RETRIES = [3000, 10000, 30000];

/**
 * Same discipline as Research: reads never count as activity, nothing is sent on render, one
 * command at a time, and an unknown outcome keeps its idempotency key so a retry cannot pay twice.
 * Only the server completes an expedition; deadline rereads are passive and bounded.
 */
export function useGalaxy(
  universe: string | null,
  enabled: boolean,
  csrf: string | undefined,
  onSessionLost: () => void,
) {
  const [state, setState] = useState<State>({
    phase: "idle",
    empires: [],
    projection: null,
    receivedAt: 0,
    error: null,
  });
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

  const accept = useCallback((projection: Projection) => {
    const previous = current.current.projection;
    if (
      previous &&
      previous.empire.id === projection.empire.id &&
      Date.parse(projection.server_time) < Date.parse(previous.server_time)
    )
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

  const read = useCallback(
    async (empire?: string) => {
      if (!universe) return;
      reads.current?.abort();
      const controller = new AbortController();
      reads.current = controller;
      const observed = generation.current;
      const timer = window.setTimeout(() => controller.abort(), 10000);
      try {
        let target = empire ?? selected.current ?? current.current.projection?.empire.id;
        if (!target) {
          const empires = await listEmpires(universe, controller.signal);
          if (!active.current || observed !== generation.current) return;
          if (!empires.length) {
            setState((old) => ({ ...old, phase: "empty", empires, projection: null, error: null }));
            return;
          }
          setState((old) => ({ ...old, empires }));
          target = empires[0].id;
        }
        selected.current = target;
        setSelectedEmpire(target);
        const projection = await readGalaxy(universe, target, controller.signal);
        if (active.current && observed === generation.current) accept(projection);
      } catch (error) {
        if (active.current && observed === generation.current && reads.current === controller)
          fail(error);
      } finally {
        window.clearTimeout(timer);
      }
    },
    [universe, accept, fail],
  );

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
    const due = projection?.missions.find((m) => m.status === "active")?.due_at;
    if (!projection || !due || state.phase !== "ready") {
      setAwaiting(false);
      return;
    }
    const remaining =
      Date.parse(due) - Date.parse(projection.server_time) - (Date.now() - state.receivedAt);
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

  const start = useCallback(
    async (expedition: Expedition) => {
      const projection = current.current.projection;
      if (!universe || !projection || !csrf || busy.current) return false;
      const empire = projection.empire.id;
      const signature = JSON.stringify([empire, expedition.colony_id, expedition.destination_id]);
      if (intent.current?.signature !== signature)
        intent.current = { signature, key: globalThis.crypto.randomUUID() };
      generation.current += 1;
      reads.current?.abort();
      busy.current = true;
      setPending(true);
      setFeedback(null);
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 15000);
      const observed = generation.current;
      try {
        const result = await startExpedition(
          universe,
          empire,
          csrf,
          expedition,
          intent.current.key,
          controller.signal,
        );
        intent.current = null;
        if (!active.current || observed !== generation.current) return true;
        late.current = 0;
        accept(result.galaxy);
        setFeedback({ tone: "success", code: "accepted" });
        return true;
      } catch (error) {
        if (!active.current || observed !== generation.current) return false;
        if (error instanceof ApiError && error.status > 0 && error.status < 500) {
          intent.current = null; // Definitive refusal: a later click is a new intention.
          if (error.status === 401) lost.current();
          setFeedback({ tone: "error", code: error.code });
          if (error.status !== 401) void read();
        } else {
          setFeedback({
            tone: "unknown",
            code: error instanceof ApiError ? error.code : "unavailable",
          });
        }
        return false;
      } finally {
        window.clearTimeout(timer);
        busy.current = false;
        if (active.current && observed === generation.current) setPending(false);
      }
    },
    [universe, csrf, accept, read],
  );

  const select = useCallback(
    (empire: string) => {
      generation.current += 1;
      intent.current = null;
      late.current = 0;
      setFeedback(null);
      setState((old) => ({ ...old, phase: "loading", projection: null }));
      void read(empire);
    },
    [read],
  );

  return {
    ...state,
    selectedEmpire,
    pending,
    feedback,
    awaiting,
    refresh: () => {
      late.current = 0;
      void read();
    },
    start,
    select,
    dismiss: () => setFeedback(null),
  };
}
