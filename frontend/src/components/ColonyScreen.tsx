import { useState } from 'react';
import type { Amounts, Option, Order, Projection } from '../colony/api';
import { costParts, duration, errorMessage, exactUnits, infrastructureLabel, placeLabel, rate, ratio, reasonLabel, resourceKeys,
  resourceLabels, time, units } from '../colony/format';
import type { useColony } from '../hooks/useColony';
import { Bar, Ico, PanelHead, Pending, Pic } from '../shell/visual';
import { asset, buildingImage, estimate, resourceIcon } from '../shell/assets';
import { useNow } from '../shell/useNow';
import { Button } from './ui';
import { DefenseSummary, DefenseTab } from './ColonyDefense';

type Colony = ReturnType<typeof useColony>;
const colonyViews = [
  { id: 'overview', label: 'Vue d’ensemble', icon: 'tab-vue-ensemble' },
  { id: 'infrastructure', label: 'Infrastructures', icon: 'tab-infrastructures' },
  { id: 'orbit', label: 'Orbite', icon: 'tab-orbite' },
  { id: 'defense', label: 'Défense', icon: 'tab-defense' },
] as const;
/** What each surface infrastructure does, in player words (its figures come from the server). */
const roles: Record<string, string> = {
  extraction_complex: 'Extrait les alliages du sous-sol de la planète.',
  flux_reactor: 'Produit le flux qui alimente la colonie.',
  data_node: 'Collecte les données utiles à la recherche.',
  industrial_complex: 'Accélère les constructions de la colonie.',
  logistics_center: 'Augmente la capacité de stockage de chaque ressource.',
  orbital_shipyard: 'Construit les vaisseaux ; chaque niveau débloque de nouvelles classes.',
  research_center: 'Permet la recherche ; son niveau ouvre les technologies avancées.',
};

/** Server dates only: an estimate between two readings, never a completion. */
function progress(order: Order, server: number) {
  if (!order.started_at || !order.due_at) return null;
  const start = Date.parse(order.started_at), end = Date.parse(order.due_at);
  return { percent: Math.max(0, Math.min(100, Math.floor((server - start) / Math.max(1, end - start) * 100))), left: Math.max(0, Math.ceil((end - server) / 1000)) };
}
/** DEF-01: an order re-targeting the level of a built module is its repair. */
const isRepair = (order: Order, data: Projection) => !!data.defense && order.infrastructure_type in data.defense.catalogue
  && data.infrastructures.some(row => row.sector_index === order.sector_index && row.level === order.target_level);
const level = (order: Order, data?: Projection) => data && isRepair(order, data) ? 'Réparation'
  : order.target_level === 1 ? 'Nouvelle infrastructure' : `Niveau ${order.target_level - 1} → ${order.target_level}`;
const where = (sector: number) => sector > 1000 ? `${placeLabel(sector)} · Orbital` : `${placeLabel(sector)} · Surface`;

function Costs({ value, minutes, stocks }: { value: Amounts; minutes?: string; stocks?: Record<string, number> }) {
  const parts = costParts(value);
  return <div className="d-costs" aria-label="Coût">
    {parts.length ? parts.map(part => <span key={part.key} className={`d-cost${stocks && stocks[part.key] < Number(value[part.key]) / 1e6 ? ' d-short' : ''}`}>
      <img src={asset(resourceIcon[part.key])} alt="" width="17" height="17" /><span className="sr-only">{part.label} </span>{part.value}</span>)
      : <span className="d-cost">Gratuit</span>}
    {minutes && <span className="d-cost"><img src={asset('icons/ui/ui-chronometre.svg')} alt="" width="17" height="17" /><span className="sr-only">Durée </span>{minutes}</span>}
  </div>;
}

function Effect({ option }: { option: Pick<Option, 'production_per_hour' | 'construction_bonus_bps' | 'capacity'> }) {
  const produced = resourceKeys.filter(key => BigInt(option.production_per_hour[key]) > 0n);
  return <p className="effect">{produced.map(key => `${resourceLabels[key]} +${rate(option.production_per_hour[key])}/h`).join(' · ')}
    {option.construction_bonus_bps ? `Construction +${option.construction_bonus_bps / 100} %` : ''}
    {option.capacity ? `Capacité ${units(option.capacity)} par ressource` : ''}</p>;
}

