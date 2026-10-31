import { useEffect, useRef, useState } from 'react';
import { useSystem } from '../hooks/useSystem';
import { Badge, Button, Panel } from './ui';
import type { KnownPlanet } from '../galaxy/api';

const time = (value: string) => new Date(value).toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });

function SystemIllustration({ planets, selected, onSelect }: {
  planets: KnownPlanet[]; selected: string; onSelect: (id: string) => void;
}) {
  return <div className="system-illustration">
    <svg viewBox="0 0 680 420" role="img" aria-labelledby="system-diagram-title system-diagram-description">
      <title id="system-diagram-title">Représentation des mondes connus</title>
      <desc id="system-diagram-description">Disposition illustrative, sans distance ou mouvement orbital de jeu. Chaque monde est décrit dans la liste ci-dessous.</desc>
      <defs><radialGradient id="system-star-light"><stop offset="0" stopColor="#fff3bc" /><stop offset=".6" stopColor="#e9b958" /><stop offset="1" stopColor="#98673e" /></radialGradient></defs>
      {[135, 205, 280].map(radius => <ellipse key={radius} cx={340} cy={210} rx={radius} ry={radius * .58} className="system-orbit" />)}
      <circle cx={340} cy={210} r={42} fill="url(#system-star-light)" />
      {planets.map((planet, i) => {
        const angle = Math.PI * 2 * i / Math.max(1, planets.length) - Math.PI / 3;
        const x = 340 + Math.cos(angle) * 250, y = 210 + Math.sin(angle) * 145;
        return <g key={planet.id} className={selected === planet.id ? 'system-world is-selected' : 'system-world'}>
          <circle cx={x} cy={y} r={selected === planet.id ? 29 : 25} className="system-world-ring" />
          <circle cx={x} cy={y} r={21} className="system-world-surface" />
          <text x={x} y={y + 47} textAnchor="middle">{i + 1}</text>
        </g>;
      })}
    </svg>
    <p className="panel-meta">Disposition illustrative · aucune échelle astronomique</p>
    <div className="system-world-shortcuts" aria-label="Sélection d’un monde">
      {planets.map((p, i) => <button key={p.id} type="button" aria-pressed={p.id === selected}
        onClick={() => onSelect(p.id)} aria-label={`Sélectionner ${p.name}`}>{i + 1} · {p.name}</button>)}
    </div>
  </div>;
}

