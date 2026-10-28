import { useEffect, useRef, useState } from 'react';
import { ColonyView } from './components/ColonyView';
import { Badge, Button, EmptyState, Panel } from './components/ui';
import { useReadiness } from './hooks/useReadiness';

const sections = [
  { id: 'empire', label: 'Empire', symbol: '◈', title: 'Votre horizon commence ici.', description: 'Retrouvez ici le bilan de votre empire, ses priorités et ses prochaines échéances.' },
  { id: 'colony', label: 'Colonie', symbol: '◉', title: 'Vos colonies', description: 'Les stocks, secteurs, infrastructures et files de construction prendront place ici.' },
  { id: 'research', label: 'Recherche', symbol: '⌘', title: 'La connaissance ouvre la voie.', description: 'Les technologies, prérequis et recherches programmées prendront place ici.' },
  { id: 'galaxy', label: 'Galaxie', symbol: '✧', title: 'Au-delà du connu.', description: 'Les systèmes découverts et vos missions d’exploration prendront place ici.' },
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
  const [destination, colonyView = 'overview'] = route.split('/');
  const section = sections.find(item => item.id === destination && (item.id === 'colony' || !route.includes('/')));

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
      <a className="brand" href="#empire" aria-label="Echosphere — Empire"><span className="brand-symbol" aria-hidden="true">◈</span> Echosphere<span className="brand-dot">.</span></a>
      <p className="sidebar-caption">CENTRE DE COMMANDEMENT</p>
      <nav aria-label="Navigation principale" className={moreOpen ? 'navigation is-expanded' : 'navigation'}
        onKeyDown={event => {
          if (event.key === 'Escape' && moreOpen) { setMoreOpen(false); moreButton.current?.focus(); }
        }}>
        {sections.slice(0, 4).map(item => <a key={item.id} href={`#${item.id}`}
          className="nav-link"
          aria-current={destination === item.id ? 'page' : undefined}>
          <span className="nav-symbol" aria-hidden="true">{item.symbol}</span><span>{item.label}</span>
        </a>)}
        <div id="more-sections" className="more-sections">
          {sections.slice(4).map(item => <a key={item.id} href={`#${item.id}`} className="nav-link secondary-link"
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
      <header className="topbar"><div><span className="eyebrow">ESPACE DE JEU</span><p>Aucun univers sélectionné</p></div>
        <div className={`network network--${status}`} role="status"><span className="status-dot" aria-hidden="true" />{statusText}</div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <div className="page-heading"><p className="eyebrow">{section?.label ?? 'Navigation'} / APERÇU</p>
          <h1 ref={heading} tabIndex={-1}>{section?.title ?? 'Page introuvable'}</h1>
          <p>{section?.description ?? 'Cette destination n’existe pas. Retrouvez les sections dans la navigation.'}</p>
        </div>
        {!section ? <a className="button" href="#empire">Revenir à l’Empire</a> : destination === 'empire' ? <>
          <section className="hero" aria-labelledby="hero-title">
            <div className="hero-copy"><Badge tone="accent">Les fondations sont en place</Badge>
              <h2 id="hero-title">Préparez la suite<br />de votre histoire.</h2>
              <p>L’interface prend forme. La création d’un univers et les premières actions de colonie arriveront aux prochaines étapes.</p>
              <a className="button button--primary" href="#colony">Découvrir l’espace Colonie <span aria-hidden="true">↗</span></a>
            </div><div className="orbital-art" aria-hidden="true"><div className="orbit" /><div className="planet" /><span className="orbital-caption">ECHOSPHERE / NOUVEL HORIZON</span></div>
          </section>
          <section className="resources" aria-label="Ressources de l’empire">
            {['Alliages', 'Flux', 'Données'].map((name, i) => <div className="resource-card" key={name}>
              <span className={`resource-symbol resource-symbol--${i}`} aria-hidden="true">{['⬡', 'ϟ', '▤'][i]}</span>
              <div><h2>{name}</h2><p>Stocks non disponibles</p></div><span className="resource-value" aria-hidden="true">—</span>
            </div>)}
          </section>
          <div className="overview-grid"><Panel title="Prochaines échéances"><EmptyState title="Aucune partie active">Les constructions et missions apparaîtront ici lorsqu’une partie pourra être créée.</EmptyState></Panel>
            <Panel title="État de la connexion" className="connection-panel"><Badge tone={status === 'connected' ? 'accent' : status === 'unavailable' ? 'warning' : 'neutral'}>{statusText}</Badge>
              <p>Cette vérification indique si les services sont joignables. Elle ne confirme pas qu’une partie est active.</p>
              <Button disabled={status === 'checking'} onClick={retry}>{status === 'checking' ? 'Vérification…' : 'Vérifier la connexion'}</Button>
            </Panel></div>
        </> : destination === 'colony' ? <ColonyView view={colonyView} /> : <section className="panel destination-panel"><Badge>À venir</Badge>
          <EmptyState title={`${section.label} : espace en préparation`}>{section.description} Aucun ordre de jeu n’est disponible à cette étape.</EmptyState>
          <a className="text-link" href="#empire">← Retour à l’Empire</a>
        </section>}
        <footer className="page-footer"><span>Echosphere · Nouvel horizon</span><span>Interface en préparation · Aucun gameplay jouable</span></footer>
      </main>
    </div>
  </div>;
}
