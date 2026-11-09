import { useEffect, useRef, useState } from 'react';
import { Icon } from '../theme/Icon';

type Membership = { membership_id: string; universe_id: string; name: string; desired_status: string;
  applied_status: string | null; delivery_state: 'pending' | 'applied'; expired: boolean;
  valid_until: string; last_checked_at: string | null; entry_available: boolean; entry_url?: string | null };
export type LobbySnapshot = Projection;
/** UX-API-02: universes this account created that Game has not started/granted yet. */
type Creation = { universe_id: string; name: string; created_at: string; state: 'starting' };
type Projection = { memberships: Membership[]; creations?: Creation[]; revocations: { scope: string; state: string; created_at: string }[] };

function validEntry(value: string, universe: string) {
  try {
    const target = new URL(value);
    return target.protocol === 'https:' && !target.username && !target.password
      && !target.search && !target.hash && target.pathname === `/api/game/${universe}/start`;
  } catch { return false; }
}

export function Lobby({ csrf, onExpired, onSnapshot }: { csrf: string; onExpired?: () => void; onSnapshot?: (snapshot: LobbySnapshot) => void }) {
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
      || ('creations' in body && (!Array.isArray(body.creations) || !body.creations.every(item => item && typeof item.universe_id === 'string'
        && typeof item.name === 'string' && typeof item.created_at === 'string' && item.state === 'starting')))
      || !body.revocations.every(item => item && ['account', 'device'].includes(item.scope)
        && ['pending', 'acknowledged'].includes(item.state) && typeof item.created_at === 'string')) throw new Error('projection');
    if (active.current && !signal.aborted) { setSnapshot(body as Projection); onSnapshot?.(body as Projection); setError(''); }
  }
  // While a created universe is starting, re-read quietly (a read never extends idle or rights).
  const starting = snapshot?.creations?.length ?? 0;
  useEffect(() => {
    if (!starting) return;
    const timer = window.setInterval(() => { void read(AbortSignal.timeout(10000)).catch(() => undefined); }, 4000);
    return () => window.clearInterval(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [starting]);
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
  return <section className="p-panel p-games-panel" id="parties" aria-labelledby="lobby-title">
    <div className="p-p-head"><h2 id="lobby-title"><Icon name="planet" />Mes parties</h2>
      <div className="p-tools"><button type="button" className="p-btn p-btn-sm" disabled={busy} onClick={() => { void refresh(); }}>Actualiser mes parties</button></div></div>
    {!snapshot && !error && <p className="p-empty" role="status">Chargement des participations…</p>}
    {!!snapshot?.creations?.length && <div className="p-games">{snapshot.creations.map(item =>
      <article key={item.universe_id} className="p-game p-game--starting" aria-busy="true">
        <img className="p-g-img" src={universeImage(item.universe_id)} alt="" width="640" height="360" loading="lazy" />
        <div className="p-g-body">
          <div className="p-g-title"><span className="p-g-emb"><Icon name="orbit" /></span><h3><span>{item.name}</span></h3></div>
          <div className="p-g-tags"><span className="p-chip"><Icon name="clock" />Création en cours</span></div>
          <p className="p-g-status">Le serveur de jeu prépare votre univers : galaxie, colonie de départ et adversaires.</p>
          <p className="p-g-note">La partie apparaîtra ici, prête à jouer, dans quelques instants.</p>
        </div>
      </article>)}</div>}
    {snapshot && snapshot.memberships.length === 0 && !snapshot.creations?.length && <p className="p-empty">Aucune participation à un univers. Aucune partie de démonstration n’est créée automatiquement.</p>}
    {!!snapshot?.memberships.length && <div className="p-games">{snapshot.memberships.map(item => {
      const live = item.desired_status === 'active' && item.delivery_state === 'applied' && !item.expired;
      const chip = item.delivery_state === 'pending' ? 'En attente' : item.desired_status === 'suspended' ? 'Suspendue' : item.desired_status === 'revoked' ? 'Révoquée' : item.expired ? 'À renouveler' : 'En cours';
      return <article key={item.membership_id} className="p-game membership">
        <img className="p-g-img" src={universeImage(item.universe_id)} alt="" width="640" height="360" loading="lazy" />
        <div className="p-g-body">
          <div className="p-g-title"><span className="p-g-emb"><Icon name="orbit" /></span><h3><span>{item.name}</span></h3></div>
          <div className="p-g-tags"><span className={`p-chip${live ? ' p-live' : ''}`}><Icon name="play" />{chip}</span></div>
          <p className="p-g-status">{item.delivery_state === 'pending' ? 'Confirmation de Game en attente' : item.desired_status === 'suspended' ? 'Participation suspendue' : item.desired_status === 'revoked' ? 'Accès révoqué' : item.expired ? 'Confirmation d’accès expirée' : 'Participation confirmée par Game'}</p>
          <dl className="p-g-info">
            <div><dt><Icon name="flag" />Empire :</dt><dd className="p-na" title="Implémentation backend nécessaire">N/D</dd></div>
            <div><dt><Icon name="layers" />Mode :</dt><dd className="p-na" title="Implémentation backend nécessaire">N/D</dd></div>
            {item.last_checked_at && <div><dt><Icon name="clock" />Dernière confirmation :</dt><dd><time dateTime={item.last_checked_at}>{new Date(item.last_checked_at).toLocaleString('fr-FR')}</time></dd></div>}
            <div><dt><Icon name="calendar" />Droits valables jusqu’au :</dt><dd><time dateTime={item.valid_until}>{new Date(item.valid_until).toLocaleString('fr-FR')}</time></dd></div>
          </dl>
          <p className="p-g-note">Empire, mode et tour de jeu : implémentation backend nécessaire.</p>
          <div className="p-g-act">
            {!error && item.entry_available && item.entry_url ? <a className="p-btn p-btn-glow" href={item.entry_url} referrerPolicy="no-referrer"><Icon name="play" />Entrer dans cet univers</a>
              : <p className="p-g-note">L’entrée requiert une adresse vérifiée et un accès actif confirmé par Game.</p>}
            {item.desired_status === 'active' && item.delivery_state === 'applied' && <button type="button" className="p-btn p-btn-sm" disabled={busy}
              onClick={() => { void renew(item.universe_id); }}>Confirmer de nouveaux droits pour cette partie</button>}
          </div>
        </div>
      </article>; })}</div>}
    {!!snapshot?.revocations.length && <div className="p-tab-pad p-revocations"><h3>Déconnexions des parties</h3>{snapshot.revocations.map((item, index) => <p key={index}>
      {item.scope === 'account' ? 'Tous les appareils' : 'Un appareil'} : {item.state === 'acknowledged' ? 'révocation confirmée par les services Game' : 'révocation encore en attente sur certains services Game'}
    </p>)}</div>}
    {error && <p className="p-empty form-error" role="alert">{error}</p>}
  </section>;
}

const images = ['partie-auralis', 'partie-orion', 'partie-nyx'];
/** Stable illustration per universe (decorative; the Portal knows no universe artwork yet). */
function universeImage(id: string) {
  let hash = 0;
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return `/assets/img/${images[hash % images.length]}.webp`;
}