function Alerts({ projection }: { projection: Projection }) {
  const items = [
    ...(projection.incoming ?? []).filter(a => a.state === 'pending').map(a => ({ key: a.id, tone: 'danger', icon: 'alerte-flotte-ennemie', title: 'Force hostile annoncée', text: `Bataille prévue ${time(a.battle_at)}` })),
    ...projection.resources.filter(r => ratio(r.stock, r.capacity) >= 90).map(r => ({ key: r.resource, tone: 'warn', icon: 'alerte-stockage-limite',
      title: 'Stock proche de la capacité', text: `${resourceLabels[r.resource]} : la production au-delà est perdue.` })),
    ...(projection.queue.length >= projection.queue_limit ? [{ key: 'queue', tone: 'warn', icon: 'alerte-construction-terminee', title: 'File de construction pleine', text: `${projection.queue.length} / ${projection.queue_limit} ordres` }] : []),
    ...(!projection.sectors.free ? [{ key: 'sectors', tone: 'danger', icon: 'alerte-critique', title: 'Secteurs à capacité maximale', text: 'Aucun secteur libre pour une nouvelle infrastructure.' }]
      : projection.sectors.free <= 2 ? [{ key: 'sectors', tone: 'warn', icon: 'alerte-stockage-limite', title: 'Secteurs bientôt saturés', text: `Plus que ${projection.sectors.free} secteur${projection.sectors.free > 1 ? 's' : ''} libre${projection.sectors.free > 1 ? 's' : ''}.` }] : []),
  ];
  return <section className="d-card d-panel" aria-labelledby="colony-alerts">
    <PanelHead id="colony-alerts" icon="icons/ui/ui-alerte.svg" title="Alertes de la colonie" />
    <ul className="d-alert-list colony-alerts" aria-label="Alertes de la colonie">{items.map(item => <li key={item.key} className={`d-${item.tone}`}>
      <Pic src={`icons/alertes/${item.icon}.svg`} size={32} /><div><strong>{item.title}</strong><span>{item.text}</span></div><time /></li>)}
      {!items.length && <li className="d-info"><Pic src="icons/alertes/alerte-construction-terminee.svg" size={32} /><div><strong>Aucune alerte</strong><span>Stocks, file et secteurs vérifiés à la dernière lecture.</span></div><time /></li>}
    </ul>
  </section>;
}

function DefenseStatus({ projection, banner }: { projection: Projection; banner?: (v: string) => string }) {
  const threats = (projection.incoming ?? []).filter(a => a.state === 'pending').length;
  const who = projection.defense ? 'la garnison et les modules opérationnels combattront' : 'seules les unités militaires stationnées combattront';
  return <section className="d-card d-panel" aria-labelledby="colony-defense-status">
    <PanelHead id="colony-defense-status" icon="icons/defense/statut-defense.svg" title="Statut de défense"
      more={projection.defense && banner ? { href: banner('colony/defense'), label: 'Gérer' } : undefined} />
    {projection.defense ? <DefenseSummary data={projection} />
      : <Pending what="Défense planétaire : nouvelles parties seulement (ruleset v0.13). Ici, seule la garnison défend." />}
    <p className="d-note">{threats ? `${threats} force${threats > 1 ? 's' : ''} hostile${threats > 1 ? 's' : ''} annoncée${threats > 1 ? 's' : ''} : ${who}.` : 'Aucune force hostile annoncée sur cette colonie.'}</p>
    {banner && <a className="d-orbital-banner" href={banner('colony/orbit')}>
      <img src={asset('img/colonie/banniere-defenses-orbitales.webp')} alt="" width="1200" height="360" />
      <span className="d-ob-ico"><Pic src="icons/defense/defenses-orbitales.svg" size={40} /></span>
      <span className="d-ob-text"><b>Gérer les défenses orbitales</b><small>Voir l’orbite de la colonie</small></span>
      <svg className="d-chev-r" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg></a>}
  </section>;
}

