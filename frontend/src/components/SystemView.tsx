import { useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { useSystem } from '../hooks/useSystem';
import { Button, Panel } from './ui';
import type { KnownOpportunity, SystemDetail } from '../galaxy/api';
import { starTint } from '../galaxy/render';
import { message } from '../fleet/messages';
import { time as clock } from '../colony/format';
import { planetImage } from '../shell/assets';
import { Kpis, Thumb, ViewHero, shipImage } from '../shell/view';
import { PanelHead } from '../shell/visual';
import { MissionPlanner } from '../command/MissionPlanner';
import { foreignName, kindNames, occupation, offers, opportunityNames, relationNames, systemFacts } from '../command/model';
import type { ActionOffer, PlanetFact, World } from '../command/model';
import type { CommandFeedback, MissionApi } from '../command/types';
import { useCommandWorld } from '../command/useCommandWorld';
import '../command/command.css';
import { useMissionFlow } from '../command/useMissionFlow';

const time = (value: string) => new Date(value).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
const resourceNames = { alloys: 'Alliages', flux: 'Flux', data: 'Données' } as const;
const whole = (micro?: string) => micro ? Math.floor(Number(micro) / 1_000_000).toLocaleString('fr-FR') : '?';
const count = (stacks: Record<string, number>) => Object.values(stacks).reduce((a, b) => a + b, 0);
const mainClass = (stacks: Record<string, number>) => Object.entries(stacks).sort(([, a], [, b]) => b - a)[0]?.[0] ?? 'probe';

type Pick = { kind: 'planet' | 'opportunity'; id: string };

/**
 * Vue système (refonte du 11/11/2026, référence system-view.png): the system's worlds around its
 * star, its opportunities, own fleets, observations and routes; every action is launched here
 * through the same planner and server summary as the command map. Knowledge only: an occupation
 * the Empire does not know stays unknown, and the illustration has no astronomical scale.
 */
export function SystemView({ universe, empire, system, onSessionLost, onColony, csrf, enabled = true, onEconomyChanged }: {
  universe: string; empire: string; system: string; onSessionLost: () => void; onColony?: () => void;
  csrf?: string; enabled?: boolean; onEconomyChanged?: () => void;
}) {
  const state = useSystem(universe, empire, system, onSessionLost);
  const command = useCommandWorld(universe, enabled, csrf, onSessionLost, onEconomyChanged, empire);
  const heading = useRef<HTMLHeadingElement>(null);
  const data = state.data;
  const back = `#universe/${universe}/galaxy`;
  const refresh = state.refresh;
  // An accepted mission re-reads this system too (positions, revealed opportunities).
  const api: MissionApi = useMemo(() => ({ ...command.api,
    async launch(plan, quote) { const result = await command.api.launch(plan, quote); if (result) refresh(); return result; } }),
  // refresh is stable enough for this purpose (a new function per render would re-create the api).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [command.api]);
  // The page title (hero) takes the focus once the system is read, like every redrawn view.
  useEffect(() => { if (data) (heading.current ?? document.querySelector<HTMLElement>('.d-system .d-vhero h1'))?.focus(); }, [data]);
  if (state.loading) return <Panel title="Vue du système"><p role="status">Lecture des connaissances du système…</p></Panel>;
  if (!data) return <Panel title="Système indisponible"><p role="alert">{state.error === 'authentication_required'
    ? 'Votre session a expiré. Retournez au lobby.' : state.error === 'system_not_found' || state.error === 'empire_not_found'
      ? 'Ce système n’est pas accessible avec vos connaissances et permissions actuelles.' : 'La lecture du système est momentanément indisponible.'}</p>
    <Button onClick={state.refresh}>Réessayer</Button><a className="button" href={back}>Retour à la Galaxie</a></Panel>;
  if (data.state === 'DETECTED') return <Panel title="Système seulement détecté">
    <h2 ref={heading} tabIndex={-1}>Structure encore inconnue</h2>
    <p>La vue détaillée devient disponible après cartographie. Retrouvez le signal et les possibilités d’exploration sur la Galaxie.</p>
    <a className="button" href={back}>Retour à la Galaxie</a></Panel>;
  const world = command.world && command.world.fleets.empire.id === empire ? command.world : null;
  return <SystemHub key={`${universe}/${empire}/${system}`} universe={universe} empire={empire} data={data} world={world} now={command.now}
    api={api} pending={command.fleets.pending} feedback={command.fleets.feedback}
    onRefresh={() => { state.refresh(); command.galaxy.refresh(); command.fleets.refresh(); }} onColony={onColony} />;
}

function SystemHub({ universe, empire, data, world, now, api, pending, feedback, onRefresh, onColony }: {
  universe: string; empire: string; data: SystemDetail; world: World | null; now: number; api: MissionApi; pending: boolean;
  feedback: CommandFeedback; onRefresh: () => void; onColony?: () => void;
}) {
  const system = data.id;
  const facts = world ? systemFacts(world, system) : null;
  const planets: PlanetFact[] = facts?.planets.length ? facts.planets : (data.planets ?? []).map(p => ({
    id: p.id, name: p.name, sectors: p.sector_capacity, orbitals: p.orbital_capacity,
    own: !!data.colony_links?.some(c => c.planet_id === p.id), colony: data.colony_links?.find(c => c.planet_id === p.id)?.colony_id ?? null,
    foreign: null, presence: null, alert: null }));
  const opportunities: KnownOpportunity[] = (world?.galaxy.systems.find(s => s.id === system)?.opportunities ?? data.opportunities)?.known ?? [];
  const signatures = (world?.galaxy.systems.find(s => s.id === system)?.opportunities ?? data.opportunities)?.signatures ?? null;
  // Open on the Empire's own world when one is linked, so its action is never hidden behind a pick.
  const first = data.colony_links?.[0]?.planet_id ?? planets.find(p => p.own)?.id ?? planets[0]?.id;
  const [pick, setPick] = useState<Pick | null>(first ? { kind: 'planet', id: first } : opportunities[0] ? { kind: 'opportunity', id: opportunities[0].id } : null);
  const [notice, setNotice] = useState<string | null>(null);
  const planet = pick?.kind === 'planet' ? planets.find(p => p.id === pick.id) ?? null : null;
  const opportunity = pick?.kind === 'opportunity' ? opportunities.find(o => o.id === pick.id) ?? null : null;
  const offered = world ? offers(world, system) : [];
  const own = planets.some(p => p.own) || !!data.observation?.own_colony_ids.length;
  const foreign = [...new Set(planets.filter(p => p.foreign !== null).map(p => p.foreign))];
  const known = [...new Set(planets.filter(p => p.presence).map(p => foreignName(p.presence!)))];
  const back = `#universe/${universe}/galaxy`;
  const systemHref = (id: string) => `#universe/${universe}/galaxy/system/${empire}/${id}`;
  const link = planet ? data.colony_links?.find(c => c.planet_id === planet.id) : undefined;
  const can = (right: string) => !!data.permissions?.includes(right);

  const kpis = [
    { icon: 'icons/sidebar/nav-galaxie.svg', label: 'Connaissance', value: data.state === 'MONITORED' ? 'Surveillé' : 'Cartographié' },
    { icon: 'icons/actions/action-lancer.svg', label: 'Distance', value: facts?.distance ? (facts.distance.hops === 0 ? 'Ici' : `${facts.distance.hops} saut${facts.distance.hops > 1 ? 's' : ''}`) : 'Inconnue',
      note: facts?.distance && facts.distance.hops > 0 ? 'par vos routes connues' : undefined },
    { icon: 'icons/stats/stat-colonies.svg', label: 'Contrôle', value: own ? 'Votre colonie' : known.length ? known.join(', ') : foreign.length ? foreign.map(n => `Empire ${n}`).join(', ') : 'Inconnu' },
    { icon: 'icons/stats/stat-systemes.svg', label: 'Mondes connus', value: planets.length },
    { icon: 'icons/colonie/panel-points-interet.svg', label: 'Opportunités', value: opportunities.length, note: signatures ? `${signatures} signature${signatures > 1 ? 's' : ''} à prospecter` : undefined },
    { icon: 'icons/stats/stat-flottes.svg', label: 'Vos flottes ici', value: facts ? facts.fleets.length : '?', note: facts?.incoming.length ? `${facts.incoming.length} en route` : undefined },
  ];

  return <div className="d-page d-system">
    <ViewHero crumb="Galaxie · Système" title={data.name!} banner="banniere-systeme"
      text={`Cartographié le ${time(data.mapped_at!)}${data.last_seen_at ? ` · ${data.state === 'MONITORED' ? 'Observation locale' : 'Dernière observation, ancienne'} : ${time(data.last_seen_at)}` : ''}. Connaissances lues au ${time(data.server_time!)}.`}>
      <a className="d-btn d-btn-ghost" href={back}>Voir sur la carte galactique <span aria-hidden="true">→</span></a>
      <button type="button" className="d-btn d-btn-ghost" onClick={onRefresh}>Actualiser</button>
    </ViewHero>
    <Kpis items={kpis} label={`Résumé du système ${data.name}`} />
    {notice && <p className="d-sys-notice" role="status">{notice}<button type="button" className="d-link-btn" onClick={() => setNotice(null)}>Fermer</button></p>}

    <div className="d-sys-grid">
      <section className="d-card d-sys-orbit-card" aria-labelledby="sys-orbit-title">
        <PanelHead icon="icons/colonie/panel-fenetre-orbitale.svg" title="Vue orbitale" id="sys-orbit-title" />
        <Orbit name={data.name!} star={starTint(system)} planets={planets} opportunities={opportunities} pick={pick} onPick={p => { setPick(p); setNotice(null); }} />
        <p className="d-note">Disposition illustrative · aucune échelle astronomique · couleur d’étoile cosmétique.</p>
      </section>

      <section className="d-card d-sys-detail" aria-labelledby="system-world-title">
        {planet ? <PlanetDetail planet={planet} universe={universe} link={link} onColony={onColony} />
          : opportunity ? <OpportunityDetail opportunity={opportunity} />
          : <h2 id="system-world-title">Aucun monde connu</h2>}
        {world ? <ActionPanel key={pick ? `${pick.kind}:${pick.id}` : 'system'} world={world} api={api} system={system} pending={pending} feedback={feedback}
            groups={[
              { title: planet ? 'Sur ce monde' : 'Sur cette opportunité', offers: offered.filter(o => planet ? o.planet === planet.id : opportunity ? o.opportunity === opportunity.id : false) },
              { title: 'Dans ce système', offers: offered.filter(o => !o.planet && !o.opportunity) },
            ]} onDone={setNotice} />
          : <LegacyActions data={data} universe={universe} empire={empire} planet={planet} link={!!link} can={can} />}
      </section>
    </div>

    <div className="d-sys-bottom">
      <section className="d-card" aria-labelledby="sys-fleets-title">
        <PanelHead icon="icons/stats/stat-flottes.svg" title="Flottes présentes" id="sys-fleets-title" more={{ href: `#universe/${universe}/fleets`, label: 'Voir toutes les flottes' }} />
        {!facts ? <p className="d-empty">Flottes indisponibles pour cet Empire.</p>
          : !facts.fleets.length && !facts.incoming.length ? <p className="d-empty">Aucune de vos flottes n’est ici ni en route vers ce système.</p>
          : <ul className="d-rows">{facts.fleets.map(f => <li key={f.id} className="d-row">
            <Thumb src={shipImage(mainClass(f.stacks))} icon="icons/sidebar/nav-flottes.svg" />
            <span className="d-row-main"><strong>{f.name}</strong><span>{count(f.stacks)} vaisseau{count(f.stacks) > 1 ? 'x' : ''}</span></span>
            <span className="d-row-side"><b>{f.kind === 'GARRISON' ? 'En garnison' : 'Stationnée'}</b></span></li>)}
            {facts.incoming.map(m => <li key={m.id} className="d-row">
              <Thumb src={shipImage(mainClass(m.stacks))} icon="icons/actions/action-lancer.svg" />
              <span className="d-row-main"><strong>{world!.fleets.fleets?.find(f => f.id === m.fleet_id)?.name ?? 'Flotte'}</strong><span>{kindNames[m.kind]} en route</span></span>
              <span className="d-row-side"><b>{Date.parse(m.travel_arrival_at) > now ? 'Arrivée' : 'Sur place'}</b><span>{clock(m.travel_arrival_at)}</span></span></li>)}</ul>}
      </section>

      <section className="d-card" aria-labelledby="sys-opps-title">
        <PanelHead icon="icons/colonie/panel-points-interet.svg" title="Gisements et curiosités" id="sys-opps-title" />
        {!world && !data.opportunities ? <p className="d-empty">Aucune donnée d’opportunité pour ce système.</p>
          : !opportunities.length ? <p className="d-empty">{signatures ? `${signatures} signature${signatures > 1 ? 's' : ''} inexpliquée${signatures > 1 ? 's' : ''} : une prospection par une sonde révélera ce qu’elles cachent.` : 'Aucune ressource ni anomalie détectée dans ce système.'}</p>
          : <ul className="d-rows">{opportunities.map(o => <li key={o.id} className={`d-row${pick?.id === o.id ? ' is-current' : ''}`}>
            <button type="button" className="d-row-btn" aria-pressed={pick?.id === o.id} onClick={() => setPick({ kind: 'opportunity', id: o.id })}>
              <span className={`d-sys-gem${o.family === 'deposit' ? ' is-deposit' : ''}`} aria-hidden="true" />
              <span className="d-row-main"><strong>{opportunityNames[o.kind] ?? o.kind}{o.tier === 'remarkable' ? ' · remarquable' : ''}</strong>
                <span>{o.family === 'deposit' ? `${resourceNames[o.resource!]} · réserve ${whole(o.reserve)}` : o.studied ? 'Déjà étudiée' : `${whole(o.data)} Données à étudier`}</span></span>
            </button></li>)}</ul>}
        {opportunities.length > 0 && !!signatures && <p className="d-note">{signatures} signature{signatures > 1 ? 's' : ''} encore inexpliquée{signatures > 1 ? 's' : ''}.</p>}
      </section>

      <section className="d-card" aria-labelledby="system-presences-title">
        <PanelHead icon="icons/sidebar/nav-relations.svg" title="Renseignements" id="system-presences-title" />
        <h3 className="d-sys-sub">Présences observées</h3>
        {!data.presences?.length ? <p className="d-empty">{data.state === 'MONITORED' ? 'Aucune présence actuellement observée.' : 'Aucune donnée de présence disponible.'}</p>
          : <ul className="d-sys-facts">{data.presences.map((presence, i) => <li key={i}>
            <strong>{presence.current ? 'Présence propre observée' : 'Ancienne présence propre observée'}{presence.colony ? ` : ${presence.colony.name}` : ''}</strong>
            {presence.observed_at && <span>Observation : <time dateTime={presence.observed_at}>{time(presence.observed_at)}</time></span>}
            {!presence.current && <span>Cette observation ancienne ne décrit pas la situation actuelle.</span>}
            {presence.colony && <a className="text-link" onClick={onColony}
              href={`#universe/${universe}/colony/overview/${presence.colony.colony_id}`}>Ouvrir la colonie {presence.colony.name} →</a>}
          </li>)}</ul>}
        {foreign.length > 0 && <p className="d-note">Partie de test : {foreign.map(n => `Empire ${n}`).join(', ')} observé{foreign.length > 1 ? 's' : ''} ici (identité inconnue).</p>}
        <h3 className="d-sys-sub">Routes connues</h3>
        {!data.routes?.length ? <p className="d-empty">Aucune route connue disponible.</p>
          : <ul className="d-sys-routes">{data.routes.map(r => <li key={r.id}>{r.neighbor.state === 'DETECTED'
            ? <span>Signal détecté — structure inconnue</span>
            : <a className="text-link" href={systemHref(r.neighbor.id)}>{r.neighbor.name} →</a>}</li>)}</ul>}
      </section>
    </div>

    <section className="d-card" aria-labelledby="system-worlds-title">
      <PanelHead icon="icons/colonie/colonie-secteurs.svg" title="Mondes connus" id="system-worlds-title" />
      <ul className="d-sys-worlds">{planets.map(p => <li key={p.id}>
        <button type="button" className={`d-sys-world${pick?.id === p.id ? ' is-current' : ''}`} aria-pressed={pick?.id === p.id} onClick={() => setPick({ kind: 'planet', id: p.id })}>
          <img src={planetImage(p.id)} alt="" width="44" height="44" />
          <span><strong>{p.name}</strong><small>{p.sectors} secteurs · {p.orbitals} orbitaux</small></span>
          <em className={`is-${occupation(p).tone}`}>{occupation(p).text}</em>
        </button></li>)}</ul>
    </section>
  </div>;
}

/** Star in the centre, worlds on illustrative orbits, opportunities as markers on a belt. */
function Orbit({ name, star, planets, opportunities, pick, onPick }: {
  name: string; star: [number, number, number]; planets: PlanetFact[]; opportunities: KnownOpportunity[];
  pick: Pick | null; onPick: (p: Pick) => void;
}) {
  const n = planets.length, W = 1000, H = 560, cx = W / 2, cy = H / 2;
  // Worlds on orbits from 210 to 395 (illustrative), opportunities on an outer belt.
  const radius = (i: number) => n <= 1 ? 280 : 210 + i * (185 / (n - 1));
  const at = (rx: number, angle: number) => ({ x: cx + Math.cos(angle) * rx, y: cy + Math.sin(angle) * rx * 0.5 });
  const belt = 455;
  const angle = (i: number) => -Math.PI * 0.62 + i * 2.39996;
  // Belt markers on twelve slots, away from the outer worlds they would hide.
  const gap = (a: number, b: number) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));
  const outer = planets.map((_, i) => i).filter(i => radius(i) > 330).map(angle);
  const all = Array.from({ length: 12 }, (_, k) => Math.PI * 0.1 + k * Math.PI / 6);
  const free = all.filter(a => outer.every(p => gap(a, p) > 0.45));
  const slots = (free.length >= opportunities.length ? free : all).filter((_, k, list) => list.length <= 6 || k % 2 === 0 || opportunities.length > list.length / 2);
  const pct = (p: { x: number; y: number }) => ({ left: `${p.x / W * 100}%`, top: `${p.y / H * 100}%` });
  return <div className="d-sys-orbit" style={{ '--d-star': `rgb(${star.join(',')})` } as CSSProperties}>
    <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      {planets.map((p, i) => <ellipse key={p.id} cx={cx} cy={cy} rx={radius(i)} ry={radius(i) * 0.5} className="d-sys-ring" />)}
      {opportunities.length > 0 && <ellipse cx={cx} cy={cy} rx={belt} ry={belt * 0.5} className="d-sys-belt" />}
    </svg>
    <span className="d-sys-star" aria-hidden="true"><span>{name}</span></span>
    {planets.map((p, i) => {
      // Golden-angle spread: neighbouring orbits never put two worlds side by side.
      const pos = at(radius(i), angle(i));
      return <button key={p.id} type="button" style={pct(pos)} aria-pressed={pick?.id === p.id} aria-label={`${i + 1} · ${p.name}`}
        className={`d-sys-planet${pick?.id === p.id ? ' is-current' : ''}${p.own ? ' is-own' : ''}${pos.x > W * 0.78 ? ' is-left' : ''}`} onClick={() => onPick({ kind: 'planet', id: p.id })}>
        <img src={planetImage(p.id)} alt="" />
        <span aria-hidden="true"><strong>{p.name}</strong><small>{p.own ? 'Votre colonie' : `${p.sectors} secteurs`}</small></span>
        {p.alert && <i className="d-sys-alert" aria-hidden="true">!</i>}
      </button>;
    })}
    {opportunities.map((o, i) => {
      const pos = at(belt, slots[i % slots.length]);
      return <button key={o.id} type="button" style={pct(pos)} aria-pressed={pick?.id === o.id}
        aria-label={`${opportunityNames[o.kind] ?? o.kind} (${o.family === 'deposit' ? 'gisement' : 'curiosité'})`}
        className={`d-sys-marker${o.family === 'deposit' ? ' is-deposit' : ''}${pick?.id === o.id ? ' is-current' : ''}`} onClick={() => onPick({ kind: 'opportunity', id: o.id })} />;
    })}
  </div>;
}

