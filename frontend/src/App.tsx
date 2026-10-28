import { useEffect, useState } from 'react';

type Status = 'checking' | 'connected' | 'unavailable';

export default function App() {
  const [status, setStatus] = useState<Status>('checking');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    void (async () => {
      try {
        const response = await fetch('/api/ready', { signal: controller.signal });
        const body: unknown = await response.json();
        const ready = response.ok && typeof body === 'object' && body !== null
          && 'status' in body && body.status === 'ready';
        if (!disposed) setStatus(ready ? 'connected' : 'unavailable');
      } catch {
        if (!disposed) setStatus('unavailable');
      } finally {
        window.clearTimeout(timeout);
      }
    })();
    return () => { disposed = true; window.clearTimeout(timeout); controller.abort(); };
  }, [attempt]);

  return (
    <main>
      <section className="panel" aria-labelledby="title">
        <p className="eyebrow">STRATÉGIE SPATIALE PERSISTANTE</p>
        <h1 id="title">Echosphere<span aria-hidden="true">.</span></h1>
        <p className="badge">Development build · Fondation technique</p>
        <p className="intro">Un univers à découvrir. Un empire à construire.</p>
        <p>La fondation technique est en place. Le gameplay arrivera aux prochaines étapes.</p>
        <div className="connection">
          <p role="status" aria-live="polite">Backend: <strong>{status}</strong></p>
          <button type="button" disabled={status === 'checking'} onClick={() => {
            setStatus('checking'); setAttempt(value => value + 1);
          }}>Vérifier la connexion</button>
        </div>
        <p className="note">La connexion vérifie aussi la disponibilité de PostgreSQL.</p>
      </section>
    </main>
  );
}
