import { useEffect, useRef, useState } from 'react';
import { ResearchView } from './components/ResearchView';
import { GalaxyScreen } from './components/GalaxyScreen';
import type { GalaxyContext } from './components/GalaxyView';
import { SystemView } from './components/SystemView';
import { FleetView } from './components/FleetView';
import { RelationsView } from './components/RelationsView';
import { GameAccess } from './components/GameAccess';
import { useGameSession } from './hooks/useGameSession';
import { useColony } from './hooks/useColony';
import { ColonyView } from './components/ColonyView';
import { Badge, Button, EmptyState, Panel } from './components/ui';
import { useReadiness } from './hooks/useReadiness';
import { GameShell } from './shell/GameShell';
import { EmpireDashboard, EmpireWelcome } from './empire/EmpireDashboard';
import { ReportsScreen } from './reports/ReportsScreen';
import './theme/fonts.css';
import './theme/icons.css';
import './theme/dashboard.css';
import './theme/colony.css';
import './theme/bridge.css';

const sections = [
  { id: 'empire', label: 'Empire', title: 'Bonjour, Commandant.', description: 'La situation de votre empire.' },
  { id: 'colony', label: 'Colonie', title: 'Vos colonies', description: 'Les stocks, secteurs, infrastructures et files de construction prendront place ici.' },
  { id: 'research', label: 'Recherche', title: 'La connaissance ouvre la voie.', description: 'Technologies acquises, recherche active et suivante programmée à l’échelle de votre Empire.' },
  { id: 'galaxy', label: 'Galaxie', title: 'Galaxie', description: 'Carte stratégique des systèmes connus de votre Empire, routes découvertes et missions de flotte, selon le serveur.' },
  { id: 'fleets', label: 'Flottes', title: 'Vos flottes', description: 'Production de vaisseaux, flottes stationnées et missions asynchrones de vos Empires.' },
  { id: 'reports', label: 'Rapports', title: 'La mémoire de votre empire.', description: 'Constructions terminées, missions, batailles, recherches et diplomatie datées par le serveur.' },
  { id: 'relations', label: 'Relations', title: 'D’autres horizons.', description: 'Civilisations rencontrées, pactes de non-agression et faits hostiles datés de vos Empires.' },
] as const;

function currentRoute() {
  return window.location.hash.slice(1) || 'empire';
}

