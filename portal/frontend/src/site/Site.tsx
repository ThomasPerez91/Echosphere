import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react';
import { Icon } from '../theme/Icon';
import type { IconName } from '../theme/Icon';

/** Honest placeholder: the layout of the mockup is kept, no figure or content is invented. */
export function Pending({ what, compact = false }: { what?: string; compact?: boolean }) {
  return <div className={`p-pending${compact ? ' p-pending--small' : ''}`}>
    <strong>Implémentation backend nécessaire</strong>{what && <span>{what}</span>}
  </div>;
}

export function Logo({ big = false }: { big?: boolean }) {
  // Official horizontal logo (emblem + wordmark); the surrounding link or heading carries the name.
  return <span className={`p-logo${big ? ' p-big' : ''}`}>
    <img className="p-logo-img" src="/assets/img/logo-echosphere-horizontal.webp" alt="Echosphere" width="1200" height="360" />
    <small>Civilisations au-delà du silence</small>
  </span>;
}

export type AuthKind = 'login' | 'register';
export type SignedIn = { email: string; verified: boolean };

function scrollToId(id: string) {
  const target = document.getElementById(id);
  target?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  // Focus moves with the view so keyboard and screen-reader users land where they asked to go.
  window.setTimeout(() => target?.querySelector<HTMLElement>('h2, input, button')?.focus({ preventScroll: true }), 0);
}

/** Sticky site header of the mockup: public navigation, or the player's space once signed in. */
export function SiteHeader({ account, onAuth }: { account: SignedIn | null; onAuth: (kind: AuthKind) => void }) {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open && !profile) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); setProfile(false); } };
    const outside = (event: MouseEvent) => { if (!profileRef.current?.contains(event.target as Node)) setProfile(false); };
    document.addEventListener('keydown', close); document.addEventListener('click', outside);
    return () => { document.removeEventListener('keydown', close); document.removeEventListener('click', outside); };
  }, [open, profile]);
  const go = (id: string) => { setOpen(false); setProfile(false); scrollToId(id); };
  const auth = (kind: AuthKind) => { setOpen(false); onAuth(kind); };
  const item = (icon: IconName, label: string, onClick: () => void, current = false) =>
    <button type="button" className="p-navbtn" aria-current={current ? 'page' : undefined} onClick={onClick}><Icon name={icon} />{label}</button>;
  const soon = (icon: IconName, label: string) =>
    <span className="p-navbtn is-pending" title="Implémentation backend nécessaire"><Icon name={icon} />{label}<small>à venir</small></span>;

  return <header className="p-site-head">
    <div className="p-wrap">
      <a className="p-home-link" href="/" aria-label="Echosphere — accueil"><Logo /></a>
      <button type="button" className="p-nav-toggle" aria-label="Menu" aria-controls="site-nav" aria-expanded={open} onClick={() => setOpen(value => !value)}>
        <Icon name="menu" /></button>
      <nav className={`p-site-nav${open ? ' p-open' : ''}`} id="site-nav" aria-label="Navigation principale">
        {account ? <>
          <div className="p-nav-main">
            {item('planet', 'Mes parties', () => go('parties'), true)}
            {soon('mail', 'Invitations')}
            {soon('users', 'Communauté')}
            {item('lock', 'Compte et sécurité', () => go('securite'))}
          </div>
          <div className="p-nav-sep" />
          <div className="p-head-actions">
            <button type="button" className="p-bell" disabled aria-label="Notifications : implémentation backend nécessaire"><Icon name="bell" /></button>
            <div className="p-profile" ref={profileRef}>
              <button type="button" aria-expanded={profile} aria-haspopup="true" aria-controls="profile-menu" onClick={() => setProfile(value => !value)}>
                <img src="/assets/img/partie-auralis.webp" alt="" width="36" height="36" />
                <span><b>Commandant</b><small>{account.verified ? 'Adresse vérifiée' : 'Adresse à confirmer'}</small></span>
                <Icon name="chevdown" />
              </button>
              {profile && <div className="p-pop p-open" id="profile-menu">
                <button type="button" onClick={() => go('securite')}><Icon name="settings" />Compte et sécurité</button>
                <span className="p-pop-note">Profil public et niveau : implémentation backend nécessaire.</span>
              </div>}
            </div>
          </div>
        </> : <>
          <div className="p-nav-main">
            {item('home', 'Accueil', () => go('main-content'), true)}
            {item('planet', 'Univers', () => go('univers'))}
            {item('layers', 'Fonctionnalités', () => go('fonctionnalites'))}
            {soon('users', 'Communauté')}
            {item('news', 'Actualités', () => go('actualites'))}
          </div>
          <div className="p-nav-sep" />
          <div className="p-head-actions">
            <button type="button" className="p-btn" onClick={() => auth('login')}><Icon name="user" />Connexion</button>
            <button type="button" className="p-btn p-btn-glow" onClick={() => auth('register')}><Icon name="userplus" />Inscription</button>
          </div>
        </>}
      </nav>
    </div>
  </header>;
}