function PlanetDetail({ planet, universe, link, onColony }: {
  planet: PlanetFact; universe: string; link?: { colony_id: string }; onColony?: () => void;
}) {
  return <div className="d-sys-head">
    <img className="d-sys-head-img" src={planetImage(planet.id)} alt="" width="96" height="96" />
    <div>
      <h2 id="system-world-title">{planet.name}</h2>
      <p className={planet.own ? 'd-tone-blue' : planet.presence ? `d-rel-${planet.presence.relation}` : planet.foreign !== null ? 'd-tone-amber' : 'd-muted'}>{planet.own ? 'Votre colonie'
        : planet.presence ? `Colonie de ${foreignName(planet.presence)} · ${relationNames[planet.presence.relation]} (${planet.presence.source === 'combat' ? 'vue lors de votre attaque du' : 'observée le'} ${time(planet.presence.observed_at)})`
        : planet.foreign !== null ? `Colonie de l’Empire ${planet.foreign} (partie de test)` : 'Occupation actuelle inconnue : elle n’est vérifiée qu’à l’arrivée d’une mission.'}</p>
      <dl className="system-capacities d-sys-dl"><div><dt>Secteurs exploitables</dt><dd>{planet.sectors}</dd></div>
        <div><dt>Capacité orbitale</dt><dd>{planet.orbitals}</dd></div></dl>
      {planet.alert && <p className="d-tone-red">Attaque annoncée : bataille le {time(planet.alert)}.</p>}
      {link && <a className="d-btn d-btn-primary" onClick={onColony} href={`#universe/${universe}/colony/overview/${link.colony_id}`}>Voir ma colonie</a>}
    </div>
  </div>;
}