export default function App() {
  const [route, setRoute] = useState(currentRoute);
  const previousRoute = useRef(route);
  const { status, retry } = useReadiness();
  const segments = route.split('/');
  const universe = segments[0] === 'universe' && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(segments[1] ?? '') ? segments[1] : null;
  const localRoute = universe ? segments.slice(2).join('/') || 'empire' : route;
  const systemMatch = localRoute.match(/^galaxy\/system\/([a-f0-9-]{36})\/([a-f0-9-]{36})$/i);
  const systemEmpire = systemMatch?.[1], systemId = systemMatch?.[2];
  // Shortcut from Galaxy/System View: the same Fleet flow with a prefilled destination.
  const sendMatch = localRoute.match(/^fleets\/send\/([a-f0-9-]{36})\/([a-f0-9-]{36})$/i)
    ?? localRoute.match(/^fleets\/(?:colonize|attack)\/([a-f0-9-]{36})\/([a-f0-9-]{36})\/([a-f0-9-]{36})$/i);
  const galaxyContexts = useRef<Record<string, GalaxyContext>>({});
  const access = useGameSession(universe);
  const colony = useColony(universe, access.phase === 'active', access.session?.csrf_token, access.retry);
  const href = (section: string) => universe ? `#universe/${universe}/${section}` : `#${section}`;
  const navigation = () => { if (universe && access.phase === 'active' && !access.busy) void access.refresh(); };
  const [destination, colonyView = 'overview'] = localRoute.split('/');
  const section = sections.find(item => item.id === destination && (item.id === 'colony' || !!systemMatch || !!sendMatch || !localRoute.includes('/')));
  const requestedColony = localRoute.match(/^colony\/overview\/([a-f0-9-]{36})$/i)?.[1];
  const selectColony = colony.select;
  const active = !!universe && access.phase === 'active';
  useEffect(() => {
    if (requestedColony && access.phase === 'active') selectColony(requestedColony);
  }, [requestedColony, access.phase, selectColony]);
  useEffect(() => {
    if (universe && systemEmpire && systemId) {
      const previous = galaxyContexts.current[universe];
      galaxyContexts.current[universe] = { empire: systemEmpire, selected: systemId, view: previous?.empire === systemEmpire ? previous.view : null };
    }
  }, [universe, systemEmpire, systemId]);

  useEffect(() => {
    const navigate = () => setRoute(currentRoute());
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);

  useEffect(() => {
    if (previousRoute.current !== route) {
      document.querySelector<HTMLElement>('#main-content h1')?.focus();
      previousRoute.current = route;
    }
  }, [route]);

  // Pages redrawn after the mockup carry their own hero/header; the others keep the classic heading.
  const ownHeader = !!section && (destination === 'empire' || (destination === 'colony' && active)
    || (destination === 'galaxy' && active && !systemMatch) || (destination === 'reports' && active));
  const statusText = { checking: 'Vérification en cours', connected: 'Services disponibles', unavailable: 'Connexion indisponible' }[status];
  const choose = (what: string) => <Panel title="Choisir une partie"><p>Ouvrez un univers depuis le lobby Portal pour consulter {what} de vos Empires.</p></Panel>;

  return <GameShell universe={universe} access={access} colony={colony} status={status} destination={section ? destination : ''} href={href} onNavigate={navigation}>
    {!ownHeader && <div className="page-heading"><p className="eyebrow">{section?.label ?? 'Navigation'} / APERÇU</p>
      <h1 tabIndex={-1}>{systemMatch ? 'Vue du système' : section?.title ?? 'Page introuvable'}</h1>
      <p>{universe && destination === 'colony' && section ? 'Stocks, secteurs, infrastructures et file de construction de votre colonie, calculés et confirmés par le serveur.'
        : systemMatch && section ? 'Structure, mondes et présences propres que votre Empire connaît de ce système, selon le serveur.'
        : universe && destination === 'fleets' && section ? 'Production, flottes stationnées et missions de votre Empire ; déplacements et échéances calculés par le serveur.'
        : universe && destination === 'relations' && section ? 'Empires que vous avez rencontrés, état de chaque relation et négociations ; échéances arbitrées par le serveur.'
        : section?.description ?? 'Cette destination n’existe pas. Retrouvez les sections dans la navigation.'}</p>
    </div>}
    {universe && access.phase !== 'active' && <GameAccess access={access} />}
    {universe && access.phase !== 'active' ? null : !section ? <a className="button" href={href('empire')}>Revenir à l’Empire</a>
      : destination === 'empire' && universe ? <EmpireDashboard universe={universe} access={access} colony={colony} href={href} />
      : destination === 'empire' ? <EmpireWelcome>
        <Panel title="État de la connexion" className="connection-panel"><Badge tone={status === 'connected' ? 'accent' : status === 'unavailable' ? 'warning' : 'neutral'}>{statusText}</Badge>
          <p>Cette vérification indique si les services sont joignables. Elle ne confirme pas qu’une partie est active.</p>
          <Button disabled={status === 'checking'} onClick={retry}>{status === 'checking' ? 'Vérification…' : 'Vérifier la connexion'}</Button>
        </Panel></EmpireWelcome>
      : destination === 'colony' ? <ColonyView view={colonyView} universe={!!universe} link={href} onNavigate={navigation} colony={colony} />
      : destination === 'research' && universe ? <ResearchView universe={universe} enabled={active} csrf={access.session?.csrf_token} onSessionLost={access.retry} onEconomyChanged={colony.refresh} />
      : destination === 'research' ? choose('la recherche')
      : destination === 'galaxy' && universe && systemEmpire && systemId ? <SystemView universe={universe} empire={systemEmpire} system={systemId} onSessionLost={access.retry} onColony={navigation} />
      : destination === 'galaxy' && universe ? <GalaxyScreen initialContext={galaxyContexts.current[universe]} onContextChange={context => { galaxyContexts.current[universe] = context; }}
          universe={universe} universeName={access.session?.universe_name} enabled={active} csrf={access.session?.csrf_token} onSessionLost={access.retry} onEconomyChanged={colony.refresh} />
      : destination === 'galaxy' ? choose('la carte')
      : destination === 'fleets' && universe ? <FleetView key={sendMatch ? localRoute : 'fleets'} universe={universe} enabled={active} csrf={access.session?.csrf_token} onSessionLost={access.retry} onEconomyChanged={colony.refresh}
          target={sendMatch ? { empire: sendMatch[1], system: sendMatch[2], planet: sendMatch[3], action: localRoute.startsWith('fleets/attack/') ? 'attack' : 'colonize' } : undefined} />
      : destination === 'fleets' ? choose('les flottes')
      : destination === 'relations' && universe ? <RelationsView universe={universe} enabled={active} csrf={access.session?.csrf_token} onSessionLost={access.retry} />
      : destination === 'relations' ? choose('les relations')
      : destination === 'reports' && universe ? <ReportsScreen universe={universe} access={access} colony={colony} />
      : destination === 'reports' ? choose('les rapports')
      : <section className="panel destination-panel"><Badge>À venir</Badge>
        <EmptyState title={`${section.label} : implémentation backend nécessaire`}>{section.description} Aucun ordre de jeu n’est disponible à cette étape.</EmptyState>
        <a className="text-link" href={href('empire')}>← Retour à l’Empire</a>
      </section>}
    <footer className="page-footer"><span>Echosphere · Civilisations au-delà du silence</span><span>{active ? 'Colonie, Recherche, Galaxie, Flottes et Relations · selon droits et ruleset de l’univers' : 'Ouvrez une partie depuis le lobby du Portal'}</span></footer>
  </GameShell>;
}
