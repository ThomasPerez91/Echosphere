import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

import type { SecurityLink } from './security-links';
import { FactorFields } from './MfaForms';
import { factorProof } from './mfa-client';
import type { FactorChoice } from './mfa-client';

class PublicOperationError extends Error {}

type Result = { old_confirmation_required?: boolean; status?: string; proof?: string; error?: { code?: string } };
async function post(path: string, payload: unknown, signal: AbortSignal, csrf?: string): Promise<Result> {
  const response = await fetch(`/api/security/${path}`, { method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}) },
    body: JSON.stringify(payload) });
  const result: Result = await response.json();
  if (!response.ok) throw new PublicOperationError(response.status === 429 ? 'Trop de demandes. Réessayez plus tard.'
    : response.status === 503 ? 'Service temporairement indisponible. Réessayez plus tard.'
    : result.error?.code === 'additional_proof_required' ? 'Ce compte nécessite une preuve MFA valide avec le facteur autorisé.'
    : 'Opération non confirmée. Vérifiez vos preuves et réessayez depuis un lien ou une connexion valide.');
  return result;
}

function useOperation() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const operation = useRef<AbortController | null>(null);
  const active = useRef(false);
  useEffect(() => { active.current = true; return () => { active.current = false; operation.current?.abort(); }; }, []);
  async function run(task: (signal: AbortSignal) => Promise<void>) {
    if (pending) return;
    const controller = new AbortController();
    operation.current = controller;
    const timer = window.setTimeout(() => controller.abort(), 120000);
    setPending(true); setError('');
    try { await task(controller.signal); }
    catch (reason) { if (active.current) setError(reason instanceof PublicOperationError ? reason.message : 'Réponse non confirmée. Vérifiez l’état avant de réessayer.'); }
    finally { window.clearTimeout(timer); if (active.current) setPending(false); }
  }
  return { pending, error, run, active };
}

export function ResetRequestForm({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const operation = useOperation();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void operation.run(async signal => {
      const result = await post('password/reset/request', { email }, signal);
      if (result.status !== 'request_received') throw new PublicOperationError('Réponse non confirmée. Réessayez.');
      if (operation.active.current) setMessage('Demande reçue. Si les conditions sont remplies, vous recevrez un lien valable 30 minutes.');
    });
  }
  return <section className="panel"><h2>Récupérer mon mot de passe</h2>
    <form onSubmit={submit} aria-busy={operation.pending}>
      <label>Adresse email<input type="email" autoComplete="username" maxLength={320} required value={email} onChange={event => setEmail(event.target.value)} /></label>
      <button disabled={operation.pending}>Demander un lien de récupération</button>
    </form>
    {operation.error && <p role="alert">{operation.error}</p>}{message && <p role="status">{message}</p>}
    <button className="text-button" type="button" onClick={onBack}>Revenir à la connexion</button>
  </section>;
}

export function RecoveryForm({ link, onBack }: { link: SecurityLink; onBack: () => void }) {
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [message, setMessage] = useState('');
  const [mismatch, setMismatch] = useState(false);
  const operation = useOperation();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (link.kind === 'alert') return;
    setMismatch(false);
    if (link.kind === 'reset' && password !== confirmation) { setMismatch(true); return; }
    void operation.run(async signal => {
      const result = await post(link.kind === 'reset' ? 'password/reset/confirm' : 'email/confirm',
        link.kind === 'reset' ? { token: link.token, new_password: password } : { token: link.token }, signal);
      if (operation.active.current) {
        setPassword(''); setConfirmation('');
        if (result.status === 'additional_confirmation_required') setMessage('Cette adresse est confirmée. Confirmez l’autre adresse depuis son lien avant l’échéance de la demande.');
        else if (result.status === 'email_changed' || result.status === 'password_reset') setMessage('Modification réussie. Connectez-vous à nouveau avec vos nouveaux identifiants. Déconnexion des parties en attente.');
        else throw new PublicOperationError('Réponse non confirmée. Vérifiez l’état avant de réessayer.');
      }
    });
  }
  return <section className="panel"><h2>{link.kind === 'reset' ? 'Choisir un nouveau mot de passe' : link.kind === 'email' ? 'Confirmer le changement d’adresse' : 'Opération non reconnue'}</h2>
    {link.kind === 'alert' ? <p>Connectez-vous pour changer votre mot de passe et déconnecter tous les appareils. Si nécessaire, demandez un lien de récupération. Aucun email seul ne contourne la MFA ni ne rétablit automatiquement une ancienne adresse.</p> : <form onSubmit={submit} aria-busy={operation.pending}>
      {link.kind === 'reset' && <>
        <label>Nouveau mot de passe<input type="password" autoComplete="new-password" minLength={15} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
        <label>Confirmer le nouveau mot de passe<input type="password" autoComplete="new-password" minLength={15} maxLength={128} required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
      </>}
      {link.kind === 'email' && <p>Les deux adresses doivent être confirmées pour la même demande, dans l’heure suivant sa création. La connexion qui a demandé le changement doit encore être valide.</p>}
      <button disabled={operation.pending || !!message}>{link.kind === 'reset' ? 'Réinitialiser mon mot de passe' : 'Confirmer cette adresse'}</button>
    </form>}
    {mismatch && <p role="alert">Les mots de passe ne correspondent pas.</p>}
    {operation.error && <p role="alert">{operation.error}</p>}{message && <p role="status">{message}</p>}
    <button type="button" className="text-button" onClick={onBack}>Retour au compte</button>
  </section>;
}

