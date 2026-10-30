import { useEffect, useRef, useState } from 'react';

type Membership = { membership_id: string; universe_id: string; name: string; desired_status: string;
  applied_status: string | null; delivery_state: 'pending' | 'applied'; expired: boolean;
  valid_until: string; last_checked_at: string | null; entry_available: boolean; entry_url?: string | null };
type Projection = { memberships: Membership[]; revocations: { scope: string; state: string; created_at: string }[] };

function validEntry(value: string, universe: string) {
  try {
    const target = new URL(value);
    return target.protocol === 'https:' && !target.username && !target.password
      && !target.search && !target.hash && target.pathname === `/api/game/${universe}/start`;
  } catch { return false; }
}

export function Lobby({ csrf, onExpired }: { csrf: string; onExpired?: () => void }) {
  const [snapshot, setSnapshot] = useState<Projection | null>(null);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const active = useRef(false); const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    active.current = true; const request = new AbortController(); controller.current = request;
    const timer = window.setTimeout(() => request.abort(), 10000);
    void read(request.signal).catch(() => { if (active.current && controller.current === request) setError('Liste des parties indisponible.'); }).finally(() => window.clearTimeout(timer));
    return () => { active.current = false; controller.current?.abort(); };
  }, []);
  async function read(signal: AbortSignal) {
    const response = await fetch('/api/lobby/memberships', { headers: { 'X-Portal-Request': 'bootstrap' }, signal });
    if (response.status === 401) { onExpired?.(); throw new Error('session'); }
    const body: unknown = await response.json();
    if (!response.ok || !body || typeof body !== 'object' || !('memberships' in body) || !Array.isArray(body.memberships)
      || !('revocations' in body) || !Array.isArray(body.revocations)
      || !body.memberships.every(item => item && typeof item.membership_id === 'string' && typeof item.universe_id === 'string'
        && typeof item.name === 'string' && ['active', 'suspended', 'revoked'].includes(item.desired_status)
        && (item.applied_status === null || ['active', 'suspended', 'revoked'].includes(item.applied_status))
        && ['pending', 'applied'].includes(item.delivery_state) && typeof item.expired === 'boolean'
        && typeof item.valid_until === 'string' && (item.last_checked_at === null || typeof item.last_checked_at === 'string')
        && typeof item.entry_available === 'boolean'
        && (!item.entry_available || (typeof item.entry_url === 'string' && validEntry(item.entry_url, item.universe_id))))
      || !body.revocations.every(item => item && ['account', 'device'].includes(item.scope)
        && ['pending', 'acknowledged'].includes(item.state) && typeof item.created_at === 'string')) throw new Error('projection');
    if (active.current && !signal.aborted) { setSnapshot(body as Projection); setError(''); }
  }
  async function refresh() {
    if (busy) return;
    const request = new AbortController(); controller.current = request;
    const timer = window.setTimeout(() => request.abort(), 10000); setBusy(true); setError('');
    try {
      // Explicit user refresh counts; the subsequent GET/polling can never extend idle or rights.
      const navigation = await fetch('/api/auth/navigation', { method: 'POST', headers: {
        'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: '{}', signal: request.signal });
      if (navigation.status === 401) onExpired?.();
      if (!navigation.ok) throw new Error('session');
      await read(request.signal);
    } catch { if (active.current) setError('Liste non confirmée. Vérifiez votre connexion et réessayez.'); }
    finally { window.clearTimeout(timer); if (active.current) setBusy(false); }
  }
  async function renew(universe: string) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await fetch(`/api/lobby/universes/${encodeURIComponent(universe)}/renew`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: '{}',
        signal: AbortSignal.timeout(10000) });
      if (result.status === 401) onExpired?.();
      if (!result.ok) throw new Error('renew');
      await read(AbortSignal.timeout(10000));
    } catch { if (active.current) setError('Renouvellement non confirmé. Actualisez la liste avant de réessayer.'); }
    finally { if (active.current) setBusy(false); }
  }
  return <section className="security-settings" aria-labelledby="lobby-title"><h3 id="lobby-title">Mes parties</h3>
    {!snapshot && !error && <p role="status">Chargement des participations…</p>}
    {snapshot && snapshot.memberships.length === 0 && <p>Aucune participation à un univers. Aucune partie de démonstration n’est créée automatiquement.</p>}
    {snapshot?.memberships.map(item => <article key={item.membership_id} className="membership">
      <h4>{item.name}</h4>
      <p>{item.delivery_state === 'pending' ? 'Confirmation de Game en attente' : item.desired_status === 'suspended' ? 'Participation suspendue' : item.desired_status === 'revoked' ? 'Accès révoqué' : item.expired ? 'Confirmation d’accès expirée' : 'Participation confirmée par Game'}</p>
      {item.last_checked_at && <p>Dernière confirmation : <time dateTime={item.last_checked_at}>{new Date(item.last_checked_at).toLocaleString('fr-FR')}</time></p>}
      {!error && item.entry_available && item.entry_url ? <a href={item.entry_url} referrerPolicy="no-referrer">Entrer dans cet univers</a>
        : <p>L’entrée requiert une adresse vérifiée et un accès actif confirmé par Game.</p>}
      {item.desired_status === 'active' && item.delivery_state === 'applied' && <button type="button" disabled={busy}
        onClick={() => { void renew(item.universe_id); }}>Confirmer de nouveaux droits pour cette partie</button>}
    </article>)}
    {!!snapshot?.revocations.length && <div><h4>Déconnexions des parties</h4>{snapshot.revocations.map((item, index) => <p key={index}>
      {item.scope === 'account' ? 'Tous les appareils' : 'Un appareil'} : {item.state === 'acknowledged' ? 'révocation confirmée par les services Game' : 'révocation encore en attente sur certains services Game'}
    </p>)}</div>}
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={() => { void refresh(); }}>Actualiser mes parties</button>
  </section>;
}
