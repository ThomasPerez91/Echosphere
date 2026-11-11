import { useEffect, useState, useSyncExternalStore } from 'react';

/** Local clock for display estimates (countdowns, stocks); never decides anything. */
export function useNow(intervalMs: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}

/** CSS media query as state; without matchMedia (tests, old browsers) the desktop layout wins. */
export function useMedia(query: string) {
  return useSyncExternalStore(
    notify => {
      const list = window.matchMedia?.(query);
      list?.addEventListener?.('change', notify);
      return () => list?.removeEventListener?.('change', notify);
    },
    () => window.matchMedia?.(query).matches ?? true,
    () => true,
  );
}