export function HomeHero({ onAuth }: { onAuth: (kind: AuthKind) => void }) {
  return <section className="p-hero">
    <div className="p-hero-bg" aria-hidden="true" />
    <div className="p-wrap">
      <h1 tabIndex={-1}>Conquérez les étoiles.<br /><span className="p-accent">Bâtissez votre empire.</span></h1>
      <span className="p-rule" aria-hidden="true" />
      <p>Echosphere est un jeu de stratégie spatiale asynchrone et persistant : développez vos colonies, explorez la galaxie,
        recherchez de nouvelles technologies et commandez vos flottes, à votre rythme.</p>
      <div className="p-cta">
        <button type="button" className="p-btn p-btn-primary" onClick={() => onAuth('register')}><Icon name="userplus" />Créer un compte<Icon name="arrow" /></button>
        <button type="button" className="p-btn" onClick={() => onAuth('login')}><Icon name="user" />Se connecter</button>
      </div>
    </div>
  </section>;
}

export function DashHero() {
  return <section className="p-dash-hero">
    <div className="p-hero-bg" aria-hidden="true" />
    <div className="p-wrap">
      <h1 tabIndex={-1}>Bienvenue, Commandant</h1>
      <p>Retrouvez vos parties, entrez dans vos univers et gardez la main sur la sécurité de votre compte.</p>
      <div className="p-cta">
        <button type="button" className="p-btn p-btn-primary" disabled title="Implémentation backend nécessaire"><Icon name="plus" />Nouvelle partie<small>à venir</small></button>
        <button type="button" className="p-btn" disabled title="Implémentation backend nécessaire"><Icon name="map" />Parcourir les univers<small>à venir</small></button>
      </div>
    </div>
  </section>;
}

const features: [string, IconName, string, string][] = [
  ['exploration', 'compass', 'Exploration', 'Détectez des signaux, cartographiez-les avec vos sondes et levez le brouillard de la galaxie.'],
  ['colonisation', 'dome', 'Colonisation', 'Fondez de nouvelles colonies et développez leurs infrastructures, secteur par secteur.'],
  ['diplomatie', 'handshake', 'Diplomatie', 'Rencontrez d’autres civilisations et négociez des pactes de non-agression.'],
  ['flottes', 'rocket', 'Flottes', 'Construisez vos vaisseaux et confiez-leur des missions : déplacer, coloniser, attaquer.'],
  ['recherche', 'flask', 'Recherche', 'Faites progresser les technologies de votre Empire, une recherche après l’autre.'],
  ['defense', 'shield', 'Défense', 'Protégez vos colonies des forces hostiles. Modules de défense à venir.'],
];

