import { useEffect, useRef, useState } from 'react';
import { ResearchView } from './components/ResearchView';
import { GalaxyView } from './components/GalaxyView';
import { GameAccess } from './components/GameAccess';
import { useGameSession } from './hooks/useGameSession';
import { useColony } from './hooks/useColony';
import { infrastructureLabel, rate, resourceLabels, resourceSymbols, time, units } from './colony/format';
import { ColonyView } from './components/ColonyView';
import { Badge, Button, EmptyState, Panel } from './components/ui';
import { useReadiness } from './hooks/useReadiness';

const sections = [
  { id: 'empire', label: 'Empire', symbol: '◈', title: 'Votre horizon commence ici.', description: 'Retrouvez ici le bilan de votre empire, ses priorités et ses prochaines échéances.' },
  { id: 'colony', label: 'Colonie', symbol: '◉', title: 'Vos colonies', description: 'Les stocks, secteurs, infrastructures et files de construction prendront place ici.' },
  { id: 'research', label: 'Recherche', symbol: '⌘', title: 'La connaissance ouvre la voie.', description: 'Technologies acquises, recherche active et suivante programmée à l’échelle de votre Empire.' },
  { id: 'galaxy', label: 'Galaxie', symbol: '✧', title: 'Au-delà du connu.', description: 'Systèmes connus de votre Empire, routes découvertes et expéditions d’exploration, selon le serveur.' },
  { id: 'fleets', label: 'Flottes', symbol: '↗', title: 'Vos flottes', description: 'Les vaisseaux engagés, missions et arrivées prendront place ici.' },
  { id: 'reports', label: 'Rapports', symbol: '≡', title: 'La mémoire de votre empire.', description: 'Les résultats des missions et les événements importants prendront place ici.' },
  { id: 'relations', label: 'Relations', symbol: '◇', title: 'D’autres horizons.', description: 'Les civilisations rencontrées et les interactions avec les IA prendront place ici.' },
] as const;

function currentRoute() {
  return window.location.hash.slice(1) || 'empire';
}

