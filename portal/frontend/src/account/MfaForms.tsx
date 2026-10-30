import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { WebAuthnAbortService } from '@simplewebauthn/browser';
import { factorProof, mfaPost, registration } from './mfa-client';
import type { FactorChoice } from './mfa-client';

type Outcome = { global_logout?: boolean; backup_codes?: string[]; privileged_recovery_blocked?: boolean };
type Status = { enabled: boolean; totp: boolean; credentials: { id: string; name: string }[] };
type Pending = { challenge_id: string; secret: string; uri: string };

export function FactorFields({ choice, setChoice, code, setCode }: { choice: FactorChoice; setChoice: (choice: FactorChoice) => void; code: string; setCode: (code: string) => void }) {
  return <>
    <label>Preuve MFA<select value={choice} onChange={event => { setChoice(event.target.value as FactorChoice); setCode(''); }}>
      <option value="none">Compte sans MFA</option><option value="totp">Application TOTP</option><option value="webauthn">WebAuthn / passkey</option>
    </select></label>
    {choice === 'totp' && <label>Code du facteur enregistré<input type="password" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required value={code} onChange={event => setCode(event.target.value)} /></label>}
  </>;
}

export function MfaSettings({ csrf, onOutcome }: { csrf: string; onOutcome: (value: Outcome) => void }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [operation, setOperation] = useState('totp');
  const [name, setName] = useState('Mon authentificateur');
  const [target, setTarget] = useState('');
  const [password, setPassword] = useState('');
  const [choice, setChoice] = useState<FactorChoice>('none');
  const [code, setCode] = useState('');
  const [newCode, setNewCode] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const active = useRef(false);
  const current = useRef<AbortController | null>(null);
  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    void fetch('/api/mfa/status', { headers: { 'X-Portal-Request': 'bootstrap' }, signal: controller.signal }).then(async response => {
      const body = await response.json();
      if (active.current && !controller.signal.aborted && response.ok && typeof body.enabled === 'boolean' && Array.isArray(body.credentials)) setStatus(body);
    }).catch(() => {});
    return () => { active.current = false; controller.abort(); current.current?.abort(); WebAuthnAbortService.cancelCeremony(); };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    const controller = new AbortController(); current.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 120000);
    setBusy(true); setError(''); setNotice('');
    try {
      let result: Outcome;
      if (pending) result = await mfaPost('enroll/finish', { challenge_id: pending.challenge_id, totp: newCode }, csrf, controller.signal);
      else {
        const enroll = operation === 'totp' || operation === 'webauthn' || operation === 'replace';
        const action = enroll ? 'mfa_enroll' : operation === 'backup' ? 'mfa_backup_codes' : operation === 'disable' ? 'mfa_disable' : 'mfa_remove';
        const parameters = enroll ? { kind: operation === 'totp' ? 'totp' : 'webauthn', name: name.trim(), replace_id: operation === 'replace' ? target : null }
          : action === 'mfa_remove' ? { kind: operation === 'remove_totp' ? 'totp' : 'webauthn', id: operation === 'remove_totp' ? null : target } : null;
        const factor = await factorProof(choice, code, action, parameters, password, csrf, controller.signal);
        const response = await fetch('/api/security/step-up', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ action, parameters, current_password: password, factor }), signal: controller.signal });
        const grant = await response.json();
        if (!response.ok || typeof grant.proof !== 'string') throw new Error('proof');
        if (enroll) {
          const start = await mfaPost('enroll/begin', { proof: grant.proof, ...parameters }, csrf, controller.signal);
          if (operation === 'totp') { if (active.current) { setPending(start); setPassword(''); setCode(''); } return; }
          const credential = await registration(start.options, controller.signal);
          result = await mfaPost('enroll/finish', { challenge_id: start.challenge_id, credential }, csrf, controller.signal);
        } else result = await mfaPost('manage', { proof: grant.proof, action, parameters }, csrf, controller.signal);
      }
      if (!active.current) return;
      setPending(null); setPassword(''); setCode(''); setNewCode('');
      onOutcome(result);
      if (!result.global_logout) {
        const response = await fetch('/api/mfa/status', { headers: { 'X-Portal-Request': 'bootstrap' }, signal: controller.signal });
        const body = await response.json(); if (active.current && response.ok) setStatus(body);
        if (active.current) setNotice('Sécurité modifiée. Vos connexions restent actives.');
      }
    } catch { if (active.current) setError('Preuve ou opération MFA non confirmée. Un code déjà utilisé ne peut pas être rejoué : attendez le suivant ou utilisez WebAuthn.'); }
    finally { window.clearTimeout(timer); if (active.current) setBusy(false); }
  }
  return <div className="security-settings"><h3>Authentification multifacteur</h3>
    <p>MFA facultative pour les joueurs. Une fois activée, votre facteur sera requis à la connexion et aux actions sensibles.</p>
    {status && <p>{status.enabled ? 'MFA activée' : 'MFA non activée'} · {status.totp ? 'Application TOTP enregistrée' : 'Pas de TOTP'} · {status.credentials.length}/5 WebAuthn</p>}
    {status?.credentials.map(item => <p key={item.id}>WebAuthn : {item.name}</p>)}
    <form onSubmit={submit} aria-busy={busy}>
      {pending ? <>
        <p>Ajoutez manuellement cette clé dans votre application TOTP. Elle ne sera plus affichée après cette étape.</p>
        <pre className="recovery-codes">{pending.secret}</pre>
        <label>Code de la nouvelle application<input type="password" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" required maxLength={6} value={newCode} onChange={event => setNewCode(event.target.value)} /></label>
      </> : <>
        <label>Opération MFA<select disabled={busy} value={operation} onChange={event => { setOperation(event.target.value); setPassword(''); setCode(''); }}>
          <option value="totp">Ajouter / remplacer TOTP</option><option value="webauthn">Ajouter WebAuthn / passkey</option>
          {status?.enabled && <><option value="replace">Remplacer WebAuthn</option><option value="remove_totp">Supprimer TOTP</option><option value="remove_web">Supprimer WebAuthn</option><option value="backup">Régénérer les secours</option><option value="disable">Désactiver la MFA</option></>}
        </select></label>
        {(operation === 'totp' || operation === 'webauthn' || operation === 'replace') && <label>Nom de l’authentificateur<input required maxLength={80} value={name} onChange={event => setName(event.target.value)} /></label>}
        {(operation === 'replace' || operation === 'remove_web') && <label>Authentificateur à remplacer ou supprimer<select required value={target} onChange={event => setTarget(event.target.value)}><option value="">Choisir</option>{status?.credentials.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        <label>Mot de passe pour la MFA<input type="password" autoComplete="current-password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
        <FactorFields choice={choice} setChoice={setChoice} code={code} setCode={setCode} />
      </>}
      <button disabled={busy}>{pending ? 'Confirmer le nouveau TOTP' : 'Valider cette opération MFA'}</button>
    </form>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
  </div>;
}

export function MfaRecovery({ onBack, onOutcome }: { onBack: () => void; onOutcome: (value: Outcome) => void }) {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [backup, setBackup] = useState('');
  const [recoveryCsrf, setRecoveryCsrf] = useState(''); const [kind, setKind] = useState('totp'); const [name, setName] = useState('Authentificateur restauré');
  const [pending, setPending] = useState<Pending | null>(null); const [code, setCode] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const active = useRef(false); const current = useRef<AbortController | null>(null);
  useEffect(() => { active.current = true; return () => { active.current = false; current.current?.abort(); WebAuthnAbortService.cancelCeremony(); }; }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return; const controller = new AbortController(); current.current = controller; const timer = window.setTimeout(() => controller.abort(), 120000); setBusy(true); setError('');
    try {
      if (!recoveryCsrf) {
        const preauth = await fetch('/api/auth/challenge', { headers: { 'X-Portal-Request': 'bootstrap' }, signal: controller.signal });
        const initial = await preauth.json();
        const result = await mfaPost('recovery/start', { email, password, backup_code: backup }, initial.csrf_token, controller.signal);
        if (active.current) { setRecoveryCsrf(result.csrf_token); setPassword(''); setBackup(''); } return;
      }
      let outcome: Outcome;
      if (pending) outcome = await mfaPost('recovery/enroll/finish', { challenge_id: pending.challenge_id, totp: code }, recoveryCsrf, controller.signal);
      else {
        const start = await mfaPost('recovery/enroll/begin', { kind, name: name.trim() }, recoveryCsrf, controller.signal);
        if (kind === 'totp') { if (active.current) setPending(start); return; }
        const credential = await registration(start.options, controller.signal);
        outcome = await mfaPost('recovery/enroll/finish', { challenge_id: start.challenge_id, credential }, recoveryCsrf, controller.signal);
      }
      if (active.current) onOutcome(outcome);
    } catch { if (active.current) setError('Récupération non confirmée. Les facteurs et codes perdus ne peuvent pas être remplacés par le seul email.'); }
    finally { window.clearTimeout(timer); if (active.current) setBusy(false); }
  }
  return <section className="panel"><h2>Récupérer ma MFA</h2><p>Mot de passe et code de secours à usage unique. Quinze minutes pour rétablir un facteur, sans accès aux parties ni privilèges. Sans aucun facteur ou secours, le compte reste bloqué : aucune procédure support automatique n’est disponible.</p>
    <form onSubmit={submit} aria-busy={busy}>
      {!recoveryCsrf ? <>
        <label>Email du compte MFA<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} /></label>
        <label>Mot de passe de récupération MFA<input type="password" autoComplete="current-password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
        <label>Code de secours<input type="password" autoComplete="off" maxLength={64} required value={backup} onChange={event => setBackup(event.target.value)} /></label>
      </> : pending ? <><pre className="recovery-codes">{pending.secret}</pre><label>Code du TOTP restauré<input type="password" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={event => setCode(event.target.value)} /></label></> : <>
        <label>Facteur à rétablir<select value={kind} onChange={event => setKind(event.target.value)}><option value="totp">TOTP</option><option value="webauthn">WebAuthn / passkey</option></select></label>
        <label>Nom du facteur restauré<input required maxLength={80} value={name} onChange={event => setName(event.target.value)} /></label>
      </>}
      <button disabled={busy}>{!recoveryCsrf ? 'Ouvrir la récupération limitée' : pending ? 'Confirmer le facteur restauré' : 'Enregistrer le nouveau facteur'}</button>
    </form>
    {error && <p role="alert">{error}</p>}<button type="button" className="text-button" onClick={onBack}>Revenir au compte</button>
  </section>;
}