export function SystemView({ universe, empire, system, onSessionLost, onColony }: {
  universe: string; empire: string; system: string; onSessionLost: () => void; onColony?: () => void;
}) {
  const state = useSystem(universe, empire, system, onSessionLost);
  const [selection, setSelection] = useState<{ scope: string; planet: string }>({ scope: '', planet: '' });
  const heading = useRef<HTMLHeadingElement>(null);
  const data = state.data;
  const scope = `${universe}/${empire}/${system}`;
  const back = `#universe/${universe}/galaxy`;
  useEffect(() => { if (data) heading.current?.focus(); }, [data]);
  if (state.loading) return <Panel title="Vue du système"><p role="status">Lecture des connaissances du système…</p></Panel>;
  if (!data) return <Panel title="Système indisponible"><p role="alert">{state.error === 'authentication_required'
    ? 'Votre session a expiré. Retournez au lobby.' : state.error === 'system_not_found' || state.error === 'empire_not_found'
      ? 'Ce système n’est pas accessible avec vos connaissances et permissions actuelles.' : 'La lecture du système est momentanément indisponible.'}</p>
    <Button onClick={state.refresh}>Réessayer</Button><a className="button" href={back}>Retour à la Galaxie</a></Panel>;
  if (data.state === 'DETECTED') return <Panel title="Système seulement détecté">
    <h2 ref={heading} tabIndex={-1}>Structure encore inconnue</h2>
    <p>La vue détaillée devient disponible après cartographie. Retrouvez le signal et les possibilités d’exploration sur la Galaxie.</p>
    <a className="button" href={back}>Retour à la Galaxie</a></Panel>;
  const planets = data.planets!;
  const selected = planets.find(p => p.id === (selection.scope === scope ? selection.planet : '')) ?? planets[0];
  const choose = (id: string) => setSelection({ scope, planet: id });
  const link = data.colony_links?.find(c => c.planet_id === selected?.id);
  return <div className="system-screen">
    <header className="system-heading panel">
      <a className="text-link" href={back}>← Retour à la Galaxie</a>
      <div className="panel-head"><h2 ref={heading} tabIndex={-1}>Système {data.name}</h2>
        <Badge tone="accent">{data.state === 'MONITORED' ? 'Surveillé' : 'Cartographié'}</Badge></div>
      <p>Cartographié : <time dateTime={data.mapped_at}>{time(data.mapped_at!)}</time></p>
      {data.last_seen_at && <p>{data.state === 'MONITORED' ? 'Observation locale' : 'Dernière observation, ancienne'} : <time dateTime={data.last_seen_at}>{time(data.last_seen_at)}</time></p>}
      <p className="panel-meta">Connaissances lues au {time(data.server_time!)}</p>
      <Button onClick={state.refresh}>Actualiser les connaissances</Button>
    </header>
    <div className="system-layout">
      <section className="panel system-map" aria-label="Vue des mondes">
        <SystemIllustration planets={planets} selected={selected?.id ?? ''} onSelect={choose} />
      </section>
      <section className="panel system-world-detail" aria-labelledby="system-world-title">
        <h2 id="system-world-title">{selected?.name ?? 'Aucun monde connu'}</h2>
        {selected && <><dl className="system-capacities"><div><dt>Secteurs exploitables</dt><dd>{selected.sector_capacity}</dd></div>
          <div><dt>Capacité orbitale</dt><dd>{selected.orbital_capacity}</dd></div></dl>
          <p>Capacités connues de ce monde.</p>
          {link && <a className="button button--primary" onClick={onColony}
            href={`#universe/${universe}/colony/overview/${link.colony_id}`}>Voir ma colonie</a>}</>}
      </section>
    </div>
    <section className="panel" aria-labelledby="system-worlds-title"><h2 id="system-worlds-title">Mondes connus</h2>
      <ul className="system-world-list">{planets.map((p, i) => <li key={p.id}><button type="button" aria-pressed={selected?.id === p.id}
        onClick={() => choose(p.id)}><strong>{i + 1} · {p.name}</strong><span>{p.sector_capacity} secteurs · {p.orbital_capacity} orbitaux</span></button></li>)}</ul>
    </section>
    <div className="system-information">
      <section className="panel" aria-labelledby="system-presences-title"><h2 id="system-presences-title">Présences observées</h2>
        {!data.presences?.length ? <p>{data.state === 'MONITORED' ? 'Aucune présence actuellement observée.' : 'Aucune donnée de présence disponible.'}</p>
          : <ul>{data.presences.map((presence, i) => <li key={i}>
            <strong>{presence.current ? 'Présence propre observée' : 'Ancienne présence propre observée'}{presence.colony ? ` : ${presence.colony.name}` : ''}</strong>
            {presence.observed_at && <p>Observation : <time dateTime={presence.observed_at}>{time(presence.observed_at)}</time></p>}
            {!presence.current && <p>Cette observation ancienne ne décrit pas la situation actuelle.</p>}
          </li>)}</ul>}
      </section>
      <section className="panel" aria-labelledby="system-routes-title"><h2 id="system-routes-title">Routes connues</h2>
        {!data.routes?.length ? <p>Aucune route connue disponible.</p> : <ul>{data.routes.map(r => <li key={r.id}>
          {r.neighbor.name ?? 'Signal détecté — structure inconnue'}
        </li>)}</ul>}
        <a className="text-link" href={back}>Revenir à la carte galactique →</a>
      </section>
    </div>
  </div>;
}
