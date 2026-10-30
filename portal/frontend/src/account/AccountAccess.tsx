import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { RevocationStatus } from './RevocationStatus';
import { Lobby } from './Lobby';
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

export function AccountAccess({ verificationToken }: { verificationToken: string | null }) {
  const [bootstrapError, setBootstrapError] = useState(false);
  const [booting, setBooting] = useState(true);
  const [reload, setReload] = useState(0);
  const [receiptVersion, setReceiptVersion] = useState(0);
  const [state, setState] = useState<SessionState | null>(null);
  const [loginMode, setLoginMode] = useState(false);
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
  if (booting && !verificationToken && !state) return <p aria-live="polite">Vérification de votre compte…</p>;
  if (bootstrapError && !verificationToken) return <section className="panel"><h2>Compte indisponible</h2>
    <p role="alert">Impossible de confirmer votre connexion. Aucun changement n’a été demandé.</p>
    <button type="button" onClick={() => setReload(value => value + 1)}>Vérifier mon compte</button></section>;
  if (verificationToken) return <AccountForms verificationToken={verificationToken} />;
  return <>
    {notice && <p role="alert">{notice}</p>}
    {!mfaRecovering && !recovering && <RevocationStatus key={receiptVersion} />}
    {codes.length > 0 && <section className="panel"><h2>Vos dix codes de secours</h2><p>Conservez ces codes en lieu sûr. Ils ne seront plus consultables après fermeture de cet écran ; chaque code sert une seule fois.</p><pre className="recovery-codes">{codes.join('\n')}</pre><button type="button" onClick={() => setCodes([])}>Masquer les codes</button></section>}
    {state ? <section className="panel" aria-labelledby="sessions-title">
      <h2 id="sessions-title">Vos connexions</h2>
      <p>{state.user.email}</p>
      {!state.user.email_verified && <p>Confirmez votre adresse email avant de pouvoir accéder aux parties.</p>}
      <Lobby csrf={state.csrf_token} onExpired={() => { transition.current++; setState(null); setLoginMode(true);
        setNotice('Votre session n’est plus valide. Connectez-vous à nouveau.'); }} />
      <button type="button" disabled={pending} onClick={() => { void action(); }}>Actualiser mes connexions</button>
      <ul className="sessions-list">{(state.sessions ?? [{ id: state.session_id, current: true }]).map((item, index) => <li key={item.id}>
        <span>{item.current ? 'Cet appareil' : `Autre connexion ${index + 1}`}</span>
        <button type="button" disabled={pending} onClick={() => { void action(item.id); }}>{item.current ? 'Se déconnecter' : `Fermer la connexion ${index + 1}`}</button>
      </li>)}</ul>
      <MfaSettings csrf={state.csrf_token} onOutcome={mfaOutcome} />
      <SensitiveSettings csrf={state.csrf_token} onSignedOut={() => {
        transition.current++; setState(null); setLoginMode(true);
        setReceiptVersion(value => value + 1);
        setNotice('Compte déconnecté de tous les appareils sur le Portal. Déconnexion des parties en attente.');
      }} />
    </section> : <>
      {mfaRecovering ? <MfaRecovery onBack={() => setMfaRecovering(false)} onOutcome={mfaOutcome} /> : recovering ? <ResetRequestForm onBack={() => { setRecovering(false); setLoginMode(true); }} /> : loginMode ? <LoginForm onLogin={value => { transition.current++; setState(value); setNotice(''); }} /> : <AccountForms verificationToken={null} />}
      {!mfaRecovering && <button type="button" className="text-button" onClick={() => setMfaRecovering(true)}>J’ai perdu mes facteurs MFA</button>}
      {loginMode && !recovering && !mfaRecovering && <button type="button" className="text-button" onClick={() => setRecovering(true)}>Mot de passe oublié ?</button>}
      <button type="button" className="text-button" onClick={() => { setRecovering(false); setMfaRecovering(false); setLoginMode(value => !value); }}>{loginMode ? 'Créer un compte ou confirmer mon adresse' : 'Se connecter à mon compte'}</button>
    </>}
  </>;
}

function LoginForm({ onLogin }: { onLogin: (value: SessionState) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [factorChoice, setFactorChoice] = useState<FactorChoice>('none');
  const [factorCode, setFactorCode] = useState('');
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
        setError(code === 'mfa_required' ? 'Choisissez votre facteur MFA enregistré pour vous connecter.' : code === 'device_limit_reached' ? 'Limite d’appareils atteinte. Fermez une connexion depuis un appareil déjà connecté.'
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
      <FactorFields choice={factorChoice} setChoice={setFactorChoice} code={factorCode} setCode={setFactorCode} />
      <button type="submit" disabled={pending}>{pending ? 'Connexion en cours…' : 'Ouvrir ma session'}</button>
    </form>
    {error && <p role="alert" className="form-error">{error}</p>}
  </section>;
}
