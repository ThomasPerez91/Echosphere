import { useEffect, useRef, useState } from 'react';
import { Icon } from '../theme/Icon';

type Membership = { membership_id: string; universe_id: string; name: string; desired_status: string;
  applied_status: string | null; delivery_state: 'pending' | 'applied'; expired: boolean;
  valid_until: string; last_checked_at: string | null; entry_available: boolean; entry_url?: string | null;
  /** UX-API-02/03: family, seats and, for the creator of a multi game, its invitations. */
  family?: string; creator?: boolean; seats_total?: number; seats_taken?: number; invite_mode?: 'link' | 'email';
  sent_invitations?: { id: string; email: string; state: string; expires_at: string }[] };
export type ReceivedInvitation = { id: string; universe_id: string; name: string; expires_at: string };
export type LobbySnapshot = Projection;
/** UX-API-02: universes this account created that Game has not started/granted yet. */
type Creation = { universe_id: string; name: string; created_at: string; state: 'starting' };
type Projection = { memberships: Membership[]; creations?: Creation[]; invitations?: ReceivedInvitation[]; revocations: { scope: string; state: string; created_at: string }[] };

function validEntry(value: string, universe: string) {
  try {
    const target = new URL(value);
    return target.protocol === 'https:' && !target.username && !target.password
      && !target.search && !target.hash && target.pathname === `/api/game/${universe}/start`;
  } catch { return false; }
}

