import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

type Mode = 'register' | 'resend' | 'verify';

export function AccountForms({ verificationToken }: { verificationToken: string | null }) {
  const [mode, setMode] = useState<Mode>(verificationToken ? 'verify' : 'register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const active = useRef(false);

  useEffect(() => { active.current = true; return () => { active.current = false; controller.current?.abort(); }; }, []);

  function changeMode(next: Mode) {
    setMode(next); setPassword(''); setMessage(''); setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true); setError(''); setMessage('');
    const request = new AbortController();
    controller.current = request;
    const timer = window.setTimeout(() => request.abort(), 10000);
    try {
      const endpoint = mode === 'register' ? 'register' : `email/${mode}`;
      const payload = mode === 'verify' ? { token: verificationToken, password } : { email, password };
      const response = await fetch(`/api/accounts/${endpoint}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: request.signal,
      });
      const body: unknown = await response.json();
      if (!active.current) return;
      const status = typeof body === 'object' && body !== null && 'status' in body ? body.status : null;
      if (response.ok && status === (mode === 'verify' ? 'verified' : 'request_received')) {
        setPassword('');
        setMessage(mode === 'verify'
          ? 'Votre adresse est confirmée. La connexion est en préparation.'
          : 'Demande reçue. Si les conditions sont remplies, vous recevrez un lien de confirmation.');
      } else if (response.status === 429) {
        setError('Trop de demandes. Réessayez plus tard.');
      } else if (response.status === 503) {
        setError('Le service est temporairement indisponible. Réessayez plus tard.');
      } else {
        setError(mode === 'verify'
          ? 'Confirmation impossible. Vérifiez le lien et le mot de passe de ce compte.'
          : 'Demande impossible. Vérifiez votre adresse et utilisez un mot de passe de 15 à 128 caractères non compromis.');
      }
    } catch {
      if (active.current) setError('La réponse du service est indisponible. Vous pouvez réessayer.');
    } finally {
      window.clearTimeout(timer);
      if (active.current) setPending(false);
    }
  }

  return <section className="panel" aria-labelledby="account-title">
    <h2 id="account-title">{mode === 'verify' ? 'Confirmer votre adresse' : mode === 'resend' ? 'Recevoir un nouveau lien' : 'Créer votre compte'}</h2>
    <p>{mode === 'verify' ? 'Utilisez le mot de passe choisi lors de cette inscription. Le lien ne fonctionne qu’une fois.' : 'Votre compte sera indépendant de vos parties. La connexion et le lobby sont en préparation.'}</p>
    <form onSubmit={submit} aria-busy={pending}>
      {mode !== 'verify' && <label>Adresse email<input type="email" name="email" autoComplete="username" maxLength={320} required value={email} onChange={event => setEmail(event.target.value)} /></label>}
      <label>Mot de passe<input type="password" name="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} minLength={mode === 'register' ? 15 : 1} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} aria-describedby="password-help" /></label>
      <p id="password-help">15 à 128 caractères, espaces autorisés. N’utilisez pas un mot de passe courant ou compromis.</p>
      <button type="submit" disabled={pending}>{pending ? 'Traitement en cours…' : mode === 'verify' ? 'Confirmer mon adresse' : mode === 'resend' ? 'Renvoyer le lien' : 'Créer le compte'}</button>
    </form>
    {error && <p className="form-error" role="alert">{error}</p>}
    {message && <p className="form-success" role="status">{message}</p>}
    {mode !== 'verify' && <button className="text-button" type="button" disabled={pending} onClick={() => changeMode(mode === 'register' ? 'resend' : 'register')}>{mode === 'register' ? 'Déjà inscrit sans lien valide ?' : 'Revenir à l’inscription'}</button>}
  </section>;
}
