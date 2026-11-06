import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { useColony } from '../hooks/useColony';
import type { useGameSession } from '../hooks/useGameSession';
import { resourceKeys, resourceLabels, rate } from '../colony/format';
import { Ico, Pic } from './visual';
import { asset, compact, estimate, planetImage, resourceIcon } from './assets';
import { useMedia, useNow } from './useNow';

export const navigation = [
  { id: 'empire', label: 'Empire', icon: 'empire' },
  { id: 'colony', label: 'Colonie', icon: 'colonie' },
  { id: 'research', label: 'Recherche', icon: 'recherche' },
  { id: 'galaxy', label: 'Galaxie', icon: 'galaxie' },
  { id: 'fleets', label: 'Flottes', icon: 'flottes' },
  { id: 'reports', label: 'Rapports', icon: 'rapports' },
  { id: 'relations', label: 'Relations', icon: 'relations' },
] as const;

type Readiness = 'checking' | 'connected' | 'unavailable';
const readiness = { checking: 'Vérification en cours', connected: 'Services disponibles', unavailable: 'Connexion indisponible' };

/**
 * Game shell of the Echosphere mockup: top bar (universe, colony, resources, notifications,
 * profile), sidebar with faction visual, mobile drawer and tab bar. Every figure comes from the
 * Game projections; what the backend does not provide is labelled, never invented.
 */
