import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { RevocationStatus } from './RevocationStatus';
import { Lobby } from './Lobby';
import type { LobbySnapshot } from './Lobby';
import { Icon } from '../theme/Icon';
import { Pending } from '../site/Site';
import type { SignedIn } from '../site/Site';
import { NewGame } from './NewGame';
import { Link, paths } from '../router';
import { AccountForms } from './AccountForms';
import { ResetRequestForm, SensitiveSettings } from './SecurityForms';
import { FactorFields, MfaRecovery, MfaSettings } from './MfaForms';
import { factorProof } from './mfa-client';
import type { FactorChoice } from './mfa-client';

type SessionState = {
  status: 'authenticated'; user: { email: string; email_verified: boolean };
  csrf_token: string; session_id: string; expires_at?: string; idle_expires_at?: string; server_time?: string;
  sessions?: { id: string; current: boolean; expires_at: string; idle_expires_at: string }[];
};

function validState(body: unknown): body is SessionState {
  if (!body || typeof body !== 'object') return false;
  const value = body as Partial<SessionState>;
  return value.status === 'authenticated' && typeof value.csrf_token === 'string'
    && typeof value.session_id === 'string' && typeof value.user?.email === 'string'
    && typeof value.user.email_verified === 'boolean'
    && (value.sessions === undefined || (Array.isArray(value.sessions) && value.sessions.every(item =>
      typeof item?.id === 'string' && typeof item.current === 'boolean')));
}

const bootstrap = { 'X-Portal-Request': 'bootstrap' };

/** Which Portal page is shown. Signed out, every private page shows the login form. */
export type AccountPage = 'home' | 'login' | 'register' | 'games' | 'new-game' | 'account';

