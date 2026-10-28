import { useEffect, useState } from 'react';

export type ConnectionStatus = 'checking' | 'connected' | 'unavailable';

export function useReadiness() {
  const [status, setStatus] = useState<ConnectionStatus>('checking');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timeout = window.setTimeout(() => {
      controller.abort();
      if (!disposed) setStatus('unavailable');
    }, 5000);
    void (async () => {
      try {
        const response = await fetch('/api/ready', { signal: controller.signal });
        const body: unknown = await response.json();
        const ready = response.ok && typeof body === 'object' && body !== null
          && 'status' in body && body.status === 'ready';
        if (!disposed && !controller.signal.aborted) setStatus(ready ? 'connected' : 'unavailable');
      } catch {
        if (!disposed) setStatus('unavailable');
      } finally {
        window.clearTimeout(timeout);
      }
    })();
    return () => { disposed = true; window.clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  function retry() {
    setStatus('checking');
    setAttempt(value => value + 1);
  }

  return { status, retry };
}