export function GameShell({ universe, access, colony, status, destination, href, onNavigate, children }: {
  universe: string | null; access: ReturnType<typeof useGameSession>; colony: ReturnType<typeof useColony>;
  status: Readiness; destination: string; href: (section: string) => string; onNavigate: () => void; children: ReactNode;
}) {
  const [drawer, setDrawer] = useState(false);
  const [popover, setPopover] = useState<'messages' | 'alerts' | 'profile' | null>(null);
  const openButton = useRef<HTMLButtonElement>(null);
  const moreButton = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const now = useNow(1000);
  // One navigation at a time: sidebar on desktop, tab bar + drawer below 1200 px (mockup breakpoint).
  const desktop = useMedia('(min-width: 1200px)');
  const active = universe && access.phase === 'active';
  const projection = active ? colony.projection : null;
  const session = universe ? access.session : null;
  const elapsed = projection ? now - colony.receivedAt : 0;
  const empireName = projection?.colony.empire.name ?? colony.colonies[0]?.empire.name ?? null;

  useEffect(() => {
    if (!drawer) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { setDrawer(false); opener.current?.focus(); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [drawer]);
  useEffect(() => {
    if (!popover) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setPopover(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [popover]);
  useEffect(() => { setDrawer(false); setPopover(null); }, [destination]);
  const open = (from: HTMLButtonElement | null) => { opener.current = from; setDrawer(true); };
  const link = (id: string) => ({ href: href(id), onClick: onNavigate, 'aria-current': destination === id ? 'page' as const : undefined });

  return <div className="d-app">
    <a className="skip-link" href="#main-content" onClick={event => {
      event.preventDefault(); document.getElementById('main-content')?.focus();
    }}>Aller au contenu</a>
    <header className="d-topbar d-scope">
      <button ref={openButton} type="button" className="d-icon-btn d-burger" aria-label="Ouvrir le menu" aria-controls="game-sidebar"
        aria-expanded={drawer} onClick={() => open(openButton.current)}><span /><span /><span /></button>
      <a className="d-brand" href={href('empire')} onClick={onNavigate} aria-label="Echosphere — Empire">
        <img className="d-brand-logo" src={asset('img/logo-echosphere-horizontal.webp')} alt="Echosphere" width="1200" height="360" />
        <span className="d-brand-tagline">Civilisations au-delà du silence</span>
      </a>
      {session?.portal_url
        ? <a className="d-selector d-universe" href={session.portal_url} referrerPolicy="no-referrer" title="Changer d’univers depuis le lobby du Portal">
          <img src={asset('img/univers-galaxie.png')} alt="" width="28" height="28" />
          <span className="d-selector-label">{session.universe_name}</span><Chevron /></a>
        : <span className="d-selector d-universe"><img src={asset('img/univers-galaxie.png')} alt="" width="28" height="28" />
          <span className="d-selector-label">{universe ? 'Vérification de la partie' : 'Aucun univers sélectionné'}</span></span>}
      {projection && <div className="d-selector d-planet-select">
        <img className="d-selector-planet" src={planetImage(projection.colony.id)} alt="" width="40" height="40" />
        <span className="d-selector-text">{colony.colonies.length > 1
          ? <label className="d-colony-pick"><span className="visually-hidden">Colonie</span>
            <select value={projection.colony.id} onChange={event => colony.select(event.target.value)}>
              {colony.colonies.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          : <strong>{projection.colony.name}</strong>}
          <small>Système {projection.colony.system.name}</small></span>
        {colony.colonies.length > 1 && <Chevron />}
      </div>}
      {projection && <ul className="d-res-bar" aria-label={`Stocks de ${projection.colony.name}`}>
        {resourceKeys.map(key => {
          const resource = projection.resources.find(r => r.resource === key);
          if (!resource) return null;
          return <li className="d-res" key={key} title="Stock estimé depuis la dernière lecture du serveur">
            <img src={asset(resourceIcon[key])} alt="" width="34" height="34" />
            <span><small>{resourceLabels[key]}</small><strong>{compact(estimate(resource, elapsed))}</strong>
              <em className="d-rate">+{rate(resource.rate_per_hour)}/h</em></span></li>;
        })}
      </ul>}
      <div className="d-top-actions">
        <div className={`d-network d-network--${status}`} role="status" title={readiness[status]}><span className="d-status-dot" aria-hidden="true" />{readiness[status]}</div>
        <button type="button" className="d-icon-btn" aria-label="Messages" aria-expanded={popover === 'messages'}
          onClick={() => setPopover(value => value === 'messages' ? null : 'messages')}><Pic src="icons/ui/ui-messages.svg" size={34} /></button>
        <button type="button" className="d-icon-btn" aria-label="Notifications" aria-expanded={popover === 'alerts'}
          onClick={() => setPopover(value => value === 'alerts' ? null : 'alerts')}><Pic src="icons/ui/ui-notifications.svg" size={34} /></button>
        {popover && popover !== 'profile' && <div className="d-popover" role="dialog" aria-label={popover === 'messages' ? 'Messages' : 'Notifications'}>
          <strong>Implémentation backend nécessaire</strong>
          <p>{popover === 'messages' ? 'La messagerie entre joueurs n’existe pas encore côté serveur.'
            : 'Le centre de notifications n’existe pas encore côté serveur. Les alertes de vos colonies et flottes sont sur l’écran Empire.'}</p>
          <button type="button" className="d-btn" onClick={() => setPopover(null)}>Fermer</button>
        </div>}
      </div>
      <button type="button" className="d-profile" aria-expanded={popover === 'profile'} aria-label={`Profil${empireName ? ` : ${empireName}` : ''}`}
        onClick={() => setPopover(value => value === 'profile' ? null : 'profile')}>
        <img src={asset('icons/embleme-consortium-novae.svg')} alt="" width="38" height="38" />
        <span><strong>{empireName ?? 'Commandant'}</strong><small>{empireName ? 'Votre Empire' : 'Aucun Empire chargé'}</small></span><Chevron />
      </button>
      {popover === 'profile' && <div className="d-popover d-popover--profile" role="dialog" aria-label="Profil">
        <strong>{empireName ?? 'Commandant'}</strong>
        <p>Niveau, emblème et devise d’Empire : implémentation backend nécessaire.</p>
        {session?.portal_url && <a className="d-btn" href={session.portal_url} referrerPolicy="no-referrer">Retour au lobby</a>}
        <a className="d-btn" href={href('empire')} onClick={onNavigate}>Session de jeu</a>
      </div>}
    </header>

    {drawer && <div className="d-scrim d-show" onClick={() => setDrawer(false)} />}
    <aside className={`d-sidebar d-scope${drawer ? ' d-open' : ''}`} id="game-sidebar" aria-label="Navigation principale"
      inert={!desktop && !drawer ? true : undefined}>
      <div className="d-drawer-head">
        <img src={asset('img/logo-echosphere-horizontal.webp')} alt="Echosphere" width="1200" height="360" />
        <button type="button" className="d-icon-btn d-close" aria-label="Fermer le menu" onClick={() => { setDrawer(false); opener.current?.focus(); }}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg></button>
      </div>
      <nav aria-label="Sections du jeu">
        {navigation.map(item => <a key={item.id} className={`d-nav-item${destination === item.id ? ' d-active' : ''}`} {...link(item.id)}>
          <Ico name={item.icon} />{item.label}</a>)}
      </nav>
      <div className="d-faction">
        <img src={asset('icons/embleme-consortium-novae.svg')} alt="" width="96" height="96" />
        <strong>{empireName ?? 'Echosphere'}</strong>
        {empireName ? <small className="d-faction-note">Emblème et devise d’Empire : implémentation backend nécessaire</small>
          : <span>Un univers<br />à découvrir</span>}
      </div>
    </aside>

    <main id="main-content" tabIndex={-1} className="d-main">{children}</main>

    {!desktop && <nav className="d-tabbar d-scope" aria-label="Navigation rapide">
      {navigation.slice(0, 4).map(item => <a key={item.id} className={destination === item.id ? 'd-active' : undefined} {...link(item.id)}>
        <Ico name={item.icon} />{item.label}</a>)}
      <button ref={moreButton} type="button" aria-controls="game-sidebar" aria-expanded={drawer}
        className={navigation.slice(4).some(item => item.id === destination) ? 'd-active' : undefined}
        onClick={() => drawer ? setDrawer(false) : open(moreButton.current)}><i className="d-dots" aria-hidden="true" />Plus</button>
    </nav>}
  </div>;
}

function Chevron() {
  return <svg className="d-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>;
}