/** Full queue with the explicit cancellation flow (refund, losses and cascade before any POST). */
function Queue({ colony, projection, server }: { colony: Colony; projection: Projection; server: number }) {
  const [confirm, setConfirm] = useState<string | null>(null);
  const canCancel = projection.permissions.includes('colony.cancel');
  return <section className="d-card d-panel queue-panel" aria-labelledby="queue-title">
    <PanelHead id="queue-title" icon="icons/colonie/panel-activites.svg" title="Constructions en cours"><span className="d-queue-count">{projection.queue.length} / {projection.queue_limit}</span></PanelHead>
    {colony.awaiting && <p className="notice" role="status">Échéance dépassée : en attente de confirmation du serveur.
      <Button onClick={colony.refresh}>Actualiser la colonie</Button></p>}
    {!projection.queue.length ? <p className="d-empty">Aucune construction en cours. Les ordres continuent sans navigateur ouvert.</p>
      : <ol className="d-job-list">{projection.queue.map(order => {
        const label = infrastructureLabel(order.infrastructure_type);
        const describeAmounts = (value: Amounts) => resourceKeys.filter(key => BigInt(value[key]) > 0n).map(key => `${exactUnits(value[key])} ${resourceLabels[key]}`).join(', ') || 'aucun';
        const pending = colony.pending === JSON.stringify({ kind: 'cancel', order_id: order.id });
        const p = progress(order, server);
        return <li key={order.id} className="d-job">
          <img className="d-job-img" src={buildingImage(order.infrastructure_type)} alt="" width="96" height="72" />
          <div className="d-job-info"><b>{label}</b><small>{where(order.sector_index)} · {level(order, projection)}</small>
            <small className="d-job-state">{order.status === 'active' ? 'En cours' : 'En file : démarre après l’ordre précédent, durée fixée au démarrage'}</small></div>
          {canCancel && confirm !== order.id && <div className="d-job-act">
            <button type="button" className="d-btn d-btn-sq" disabled aria-label={`Accélérer ${label} : implémentation backend nécessaire`}
              title="Accélération : implémentation backend nécessaire"><Ico name="act-accelerer" /></button>
            <button type="button" className="d-btn d-btn-sq d-danger" disabled={!!colony.pending || !order.cancel.available}
              aria-describedby={order.cancel.reason ? `cancel-${order.id}` : undefined} onClick={() => setConfirm(order.id)}
              aria-label={pending ? 'Annulation…' : `Annuler ${label}`}><Ico name="act-annuler" /></button></div>}
          <div className="d-job-prog">{p ? <><Bar value={p.percent} label={`Avancement estimé de ${label}`} />
            <span className="d-job-meta"><b className="d-pct">{p.percent} %</b><time dateTime={order.due_at!}>{p.left > 0 ? `${duration(String(p.left * 1_000_000))} · fin ${time(order.due_at!)}` : 'Confirmation serveur…'}</time></span></>
            : <span className="queue-waiting">En attente du démarrage</span>}</div>
          {order.cancel.reason && <span id={`cancel-${order.id}`} className="reason">{reasonLabel(order.cancel.reason)}</span>}
          {canCancel && confirm === order.id && <div className="confirm" role="group" aria-label={`Confirmer l’annulation de ${label}`}>
            <p>Remboursement théorique : {describeAmounts(order.cancel.refund)}.</p>
            <p>Vous récupérerez : {describeAmounts(order.cancel.recoverable)}.</p>
            <p>Perte définitive faute de stockage : {describeAmounts(order.cancel.lost)}.</p>
            {!!order.cancel.also_cancels.length && <>
              <p>Seront aussi annulées les améliorations dépendantes suivantes (incluses dans ces montants) :</p>
              <ul>{order.cancel.also_cancels.map(id => {
                const dependent = projection.queue.find(row => row.id === id)!;
                return <li key={id}>{infrastructureLabel(dependent.infrastructure_type)} · Secteur {dependent.sector_index} · Niveau {dependent.target_level}</li>;
              })}</ul>
            </>}
            <p className="muted">Estimation à la date serveur affichée ; montants recalculés au moment de l’annulation.</p>
            <Button className="button--danger" disabled={!!colony.pending || !order.cancel.available}
              onClick={() => { void colony.command({ kind: 'cancel', order_id: order.id }); setConfirm(null); }}>Confirmer l’annulation</Button>
            <Button onClick={() => setConfirm(null)}>Garder</Button>
          </div>}
        </li>;
      })}</ol>}
  </section>;
}

function OptionCard({ colony, option, free, canBuild, stocks }: { colony: Colony; option: Option; free: number[]; canBuild: boolean; stocks: Record<string, number> }) {
  const [sector, setSector] = useState(option.sector_index);
  const label = infrastructureLabel(option.infrastructure_type);
  const chosen = option.action === 'build' ? (sector && free.includes(sector) ? sector : option.sector_index) : option.sector_index;
  const command = { kind: 'construct' as const, infrastructure_type: option.infrastructure_type, sector_index: chosen ?? 0, target_level: option.target_level };
  const pending = colony.pending === JSON.stringify(command);
  const describe = `option-${option.action}-${option.infrastructure_type}-${option.sector_index ?? 'none'}`;
  const locked = !option.available && option.reason === 'prerequisites_unmet';
  return <li className={`d-bcard option-card${option.available ? '' : ' is-locked'}${locked ? ' d-locked' : ''}`}>
    <img src={buildingImage(option.infrastructure_type)} alt="" width="420" height="420" />
    <div className="d-bcard-body">
      <h3>{option.action === 'build' ? label : `${label} · secteur ${option.sector_index}`}</h3>
      <p>{option.action === 'build' ? roles[option.infrastructure_type] ?? 'Nouvelle infrastructure de surface.' : `Amélioration niveau ${option.target_level - 1} → ${option.target_level}`}</p>
      <Effect option={option} />
      <Costs value={option.cost} stocks={stocks} minutes={duration(option.estimated_duration_us ?? option.base_duration_us)} />
      {option.action === 'build' && option.available && free.length > 1 && <label className="sector-select">Secteur
        <select value={chosen ?? ''} onChange={event => setSector(Number(event.target.value))}>
          {free.map(index => <option key={index} value={index}>Secteur {index}</option>)}
        </select></label>}
      {canBuild && <button type="button" className={`d-btn d-btn-block${option.available ? ' d-primary' : ''}`}
        disabled={!option.available || !!colony.pending || !chosen} aria-describedby={option.reason ? describe : undefined}
        onClick={() => { void colony.command(command); }}
        aria-label={pending ? 'Envoi…' : option.action === 'build' ? `Construire ${label}` : `Améliorer ${label} niveau ${option.target_level}`}>
        <Ico name={locked ? 'act-verrouille' : option.action === 'build' ? 'act-construire' : 'act-ameliorer'} />
        <span aria-hidden="true">{pending ? 'Envoi…' : locked ? 'Verrouillé' : option.action === 'build' ? 'Construire' : 'Améliorer'}</span></button>}
      {option.reason && <p id={describe} className="reason">{locked && option.requires?.length
        ? `Débloqué par : ${option.requires.map(r => `${infrastructureLabel(r.infrastructure_type)} niveau ${r.level}`).join(', ')}.`
        : reasonLabel(option.reason)}</p>}
    </div>
  </li>;
}

