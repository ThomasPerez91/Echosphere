import type { ReactNode } from 'react';
import type { useColony } from '../hooks/useColony';
import type { useGameSession } from '../hooks/useGameSession';
import { useGalaxy } from '../hooks/useGalaxy';
import { useFleets } from '../hooks/useFleets';
import { useResearch } from '../hooks/useResearch';
import { useRelations } from '../hooks/useRelations';
import { GameAccess } from '../components/GameAccess';
import { infrastructureLabel, ratio, rate, resourceKeys, resourceLabels, time } from '../colony/format';
import type { Order, Resource } from '../colony/api';
import { GalaxyCanvas } from '../galaxy/GalaxyCanvas';
import type { Scene } from '../galaxy/render';
import { missionPosition } from '../command/model';
import { Bar, PanelHead, Pending, Pic } from '../shell/visual';
import { ago, asset, buildingImage, compact, estimate, integer, planetImage, resourceIcon } from '../shell/assets';
import { useNow } from '../shell/useNow';
import { combatEvents, missionEvents, newestFirst, relationEvents, researchEvents } from '../reports/events';

function Hero({ universeName }: { universeName?: string }) {
  return <section className="d-hero d-scope">
    <div className="d-hero-text">
      <h1 tabIndex={-1}>Bonjour, <span>Commandant.</span></h1>
      <p>{universeName ? `Voici la situation de votre empire dans ${/^univers\b/i.test(universeName) ? `l’${universeName}` : `l’univers ${universeName}`}.` : 'Ouvrez une partie depuis le lobby du Portal pour retrouver votre empire.'}</p>
    </div>
    <blockquote className="d-hero-quote"><p>« Chaque monde est un écho.<br />Chaque décision, une onde. »</p><cite>— Archives de l’Echosphère</cite></blockquote>
  </section>;
}

/** Empire page without an open universe: same hero, no game data. */
export function EmpireWelcome({ children }: { children: ReactNode }) {
  return <div className="d-page">
    <Hero />
    <section className="d-stats d-scope" aria-label="Indicateurs">
      {resourceKeys.map(key => <article className="d-card d-stat-res" key={key}>
        <img src={asset(resourceIcon[key])} alt="" width="56" height="56" />
        <div><span className="d-label">{resourceLabels[key]}</span><strong aria-hidden="true">—</strong><em>Stocks non disponibles</em></div>
      </article>)}
    </section>
    <div className="d-panels d-scope">
      <section className="d-card d-panel d-span-8"><PanelHead icon="icons/stats/stat-colonies.svg" title="Aucune partie active" />
        <p className="d-muted">Les ressources, constructions, systèmes connus et événements de votre empire apparaîtront ici une fois une partie ouverte depuis le Portal.</p></section>
    </div>
    {children}
  </div>;
}

/** Storage gauge (recette 09/11/2026, instead of an always-rising 24 h curve): how full the
 * storage is now and when it will be full at the current rate. */