export function AccountAccess({ verificationToken, onSession, page = 'register', onNavigate }: {
  verificationToken: string | null;
  /** Lets the page switch between the public home and the player's space; never carries the CSRF token. */
  onSession?: (account: SignedIn | null) => void;
  page?: AccountPage;
  /** Moves between the login and registration pages when the visitor switches form. */
  onNavigate?: (path: string) => void;
}) {
  const [bootstrapError, setBootstrapError] = useState(false);
  const [booting, setBooting] = useState(true);
  const [reload, setReload] = useState(0);
  const [receiptVersion, setReceiptVersion] = useState(0);
  const [state, setState] = useState<SessionState | null>(null);
  const [loginMode, setLoginMode] = useState(page !== 'register');
  const [recovering, setRecovering] = useState(false);
  const [mfaRecovering, setMfaRecovering] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState(false);
  const active = useRef(false);
  const operation = useRef<AbortController | null>(null);
  const transition = useRef(0);
  const bootstrapFlight = useRef<AbortController | null>(null);
  const currentState = useRef(state); currentState.current = state;
  const [lobby, setLobby] = useState<LobbySnapshot | null>(null);
  const email = state?.user.email ?? null, verified = state?.user.email_verified ?? false;
  useEffect(() => { onSession?.(email ? { email, verified } : null); }, [email, verified, onSession]);
  useEffect(() => { if (!state) setLobby(null); }, [state]);
  useEffect(() => {
    if (page === 'home') return;
    setRecovering(false); setMfaRecovering(false); setLoginMode(page !== 'register');
  }, [page]);
  const switchForm = () => {
    setRecovering(false); setMfaRecovering(false);
    const next = !loginMode; setLoginMode(next);
    onNavigate?.(next ? paths.login : paths.register);
  };

  useEffect(() => {
    active.current = true; setBooting(true); setBootstrapError(false);
    const observed = transition.current;
    const controller = new AbortController(); bootstrapFlight.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 10000);
    void fetch('/api/auth/sessions', { headers: bootstrap, signal: controller.signal })
      .then(async response => {
        const body: unknown = await response.json();
        if (!active.current || bootstrapFlight.current !== controller || observed !== transition.current || controller.signal.aborted) return;
        if (response.ok && validState(body)) setState(body);
        else if (response.status === 401) {
          setState(null);
          if (currentState.current) { setLoginMode(true); setNotice('Votre session n’est plus valide. Connectez-vous à nouveau.'); }
        } else setBootstrapError(true);
      }).catch(() => { if (active.current && bootstrapFlight.current === controller && observed === transition.current) setBootstrapError(true); })
      .finally(() => { window.clearTimeout(timer); if (active.current && bootstrapFlight.current === controller && observed === transition.current) setBooting(false); });
    return () => { active.current = false; controller.abort(); operation.current?.abort(); };
  }, [reload]);

  useEffect(() => {
    if (!state?.expires_at || !state.idle_expires_at || !state.server_time) return;
    const deadline = Math.min(Date.parse(state.expires_at), Date.parse(state.idle_expires_at));
    const now = Date.parse(state.server_time);
    if (!Number.isFinite(deadline) || !Number.isFinite(now)) return;
    const timer = window.setTimeout(() => setReload(value => value + 1), Math.max(0, deadline - now) + 100);
    return () => window.clearTimeout(timer);
  }, [state]);

  async function action(target?: string) {
    if (!state || pending) return;
    const controller = new AbortController();
    operation.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 10000);
    setPending(true); setNotice('');
    try {
      const path = target ? `/sessions/${target}/logout` : '/navigation';
      const response = await fetch(`/api/auth${path}`, { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf_token },
        body: '{}', signal: controller.signal });
      if (!active.current || controller.signal.aborted) return;
      if (response.status === 401) { transition.current++; setState(null); setLoginMode(true); setNotice('Votre session n’est plus valide. Connectez-vous à nouveau.'); return; }
      if (response.status === 403) {
        const current = await fetch('/api/auth/sessions', { headers: bootstrap, signal: controller.signal });
        const body: unknown = await current.json();
        if (active.current && !controller.signal.aborted) {
          if (current.ok && validState(body)) setState(body);
          else if (current.status === 401) { transition.current++; setState(null); setLoginMode(true); }
          setNotice('Votre connexion a changé. Vérifiez son état puis réessayez.');
        }
        return;
      }
      if (!response.ok) throw new Error('request');
      const body: unknown = await response.json();
      if (target && body && typeof body === 'object' && 'current_session_closed' in body && body.current_session_closed === true) {
        transition.current++; setState(null); setLoginMode(true);
        setReceiptVersion(value => value + 1);
        setNotice('Compte déconnecté ici. Déconnexion des parties en attente.');
        return;
      }
      const refreshed = await fetch('/api/auth/sessions', { headers: bootstrap, signal: controller.signal });
      const snapshot: unknown = await refreshed.json();
      if (active.current && !controller.signal.aborted && refreshed.status === 401) {
        transition.current++; setState(null); setLoginMode(true);
        setNotice('Votre session n’est plus valide. Connectez-vous à nouveau.');
        return;
      }
      if (active.current && !controller.signal.aborted && refreshed.ok && validState(snapshot)) {
        setState(snapshot);
        if (target) setNotice('Connexion fermée. Déconnexion des parties de cet appareil en attente.');
      }
    } catch {
      if (active.current) setNotice('Action non confirmée. Réessayez pour vérifier son état.');
    } finally {
      window.clearTimeout(timer);
      if (active.current) setPending(false);
    }
  }

  function mfaOutcome(value: { global_logout?: boolean; backup_codes?: string[]; privileged_recovery_blocked?: boolean }) {
    if (value.backup_codes) setCodes(value.backup_codes);
    if (value.global_logout) {
      setReceiptVersion(value => value + 1);
      transition.current++; setState(null); setLoginMode(true); setMfaRecovering(false);
      setNotice(value.privileged_recovery_blocked ? 'Facteur rétabli. Les privilèges restent bloqués en attente d’une procédure approuvée.' : 'MFA modifiée. Reconnectez-vous normalement. Déconnexion des parties en attente.');
    }
  }
  if (page === 'home' && !verificationToken) return null; // the public home only needs to know whether a session exists
  if (booting && !verificationToken && !state) return <p aria-live="polite">Vérification de votre compte…</p>;
  if (bootstrapError && !verificationToken) return <section className="panel"><h2>Compte indisponible</h2>
    <p role="alert">Impossible de confirmer votre connexion. Aucun changement n’a été demandé.</p>
    <button type="button" onClick={() => setReload(value => value + 1)}>Vérifier mon compte</button></section>;
  if (verificationToken) return <AccountForms verificationToken={verificationToken} />;
  const expired = () => { transition.current++; setState(null); setLoginMode(true); setNotice('Votre session n’est plus valide. Connectez-vous à nouveau.'); };
  const games = state && <>
    <Stats snapshot={lobby} />
    <div className="p-dash-grid">
      <div className="p-games-col">
        <Lobby csrf={state.csrf_token} onSnapshot={setLobby} onExpired={expired} />
        {lobby && lobby.memberships.length === 0 && <section className="p-panel p-first-game" aria-labelledby="first-game-title">
          <div className="p-tab-pad"><h2 id="first-game-title">Aucune partie pour l’instant</h2>
            <p>Créez votre premier univers : vous y commencez avec une colonie, face à des Empires dirigés par l’IA.</p>
            <Link to={paths.newGame} className="p-btn p-btn-primary">Créer ma première partie</Link></div>
        </section>}
      </div>
      <div className="p-side">
        <section className="p-panel" aria-labelledby="invitations-title">
          <div className="p-p-head"><h2 id="invitations-title"><Icon name="mail" />Invitations</h2></div>
          <div className="p-tab-pad"><Pending what="Invitations à rejoindre une partie (accepter / refuser)." /></div>
        </section>
        <Activity snapshot={lobby} />
      </div>
    </div>
  </>;
  const account = state && <section className="p-panel p-account" id="securite" aria-labelledby="sessions-title">
    <div className="p-p-head"><h2 id="sessions-title"><Icon name="lock" />Vos connexions</h2></div>
    <div className="p-account-body">
      <p className="p-account-mail"><Icon name="user" />{state.user.email}</p>
      {!state.user.email_verified && <p>Confirmez votre adresse email avant de pouvoir accéder aux parties.</p>}
      <p className="p-account-help">Chaque appareil connecté à votre compte apparaît ici. Fermez ceux que vous n’utilisez plus.</p>
      <button type="button" disabled={pending} onClick={() => { void action(); }}>Actualiser mes connexions</button>
      <ul className="sessions-list">{(state.sessions ?? [{ id: state.session_id, current: true }]).map((item, index) => <li key={item.id}>
        <span>{item.current ? 'Cet appareil' : `Autre connexion ${index + 1}`}</span>
        <button type="button" disabled={pending} onClick={() => { void action(item.id); }}>{item.current ? 'Se déconnecter' : `Fermer la connexion ${index + 1}`}</button>
      </li>)}</ul>
      {/* Optional: kept out of the way, explained in plain words, never required to play. */}
      <details className="p-advanced">
        <summary>Sécurité avancée <small>facultatif</small></summary>
        <p className="p-account-help"><b>Double vérification (MFA).</b> En plus du mot de passe, la connexion demande un code à six chiffres
          d’une application (Google Authenticator, Microsoft Authenticator…) ou une clé de sécurité. Elle protège votre compte si votre mot de passe
          fuit. Vous pouvez jouer sans l’activer.</p>
        <MfaSettings csrf={state.csrf_token} onOutcome={mfaOutcome} />
        <p className="p-account-help"><b>Opérations sensibles.</b> Changer de mot de passe ou d’adresse, ou déconnecter le compte de tous les appareils.</p>
        <SensitiveSettings csrf={state.csrf_token} onSignedOut={() => {
          transition.current++; setState(null); setLoginMode(true);
          setReceiptVersion(value => value + 1);
          setNotice('Compte déconnecté de tous les appareils sur le Portal. Déconnexion des parties en attente.');
        }} />
      </details>
    </div>
  </section>;
  return <>
    {notice && <p role="alert">{notice}</p>}
    {!mfaRecovering && !recovering && <RevocationStatus key={receiptVersion} />}
    {codes.length > 0 && <section className="panel"><h2>Vos dix codes de secours</h2><p>Conservez ces codes en lieu sûr. Ils ne seront plus consultables après fermeture de cet écran ; chaque code sert une seule fois.</p><pre className="recovery-codes">{codes.join('\n')}</pre><button type="button" onClick={() => setCodes([])}>Masquer les codes</button></section>}
    {state ? (page === 'account' ? account : page === 'new-game' ? <NewGame /> : games) : <>
      {(page === 'games' || page === 'new-game' || page === 'account') && !mfaRecovering && !recovering && <p className="p-auth-note">Connectez-vous pour accéder à cette page.</p>}
      {mfaRecovering ? <MfaRecovery onBack={() => setMfaRecovering(false)} onOutcome={mfaOutcome} /> : recovering ? <ResetRequestForm onBack={() => { setRecovering(false); setLoginMode(true); }} /> : loginMode ? <LoginForm onLogin={value => {
        // Login deleted the previous receipt server-side; never keep showing its stale status.
        transition.current++; setState(value); setNotice(''); setReceiptVersion(version => version + 1);
      }} /> : <AccountForms verificationToken={null} />}
      <div className="p-auth-links">
        {loginMode && !recovering && !mfaRecovering && <button type="button" className="text-button" onClick={() => setRecovering(true)}>Mot de passe oublié ?</button>}
        <button type="button" className="text-button" onClick={switchForm}>{loginMode ? 'Pas encore de compte ? Créer un compte' : 'Se connecter à mon compte'}</button>
        {loginMode && !mfaRecovering && <button type="button" className="text-button p-quiet" onClick={() => setMfaRecovering(true)}>Double vérification perdue (téléphone ou clé) ?</button>}
      </div>
    </>}
  </>;
}