function OpportunityDetail({ opportunity: o }: { opportunity: KnownOpportunity }) {
  return <div className="d-sys-head">
    <span className={`d-sys-head-gem${o.family === 'deposit' ? ' is-deposit' : ''}`} aria-hidden="true" />
    <div>
      <h2 id="system-world-title">{opportunityNames[o.kind] ?? o.kind}</h2>
      <p className="d-muted">{o.family === 'deposit' ? 'Gisement' : 'Curiosité'}{o.tier === 'remarkable' ? ' remarquable' : ''} · observé le {new Date(o.observed_at).toLocaleDateString('fr-FR')}</p>
      <dl className="system-capacities d-sys-dl">{o.family === 'deposit' ? <>
        <div><dt>Ressource</dt><dd>{resourceNames[o.resource!]}</dd></div>
        <div><dt>Réserve observée</dt><dd>{whole(o.reserve)}</dd></div>
        <div><dt>Débit maximal</dt><dd>{whole(o.throughput_per_hour)}/h</dd></div></> : <>
        <div><dt>Étude</dt><dd>{Math.round((o.study_seconds ?? 0) / 3600)} h</dd></div>
        <div><dt>Données</dt><dd>{whole(o.data)}</dd></div>
        <div><dt>État</dt><dd>{o.studied ? 'Étudiée' : 'À étudier'}</dd></div></>}</dl>
      {o.dossier !== undefined && <p className="d-note">Indice d’un dossier : étudier tous ses indices révèle les systèmes remarquables de la région.</p>}
      {o.family === 'deposit' && <p className="d-note">La réserve est celle de l’observation ; d’autres Empires peuvent l’avoir entamée depuis.</p>}
    </div>
  </div>;
}

