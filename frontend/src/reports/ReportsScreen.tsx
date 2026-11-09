import { useMemo, useState } from 'react';
import type { useColony } from '../hooks/useColony';
import type { useGameSession } from '../hooks/useGameSession';
import { useFleets } from '../hooks/useFleets';
import { useResearch } from '../hooks/useResearch';
import { useRelations } from '../hooks/useRelations';
import { useConstructionHistory } from '../hooks/useConstructionHistory';
import { PanelHead, Pending, Pic } from '../shell/visual';
import { categoryLabels, combatEvents, constructionEvents, frontierEvents, missionEvents, newestFirst, relationEvents, researchEvents } from './events';
import type { Category, ReportEvent } from './events';

const dayFormat = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const hourFormat = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const filters: ('all' | Category)[] = ['all', 'construction', 'mission', 'combat', 'frontier', 'research', 'diplomacy'];

/**
 * D-UX-6 Rapports: one dated feed composed client-side from what the Game server already persists
 * (completed constructions, fleet missions and battle reports, frontier facts, research, diplomacy).
 * Nothing is predicted here: an entry exists only once the server reports it.
 */
export function ReportsScreen({ universe, access, colony }: {
  universe: string; access: ReturnType<typeof useGameSession>; colony: ReturnType<typeof useColony>;
}) {
  const enabled = access.phase === 'active';
  const csrf = access.session?.csrf_token;
  const empireId = colony.projection?.colony.empire.id;
  const fleets = useFleets(universe, enabled, csrf, access.retry, empireId);
  const research = useResearch(universe, enabled, csrf, access.retry);
  const relations = useRelations(universe, enabled, csrf, access.retry);
  const history = useConstructionHistory(universe, colony.colonies, enabled, access.retry);
  const [filter, setFilter] = useState<'all' | Category>('all');
  const f = fleets.projection?.available ? fleets.projection : null;

  const events = useMemo(() => [
    ...colony.colonies.flatMap(c => constructionEvents(history.history[c.id]?.entries ?? [], c)),
    ...missionEvents(f), ...combatEvents(f), ...frontierEvents(f),
    ...researchEvents(research.projection), ...relationEvents(relations.projection),
  ].sort(newestFirst), [colony.colonies, history.history, f, research.projection, relations.projection]);
  const count = (c: 'all' | Category) => c === 'all' ? events.length : events.filter(e => e.category === c).length;
  const shown = filter === 'all' ? events : events.filter(e => e.category === filter);
  const days: [string, ReportEvent[]][] = [];
  for (const e of shown) {
    const day = dayFormat.format(new Date(e.at));
    if (days.at(-1)?.[0] === day) days.at(-1)![1].push(e); else days.push([day, [e]]);
  }
  const loading = history.busy && !events.length;
  const refresh = () => { history.refresh(); fleets.refresh(); research.refresh(); relations.refresh(); colony.refresh(); };
  const sources: [string, string][] = [
    ['Constructions', !colony.colonies.length ? 'Aucune colonie'
      : history.unavailable === colony.colonies.length ? 'Indisponible sur ce serveur'
      : history.failed ? 'Lecture incomplète' : `${colony.colonies.length} colonie${colony.colonies.length > 1 ? 's' : ''}`],
    ['Missions et combats', f ? 'À jour' : fleets.phase === 'loading' || fleets.phase === 'idle' ? 'Lecture…' : 'Indisponible'],
    ['Recherche', research.projection ? 'À jour' : research.phase === 'error' ? 'Indisponible' : 'Lecture…'],
    ['Diplomatie', relations.projection ? 'À jour' : relations.phase === 'error' || relations.phase === 'empty' || relations.phase === 'unavailable' ? 'Indisponible' : 'Lecture…'],
  ];

  return <div className="d-page d-reports">
    <section className="d-hero d-scope d-hero--reports">
      <div className="d-hero-text">
        <h1 tabIndex={-1}>La mémoire de <span>votre empire.</span></h1>
        <p>Constructions terminées, missions, batailles, frontière, recherches et diplomatie, datés par le serveur.</p>
      </div>
    </section>

    <div className="d-panels d-scope">
      <section className="d-card d-panel d-span-8" aria-labelledby="reports-feed">
        <PanelHead id="reports-feed" icon="icons/sidebar/nav-rapports.svg" title="Fil des rapports">
          <button type="button" className="d-btn" onClick={refresh} disabled={history.busy}>Actualiser</button>
        </PanelHead>
        <div className="d-filters" role="group" aria-label="Filtrer les rapports">
          {filters.map(c => <button key={c} type="button" className={`d-filter${filter === c ? ' d-active' : ''}`} aria-pressed={filter === c}
            onClick={() => setFilter(c)}>{c === 'all' ? 'Tous' : categoryLabels[c]}<span aria-hidden="true">{count(c)}</span>
            <span className="visually-hidden"> ({count(c)})</span></button>)}
        </div>
        {loading ? <p className="d-muted" role="status">Lecture des rapports…</p>
          : !shown.length ? <p className="d-empty">{filter === 'all' ? 'Aucun rapport daté par le serveur pour le moment.' : `Aucun rapport « ${categoryLabels[filter]} » pour le moment.`}</p>
          : days.map(([day, list]) => <section key={day} className="d-report-day" aria-label={day}>
            <h2 className="d-report-date">{day}</h2>
            <ol className="d-timeline">{list.map(e => <li key={e.key} className={`d-${e.tone}`}>
              <Pic src={e.icon} size={30} />
              <div><strong>{e.title}</strong><span>{e.text}</span></div>
              <time dateTime={e.at} title={new Date(e.at).toLocaleString('fr-FR')}>{hourFormat.format(new Date(e.at))}</time>
            </li>)}</ol>
          </section>)}
        {history.hasMore && (filter === 'all' || filter === 'construction') &&
          <button type="button" className="d-btn d-more-btn" disabled={history.busy} onClick={history.more}>Afficher des constructions plus anciennes</button>}
        {history.unavailable > 0 && <Pending compact what={history.unavailable === colony.colonies.length
          ? 'Historique des constructions terminées : ce serveur Game ne le propose pas encore.'
          : 'Historique des constructions indisponible pour une partie de vos colonies.'} />}
        {history.failed > 0 && <p className="d-note" role="alert">Une partie de l’historique des constructions n’a pas pu être lue. Réessayez avec « Actualiser ».</p>}
      </section>

      <aside className="d-card d-panel d-span-4" aria-labelledby="reports-sources">
        <PanelHead id="reports-sources" icon="icons/sidebar/nav-empire.svg" title="Sources" />
        <dl className="d-kv">{sources.map(([label, state]) => <div key={label}><dt>{label}</dt><dd>{state}</dd></div>)}</dl>
        <p className="d-note">Les missions, combats et faits de frontière sont ceux que conserve la projection Flottes ; les plus anciens peuvent ne plus y figurer.</p>
        <Pending compact what="Recherche et export du fil." />
      </aside>
    </div>
  </div>;
}