function LoginForm({ onLogin }: { onLogin: (value: SessionState) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [factorChoice, setFactorChoice] = useState<FactorChoice>('none');
  const [factorCode, setFactorCode] = useState('');
  const [secondFactor, setSecondFactor] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const operation = useRef<AbortController | null>(null);
  const active = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; operation.current?.abort(); }; }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const controller = new AbortController();
    operation.current = controller;
    const timer = window.setTimeout(() => controller.abort(), factorChoice === 'webauthn' ? 120000 : 10000);
    setPending(true); setError('');
    try {
      const challenge = await fetch('/api/auth/challenge', { headers: bootstrap, signal: controller.signal });
      const proof: unknown = await challenge.json();
      if (!challenge.ok || !proof || typeof proof !== 'object' || !('csrf_token' in proof) || typeof proof.csrf_token !== 'string') throw new Error('challenge');
      const factor = await factorProof(factorChoice, factorCode, 'login', null, password, proof.csrf_token, controller.signal, email);
      const response = await fetch('/api/auth/login', { method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': proof.csrf_token },
        body: JSON.stringify({ email, password, factor }), signal: controller.signal });
      const body: unknown = await response.json();
      if (!active.current || controller.signal.aborted) return;
      if (response.ok && validState(body)) { setPassword(''); onLogin(body); }
      else {
        const code = body && typeof body === 'object' && 'error' in body && body.error && typeof body.error === 'object' && 'code' in body.error ? body.error.code : null;
        if (code === 'mfa_required') setSecondFactor(true);
        setError(code === 'mfa_required' ? 'Ce compte utilise la double vérification : choisissez votre code ou votre clé ci-dessous.' : code === 'device_limit_reached' ? 'Limite d’appareils atteinte. Fermez une connexion depuis un appareil déjà connecté.'
          : response.status === 429 ? 'Trop de tentatives. Réessayez plus tard.'
          : response.status === 503 ? 'Le service est temporairement indisponible.'
          : 'Connexion impossible. Vérifiez votre adresse et votre mot de passe.');
      }
    } catch { if (active.current) setError('Connexion non confirmée. Réessayez.'); }
    finally { window.clearTimeout(timer); if (active.current) setPending(false); }
  }

  return <section className="panel" aria-labelledby="login-title">
    <h2 id="login-title">Connexion au compte</h2>
    <form onSubmit={submit} aria-busy={pending}>
      <label>Adresse email<input name="email" type="email" autoComplete="username" required maxLength={320} value={email} onChange={event => setEmail(event.target.value)} /></label>
      <label>Mot de passe<input name="password" type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={event => setPassword(event.target.value)} /></label>
      {secondFactor ? <FactorFields choice={factorChoice} setChoice={setFactorChoice} code={factorCode} setCode={setFactorCode} />
        : <button type="button" className="text-button p-quiet" onClick={() => setSecondFactor(true)}>J’ai activé la double vérification</button>}
      <button type="submit" disabled={pending}>{pending ? 'Connexion en cours…' : 'Ouvrir ma session'}</button>
    </form>
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}

