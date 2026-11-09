import { useEffect, useMemo, useRef, useState } from 'react';
import type { useColony } from '../hooks/useColony';
import type { useGameSession } from '../hooks/useGameSession';
import { useFleets } from '../hooks/useFleets';
import { useResearch } from '../hooks/useResearch';
import { useRelations } from '../hooks/useRelations';
import { useConstructionHistory } from '../hooks/useConstructionHistory';
import { alertEvents, combatEvents, constructionEvents, frontierEvents, missionEvents, newestFirst, relationEvents, researchEvents } from '../reports/events';
import type { ReportEvent } from '../reports/events';
import { Pic } from '../shell/visual';
import { initialSeen, markAll, readSeen, storageKey, unread, writeSeen } from './unread';
import type { Seen } from './unread';

const SHOWN = 8;
const POLL_MS = 120_000;
const timeFormat = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

/** Where each notification leads: the screen that carries the server state (Q60). */
const section = (e: ReportEvent) => e.key.startsWith('alert-') ? 'fleets' : e.category === 'research' ? 'research'
  : e.category === 'diplomacy' ? 'relations' : e.category === 'construction' ? 'colony' : 'reports';

/**
 * Q60 bell: attacks announced, constructions and research completed, missions over, diplomacy and
 * contacts. Composed from the same server projections as Rapports; the unread mark is a per-browser
 * convenience, never game state.
 */
export function NotificationBell({ universe, access, colony, open, onToggle, href, onNavigate }: {
  universe: string; access: ReturnType<typeof useGameSession>; colony: ReturnType<typeof useColony>;
  open: boolean; onToggle: (open: boolean) => void; href: (section: string) => string; onNavigate: () => void;
}) {
  const enabled = access.phase === 'active';
  const csrf = access.session?.csrf_token;
  const empire = colony.projection?.colony.empire.id ?? colony.colonies[0]?.empire.id;
  const fleets = useFleets(universe, enabled, csrf, access.retry, empire);
  const research = useResearch(universe, enabled, csrf, access.retry);
  const relations = useRelations(universe, enabled, csrf, access.retry);
  const history = useConstructionHistory(universe, colony.colonies, enabled, access.retry);
  const f = fleets.projection?.available ? fleets.projection : null;
  const events = useMemo(() => [
    ...alertEvents(f),
    ...colony.colonies.flatMap(c => constructionEvents(history.history[c.id]?.entries ?? [], c)),
    ...missionEvents(f), ...combatEvents(f), ...frontierEvents(f),
    ...researchEvents(research.projection), ...relationEvents(relations.projection),
  ].sort(newestFirst), [colony.colonies, history.history, f, research.projection, relations.projection]);

  // Facts that do not come from our own deadlines (an attack, a pact offer) are found by a slow re-read.
  const sources = useRef({ fleets, research, relations, history });
  sources.current = { fleets, research, relations, history };
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      const s = sources.current;
      s.fleets.refresh(); s.research.refresh(); s.relations.refresh(); s.history.refresh();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [enabled]);

  const key = empire ? storageKey(universe, empire) : null;
  const [seen, setSeen] = useState<Seen | null>(null);
  // Wait for each source to answer (or fail) before deciding what is old news.
  const settled = (phase: string, has: unknown) => !!has || ['error', 'empty', 'unavailable'].includes(phase);
  const loaded = !!f && settled(research.phase, research.projection) && settled(relations.phase, relations.projection) && !history.busy;
  useEffect(() => {
    if (!key || seen || !loaded) return;
    const stored = readSeen(key);
    const first = stored ?? initialSeen(events);
    if (!stored) writeSeen(key, first);
    setSeen(first);
  }, [key, seen, loaded, events]);
  const fresh = seen ? unread(events, seen) : [];
  // Opening marks everything as read; what was new stays highlighted while the list is open.
  const [highlight, setHighlight] = useState<Set<string>>(() => new Set());
  const toggle = () => {
    if (!open) {
      setHighlight(new Set(fresh.map(e => e.key)));
      if (seen && key) { const next = markAll(events, seen); writeSeen(key, next); setSeen(next); }
    }
    onToggle(!open);
  };

  const count = fresh.length;
  return <>
    <button type="button" className="d-icon-btn d-bell" aria-expanded={open} aria-haspopup="dialog" onClick={toggle}
      aria-label={count ? `Notifications : ${count} non lue${count > 1 ? 's' : ''}` : 'Notifications'}>
      <Pic src="icons/ui/ui-notifications.svg" size={34} />
      {count > 0 && <span className="d-badge" aria-hidden="true">{count > 99 ? '99+' : count}</span>}
    </button>
    {open && <div className="d-popover d-popover--notifications" role="dialog" aria-label="Notifications">
      <strong>Notifications</strong>
      {!events.length ? <p>{loaded ? 'Rien à signaler pour le moment.' : 'Lecture en cours…'}</p>
        : <ol className="d-notif-list">{events.slice(0, SHOWN).map(e => <li key={e.key} className={`d-${e.tone}${highlight.has(e.key) ? ' d-notif-new' : ''}`}>
          <a href={href(section(e))} onClick={() => { onToggle(false); onNavigate(); }}>
            <Pic src={e.icon} size={26} />
            <span><b>{e.title}</b>{highlight.has(e.key) && <span className="visually-hidden"> (nouveau)</span>}<small>{e.text}</small></span>
            <time dateTime={e.at}>{timeFormat.format(new Date(e.at))}</time>
          </a></li>)}</ol>}
      <a className="d-btn" href={href('reports')} onClick={() => { onToggle(false); onNavigate(); }}>Voir tous les rapports</a>
    </div>}
  </>;
}
