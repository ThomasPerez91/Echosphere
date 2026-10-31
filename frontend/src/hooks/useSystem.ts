import { useEffect, useRef, useState } from 'react';
import { ApiError, readSystem } from '../galaxy/api';
import type { SystemDetail } from '../galaxy/api';

type State = { scope: string; data: SystemDetail | null; error: string | null; loading: boolean };
/** Persisted knowledge only; no command, deadline timer or automatic session renewal. */
export function useSystem(universe: string, empire: string, system: string, onSessionLost: () => void) {
  const scope = `${universe}/${empire}/${system}`;
  const [state, setState] = useState<State>({ scope: '', data: null, error: null, loading: true });
  const [revision, setRevision] = useState(0);
  const lost = useRef(onSessionLost); lost.current = onSessionLost;
  useEffect(() => {
    let current = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 10000);
    setState({ scope, data: null, error: null, loading: true });
    void readSystem(universe, empire, system, controller.signal).then(data => {
      if (current) setState({ scope, data, error: null, loading: false });
    }).catch((error: unknown) => {
      if (!current) return;
      if (error instanceof ApiError && error.status === 401) lost.current();
      setState({ scope, data: null, error: error instanceof ApiError ? error.code : 'unavailable', loading: false });
    }).finally(() => window.clearTimeout(timer));
    return () => { current = false; controller.abort(); window.clearTimeout(timer); };
  }, [universe, empire, system, scope, revision]);
  return { ...(state.scope === scope ? state : { data: null, error: null, loading: true }),
    refresh: () => setRevision(value => value + 1) };
}