/** Mockup stat strip: counts come from the lobby projection, the rest is not provided by the server yet. */
function Stats({ snapshot }: { snapshot: LobbySnapshot | null }) {
  const live = snapshot?.memberships.filter(item => item.desired_status === 'active' && item.delivery_state === 'applied' && !item.expired).length;
  const tile = (icon: 'gamepad' | 'planet', value: number | undefined, label: string) => <div><Icon name={icon} />
    <p><b>{value ?? '…'}</b><span>{label}</span></p></div>;
  return <div className="p-stats" aria-label="Vos parties en chiffres">
    {tile('gamepad', live, 'Parties actives')}
    {tile('planet', snapshot?.memberships.length, 'Univers rejoints')}
    <div className="p-stat-pending"><Icon name="layers" /><div className="p-stat-body"><span>Tours récents</span><Pending compact /></div></div>
    <div className="p-stat-pending"><Icon name="users" /><div className="p-stat-body"><span>Alliés et partenaires</span><Pending compact /></div></div>
  </div>;
}

function since(date: string) {
  const ms = Date.now() - Date.parse(date);
  if (!Number.isFinite(ms)) return '';
  const minutes = Math.max(0, Math.round(ms / 60000));
  return minutes < 60 ? `Il y a ${minutes} min` : minutes < 1440 ? `Il y a ${Math.round(minutes / 60)} h` : `Il y a ${Math.round(minutes / 1440)} j`;
}