/** Recette 09/11/2026: the player names the colony (the planet name until then). */
function ColonyTitle({ colony, name, canRename }: { colony: Colony; name: string; canRename: boolean }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(name);
  const [hint, setHint] = useState('');
  if (!editing) return <div className="d-col-title"><h1 tabIndex={-1}>{name}</h1>
    {canRename && <button type="button" className="d-btn d-btn-ghost d-btn-sm" onClick={() => { setValue(name); setHint(''); setEditing(true); }}>Renommer</button>}</div>;
  const save = async () => {
    const clean = value.split(/\s+/).filter(Boolean).join(' ');
    if (clean.length < 2 || clean.length > 40) { setHint('Le nom doit compter 2 à 40 caractères.'); return; }
    await colony.command({ kind: 'rename', name: clean });
    setEditing(false);
  };
  return <form className="d-col-title d-col-rename" onSubmit={event => { event.preventDefault(); void save(); }}>
    <label className="visually-hidden" htmlFor="colony-name">Nom de la colonie</label>
    <input id="colony-name" value={value} maxLength={40} autoFocus onChange={event => setValue(event.target.value)} />
    <button type="submit" className="d-btn d-primary d-btn-sm" disabled={!!colony.pending}>Enregistrer</button>
    <button type="button" className="d-btn d-btn-ghost d-btn-sm" onClick={() => setEditing(false)}>Annuler</button>
    {hint && <p role="alert" className="reason">{hint}</p>}
  </form>;
}

/** Recette 09/11/2026: the queue first, then the colony's buildings each with its next level
 * (cost, duration, action) in the same row, then new constructions; unavailable ones greyed. */
function BuiltRow({ colony, row, upgrade, canBuild, stocks }: { colony: Colony; row: Projection['infrastructures'][number]; upgrade?: Option; canBuild: boolean; stocks: Record<string, number> }) {
  const label = infrastructureLabel(row.infrastructure_type);
  const command = upgrade && { kind: 'construct' as const, infrastructure_type: upgrade.infrastructure_type, sector_index: upgrade.sector_index ?? 0, target_level: upgrade.target_level };
  const pending = !!command && colony.pending === JSON.stringify(command);
  const describe = `upgrade-${row.sector_index}`;
  return <li className={`d-built${upgrade && !upgrade.available ? ' is-waiting' : ''}`}>
    <img src={buildingImage(row.infrastructure_type)} alt="" width="96" height="72" />
    <div className="d-built-info">
      <span className="d-inst-top"><b>{label}</b><em className="d-lvl-badge">Niveau {row.level}</em></span>
      <small>Secteur {row.sector_index} · Surface</small><Effect option={row} />
    </div>
    {upgrade ? <div className="d-built-next">
      <span className="d-built-next-title">Niveau {upgrade.target_level} : <Effect option={upgrade} /></span>
      <Costs value={upgrade.cost} stocks={stocks} minutes={duration(upgrade.estimated_duration_us ?? upgrade.base_duration_us)} />
      {upgrade.reason && <p id={describe} className="reason">{reasonLabel(upgrade.reason)}</p>}
    </div> : <div className="d-built-next"><span className="muted">Aucune amélioration proposée pour l’instant.</span></div>}
    {upgrade && canBuild && command && <button type="button" className={`d-btn${upgrade.available ? ' d-primary' : ''}`}
      disabled={!upgrade.available || !!colony.pending} aria-describedby={upgrade.reason ? describe : undefined}
      onClick={() => { void colony.command(command); }} aria-label={pending ? 'Envoi…' : `Améliorer ${label} niveau ${upgrade.target_level}`}>
      <Ico name="act-ameliorer" /><span aria-hidden="true">{pending ? 'Envoi…' : 'Améliorer'}</span></button>}
  </li>;
}