export function SensitiveSettings({ csrf, onSignedOut }: { csrf: string; onSignedOut: () => void }) {
  const [action, setAction] = useState<'password_change' | 'email_change' | 'logout_all'>('password_change');
  const [password, setPassword] = useState('');
  const [factorChoice, setFactorChoice] = useState<FactorChoice>('none');
  const [factorCode, setFactorCode] = useState('');
  const [nextPassword, setNextPassword] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const operation = useOperation();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage('');
    void operation.run(async signal => {
      const parameters = action === 'password_change' ? { new_password: nextPassword } : action === 'email_change' ? { new_email: email } : {};
      const factor = await factorProof(factorChoice, factorCode, action, action === 'password_change' ? nextPassword : action === 'email_change' ? email : null, password, csrf, signal);
      const grant = await post('step-up', { action, current_password: password, ...parameters, factor }, signal, csrf);
      if (typeof grant.proof !== 'string') throw new PublicOperationError('Réauthentification non confirmée. Réessayez.');
      const result = await post(action === 'password_change' ? 'password/change' : action === 'email_change' ? 'email/request' : 'logout-all',
        { proof: grant.proof, ...parameters }, signal, csrf);
      if (!operation.active.current) return;
      setPassword(''); setNextPassword(''); setFactorCode('');
      if (result.status === 'confirmation_required') setMessage(result.old_confirmation_required === false ? 'Demande enregistrée avec MFA. Confirmez la nouvelle adresse avant l’échéance d’une heure.' : 'Demande enregistrée. Confirmez l’ancienne et la nouvelle adresse dans un délai commun d’une heure.');
      else if (result.status === 'password_changed' || result.status === 'portal_logged_out') onSignedOut();
      else throw new PublicOperationError('Réponse non confirmée. Vérifiez l’état avant de réessayer.');
    });
  }
  return <div className="security-settings"><h3>Sécurité du compte</h3>
    <p>Un changement réussi de mot de passe ou d’email déconnecte tous les appareils. Sans MFA, les deux adresses sont à confirmer. Avec une preuve MFA forte, seule la nouvelle adresse doit être confirmée.</p>
    <form onSubmit={submit} aria-busy={operation.pending}>
      <label>Opération de sécurité<select disabled={operation.pending} value={action} onChange={event => { setAction(event.target.value as typeof action); setPassword(''); setNextPassword(''); setMessage(''); }}>
        <option value="password_change">Changer le mot de passe</option><option value="email_change">Changer l’adresse email</option><option value="logout_all">Déconnecter tous les appareils</option>
      </select></label>
      <label>Mot de passe actuel<input type="password" autoComplete="current-password" maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
      {action === 'password_change' && <label>Nouveau mot de passe<input type="password" autoComplete="new-password" minLength={15} maxLength={128} required value={nextPassword} onChange={event => setNextPassword(event.target.value)} /></label>}
      {action === 'email_change' && <label>Nouvelle adresse email<input type="email" autoComplete="email" maxLength={320} required value={email} onChange={event => setEmail(event.target.value)} /></label>}
      <FactorFields choice={factorChoice} setChoice={setFactorChoice} code={factorCode} setCode={setFactorCode} />
      <button disabled={operation.pending}>{action === 'password_change' ? 'Changer mon mot de passe' : action === 'email_change' ? 'Demander le changement d’email' : 'Déconnecter tous mes appareils'}</button>
    </form>
    {operation.error && <p role="alert">{operation.error}</p>}{message && <p role="status">{message}</p>}
  </div>;
}
