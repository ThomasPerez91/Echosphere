import { useEffect, useRef, useState } from 'react';
import { consumeVerificationFragment } from './account/verification';
import { AccountAccess } from './account/AccountAccess';
import type { AccountPage } from './account/AccountAccess';
import { RecoveryForm } from './account/SecurityForms';
import { consumeSecurityFragment } from './account/security-links';
import type { SecurityLink } from './account/security-links';
import { useReadiness } from './useReadiness';
import { DashHero, HomeHero, HomeSections, JoinBand, Logo, SiteFooter, SiteHeader } from './site/Site';
import type { SignedIn } from './site/Site';
import { Link, navigate, pageOf, paths, usePath } from './router';
import './theme/fonts.css';
import './theme/portail.css';

const titles: Record<string, string> = {
  home: 'Echosphere', login: 'Connexion — Echosphere', register: 'Inscription — Echosphere', games: 'Mes parties — Echosphere',
  newGame: 'Nouvelle partie — Echosphere', account: 'Mon compte — Echosphere', join: 'Rejoindre une partie — Echosphere',
  missing: 'Page introuvable — Echosphere',
};

function consumeInvite() {
  const value = new URLSearchParams(window.location.hash.slice(1)).get('invite');
  if (value === null) return null;
  window.history.replaceState(null, '', window.location.pathname + window.location.search);
  return /^[A-Za-z0-9_-]{40,64}$/.test(value) ? value : null;
}

export default function App({ verificationToken = null, securityLink = null }: { verificationToken?: string | null; securityLink?: SecurityLink | null }) {
  const [security, setSecurity] = useState(securityLink);
  const [token, setToken] = useState(verificationToken);
  const [account, setAccount] = useState<SignedIn | null>(null);
  const page = pageOf(usePath());
  // UX-API-03: an invitation link carries its token in the fragment; it stays in memory only.
  const [invite, setInvite] = useState<string | null>(() => consumeInvite());
  useEffect(() => {
    const read = () => {
      const invited = consumeInvite();
      if (invited) setInvite(invited);
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
  const flow = !!security || !!token; // one-time links (email confirmation, password reset) take the account card
  const signedIn = !!account && !flow;

  // Signed in, the public entry pages lead to the player's games; never during a one-time link.
  useEffect(() => {
    if (signedIn && (page === 'home' || page === 'login' || page === 'register')) navigate(paths.games, { replace: true });
  }, [signedIn, page]);
  useEffect(() => { document.title = titles[page] ?? 'Echosphere'; }, [page]);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    document.querySelector<HTMLElement>('#main-content h1, #main-content h2')?.focus({ preventScroll: true });
  }, [page]);

  const view: AccountPage = page === 'newGame' ? 'new-game' : page === 'missing' ? 'home' : page;
  const auth = flow || (!signedIn && view !== 'home');
  const connection = <section className="p-connection" aria-labelledby="connection-title">
    <div><h2 id="connection-title">Connexion au Portal</h2>
      <p role="status" aria-live="polite" className={`p-ready p-ready--${status}`}><span className="p-ready-dot" aria-hidden="true" />{message}</p></div>
    <button type="button" className="p-btn p-btn-sm" onClick={retry} disabled={status === 'checking'}>Vérifier à nouveau</button>
  </section>;

  return <div className="p-app">
    <div className="p-sky" aria-hidden="true" />
    <a className="p-skip-link" href="#main-content">Aller au contenu</a>
    <SiteHeader account={signedIn ? account : null} page={page} />
    <main id="main-content" tabIndex={-1}>
      {page === 'missing' && !auth ? <section className="p-wrap p-missing"><h1 tabIndex={-1}>Page introuvable</h1>
        <p>Cette adresse n’existe pas sur le Portal.</p><Link to={signedIn ? paths.games : paths.home} className="p-btn">Retour à l’accueil</Link></section>
        : auth ? null : signedIn ? <DashHero page={page} /> : <HomeHero />}
      <div className="p-wrap">
        {/* AccountAccess keeps the same place in the tree on every page: changing page never remounts it. */}
        <section id="compte" className={auth ? 'p-auth-zone' : signedIn ? 'p-account-zone' : 'p-account-zone is-idle'}
          aria-label={auth ? 'Votre compte' : undefined}>
          {auth && <aside className="p-auth-side" aria-hidden="true"><Logo big /></aside>}
          <div className={auth ? 'p-panel p-glow p-auth-card p-forms' : 'p-forms p-dash'}>
            {auth && <div className="p-auth-intro">
              <h1 className="p-auth-title" tabIndex={-1}><img src="/assets/img/logo-echosphere-embleme.webp" alt="" width="48" height="48" />
                {flow ? 'Votre compte' : view === 'register' ? 'Inscription' : view === 'join' ? 'Rejoindre une partie' : 'Connexion'}</h1>
              <span className="p-rule" aria-hidden="true" />
              <p className="p-lead">{view === 'register' && !flow ? <>Un compte <span className="p-accent">Echosphere</span>, plusieurs univers. Le jeu continue de progresser à son propre rythme.</>
                : <>Bon retour, Commandant. Vos univers vous attendent.</>}</p></div>}
            {security ? <RecoveryForm key={security.kind === 'alert' ? 'alert' : security.token} link={security} onBack={() => { setSecurity(null); navigate(paths.login); }} />
              : <AccountAccess key={token ?? 'public'} verificationToken={token} onSession={setAccount} page={view} onNavigate={path => navigate(path)} inviteToken={invite} />}
          </div>
        </section>
        {!signedIn && !auth && page === 'home' && <HomeSections />}
      </div>
      {!signedIn && !auth && page === 'home' && <JoinBand />}
      {signedIn && <div className="p-planet-foot" aria-hidden="true" />}
    </main>
    <SiteFooter connection={connection} />
  </div>;
}