/** Recent activity made only of dated facts the Portal holds: Game confirmations and logout receipts. */
function Activity({ snapshot }: { snapshot: LobbySnapshot | null }) {
  const items = [
    ...(snapshot?.memberships ?? []).filter(item => item.last_checked_at).map(item => ({ at: item.last_checked_at!, icon: 'play' as const,
      text: <><b>{item.name}</b> — accès vérifié auprès de Game</> })),
    ...(snapshot?.revocations ?? []).map(item => ({ at: item.created_at, icon: 'logout' as const,
      text: <>Déconnexion des parties ({item.scope === 'account' ? 'tous les appareils' : 'un appareil'}) — {item.state === 'acknowledged' ? 'terminée' : 'en cours'}</> })),
  ].sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, 6);
  return <section className="p-panel" aria-labelledby="activity-title">
    <div className="p-p-head"><h2 id="activity-title"><Icon name="news" />Activité récente</h2></div>
    {items.length ? <ul className="p-activity">{items.map((item, index) => <li key={index}><Icon name={item.icon} /><span>{item.text}</span>
      <time dateTime={item.at}>{since(item.at)}</time></li>)}</ul>
      : <p className="p-empty">Aucune activité datée pour l’instant.</p>}
    <div className="p-tab-pad"><Pending compact what="Journal des parties (tours, recherches, messages)." /></div>
  </section>;
}
