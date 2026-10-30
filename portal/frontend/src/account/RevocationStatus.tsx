import { useCallback, useEffect, useRef, useState } from 'react';

export function RevocationStatus() {
  const [state, setState] = useState<'absent' | 'pending' | 'acknowledged' | 'error'>('absent');
  const [busy, setBusy] = useState(false); const active = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const read = useCallback(async () => {
    controller.current?.abort(); const request = new AbortController(); controller.current = request;
    const timer = window.setTimeout(() => request.abort(), 10000); setBusy(true);
    try {
      const result = await fetch('/api/auth/revocation-status', { headers: { 'X-Portal-Request': 'bootstrap' }, signal: request.signal });
      const body: unknown = await result.json();
      if (!active.current || request.signal.aborted) return;
      if (result.status === 404) setState('absent');
      else if (result.ok && body && typeof body === 'object' && 'state' in body && ['pending', 'acknowledged'].includes(String(body.state))) setState(body.state as 'pending' | 'acknowledged');
      else setState('error');
    } catch { if (active.current && controller.current === request) setState('error'); }
    finally { window.clearTimeout(timer); if (active.current && controller.current === request) setBusy(false); }
  }, []);
  useEffect(() => { active.current = true; void read(); return () => { active.current = false; controller.current?.abort(); }; }, [read]);
  if (state === 'absent') return null;
  return <section className="panel" aria-labelledby="revocation-title"><h2 id="revocation-title">Déconnexion des parties</h2>
    <p aria-live="polite">{state === 'acknowledged' ? 'Déconnexion terminée : tous les services Game concernés ont confirmé.'
      : state === 'pending' ? 'Déconnexion encore en attente sur certains services Game.'
      : 'État distant non confirmé. Reconnectez-vous pour consulter vos connexions si ce suivi a expiré.'}</p>
    {state !== 'acknowledged' && <button type="button" disabled={busy} onClick={() => { void read(); }}>Vérifier la déconnexion des parties</button>}
  </section>;
}