function Projection({ resource, color, elapsed }: { resource: Resource; color: string; elapsed: number }) {
  const capacity = resource.capacity === null ? null : Number(resource.capacity) / 1e6;
  if (!capacity) return <p className="d-store"><small>Stockage illimité</small></p>;
  const stock = estimate(resource, elapsed), perHour = Number(resource.rate_per_hour) / 1e6;
  const share = Math.min(100, stock / capacity * 100);
  const hours = perHour > 0 ? (capacity - stock) / perHour : Infinity;
  const when = share >= 100 ? 'Stockage plein : la production est perdue' : !Number.isFinite(hours) ? 'Pas de production'
    : hours < 1 ? `Plein dans ${Math.max(1, Math.round(hours * 60))} min` : hours < 48 ? `Plein dans ${Math.round(hours)} h` : `Plein dans ${Math.round(hours / 24)} j`;
  return <div className={`d-store${share >= 90 ? ' is-high' : ''}`}>
    <span className="d-store-bar" role="meter" aria-label={`Stockage ${resource.resource}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share)}>
      <i style={{ width: `${share}%`, background: color }} /></span>
    <small>{Math.round(share)} % du stockage · {when}</small>
  </div>;
}

function Countdown({ order, offset, now }: { order: Order; offset: number; now: number }) {
  if (!order.started_at || !order.due_at) return <span className="d-sub">En file : démarre après l’ordre précédent</span>;
  const start = Date.parse(order.started_at), end = Date.parse(order.due_at), server = now + offset;
  const p = Math.max(0, Math.min(100, (server - start) / Math.max(1, end - start) * 100));
  const left = Math.max(0, Math.round((end - server) / 1000));
  const h = Math.floor(left / 3600), m = Math.floor(left % 3600 / 60), s = left % 60;
  return <>
    <span className="d-timer"><Pic src="icons/ui/ui-chronometre.svg" size={16} /><time dateTime={order.due_at}>{left ? `${h}h ${String(m).padStart(2, '0')}min ${String(s).padStart(2, '0')}s` : 'Confirmation serveur…'}</time></span>
    <div className="d-progress"><Bar value={p} label={`Avancement estimé de ${infrastructureLabel(order.infrastructure_type)}`} /><b className="d-pct">{Math.floor(p)} %</b></div>
  </>;
}

type Alert = { key: string; tone: 'danger' | 'warn' | 'info'; icon: string; title: string; text: ReactNode; at?: string };

export function EmpireDashboard({ universe, access, colony, href }: {
  universe: string; access: ReturnType<typeof useGameSession>; colony: ReturnType<typeof useColony>;
  href: (section: string) => string;
}) {
  const enabled = access.phase === 'active';
  const csrf = access.session?.csrf_token;
  const projection = colony.projection;
  const empireId = projection?.colony.empire.id;
  const galaxy = useGalaxy(universe, enabled, csrf, access.retry, empireId);
  const fleets = useFleets(universe, enabled, csrf, access.retry, empireId);
  const research = useResearch(universe, enabled, csrf, access.retry);
  const relations = useRelations(universe, enabled, csrf, access.retry);
  const now = useNow(1000);
  const offset = projection ? Date.parse(projection.server_time) - colony.receivedAt : 0;
  const serverNow = now + offset;
  const elapsed = projection ? now - colony.receivedAt : 0;
  const g = galaxy.projection, f = fleets.projection?.available ? fleets.projection : null;
  const r = research.projection, rel = relations.projection;
  const link = (id: string, label: string) => ({ href: href(id), label });

  const systems = g?.systems ?? [];
  const known = systems.filter(s => s.state !== 'DETECTED');
  const capitalSystem = systems.find(s => projection && s.observation?.own_colony_ids.includes(projection.colony.id))
    ?? systems.find(s => s.observation?.own_colony_ids.length);
  const ordered = [...systems].sort((a, b) => Number(b.id === capitalSystem?.id) - Number(a.id === capitalSystem?.id)
    || Number(!!b.observation?.own_colony_ids.length) - Number(!!a.observation?.own_colony_ids.length)
    || Number(b.state !== 'DETECTED') - Number(a.state !== 'DETECTED'));
  const world = g && f && f.empire.id === g.empire.id ? { galaxy: { systems: g.systems, routes: g.routes }, fleets: f } : null;
  const scene: Scene | null = g ? {
    systems: systems.map(s => ({ id: s.id, x: s.x, y: s.y, state: s.state, own: !!s.observation?.own_colony_ids.length,
      capital: s.id === capitalSystem?.id, name: s.state === 'DETECTED' ? undefined : s.name })),
    routes: g.routes.map(route => ({ a: route.a_id, b: route.b_id })),
    fleets: world ? (world.fleets.missions ?? []).filter(m => m.status !== 'completed').flatMap(m => {
      const p = missionPosition(world, m, serverNow);
      const to = systems.find(s => s.id === m.destination?.id), from = systems.find(s => s.id === m.origin?.id);
      return p && to && from ? [{ x: p.x, y: p.y, angle: Math.atan2(to.y - from.y, to.x - from.x) + (m.status === 'returning' ? Math.PI : 0) }] : [];
    }) : [],
  } : null;

  const activeResearch = r?.queue.find(o => o.status === 'active');
  const availableTech = r?.technologies.filter(t => t.available).length ?? 0;
  const alerts: Alert[] = [];
  for (const a of projection?.incoming ?? []) if (a.state === 'pending')
    alerts.push({ key: a.id, tone: 'danger', icon: 'icons/alertes/alerte-flotte-ennemie.svg', title: 'Force hostile en approche', text: <>{projection!.colony.name} · bataille {time(a.battle_at)}</> });
  for (const res of projection?.resources ?? []) {
    const filled = ratio(res.stock, res.capacity);
    if (filled >= 90) alerts.push({ key: `full-${res.resource}`, tone: 'warn', icon: 'icons/alertes/alerte-stockage-limite.svg', title: 'Capacité de stockage proche de la limite',
      text: <>{resourceLabels[res.resource]} (<b className="d-danger-txt">{Math.floor(filled)} %</b>)</> });
  }
  if (projection && projection.queue.length >= projection.queue_limit) alerts.push({ key: 'queue', tone: 'warn', icon: 'icons/alertes/alerte-construction-terminee.svg', title: 'File de construction pleine', text: projection.colony.name });
  if (projection && !projection.sectors.free) alerts.push({ key: 'sectors', tone: 'warn', icon: 'icons/alertes/alerte-critique.svg', title: 'Aucun secteur libre', text: projection.colony.name });
  if (r && !activeResearch && availableTech) alerts.push({ key: 'research', tone: 'info', icon: 'icons/alertes/alerte-recherche-disponible.svg', title: 'Recherche disponible',
    text: `${availableTech} technologie${availableTech > 1 ? 's peuvent' : ' peut'} être lancée${availableTech > 1 ? 's' : ''}` });
  for (const x of rel?.relations ?? []) if (x.proposal?.direction === 'received')
    alerts.push({ key: `pact-${x.empire.id}`, tone: 'info', icon: 'icons/alertes/alerte-proposition-diplomatique.svg', title: 'Proposition diplomatique', text: `Pacte proposé par ${x.empire.name}`, at: x.proposal.proposed_at });
  if (fleets.awaiting) alerts.push({ key: 'fleets', tone: 'info', icon: 'icons/alertes/alerte-defense.svg', title: 'Échéance de flotte passée', text: 'En attente de la confirmation du serveur' });

  const events = [...missionEvents(f), ...combatEvents(f), ...researchEvents(r), ...relationEvents(rel)].sort(newestFirst).slice(0, 5);

  const pacts = rel?.relations.filter(x => x.state === 'PACT').length ?? 0;
  const proposals = rel?.relations.filter(x => x.proposal?.direction === 'received').length ?? 0;
  const threats = (projection?.incoming ?? []).filter(a => a.state === 'pending').length;
  const signals = systems.length - known.length;

  return <div className="d-page">
    <Hero universeName={access.session?.universe_name} />
    {colony.phase === 'loading' || colony.phase === 'idle' ? <p className="panel" aria-live="polite">Chargement de votre colonie…</p>
      : colony.phase === 'empty' ? <p className="panel">Aucune colonie accessible dans cet univers.</p>
      : !projection ? <p className="panel" role="alert">Colonie indisponible pour le moment.</p> : null}

    <section className="d-stats d-scope" aria-label="Indicateurs">
      {projection?.resources.map(res => <article className="d-card d-stat-res" key={res.resource}>
        <img src={asset(resourceIcon[res.resource])} alt="" width="56" height="56" />
        <div><span className="d-label">{resourceLabels[res.resource]}</span><strong>{compact(estimate(res, elapsed))}</strong><em className="d-pos">+{rate(res.rate_per_hour)}/h</em></div>
        <Projection resource={res} elapsed={elapsed} color={res.resource === 'data' ? '#FFB547' : '#3BE3FF'} />
      </article>)}
      <article className="d-card d-stat-mini"><Pic src="icons/stats/stat-colonies.svg" size={44} /><div><strong>{colony.colonies.length}</strong><span>Colonie{colony.colonies.length > 1 ? 's' : ''}</span></div></article>
      <article className="d-card d-stat-mini"><Pic src="icons/stats/stat-systemes.svg" size={44} /><div><strong>{g ? known.length : '—'}</strong><span>Systèmes connus</span></div></article>
      <article className="d-card d-stat-mini"><Pic src="icons/stats/stat-flottes.svg" size={44} /><div><strong>{f ? f.fleets?.length ?? 0 : '—'}</strong><span>Flottes</span></div></article>
    </section>

    <div className="d-panels d-scope">
      <section className="d-card d-panel d-production" aria-labelledby="empire-production">
        <PanelHead id="empire-production" icon="icons/sidebar/nav-empire.svg" title={colony.colonies.length > 1 ? `Production — ${projection?.colony.name ?? ''}` : 'Production de l’empire'} more={link('colony', 'Voir tous les détails')} />
        {projection ? <ul className="d-prod">{resourceKeys.map(key => {
          const res = projection.resources.find(x => x.resource === key); if (!res) return null;
          const filled = ratio(res.stock, res.capacity);
          return <li key={key}><img src={asset(resourceIcon[key])} alt="" width="26" height="26" /><span className="d-name">{resourceLabels[key]}</span>
            <span className="d-rate d-pos">{rate(res.rate_per_hour)} / h</span><Bar value={res.capacity ? filled : 0} tone={key === 'data' ? 'amber' : undefined} label={`Remplissage ${resourceLabels[key]}`} />
            <span className="d-stock">{compact(estimate(res, elapsed))}</span></li>;
        })}</ul> : <Pending what="Production des colonies" compact />}
        {colony.colonies.length > 1 && <p className="d-note">Production cumulée de toutes vos colonies : implémentation backend nécessaire.</p>}
      </section>

      <section className="d-card d-panel d-constructions" aria-labelledby="empire-builds">
        <PanelHead id="empire-builds" icon="icons/evenements/evt-construction-terminee.svg" title="Constructions en cours" more={link('colony/infrastructure', 'Voir la colonie')} />
        <ul className="d-builds">
          {projection?.queue.map(order => <li className="d-build" key={order.id}>
            <img className="d-thumb" src={buildingImage(order.infrastructure_type)} alt="" width="72" height="72" />
            <div className="d-build-body">
              <div className="d-build-top"><strong>{infrastructureLabel(order.infrastructure_type)}</strong></div>
              <span className="d-sub">{projection.colony.name} · Secteur {order.sector_index}</span>
              <span className="d-sub">{order.target_level === 1 ? 'Nouvelle infrastructure' : `Niveau ${order.target_level - 1} → ${order.target_level}`}</span>
              <Countdown order={order} offset={offset} now={now} />
            </div></li>)}
          {activeResearch && <li className="d-build">
            <img className="d-thumb" src={asset('img/batiments/laboratoire-orbital.webp')} alt="" width="72" height="72" />
            <div className="d-build-body"><div className="d-build-top"><strong>{activeResearch.name}</strong></div>
              <span className="d-sub">Recherche d’Empire</span>
              {activeResearch.due_at && <span className="d-timer"><Pic src="icons/ui/ui-chronometre.svg" size={16} /><time dateTime={activeResearch.due_at}>fin {time(activeResearch.due_at)}</time></span>}
            </div></li>}
          {projection && !projection.queue.length && !activeResearch && <li className="d-empty">Aucune construction ni recherche en cours.</li>}
        </ul>
      </section>

      <section className="d-card d-panel d-alerts" aria-labelledby="empire-alerts">
        <PanelHead id="empire-alerts" icon="icons/ui/ui-alerte.svg" title="Alertes" />
        <ul className="d-alert-list">{alerts.map(a => <li key={a.key} className={`d-${a.tone}`}><Pic src={a.icon} size={32} />
          <div><strong>{a.title}</strong><span>{a.text}</span></div><time>{a.at ? ago(a.at, serverNow) : ''}</time></li>)}
          {!alerts.length && <li className="d-info"><Pic src="icons/alertes/alerte-construction-terminee.svg" size={32} /><div><strong>Aucune alerte</strong><span>Stocks, files, menaces et propositions vérifiés à la dernière lecture.</span></div><time /></li>}
        </ul>
      </section>

      <section className="d-card d-panel d-systems" aria-labelledby="empire-systems">
        <PanelHead id="empire-systems" icon="icons/stats/stat-systemes.svg" title="Systèmes connus" more={link('galaxy', 'Voir la galaxie')} />
        <div className="d-systems-body">
          <ul className="d-sys-list">{ordered.slice(0, 5).map(s => {
            const own = !!s.observation?.own_colony_ids.length;
            return <li key={s.id}><img src={planetImage(s.id)} alt="" width="40" height="40" />
              <div><strong>{s.state === 'DETECTED' ? 'Signal détecté' : s.name}</strong>
                <span>{s.state === 'DETECTED' ? 'Position approximative' : `${s.planets?.length ?? 0} planète${(s.planets?.length ?? 0) > 1 ? 's' : ''}`}</span></div>
              {s.id === capitalSystem?.id ? <em className="d-tag-main">★ Système principal</em>
                : <em>{own ? 'Votre colonie' : s.state === 'MONITORED' ? 'Surveillé' : s.state === 'MAPPED' ? 'Cartographié' : 'Détecté'}</em>}</li>;
          })}
            {!g && <li className="d-empty">{galaxy.phase === 'error' ? 'Galaxie indisponible pour votre accès.' : 'Chargement des systèmes…'}</li>}
            {g && signals > 0 && <li className="d-more-line"><span>{signals} signal{signals > 1 ? 's' : ''} détecté{signals > 1 ? 's' : ''} à cartographier</span></li>}
          </ul>
          <div className="d-galaxy-view">
            {scene && scene.systems.length > 0 && <GalaxyCanvas scene={scene} drift label={`Carte animée des systèmes connus${capitalSystem?.name ? ` autour de ${capitalSystem.name}` : ''}`} />}
          </div>
        </div>
        <p className="d-note">Distances en années-lumière : implémentation backend nécessaire.</p>
      </section>

      <section className="d-card d-panel d-events" aria-labelledby="empire-events">
        <PanelHead id="empire-events" icon="icons/sidebar/nav-rapports.svg" title="Événements récents" more={link('reports', 'Voir les rapports')} />
        <ol className="d-timeline">{events.map(e => <li key={e.key} className={`d-${e.tone}`}><Pic src={e.icon} size={30} />
          <div><strong>{e.title}</strong><span>{e.text}</span></div><time dateTime={e.at}>{ago(e.at, serverNow)}</time></li>)}</ol>
        {!events.length && <p className="d-muted">Aucun événement daté par le serveur pour le moment.</p>}
        <p className="d-note">Constructions terminées et fil complet dans Rapports.</p>
      </section>

      <section className="d-card d-panel d-summary" aria-labelledby="empire-summary">
        <header className="d-panel-head"><h2 id="empire-summary"><svg className="d-h-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V12M10 20V6M16 20V9M22 20V3" /></svg>Résumé stratégique</h2></header>
        <ul className="d-summary-list">
          <li className="d-green"><strong>Développement</strong><span>{projection ? `${projection.sectors.built + projection.sectors.reserved} / ${projection.sectors.capacity} secteurs utilisés à ${projection.colony.name}, ${projection.queue.length} ordre${projection.queue.length > 1 ? 's' : ''} en file.` : 'Données de colonie en attente.'}</span></li>
          <li className="d-blue"><strong>Recherche</strong><span>{r ? `${r.acquired.length} technologie${r.acquired.length > 1 ? 's' : ''} acquise${r.acquired.length > 1 ? 's' : ''}${activeResearch ? `, ${activeResearch.name} en cours` : availableTech ? `, ${availableTech} disponible${availableTech > 1 ? 's' : ''}` : ''}.` : 'Recherche indisponible pour votre accès.'}</span></li>
          <li className="d-blue"><strong>Position galactique</strong><span>{g ? `${known.length} système${known.length > 1 ? 's' : ''} connu${known.length > 1 ? 's' : ''}, ${signals} signal${signals > 1 ? 's' : ''} à cartographier.` : 'Galaxie indisponible pour votre accès.'}</span></li>
          <li className={threats ? 'd-amber' : 'd-green'}><strong>Sécurité</strong><span>{threats ? `${threats} bataille${threats > 1 ? 's' : ''} annoncée${threats > 1 ? 's' : ''} sur vos colonies.` : 'Aucune force hostile annoncée sur la colonie affichée.'}</span></li>
          <li className="d-blue"><strong>Diplomatie</strong><span>{rel ? `${rel.relations.length} Empire${rel.relations.length > 1 ? 's' : ''} rencontré${rel.relations.length > 1 ? 's' : ''}, ${pacts} pacte${pacts > 1 ? 's' : ''}${proposals ? `, ${proposals} proposition${proposals > 1 ? 's' : ''} en attente` : ''}.` : 'Relations indisponibles pour votre accès.'}</span></li>
        </ul>
      </section>
    </div>
    <div className="d-session"><GameAccess access={access} /></div>
    {projection && <p className="d-server-time">État serveur au {time(projection.server_time)} · stocks estimés entre deux lectures ({integer(estimate(projection.resources[0], elapsed))} {resourceLabels[projection.resources[0].resource].toLowerCase()} à l’instant).</p>}
  </div>;
}