export default function App() {
  const [route, setRoute] = useState(currentRoute);
  const [moreOpen, setMoreOpen] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const moreButton = useRef<HTMLButtonElement>(null);
  const previousRoute = useRef(route);
  const { status, retry } = useReadiness();
  const segments = route.split('/');
  const universe = segments[0] === 'universe' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(segments[1] ?? '') ? segments[1] : null;
  const localRoute = universe ? segments.slice(2).join('/') || 'empire' : route;
  const access = useGameSession(universe);
  const colony = useColony(universe, access.phase === 'active', access.session?.csrf_token, access.retry);
  const projection = universe && access.phase === 'active' ? colony.projection : null;
  const active = projection?.queue.find(order => order.status === 'active');
  const href = (section: string) => universe ? `#universe/${universe}/${section}` : `#${section}`;
  const navigation = () => { if (universe && access.phase === 'active' && !access.busy) void access.refresh(); };
  const [destination, colonyView = 'overview'] = localRoute.split('/');
  const section = sections.find(item => item.id === destination && (item.id === 'colony' || !localRoute.includes('/')));

  useEffect(() => {
    const navigate = () => { setRoute(currentRoute()); setMoreOpen(false); };
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);

  useEffect(() => {
    if (previousRoute.current !== route) {
      heading.current?.focus();
      previousRoute.current = route;
    }
  }, [route]);

  const statusText = { checking: 'Vérification en cours', connected: 'Services disponibles', unavailable: 'Connexion indisponible' }[status];

  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={event => {
      event.preventDefault(); document.getElementById('main-content')?.focus();
    }}>Aller au contenu</a>
    <aside className="sidebar">
      <a className="brand" href={href('empire')} aria-label="Echosphere — Empire"><span className="brand-symbol" aria-hidden="true">◈</span> Echosphere<span className="brand-dot">.</span></a>
      <p className="sidebar-caption">CENTRE DE COMMANDEMENT</p>
      <nav aria-label="Navigation principale" className={moreOpen ? 'navigation is-expanded' : 'navigation'}
        onKeyDown={event => {
          if (event.key === 'Escape' && moreOpen) { setMoreOpen(false); moreButton.current?.focus(); }
        }}>
        {sections.slice(0, 4).map(item => <a key={item.id} href={href(item.id)} onClick={navigation}
          className="nav-link"
          aria-current={destination === item.id ? 'page' : undefined}>
          <span className="nav-symbol" aria-hidden="true">{item.symbol}</span><span>{item.label}</span>
        </a>)}
        <div id="more-sections" className="more-sections">
          {sections.slice(4).map(item => <a key={item.id} href={href(item.id)} onClick={navigation} className="nav-link secondary-link"
            aria-current={destination === item.id ? 'page' : undefined}>
            <span className="nav-symbol" aria-hidden="true">{item.symbol}</span><span>{item.label}</span>
          </a>)}
        </div>
        <button ref={moreButton} type="button" className={`more-toggle ${sections.slice(4).some(item => item.id === destination) ? 'has-active-route' : ''}`} aria-expanded={moreOpen} aria-controls="more-sections"
          onClick={() => setMoreOpen(value => !value)}>
          <span aria-hidden="true">{moreOpen ? '×' : '···'}</span><span>Plus</span>
        </button>
      </nav>
      <div className="sidebar-footer"><Badge tone="warning">Version de développement</Badge><p>Un univers à découvrir.<br />Un empire à construire.</p></div>
    </aside>

    <div className="workspace">
      <header className="topbar"><div><span className="eyebrow">ESPACE DE JEU</span><p>{universe ? access.session?.universe_name ?? 'Vérification de la partie' : 'Aucun univers sélectionné'}</p></div>
        {projection && <dl className="topbar-resources" aria-label={`Stocks de ${projection.colony.name}`}>
          {projection.resources.map(resource => <div key={resource.resource}><dt><span aria-hidden="true" className={`resource-symbol--${resource.resource}`}>{resourceSymbols[resource.resource]}</span> {resourceLabels[resource.resource]}</dt>
            <dd>{units(resource.stock)} <span>+{rate(resource.rate_per_hour)}/h</span></dd></div>)}
        </dl>}
        <div className={`network network--${status}`} role="status"><span className="status-dot" aria-hidden="true" />{statusText}</div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <div className="page-heading"><p className="eyebrow">{section?.label ?? 'Navigation'} / APERÇU</p>
          <h1 ref={heading} tabIndex={-1}>{section?.title ?? 'Page introuvable'}</h1>
          <p>{universe && destination === 'colony' && section ? 'Stocks, secteurs, infrastructures et file de construction de votre colonie, calculés et confirmés par le serveur.'
            : universe && destination === 'empire' && section ? 'Situation de votre colonie et constructions en cours, selon le serveur Game.'
            : section?.description ?? 'Cette destination n’existe pas. Retrouvez les sections dans la navigation.'}</p>
        </div>
        {universe && (destination === 'empire' || access.phase !== 'active') && <GameAccess access={access} />}
        {universe && access.phase !== 'active' ? null : !section ? <a className="button" href={href('empire')}>Revenir à l’Empire</a> : destination === 'empire' && universe ? <>
          <section className="resources" aria-label={projection ? `Ressources de ${projection.colony.name}` : 'Ressources de l’empire'}>
            {projection ? projection.resources.map(resource => <div className="resource-card" key={resource.resource}>
              <span className={`resource-symbol resource-symbol--${resource.resource}`} aria-hidden="true">{resourceSymbols[resource.resource]}</span>
              <div><h2>{resourceLabels[resource.resource]}</h2><p>+{rate(resource.rate_per_hour)}/h</p></div><span className="resource-value">{units(resource.stock)}</span>
            </div>) : <p className="panel" aria-live="polite">{colony.phase === 'empty' ? 'Aucune colonie accessible dans cet univers.' : colony.phase === 'error' ? 'Colonie indisponible pour le moment.' : 'Chargement de votre colonie…'}</p>}
          </section>
          <div className="overview-grid"><Panel title="Construction en cours">{active ? <p><strong>{infrastructureLabel(active.infrastructure_type)}</strong> niveau {active.target_level}
            {active.due_at ? ` · fin prévue ${time(active.due_at)}` : ''}</p> : <p>{projection ? 'Aucune construction en cours.' : 'Données de colonie en attente.'}</p>}
            <a className="button button--primary" href={href('colony/infrastructure')} onClick={navigation}>Gérer les infrastructures <span aria-hidden="true">↗</span></a></Panel>
            <Panel title="Colonie">{projection ? <p>{projection.colony.name} · {projection.sectors.built + projection.sectors.reserved} / {projection.sectors.capacity} secteurs utilisés · {projection.queue.length} / {projection.queue_limit} ordres</p>
              : <p>Les autres domaines de l’Empire arriveront aux prochaines étapes.</p>}
              <a className="text-link" href={href('colony')} onClick={navigation}>Ouvrir la colonie →</a></Panel></div>
        </> : destination === 'empire' ? <>
          <section className="hero" aria-labelledby="hero-title">
            <div className="hero-copy"><Badge tone="accent">Les fondations sont en place</Badge>
              <h2 id="hero-title">Préparez la suite<br />de votre histoire.</h2>
              <p>L’interface prend forme. La création d’un univers et les premières actions de colonie arriveront aux prochaines étapes.</p>
              <a className="button button--primary" href={href('colony')}>Découvrir l’espace Colonie <span aria-hidden="true">↗</span></a>
            </div><div className="orbital-art" aria-hidden="true"><div className="orbit" /><div className="planet" /><span className="orbital-caption">ECHOSPHERE / NOUVEL HORIZON</span></div>
          </section>
          <section className="resources" aria-label="Ressources de l’empire">
            {['Alliages', 'Flux', 'Données'].map((name, i) => <div className="resource-card" key={name}>
              <span className={`resource-symbol resource-symbol--${i}`} aria-hidden="true">{['⬡', 'ϟ', '▤'][i]}</span>
              <div><h2>{name}</h2><p>Stocks non disponibles</p></div><span className="resource-value" aria-hidden="true">—</span>
            </div>)}
          </section>
          <div className="overview-grid"><Panel title="Prochaines échéances"><EmptyState title={universe ? "Aucune donnée de jeu disponible" : "Aucune partie active"}>Les constructions et missions apparaîtront ici lorsque leurs services seront disponibles.</EmptyState></Panel>
            <Panel title="État de la connexion" className="connection-panel"><Badge tone={status === 'connected' ? 'accent' : status === 'unavailable' ? 'warning' : 'neutral'}>{statusText}</Badge>
              <p>Cette vérification indique si les services sont joignables. Elle ne confirme pas qu’une partie est active.</p>
              <Button disabled={status === 'checking'} onClick={retry}>{status === 'checking' ? 'Vérification…' : 'Vérifier la connexion'}</Button>
            </Panel></div>
        </> : destination === 'colony' ? <ColonyView view={colonyView} universe={!!universe} link={href} onNavigate={navigation} colony={colony} /> : destination === 'research' && universe ? <ResearchView universe={universe} enabled={access.phase === 'active'} csrf={access.session?.csrf_token} onSessionLost={access.retry} onEconomyChanged={colony.refresh} /> : destination === 'research' ? <Panel title="Choisir une partie"><p>Ouvrez un univers depuis le lobby Portal pour consulter la recherche de vos Empires.</p></Panel> : destination === 'galaxy' && universe ? <GalaxyView universe={universe} enabled={access.phase === 'active'} csrf={access.session?.csrf_token} onSessionLost={access.retry} onEconomyChanged={colony.refresh} /> : destination === 'galaxy' ? <Panel title="Choisir une partie"><p>Ouvrez un univers depuis le lobby Portal pour consulter la carte de vos Empires.</p></Panel> : <section className="panel destination-panel"><Badge>À venir</Badge>
          <EmptyState title={`${section.label} : espace en préparation`}>{section.description} Aucun ordre de jeu n’est disponible à cette étape.</EmptyState>
          <a className="text-link" href={href('empire')}>← Retour à l’Empire</a>
        </section>}
        <footer className="page-footer"><span>Echosphere · Nouvel horizon</span><span>{universe && access.phase === 'active' ? 'Colonie, Recherche et Galaxie · selon droits et ruleset de l’univers' : 'Interface en préparation · Aucun gameplay jouable'}</span></footer>
      </main>
    </div>
  </div>;
}