export function HomeSections() {
  const [tab, setTab] = useState<'modes' | 'univers'>('modes');
  const tabs: ['modes' | 'univers', IconName, string][] = [['modes', 'planet', 'Modes de jeu'], ['univers', 'chart', 'Univers disponibles']];
  const move = (event: ReactKeyboardEvent) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const next = tab === 'modes' ? 'univers' : 'modes';
    setTab(next); document.getElementById(`tab-${next}`)?.focus();
  };
  return <>
    <section id="fonctionnalites" aria-labelledby="features-title" className="p-features-zone">
      <h2 id="features-title" className="p-sr-only">Fonctionnalités</h2>
      <div className="p-features">{features.map(([id, icon, title, text]) =>
        <article key={id} className="p-feature"><img src={`/assets/img/fonction-${id}.webp`} alt="" loading="lazy" width="640" height="360" />
          <Icon name={icon} /><h3>{title}</h3><p>{text}</p></article>)}</div>
    </section>
    <div className="p-home-grid">
      <section className="p-panel" id="univers" aria-label="Découvrir le jeu">
        <div className="p-tabs-bar" role="tablist" aria-label="Découvrir le jeu" onKeyDown={move}>
          {tabs.map(([id, icon, label]) => <button key={id} type="button" role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`}
            aria-selected={tab === id} tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}><Icon name={icon} />{label}</button>)}
        </div>
        {tab === 'modes' ? <div id="panel-modes" role="tabpanel" aria-labelledby="tab-modes" className="p-modes">
          <article className="p-mode p-featured"><img src="/assets/img/mode-persistant.webp" alt="" loading="lazy" width="640" height="360" />
            <div className="p-mode-body"><h3><Icon name="infinity" />Univers persistants</h3>
              <p>Un univers qui continue d’avancer sans vous : constructions, recherches et missions arrivent à échéance pendant votre absence.</p>
              <ul><li><Icon name="clock" />Quelques minutes par jour suffisent</li><li><Icon name="calendar" />Progression continue</li></ul></div></article>
          <article className="p-mode"><img src="/assets/img/mode-rapide.webp" alt="" loading="lazy" width="640" height="360" />
            <div className="p-mode-body"><h3><Icon name="bolt" />Parties rapides</h3><p>Des sessions plus courtes et plus intenses.</p>
              <Pending compact what="Format non encore proposé par le serveur." /></div></article>
          <article className="p-mode"><img src="/assets/img/mode-coop.webp" alt="" loading="lazy" width="640" height="360" />
            <div className="p-mode-body"><h3><Icon name="users" />Coop / Multijoueur</h3><p>Jouer avec ou contre d’autres commandants.</p>
              <Pending compact what="Univers multijoueurs prévus après le MVP solo." /></div></article>
        </div> : <div id="panel-univers" role="tabpanel" aria-labelledby="tab-univers" className="p-tab-pad">
          <Pending what="Le Portal ne publie pas encore de catalogue d’univers ouverts à l’inscription. Vos univers apparaissent dans « Mes parties » une fois connecté." />
        </div>}
      </section>
      <section className="p-panel" id="actualites" aria-labelledby="news-title">
        <div className="p-p-head"><h2 id="news-title"><Icon name="news" />Actualités du secteur</h2></div>
        <div className="p-tab-pad"><Pending what="Publication des actualités et carnets de développement." /></div>
      </section>
    </div>
  </>;
}

export function JoinBand({ onAuth }: { onAuth: (kind: AuthKind) => void }) {
  return <section className="p-join" aria-labelledby="join-title">
    <div className="p-wrap">
      <p className="p-join-text"><Icon name="laurel" /><span id="join-title"><b>Rejoignez les stratèges</b><br />et écrivez votre propre chapitre dans <span className="p-accent">Echosphere.</span></span></p>
      <div className="p-join-stats"><Pending compact what="Statistiques publiques (commandants, univers actifs, colonies fondées)." /></div>
      <button type="button" className="p-btn p-btn-primary" onClick={() => onAuth('register')}><Icon name="userplus" />Rejoindre Echosphere<Icon name="arrow" /></button>
    </div>
  </section>;
}

export function SiteFooter({ connection }: { connection: ReactNode }) {
  return <footer className="p-site-foot">
    <div className="p-wrap">
      <Logo />
      <ul className="p-foot-links" aria-label="Informations">
        {['À propos', 'Aide / Support', 'Conditions d’utilisation', 'Politique de confidentialité'].map(label =>
          <li key={label} title="Page à venir">{label}</li>)}
      </ul>
      {connection}
    </div>
    <p className="p-wrap p-foot-version">Version de développement · Echosphere</p>
  </footer>;
}
