import { useEffect, useState } from 'react';
import { consumeVerificationFragment } from './account/verification';
import { AccountAccess } from './account/AccountAccess';
import { RecoveryForm } from './account/SecurityForms';
import { consumeSecurityFragment } from './account/security-links';
import type { SecurityLink } from './account/security-links';
import { useReadiness } from './useReadiness';
import { DashHero, HomeHero, HomeSections, JoinBand, Logo, SiteFooter, SiteHeader } from './site/Site';
import type { AuthKind, SignedIn } from './site/Site';
import './theme/fonts.css';
import './theme/portail.css';

export default function App({ verificationToken = null, securityLink = null }: { verificationToken?: string | null; securityLink?: SecurityLink | null }) {
  const [security, setSecurity] = useState(securityLink);
  const [token, setToken] = useState(verificationToken);
  const [account, setAccount] = useState<SignedIn | null>(null);
  const [request, setRequest] = useState<{ kind: AuthKind; seq: number } | null>(null);
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
  const signedIn = !!account && !security && !token;
  const auth = (kind: AuthKind) => {
    setSecurity(null);
    setRequest(previous => ({ kind, seq: (previous?.seq ?? 0) + 1 }));
    const zone = document.getElementById('compte');
    zone?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    window.setTimeout(() => zone?.querySelector<HTMLElement>('input, h2')?.focus({ preventScroll: true }), 50);
  };

  const connection = <section className="p-connection" aria-labelledby="connection-title">
    <div><h2 id="connection-title">Connexion au Portal</h2>
      <p role="status" aria-live="polite" className={`p-ready p-ready--${status}`}><span className="p-ready-dot" aria-hidden="true" />{message}</p></div>
    <button type="button" className="p-btn p-btn-sm" onClick={retry} disabled={status === 'checking'}>Vérifier à nouveau</button>
  </section>;

  return <div className="p-app">
    <div className="p-sky" aria-hidden="true" />
    <a className="p-skip-link" href="#main-content">Aller au contenu</a>
    <SiteHeader account={signedIn ? account : null} onAuth={auth} />
    <main id="main-content" tabIndex={-1}>
      {signedIn ? <DashHero /> : <HomeHero onAuth={auth} />}
      <div className="p-wrap">
        {/* AccountAccess keeps the same place in the tree: signing in or out never remounts it. */}
        <section id="compte" className={signedIn ? 'p-account-zone' : 'p-auth-zone'} aria-label={signedIn ? undefined : 'Votre compte'}>
          {!signedIn && <aside className="p-auth-side" aria-hidden="true"><Logo big /></aside>}
          <div className={signedIn ? 'p-forms p-dash' : 'p-panel p-glow p-auth-card p-forms'}>
            {!signedIn && <div className="p-auth-intro"><p className="p-auth-title"><img src="/assets/img/logo-echosphere-embleme.webp" alt="" width="48" height="48" />Espace compte</p>
              <span className="p-rule" aria-hidden="true" />
              <p className="p-lead">Un compte <span className="p-accent">Echosphere</span>, plusieurs univers. Le jeu continue de progresser à son propre rythme.</p></div>}
            {security ? <RecoveryForm key={security.kind === 'alert' ? 'alert' : security.token} link={security} onBack={() => setSecurity(null)} />
              : <AccountAccess key={token ?? 'public'} verificationToken={token} onSession={setAccount} request={request} />}
          </div>
        </section>
        {!signedIn && <HomeSections />}
      </div>
      {!signedIn && <JoinBand onAuth={auth} />}
      {signedIn && <div className="p-planet-foot" aria-hidden="true" />}
    </main>
    <SiteFooter connection={connection} />
  </div>;
}
