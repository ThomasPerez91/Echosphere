import { useEffect, useState } from 'react';
import type { Option, Order, Projection } from '../colony/api';
import { costParts, duration, errorMessage, infrastructureLabel, rate, ratio, reasonLabel, resourceKeys,
  resourceLabels, resourceSymbols, time, units } from '../colony/format';
import type { useColony } from '../hooks/useColony';
import { Badge, Button } from './ui';

type Colony = ReturnType<typeof useColony>;
const colonyViews = [
  { id: 'overview', label: 'Vue d’ensemble' },
  { id: 'infrastructure', label: 'Infrastructures' },
  { id: 'orbit', label: 'Orbite' },
  { id: 'defense', label: 'Défense' },
] as const;

/** Visual projection of server dates only; it never completes or changes anything. */
function Progress({ order, offset }: { order: Order; offset: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  if (!order.started_at || !order.due_at) return <span className="queue-waiting">En attente du démarrage</span>;
  const start = Date.parse(order.started_at), end = Date.parse(order.due_at), server = now + offset;
  const percent = Math.max(0, Math.min(100, Math.floor((server - start) / Math.max(1, end - start) * 100)));
  const left = Math.max(0, Math.ceil((end - server) / 1000));
  return <div className="queue-progress">
    <div className="meter" role="progressbar" aria-label={`Avancement estimé de ${infrastructureLabel(order.infrastructure_type)}`}
      aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><span style={{ width: `${percent}%` }} /></div>
    <span>{left > 0 ? `${duration(String(left * 1_000_000))} restantes · fin ${time(order.due_at)}` : 'Échéance atteinte, confirmation serveur…'}</span>
  </div>;
}

function Cost({ value }: { value: Option['cost'] }) {
  const parts = costParts(value);
  return <ul className="cost" aria-label="Coût">{parts.length ? parts.map(part => <li key={part.key}>
    <span aria-hidden="true" className={`resource-symbol--${part.key}`}>{resourceSymbols[part.key]}</span>
    <span className="sr-only">{part.label} </span>{part.value}</li>) : <li>Gratuit</li>}</ul>;
}

function Effect({ option }: { option: Pick<Option, 'production_per_hour' | 'construction_bonus_bps' | 'capacity'> }) {
  const produced = resourceKeys.filter(key => BigInt(option.production_per_hour[key]) > 0n);
  return <p className="effect">{produced.map(key => `${resourceLabels[key]} +${rate(option.production_per_hour[key])}/h`).join(' · ')}
    {option.construction_bonus_bps ? `Construction +${option.construction_bonus_bps / 100} %` : ''}
    {option.capacity ? `Capacité ${units(option.capacity)} par ressource` : ''}</p>;
}

function Resources({ projection }: { projection: Projection }) {
  return <section className="colony-resources" aria-label="Stocks de la colonie">
    {projection.resources.map(resource => {
      const filled = ratio(resource.stock, resource.capacity);
      return <div className="resource-card" key={resource.resource}>
        <span className={`resource-symbol resource-symbol--${resource.resource}`} aria-hidden="true">{resourceSymbols[resource.resource]}</span>
        <div className="resource-body"><h2>{resourceLabels[resource.resource]}</h2>
          <p className="resource-amount">{units(resource.stock)} <span>/ {resource.capacity ? units(resource.capacity) : '∞'}</span></p>
          <p className="resource-rate">+{rate(resource.rate_per_hour)}/h</p>
          <div className={`meter ${filled >= 90 ? 'meter--warning' : ''}`} role="meter" aria-label={`Remplissage ${resourceLabels[resource.resource]}`}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={filled}><span style={{ width: `${filled}%` }} /></div>
        </div>
      </div>;
    })}
  </section>;
}

function Alerts({ projection }: { projection: Projection }) {
  const full = projection.resources.filter(r => ratio(r.stock, r.capacity) >= 90);
  const items = [
    ...full.map(r => ({ key: r.resource, text: `${resourceLabels[r.resource]} : stock proche de la capacité. La production au-delà est perdue.` })),
    ...(projection.queue.length >= projection.queue_limit ? [{ key: 'queue', text: 'File de construction pleine.' }] : []),
    ...(!projection.sectors.free ? [{ key: 'sectors', text: 'Aucun secteur libre pour une nouvelle infrastructure.' }] : []),
  ];
  if (!items.length) return null;
  return <ul className="colony-alerts" aria-label="Alertes de la colonie">{items.map(item => <li key={item.key}><span aria-hidden="true">▲</span>{item.text}</li>)}</ul>;
}

function Queue({ colony, projection, offset }: { colony: Colony; projection: Projection; offset: number }) {
  const [confirm, setConfirm] = useState<string | null>(null);
  return <section className="panel queue-panel" aria-labelledby="queue-title">
    <div className="panel-head"><h2 id="queue-title">Constructions en cours</h2><span className="panel-meta">{projection.queue.length} / {projection.queue_limit}</span></div>
    {colony.awaiting && <p className="notice" role="status">Échéance dépassée : en attente de confirmation du serveur.
      <Button onClick={colony.refresh}>Actualiser la colonie</Button></p>}
    {!projection.queue.length ? <p className="muted">Aucune construction en cours. Les ordres continuent sans navigateur ouvert.</p>
      : <ol className="queue-list">{projection.queue.map(order => {
        const label = infrastructureLabel(order.infrastructure_type);
        const refund = costParts(order.cancel.refund).map(part => `${part.value} ${part.label}`).join(', ') || 'aucun';
        const pending = colony.pending === JSON.stringify({ kind: 'cancel', order_id: order.id });
        return <li key={order.id} className="queue-item">
          <div className="queue-title"><strong>{label}</strong>
            <span>Secteur {order.sector_index} · {order.target_level === 1 ? 'Nouvelle infrastructure' : `Niveau ${order.target_level - 1} → ${order.target_level}`}</span>
            <Badge tone={order.status === 'active' ? 'accent' : 'neutral'}>{order.status === 'active' ? 'En cours' : 'En file'}</Badge></div>
          {order.status === 'active' ? <Progress order={order} offset={offset} /> : <span className="queue-waiting">Démarre après l’ordre précédent ; durée fixée au démarrage.</span>}
          {projection.permissions.includes('colony.cancel') && (confirm === order.id
            ? <div className="confirm" role="group" aria-label={`Confirmer l’annulation de ${label}`}>
                <p>Remboursement : {refund}{order.cancel.also_cancels.length ? ` · annule aussi ${order.cancel.also_cancels.length} amélioration(s) dépendante(s)` : ''}.</p>
                <Button className="button--danger" disabled={!!colony.pending || !order.cancel.available}
                  onClick={() => { void colony.command({ kind: 'cancel', order_id: order.id }); setConfirm(null); }}>Confirmer l’annulation</Button>
                <Button onClick={() => setConfirm(null)}>Garder</Button>
              </div>
            : <div className="queue-actions"><Button disabled={!!colony.pending || !order.cancel.available}
                aria-describedby={order.cancel.reason ? `cancel-${order.id}` : undefined}
                onClick={() => setConfirm(order.id)}>{pending ? 'Annulation…' : `Annuler ${label}`}</Button>
              {order.cancel.reason && <span id={`cancel-${order.id}`} className="reason">{reasonLabel(order.cancel.reason)}</span>}</div>)}
        </li>;
      })}</ol>}
  </section>;
}

function OptionCard({ colony, option, free, canBuild, compact = false }: { colony: Colony; option: Option; free: number[]; canBuild: boolean; compact?: boolean }) {
  const [sector, setSector] = useState(option.sector_index);
  const label = infrastructureLabel(option.infrastructure_type);
  const chosen = option.action === 'build' ? (sector && free.includes(sector) ? sector : option.sector_index) : option.sector_index;
  const command = { kind: 'construct' as const, infrastructure_type: option.infrastructure_type, sector_index: chosen ?? 0, target_level: option.target_level };
  const pending = colony.pending === JSON.stringify(command);
  const describe = `option-${option.action}-${option.infrastructure_type}-${option.sector_index ?? 'none'}`;
  return <li className={`option-card ${option.available ? '' : 'is-locked'} ${compact ? 'option-card--compact' : ''}`}>
    {compact ? <p className="option-meta">Amélioration vers le niveau {option.target_level}</p> : <>
      <h3>{label}</h3>
      <p className="option-meta">{option.action === 'build' ? 'Nouvelle infrastructure · niveau 1' : `Secteur ${option.sector_index} · niveau ${option.target_level - 1} → ${option.target_level}`}</p></>}
    <Effect option={option} />
    <Cost value={option.cost} />
    <p className="option-time">Durée de base {duration(option.base_duration_us)}
      {option.estimated_duration_us && option.estimated_duration_us !== option.base_duration_us ? ` · effective ${duration(option.estimated_duration_us)}` : ''}</p>
    {option.action === 'build' && option.available && free.length > 1 && <label className="sector-select">Secteur
      <select value={chosen ?? ''} onChange={event => setSector(Number(event.target.value))}>
        {free.map(index => <option key={index} value={index}>Secteur {index}</option>)}
      </select></label>}
    {canBuild && <Button className={option.available ? 'button--primary' : ''}
      disabled={!option.available || !!colony.pending || !chosen} aria-describedby={option.reason ? describe : undefined}
      onClick={() => { void colony.command(command); }}>
      {pending ? 'Envoi…' : option.action === 'build' ? `Construire ${label}` : `Améliorer ${label} niveau ${option.target_level}`}</Button>}
    {option.reason && <p id={describe} className="reason">{reasonLabel(option.reason)}</p>}
  </li>;
}

function Infrastructures({ colony, data, offset }: { colony: Colony; data: Projection; offset: number }) {
  const builds = data.options.filter(option => option.action === 'build');
  const canBuild = data.permissions.includes('colony.construct');
  const upgrades = new Map(data.options.filter(option => option.action === 'upgrade').map(option => [option.sector_index, option]));
  return <div className="infrastructure-layout">
    <Queue colony={colony} projection={data} offset={offset} />
    <section className="panel" aria-labelledby="built-title">
      <div className="panel-head"><h2 id="built-title">Infrastructures de la colonie</h2>
        <span className="panel-meta">{data.sectors.built} / {data.sectors.capacity} secteurs</span></div>
      <ul className="option-grid">{data.infrastructures.map(row => {
        const upgrade = upgrades.get(row.sector_index);
        return <li key={row.sector_index} className="built-card">
          <h3>{infrastructureLabel(row.infrastructure_type)}</h3>
          <p className="option-meta">Secteur {row.sector_index} · niveau {row.level}</p>
          <Effect option={row} />
          {upgrade && <ul className="option-grid nested"><OptionCard colony={colony} option={upgrade} free={data.sectors.free_indices} canBuild={canBuild} compact /></ul>}
        </li>;
      })}</ul>
    </section>
    <section className="panel" aria-labelledby="available-title">
      <div className="panel-head"><h2 id="available-title">Nouvelles infrastructures</h2>
        <span className="panel-meta">{data.sectors.free} secteur(s) libre(s)</span></div>
      <ul className="option-grid">{builds.map(option => <OptionCard key={option.infrastructure_type} colony={colony} option={option}
        free={data.sectors.free_indices} canBuild={canBuild} />)}</ul>
    </section>
  </div>;
}

function Overview({ colony, data, offset, link }: { colony: Colony; data: Projection; offset: number; link: (v: string) => string }) {
  return <div className="overview-layout">
    <Alerts projection={data} />
    <Queue colony={colony} projection={data} offset={offset} />
    <section className="panel" aria-labelledby="summary-title">
      <div className="panel-head"><h2 id="summary-title">Infrastructures</h2><a className="text-link" href={link('colony/infrastructure')}>Gérer →</a></div>
      <table className="summary-table"><caption className="sr-only">Résumé des infrastructures</caption>
        <thead><tr><th scope="col">Secteur</th><th scope="col">Infrastructure</th><th scope="col">Niveau</th><th scope="col">Effet</th></tr></thead>
        <tbody>{data.infrastructures.map(row => <tr key={row.sector_index}><td>{row.sector_index}</td><td>{infrastructureLabel(row.infrastructure_type)}</td>
          <td>{row.level}</td><td><Effect option={row} /></td></tr>)}</tbody></table>
    </section>
  </div>;
}

export function ColonyScreen({ colony, view, link, onNavigate }: { colony: Colony; view: string; link: (v: string) => string; onNavigate?: () => void }) {
  if (colony.phase === 'loading' || colony.phase === 'idle') return <p className="panel" aria-live="polite">Chargement de votre colonie…</p>;
  if (colony.phase === 'empty') return <section className="panel"><h2>Aucune colonie accessible</h2>
    <p>Votre participation ne donne accès à aucune colonie dans cet univers.</p></section>;
  if (colony.phase === 'error' || !colony.projection) return <section className="panel" role="alert"><h2>Colonie indisponible</h2>
    <p>{errorMessage(colony.error ?? 'unavailable')}</p><Button onClick={colony.refresh}>Réessayer</Button></section>;
  const data = colony.projection;
  const offset = Date.parse(data.server_time) - colony.receivedAt;
  const used = data.sectors.built + data.sectors.reserved;
  return <section className="colony-screen" aria-label={`Colonie ${data.colony.name}`}>
    <header className="colony-header">
      <div><p className="eyebrow">COLONIE · {data.colony.system.name.toUpperCase()}</p>
        <h2 className="colony-name">{data.colony.name}</h2>
        <p className="muted">Empire {data.colony.empire.name} · Univers {data.colony.universe.name}</p></div>
      <div className="colony-stats">
        <div className="stat"><strong>{used} / {data.sectors.capacity}</strong><span>Secteurs utilisés</span>
          <div className="meter" role="meter" aria-label="Secteurs utilisés" aria-valuemin={0} aria-valuemax={data.sectors.capacity} aria-valuenow={used}>
            <span style={{ width: `${used / data.sectors.capacity * 100}%` }} /></div></div>
        <div className="stat"><strong>{data.colony.planet.orbital_capacity}</strong><span>Emplacements orbitaux · à venir</span></div>
      </div>
      {colony.colonies.length > 1 && <label className="sector-select">Colonie
        <select value={data.colony.id} onChange={event => colony.select(event.target.value)}>
          {colony.colonies.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
    </header>
    <Resources projection={data} />
    <nav aria-label="Sections de la colonie" className="colony-navigation">
      {colonyViews.map(item => <a key={item.id} href={link(`colony/${item.id}`)} onClick={onNavigate} aria-current={item.id === view ? 'page' : undefined}>{item.label}</a>)}
    </nav>
    <div className="feedback-zone" aria-live="polite">
      {colony.feedback && <div className={`feedback feedback--${colony.feedback.tone}`} role={colony.feedback.tone === 'success' ? 'status' : 'alert'}>
        <p>{colony.feedback.tone === 'success' ? colony.feedback.text : colony.feedback.tone === 'unknown'
          ? `Résultat non confirmé. ${errorMessage(colony.feedback.code ?? 'unavailable')}` : errorMessage(colony.feedback.code ?? 'unavailable')}</p>
        <Button onClick={colony.dismiss}>Fermer</Button></div>}
      {colony.error && <p className="feedback feedback--error" role="alert">Actualisation impossible : {errorMessage(colony.error)}</p>}
    </div>
    <div className="colony-toolbar"><span className="muted">État serveur au {time(data.server_time)} · ruleset {data.ruleset_version}</span>
      <Button onClick={colony.refresh}>Actualiser la colonie</Button></div>
    {view === 'infrastructure' ? <Infrastructures colony={colony} data={data} offset={offset} />
      : view === 'orbit' ? <section className="panel destination-panel"><Badge>À venir</Badge><h2>Orbite — système futur</h2>
          <p>Les {data.colony.planet.orbital_capacity} emplacements orbitaux de référence sont réservés. Aucune construction orbitale n’est disponible à cette étape.</p></section>
      : view === 'defense' ? <section className="panel destination-panel"><Badge>À venir</Badge><h2>Défense — système futur</h2>
          <p>La défense planétaire sera un réseau limité de modules persistants. Aucun module, réparation ou effet de combat n’est disponible.</p></section>
      : <Overview colony={colony} data={data} offset={offset} link={link} />}
  </section>;
}
