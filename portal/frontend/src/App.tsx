import { useEffect, useState } from 'react';
import { consumeVerificationFragment } from './account/verification';
import { AccountAccess } from './account/AccountAccess';
import { RecoveryForm } from './account/SecurityForms';
import { consumeSecurityFragment } from './account/security-links';
import type { SecurityLink } from './account/security-links';
import { useReadiness } from './useReadiness';

export default function App({ verificationToken = null, securityLink = null }: { verificationToken?: string | null; securityLink?: SecurityLink | null }) {
  const [security, setSecurity] = useState(securityLink);
  const [token, setToken] = useState(verificationToken);
  useEffect(() => {
    const read = () => {
      const next = consumeVerificationFragment();
      const sensitive = consumeSecurityFragment();
      if (next) { setToken(next); setSecurity(null); }
      if (sensitive) { setSecurity(sensitive); setToken(null); }
    };
    window.addEventListener('hashchange', read);
    return () => window.removeEventListener('hashchange', read);
  }, []);
  const { status, retry } = useReadiness();
  const message = { checking: 'Vérification du Portal', connected: 'Portal disponible', unavailable: 'Portal indisponible' }[status];

  return <div className="portal-shell">
    <a className="skip-link" href="#main-content">Aller au contenu</a>
    <header><a className="brand" href="/">◈ Echosphere<span>.</span></a><span className="portal-label">ESPACE COMPTE</span></header>
    <main id="main-content" tabIndex={-1}>
      <p className="eyebrow">UN COMPTE, PLUSIEURS HORIZONS</p>
      <h1>Votre prochain univers<br />commence ici.</h1>
      <p className="intro">Le Portal réunira votre compte et vos parties. Le jeu continuera de progresser à son propre rythme.</p>
      {security ? <RecoveryForm key={security.kind === 'alert' ? 'alert' : security.token} link={security} onBack={() => setSecurity(null)} /> : <AccountAccess key={token ?? 'public'} verificationToken={token} />}
      <section className="panel connection" aria-labelledby="connection-title">
        <div><h2 id="connection-title">Connexion au Portal</h2><p role="status" aria-live="polite">{message}</p></div>
        <button type="button" onClick={retry} disabled={status === 'checking'}>Vérifier à nouveau</button>
      </section>
    </main>
    <footer>Version de développement · Echosphere</footer>
  </div>;
}