function Infrastructures({ colony, data, server, stocks }: { colony: Colony; data: Projection; server: number; stocks: Record<string, number> }) {
  // DEF-01: defense modules live in the Défense tab, the Défense center stays here (key building).
  const module = (kind: string) => !!data.defense && kind in data.defense.catalogue;
  const builds = data.options.filter(option => option.action === 'build' && !module(option.infrastructure_type));
  const upgrades = data.options.filter(option => option.action === 'upgrade');
  const surface = data.infrastructures.filter(row => !module(row.infrastructure_type));
  const canBuild = data.permissions.includes('colony.construct');
  // Available constructions first; unavailable ones stay visible, greyed, after them.
  // A unique building already built (or queued) lives in the list above, not here (COL-11).
  const ordered = builds.filter(option => option.reason !== 'unique_limit')
    .sort((a, b) => Number(b.available) - Number(a.available));
  // Closest locked building: the fewest missing levels among its prerequisites (COL-11 guidance).
  const levels = new Map<string, number>();
  for (const row of data.infrastructures) levels.set(row.infrastructure_type, Math.max(levels.get(row.infrastructure_type) ?? 0, row.level));
  const missing = (option: typeof builds[number]) => (option.requires ?? [])
    .filter(r => (levels.get(r.infrastructure_type) ?? 0) < r.level);
  const next = builds.filter(option => option.reason === 'prerequisites_unmet' && missing(option).length)
    .map(option => ({ option, gap: missing(option).reduce((n, r) => n + r.level - (levels.get(r.infrastructure_type) ?? 0), 0) }))
    .sort((a, b) => a.gap - b.gap)[0];
  return <div className="d-tabpanel">
    <Queue colony={colony} projection={data} server={server} />
    {next && <p className="d-next-unlock" role="note"><Ico name="act-verrouille" /><span><strong>Prochain déblocage : {infrastructureLabel(next.option.infrastructure_type)}</strong>{' '}
      — il faut {missing(next.option).map(r => `${infrastructureLabel(r.infrastructure_type)} niveau ${r.level} (actuel ${levels.get(r.infrastructure_type) ?? 0})`).join(', ')}.</span></p>}
    <section className="d-card d-panel" aria-labelledby="built-title">
      <PanelHead id="built-title" icon="icons/colonie/colonie-secteurs.svg" title="Bâtiments de la colonie"><span className="d-queue-count">{data.sectors.built} / {data.sectors.capacity} secteurs</span></PanelHead>
      {surface.length ? <ul className="d-built-list">{surface.map(row => <BuiltRow key={row.sector_index} colony={colony} row={row}
        upgrade={upgrades.find(option => option.sector_index === row.sector_index)} canBuild={canBuild} stocks={stocks} />)}</ul>
        : <p className="muted">Aucun bâtiment pour l’instant : commencez par une construction ci-dessous.</p>}
    </section>
    <section className="d-card d-panel" aria-labelledby="available-title">
      <PanelHead id="available-title" icon="icons/actions/action-construire.svg" title="Nouvelles constructions"><span className="d-queue-count">{data.sectors.free} secteur{data.sectors.free > 1 ? 's' : ''} libre{data.sectors.free > 1 ? 's' : ''}</span></PanelHead>
      <ul className="d-build-grid option-grid">{ordered.map(option => <OptionCard key={option.infrastructure_type} colony={colony} option={option}
        free={data.sectors.free_indices} canBuild={canBuild} stocks={stocks} />)}</ul>
    </section>
  </div>;
}

