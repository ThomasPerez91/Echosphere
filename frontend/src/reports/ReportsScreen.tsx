import { useMemo, useState } from 'react';
import type { useColony } from '../hooks/useColony';
import type { useGameSession } from '../hooks/useGameSession';
import { useFleets } from '../hooks/useFleets';
import { useResearch } from '../hooks/useResearch';
import { useRelations } from '../hooks/useRelations';
import { useConstructionHistory } from '../hooks/useConstructionHistory';
import { PanelHead, Pending, Pic } from '../shell/visual';
import { Kpis, Thumb, ViewHero, reportImage } from '../shell/view';
import type { Kpi } from '../shell/view';
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
  const [chosen, setChosen] = useState<string | null>(null);
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

  const selected = shown.find(e => e.key === chosen) ?? shown[0] ?? null;
  const kpis: Kpi[] = [
    { icon: 'icons/sidebar/nav-rapports.svg', value: events.length, label: 'Rapports datés' },
    { icon: 'icons/evenements/evt-flotte-revenue.svg', value: count('mission'), label: 'Missions' },
    { icon: 'icons/evenements/evt-combat.svg', value: count('combat') + count('frontier'), label: 'Combats et frontière' },
    { icon: 'icons/evenements/evt-construction-terminee.svg', value: count('construction'), label: 'Constructions' },
    { icon: 'icons/evenements/evt-recherche-terminee.svg', value: count('research'), label: 'Recherches' },
    { icon: 'icons/evenements/evt-contact-diplomatique.svg', value: count('diplomacy'), label: 'Événements diplomatiques' },
  ];

  return <div className="d-page d-reports">
    <ViewHero crumb="Rapports" title="Rapports" banner="banniere-rapports"
      text="Journal des événements de votre Empire : constructions, missions, batailles, frontière, recherches et diplomatie, datés par le serveur." />
    <Kpis items={kpis} label="Rapports par catégorie" />

    <div className="d-view-grid d-rep-grid d-scope">
      <section className="d-card d-panel" aria-labelledby="reports-feed">
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
          : <div className="d-report-list" aria-label="Rapports">{days.map(([day, list]) => <section key={day} className="d-report-day" aria-label={day}>
            <h2 className="d-report-date">{day}</h2>
            <ol className="d-rows">{list.map(e => <li key={e.key} className={`d-row d-${e.tone}${selected?.key === e.key ? ' is-current' : ''}`}>
              <button type="button" className="d-row-btn" aria-pressed={selected?.key === e.key} onClick={() => setChosen(e.key)}>
                <Thumb src={reportImage(e.category)} icon={e.icon} />
                <span className="d-row-main"><strong>{e.title}</strong><span>{e.text}</span></span>
                <span className="d-row-side"><time dateTime={e.at} title={new Date(e.at).toLocaleString('fr-FR')}>{hourFormat.format(new Date(e.at))}</time>
                  <span>{categoryLabels[e.category]}</span></span>
              </button>
            </li>)}</ol>
          </section>)}</div>}
        {history.hasMore && (filter === 'all' || filter === 'construction') &&
          <button type="button" className="d-btn d-more-btn" disabled={history.busy} onClick={history.more}>Afficher des constructions plus anciennes</button>}
        {history.unavailable > 0 && <Pending compact what={history.unavailable === colony.colonies.length
          ? 'Historique des constructions terminées : ce serveur Game ne le propose pas encore.'
          : 'Historique des constructions indisponible pour une partie de vos colonies.'} />}
        {history.failed > 0 && <p className="d-note" role="alert">Une partie de l’historique des constructions n’a pas pu être lue. Réessayez avec « Actualiser ».</p>}
      </section>

      <div className="d-stack">
        <section className="d-card d-panel d-rep-detail" aria-labelledby="report-detail" aria-live="polite">
          {selected ? <>
            <header className="d-rep-head"><Pic src={selected.icon} size={40} />
              <div><h2 id="report-detail">{selected.title}</h2><p>{selected.text}</p></div>
              <time dateTime={selected.at}>{new Date(selected.at).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })}</time></header>
            <Thumb src={reportImage(selected.category)} icon={selected.icon} className="d-thumb--wide" />
            <dl className="d-kv"><div><dt>Catégorie</dt><dd>{categoryLabels[selected.category]}</dd></div>
              <div><dt>Date serveur</dt><dd>{new Date(selected.at).toLocaleString('fr-FR')}</dd></div></dl>
            <Pending compact what="Détail complet du rapport (déroulé, trajet, chronologie) : seul le résumé daté est transmis aujourd’hui." />
          </> : <><h2 id="report-detail" className="d-rep-empty">Aucun rapport sélectionné</h2>
            <p className="d-note">Les rapports apparaissent ici dès que le serveur les date.</p></>}
        </section>
        <aside className="d-card d-panel" aria-labelledby="reports-sources">
          <PanelHead id="reports-sources" icon="icons/sidebar/nav-empire.svg" title="Sources" />
          <dl className="d-kv">{sources.map(([label, state]) => <div key={label}><dt>{label}</dt><dd>{state}</dd></div>)}</dl>
          <p className="d-note">Les missions, combats et faits de frontière sont ceux que conserve la projection Flottes ; les plus anciens peuvent ne plus y figurer.</p>
          <Pending compact what="Recherche et export du fil." />
        </aside>
      </div>
    </div>
  </div>;
}