/** Offered actions of the selected item and of the system, then the shared mission planner. */
function ActionPanel({ world, api, system, pending, feedback, groups, onDone }: {
  world: World; api: MissionApi; system: string; pending: boolean; feedback: CommandFeedback;
  groups: { title: string; offers: ActionOffer[] }[]; onDone: (notice: string) => void;
}) {
  const flow = useMissionFlow(world, api, system, pending);
  const canCommand = world.fleets.permissions.includes('fleet.command');
  if (flow.intent) return <div className="d-sys-planner cmd-root">
    <MissionPlanner world={world} target={system} offer={flow.intent.offer} fleets={flow.candidates} fleet={flow.fleet} units={flow.intent.units}
      hours={flow.intent.hours} onHours={h => flow.update({ hours: h })} comeBack={flow.intent.comeBack} onComeBack={b => flow.update({ comeBack: b })}
      step={flow.step} quoteKey={flow.planKey} quote={flow.quote} path={flow.path} pending={pending || flow.busy}
      onFleet={flow.chooseFleet} onUnits={u => flow.update({ units: u })} onStep={flow.setStep}
      onConfirm={() => { void flow.confirm().then(label => { if (label) onDone(`${label} Suivez-la dans « Flottes » ou sur la carte.`); }); }}
      onCancel={flow.stop} />
    {flow.failed && feedback && feedback.tone !== 'success' && <p role="alert" className="feedback feedback--error">
      {feedback.tone === 'unknown' ? 'Résultat non confirmé. Confirmez à nouveau : la même intention est réutilisée, sans double envoi.' : message(feedback.code)}</p>}
  </div>;
  const shown = groups.filter(g => g.offers.length);
  return <div className="d-sys-actions">
    {!canCommand ? <p className="d-muted">Votre accès ne permet pas de commander les flottes de cet Empire.</p>
      : !shown.length ? <p className="d-muted">Aucune action de flotte possible ici.</p>
      : shown.map(g => <div key={g.title}><h3 className="d-sys-sub">{g.title}</h3>
        <ul className="cmd-actions">{g.offers.map((o, i) => <li key={`${o.kind}-${o.planet ?? o.opportunity ?? ''}`}>
          <button type="button" className={`d-btn${!o.reason && i === 0 ? ' d-btn-primary' : ''}`} disabled={!!o.reason}
            aria-describedby={`sys-hint-${o.kind}-${o.planet ?? o.opportunity ?? 's'}`} onClick={() => flow.start(o)}>{o.label}</button>
          <p id={`sys-hint-${o.kind}-${o.planet ?? o.opportunity ?? 's'}`} className="d-note">{o.reason ?? o.hint}</p></li>)}</ul></div>)}
  </div>;
}