function Overview({ data, server, link }: { data: Projection; server: number; link: (v: string) => string }) {
  const maxRate = Math.max(1, ...data.resources.map(r => Number(r.rate_per_hour)));
  const used = data.sectors.built + data.sectors.reserved;
  return <div className="d-tabpanel d-grid-2">
    <section className="d-card d-panel" aria-labelledby="summary-title">
      <PanelHead id="summary-title" icon="icons/colonie/panel-resume-colonie.svg" title="Résumé de la colonie" />
      <div className="d-summary">
        <img className="d-summary-img" src={asset('img/batiments/centre-de-commandement.webp')} alt={`Centre de commandement de ${data.colony.name}`} width="420" height="420" />
        <dl className="d-kv">
          <div><dt><Pic src="icons/colonie/colonie-secteurs.svg" size={24} />Secteurs (utilisés / total)</dt><dd>{used} / {data.sectors.capacity}</dd></div>
          <div><dt><Pic src="icons/colonie/stat-emplacements.svg" size={24} />Emplacements orbitaux</dt><dd>{data.colony.planet.orbital_capacity}</dd></div>
          <div><dt><Pic src="icons/colonie/panel-activites.svg" size={24} />File de construction</dt><dd>{data.queue.length} / {data.queue_limit}</dd></div>
          {[['stat-niveau-colonie', 'Niveau de la colonie'], ['stat-population', 'Population estimée'], ['stat-stabilite', 'Stabilité'], ['stat-habitabilite', 'Habitabilité']].map(([icon, label]) =>
            <div key={icon}><dt><Pic src={`icons/colonie/${icon}.svg`} size={24} />{label}</dt><dd className="d-na" title="Implémentation backend nécessaire">N/D</dd></div>)}
        </dl>
      </div>
      <p className="d-note">N/D : niveau, population, stabilité et habitabilité — implémentation backend nécessaire.</p>
    </section>
    <section className="d-card d-panel" aria-labelledby="activity-title">
      <PanelHead id="activity-title" icon="icons/colonie/panel-activites.svg" title="Activités en cours" more={{ href: link('colony/infrastructure'), label: 'Voir la file complète' }} />
      <ul className="d-activity-list">{data.queue.slice(0, 3).map(order => {
        const p = progress(order, server);
        return <li className="d-act" key={order.id}><img src={buildingImage(order.infrastructure_type)} alt="" width="84" height="56" />
          <div><span className="d-act-top"><b>{order.target_level === 1 ? 'Construction' : 'Amélioration'} : {infrastructureLabel(order.infrastructure_type)}</b><b className="d-pct">{p ? `${p.percent} %` : 'En file'}</b></span>
            <small>{where(order.sector_index)} · {level(order, data)}</small><Bar value={p?.percent ?? 0} /></div></li>;
      })}
        {!data.queue.length && <li className="d-empty">Aucune activité en cours.</li>}</ul>
    </section>
    <section className="d-card d-panel" aria-labelledby="production-title">
      <PanelHead id="production-title" icon="icons/sidebar/nav-empire.svg" title="Production par heure" />
      <ul className="d-prod-list">{data.resources.map(r => <li key={r.resource}><img src={asset(resourceIcon[r.resource])} alt="" width="40" height="40" />
        <div><span className="d-pl-top"><b>{resourceLabels[r.resource]}</b><em>+{rate(r.rate_per_hour)} /h</em></span>
          <Bar value={Number(r.rate_per_hour) / maxRate * 100} tone={r.resource === 'data' ? 'amber' : undefined} /></div></li>)}</ul>
    </section>
    <section className="d-card d-panel" aria-labelledby="infra-title">
      <PanelHead id="infra-title" icon="icons/colonie/panel-points-interet.svg" title="Infrastructures en service" more={{ href: link('colony/infrastructure'), label: 'Gérer' }} />
      <div className="d-poi">
        <img src={buildingImage(data.infrastructures[0]?.infrastructure_type ?? 'data_node')} alt="" width="420" height="420" />
        <div><h3>Rôle de {data.colony.name}</h3>
          <ul className="d-checks summary-table" aria-label="Résumé des infrastructures">{data.infrastructures.map(row =>
            <li key={row.sector_index}>{infrastructureLabel(row.infrastructure_type)} · niveau {row.level} <span className="d-muted">(secteur {row.sector_index})</span></li>)}
            {!data.infrastructures.length && <li>Aucune infrastructure construite.</li>}</ul></div>
      </div>
    </section>
  </div>;
}