export function Lobby({ csrf, onExpired, onSnapshot, version = 0 }: {
  csrf: string; onExpired?: () => void; onSnapshot?: (snapshot: LobbySnapshot) => void;
  /** Bumped by the page after an action elsewhere (an accepted invitation) to re-read the lobby. */
  version?: number;
}) {
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
      || ('invitations' in body && (!Array.isArray(body.invitations) || !body.invitations.every(item => item && typeof item.id === 'string'
        && typeof item.universe_id === 'string' && typeof item.name === 'string' && typeof item.expires_at === 'string')))
      || !body.memberships.every(item => (item.seats_total === undefined || (Number.isInteger(item.seats_total) && Number.isInteger(item.seats_taken)))
        && (item.invite_mode === undefined || ['link', 'email'].includes(item.invite_mode))
        && (item.sent_invitations === undefined || (Array.isArray(item.sent_invitations) && item.sent_invitations.every(
          (sent: unknown) => !!sent && typeof sent === 'object' && typeof (sent as { id?: unknown }).id === 'string'))))
      || ('creations' in body && (!Array.isArray(body.creations) || !body.creations.every(item => item && typeof item.universe_id === 'string'
        && typeof item.name === 'string' && typeof item.created_at === 'string' && item.state === 'starting')))
      || !body.revocations.every(item => item && ['account', 'device'].includes(item.scope)
        && ['pending', 'acknowledged'].includes(item.state) && typeof item.created_at === 'string')) throw new Error('projection');
    if (active.current && !signal.aborted) { setSnapshot(body as Projection); onSnapshot?.(body as Projection); setError(''); }
  }
  useEffect(() => {
    if (!version) return;
    void read(AbortSignal.timeout(10000)).catch(() => undefined);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);
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
            <div><dt><Icon name="layers" />Mode :</dt>{item.family === 'solo' ? <dd>Solo</dd> : item.family === 'private' ? <dd>Multijoueur</dd>
              : <dd className="p-na" title="Implémentation backend nécessaire">N/D</dd>}</div>
            {item.seats_total !== undefined && <div><dt><Icon name="users" />Joueurs :</dt><dd>{item.seats_taken} / {item.seats_total}</dd></div>}
            {item.last_checked_at && <div><dt><Icon name="clock" />Dernière confirmation :</dt><dd><time dateTime={item.last_checked_at}>{new Date(item.last_checked_at).toLocaleString('fr-FR')}</time></dd></div>}
            <div><dt><Icon name="calendar" />Droits valables jusqu’au :</dt><dd><time dateTime={item.valid_until}>{new Date(item.valid_until).toLocaleString('fr-FR')}</time></dd></div>
          </dl>
          <p className="p-g-note">Nom d’Empire et tour de jeu : implémentation backend nécessaire.</p>
          {item.creator && item.invite_mode && <InvitePanel csrf={csrf} item={item} onChanged={() => { void read(AbortSignal.timeout(10000)).catch(() => undefined); }} />}
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

const inviteErrors: Record<string, string> = {
  game_full: 'Toutes les places sont prises ou promises.', already_invited: 'Cette adresse a déjà une invitation en cours.',
  invitation_self: 'Vous êtes déjà dans cette partie.', invalid_request: 'Adresse email invalide.',
};

/** Creator of a multi game: share one link, or invite addresses one by one (Q59, mode fixed at creation). */
function InvitePanel({ csrf, item, onChanged }: { csrf: string; item: Membership; onChanged: () => void }) {
  const [link, setLink] = useState('');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const full = (item.seats_taken ?? 0) >= (item.seats_total ?? 0);
  async function post(path: string, body: object) {
    const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify(body), signal: AbortSignal.timeout(10000) });
    const data: unknown = await response.json().catch(() => null);
    const code = data && typeof data === 'object' && 'error' in data && data.error && typeof data.error === 'object' && 'code' in data.error ? String(data.error.code) : '';
    if (!response.ok) throw new Error(code || 'request');
    return data as Record<string, unknown>;
  }
  async function run(action: () => Promise<void>) {
    if (busy) return; setBusy(true); setMessage('');
    try { await action(); } catch (error) { setMessage(inviteErrors[(error as Error).message] ?? 'Action non confirmée. Réessayez.'); }
    finally { setBusy(false); }
  }
  const copy = () => { void navigator.clipboard?.writeText(link).then(() => setMessage('Lien copié.'), () => setMessage('Copiez le lien manuellement.')); };
  return <div className="p-invite" aria-label={`Inviter des joueurs dans ${item.name}`} role="group">
    <h4>Inviter des joueurs</h4>
    {full ? <p className="p-g-note">Toutes les places sont prises.</p> : item.invite_mode === 'link' ? <>
      <p className="p-g-note">Partagez ce lien : chaque personne connectée qui l’ouvre prend une place libre. Un nouveau lien remplace l’ancien.</p>
      <button type="button" className="p-btn p-btn-sm" disabled={busy} onClick={() => { void run(async () => {
        const data = await post(`/api/lobby/universes/${encodeURIComponent(item.universe_id)}/invite-link`, {});
        if (typeof data.url === 'string') setLink(data.url);
      }); }}>{link ? 'Générer un nouveau lien' : 'Générer un lien d’invitation'}</button>
      {link && <div className="p-invite-link"><label className="visually-hidden" htmlFor={`link-${item.universe_id}`}>Lien d’invitation</label>
        <input id={`link-${item.universe_id}`} readOnly value={link} onFocus={event => event.currentTarget.select()} />
        <button type="button" className="p-btn p-btn-sm" onClick={copy}>Copier le lien</button></div>}
    </> : <form onSubmit={event => { event.preventDefault(); void run(async () => {
      await post(`/api/lobby/universes/${encodeURIComponent(item.universe_id)}/invitations`, { email });
      setEmail(''); setMessage('Invitation envoyée.'); onChanged();
    }); }}>
      <label>Adresse email du joueur<input type="email" required maxLength={320} value={email} onChange={event => setEmail(event.target.value)} /></label>
      <button type="submit" className="p-btn p-btn-sm" disabled={busy}>Envoyer l’invitation</button>
    </form>}
    {!!item.sent_invitations?.length && <ul className="p-sent">{item.sent_invitations.map(sent => <li key={sent.id}>
      <span>{sent.email}</span><span className="p-chip">{({ open: 'En attente', accepted: 'Acceptée', declined: 'Refusée', revoked: 'Retirée' } as Record<string, string>)[sent.state] ?? sent.state}</span>
      {sent.state === 'open' && <button type="button" className="text-button" disabled={busy} onClick={() => { void run(async () => {
        await post(`/api/lobby/invitations/${encodeURIComponent(sent.id)}/revoke`, {}); onChanged(); }); }}>Retirer</button>}
    </li>)}</ul>}
    {message && <p className="p-g-note" role="status">{message}</p>}
  </div>;
}