/** Without the Fleet projection (older rules, missing rights): the Fleet screen shortcuts of step 8. */
function LegacyActions({ data, universe, empire, planet, link, can }: {
  data: SystemDetail; universe: string; empire: string; planet: PlanetFact | null; link: boolean; can: (right: string) => boolean;
}) {
  const system = data.id;
  return <div className="d-sys-actions">
    {planet && !link && data.colonization && <>
      {/* Never "Libre": the current occupation of a structure-only world is not known. */}
      {can('fleet.command') && can('colony.expand') &&
        <a className="d-btn" href={`#universe/${universe}/fleets/colonize/${empire}/${system}/${planet.id}`}>Coloniser…</a>}</>}
    {planet && !link && data.combat && can('fleet.command') && can('combat.attack') && can('combat.read') && <>
      {/* Occupation and defence are never shown: the attack itself is the only way to learn. */}
      <p className="d-note">Occupation et défense non confirmées.</p>
      <a className="d-btn" href={`#universe/${universe}/fleets/attack/${empire}/${system}/${planet.id}`}>Attaquer…</a></>}
    {can('fleet.command') && <a className="d-btn d-btn-ghost" href={`#universe/${universe}/fleets/send/${empire}/${system}`}>Envoyer une flotte ici</a>}
  </div>;
}