function Orbit({ data, link }: { data: Projection; link: (v: string) => string }) {
  const d = data.defense;
  const slot = (i: number) => d?.modules.find(m => m.sector_index === d.orbital.base + i + 1);
  const used = d ? data.colony.planet.orbital_capacity - d.orbital.free_indices.length : 0;
  return <div className="d-tabpanel d-grid-orbit">
    <section className="d-card d-panel d-installs" aria-labelledby="orbit-title">
      <PanelHead id="orbit-title" icon="icons/colonie/stat-emplacements.svg" title="Installations orbitales"><span className="d-more d-static">{used} / {data.colony.planet.orbital_capacity} emplacements utilisés</span></PanelHead>
      <ul className="d-install-list">{Array.from({ length: data.colony.planet.orbital_capacity }, (_, i) => {
        const m = slot(i);
        return m ? <li key={i} className="d-install">
          <img src={buildingImage(m.infrastructure_type)} alt="" width="72" height="72" />
          <div className="d-inst-info"><b>{infrastructureLabel(m.infrastructure_type)}</b><small>Emplacement orbital {i + 1} · {m.condition === 'operational' ? 'Opérationnel' : m.condition === 'damaged' ? 'Endommagé' : 'Désactivé (Flux)'}</small></div>
        </li> : <li key={i} className="d-install d-free">
          <span className="d-free-ico"><Pic src="icons/colonie/emplacement-libre.svg" size={52} /></span>
          <div className="d-inst-info"><b>Emplacement orbital {i + 1}</b><small>{d ? <>Libre : une plateforme orbitale peut s’y installer (<a className="text-link" href={link('colony/defense')}>onglet Défense</a>).</>
            : 'Constructions orbitales : nouvelles parties (ruleset v0.13).'}</small></div>
        </li>;
      })}</ul>
    </section>
    <div className="d-stack">
      <section className="d-card d-panel" aria-labelledby="yards-title"><PanelHead id="yards-title" icon="icons/colonie/panel-chantiers-orbitaux.svg" title="Chantiers orbitaux" />
        <Pending what="File de construction orbitale." /></section>
      <section className="d-card d-panel" aria-labelledby="traffic-title"><PanelHead id="traffic-title" icon="icons/colonie/panel-trafic-orbital.svg" title="Trafic orbital" />
        <Pending what="Flottes amarrées, convois entrants et routes de fret de la colonie." /></section>
    </div>
  </div>;
}

export function ColonyScreen({ colony, view, link, onNavigate }: { colony: Colony; view: string; link: (v: string) => string; onNavigate?: () => void }) {
  const now = useNow(1000);
  if (colony.phase === 'loading' || colony.phase === 'idle') return <p className="panel" aria-live="polite">Chargement de votre colonie…</p>;
  if (colony.phase === 'empty') return <section className="panel"><h1 tabIndex={-1}>Aucune colonie accessible</h1>
    <p>Votre participation ne donne accès à aucune colonie dans cet univers.</p></section>;
  if (colony.phase === 'error' || !colony.projection) return <section className="panel" role="alert"><h1 tabIndex={-1}>Colonie indisponible</h1>
    <p>{errorMessage(colony.error ?? 'unavailable')}</p><Button onClick={colony.refresh}>Réessayer</Button></section>;
  const data = colony.projection;
  const offset = Date.parse(data.server_time) - colony.receivedAt;
  const server = now + offset, elapsed = now - colony.receivedAt;
  const used = data.sectors.built + data.sectors.reserved;
  const stocks = Object.fromEntries(data.resources.map(r => [r.resource, estimate(r, elapsed)]));
  const current = colonyViews.find(item => item.id === view)?.id ?? 'overview';
  const orbitUsed = data.defense ? data.colony.planet.orbital_capacity - data.defense.orbital.free_indices.length : 0;
  return <div className="d-colony d-scope colony-screen" aria-label={`Colonie ${data.colony.name}`}>
    <section className="d-col-hero">
      <div className="d-col-hero-text">
        <nav className="d-crumbs" aria-label="Fil d’Ariane"><span>Colonies</span><span aria-hidden="true">›</span><span aria-current="page">{data.colony.name}</span></nav>
        <ColonyTitle colony={colony} name={data.colony.name} canRename={data.permissions.includes('colony.construct')} />
        <p className="d-col-level">Colonie de l’Empire {data.colony.empire.name}</p>
        <p className="d-col-meta"><span>Planète {data.colony.planet.name}</span><span>Système {data.colony.system.name}</span><span>{/^univers\b/i.test(data.colony.universe.name) ? data.colony.universe.name : `Univers ${data.colony.universe.name}`}</span></p>
        <p className="d-col-desc">Type de monde, niveau et description de la colonie : implémentation backend nécessaire.</p>
      </div>
      <a className="d-btn d-btn-ghost d-hero-cta" href={link('galaxy')} onClick={onNavigate}>Voir sur la galaxie <span aria-hidden="true">→</span></a>
    </section>

    <section className="d-col-stats" aria-label="Capacités de la colonie">
      <article className="d-card d-cap-card"><Pic src="icons/colonie/colonie-secteurs.svg" size={64} />
        <div className="d-cap-body"><div className="d-cap-top"><strong>{used} <i>/</i> {data.sectors.capacity}</strong>
          <span className={`d-cap-free${data.sectors.free ? '' : ' d-none'}`}>{data.sectors.free} libre{data.sectors.free > 1 ? 's' : ''}</span></div>
          <span className="d-cap-label">Secteurs utilisés</span>
          <span role="meter" aria-label="Secteurs utilisés" aria-valuemin={0} aria-valuemax={data.sectors.capacity} aria-valuenow={used}><Bar value={used / data.sectors.capacity * 100} /></span></div></article>
      <article className="d-card d-cap-card"><Pic src="icons/colonie/colonie-emplacements-orbitaux.svg" size={64} />
        <div className="d-cap-body"><div className="d-cap-top"><strong>{orbitUsed} <i>/</i> {data.colony.planet.orbital_capacity}</strong>
          <span className="d-cap-free">{data.defense ? `${data.defense.orbital.free_indices.length} libre${data.defense.orbital.free_indices.length > 1 ? 's' : ''}` : 'à venir'}</span></div>
          <span className="d-cap-label">Emplacements orbitaux</span><Bar value={data.colony.planet.orbital_capacity ? orbitUsed / data.colony.planet.orbital_capacity * 100 : 0} /></div></article>
    </section>

    {data.incoming?.some(a => a.state === 'pending') && <section className="d-card d-panel panel combat-alert" role="alert" aria-labelledby="incoming-title">
      <h2 id="incoming-title">Force hostile en approche</h2>
      <ul>{data.incoming.filter(a => a.state === 'pending').map(a => <li key={a.id}>Bataille prévue : {time(a.battle_at)}</li>)}</ul>
      <p className="panel-meta">{data.defense
        ? 'Ni l’attaquant ni sa force ne sont connus avant la bataille. Les unités militaires stationnées et les modules de défense opérationnels combattront ; un module perdu est endommagé jusqu’à sa réparation, aucune ressource, aucun autre bâtiment ni aucune recherche ne peut être perdu.'
        : 'Ni l’attaquant ni sa force ne sont connus avant la bataille. Seules les unités militaires stationnées dans ce système combattront ; aucune ressource, aucun bâtiment ni aucune recherche ne peut être perdu.'}</p>
    </section>}
    <div className="feedback-zone" aria-live="polite">
      {colony.feedback && <div className={`feedback feedback--${colony.feedback.tone}`} role={colony.feedback.tone === 'success' ? 'status' : 'alert'}>
        <p>{colony.feedback.tone === 'success' ? colony.feedback.text : colony.feedback.tone === 'unknown'
          ? `Résultat non confirmé. ${errorMessage(colony.feedback.code ?? 'unavailable')}` : errorMessage(colony.feedback.code ?? 'unavailable')}</p>
        <Button onClick={colony.dismiss}>Fermer</Button></div>}
      {colony.error && <p className="feedback feedback--error" role="alert">Actualisation impossible : {errorMessage(colony.error)}</p>}
    </div>

    <div className="d-col-layout">
      <nav className="d-col-tabs" aria-label="Sections de la colonie">
        {colonyViews.map(item => <a key={item.id} href={link(`colony/${item.id}`)} onClick={onNavigate} aria-current={item.id === current ? 'page' : undefined}
          className={item.id === current ? 'd-tab is-current' : 'd-tab'}><Ico name={item.icon} /><span>{item.label}</span></a>)}
      </nav>
      <div className="d-col-main">
        {current === 'infrastructure' ? <Infrastructures colony={colony} data={data} server={server} stocks={stocks} />
          : current === 'orbit' ? <Orbit data={data} link={link} />
          : current === 'defense' ? <DefenseTab colony={colony} data={data} />
          : <Overview data={data} server={server} link={link} />}
      </div>
      <aside className="d-col-side" aria-label="Informations complémentaires">
        {current !== 'orbit' && <Alerts projection={data} />}
        {current === 'overview' && <section className="d-card d-panel" aria-labelledby="objectives-title">
          <PanelHead id="objectives-title" icon="icons/colonie/panel-objectifs.svg" title="Objectifs prioritaires" />
          <Pending what="Objectifs de colonie suivis par le serveur." /></section>}
        {current === 'orbit' && <>
          <section className="d-card d-panel" aria-labelledby="window-title"><PanelHead id="window-title" icon="icons/colonie/panel-fenetre-orbitale.svg" title="Fenêtre orbitale" />
            <div className="d-window"><img src={asset('img/colonie/fenetre-orbitale.webp')} alt="" width="420" height="420" /><Pending what="Fenêtres de lancement et leurs effets." compact /></div></section>
          <section className="d-card d-panel" aria-labelledby="routes-title"><PanelHead id="routes-title" icon="icons/colonie/panel-routes-commerciales.svg" title="Routes commerciales" />
            <Pending what="Routes commerciales, volume et revenus." compact /></section>
        </>}
        <DefenseStatus projection={data} banner={current === 'orbit' ? undefined : link} />
        <div className="d-sync"><span className="muted">État serveur au {time(data.server_time)} · ruleset {data.ruleset_version}</span>
          <Button onClick={colony.refresh}>Actualiser la colonie</Button></div>
      </aside>
    </div>
  </div>;
}
