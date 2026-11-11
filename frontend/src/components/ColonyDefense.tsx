import { useState } from 'react';
import type { Defense as Network, Option, Projection } from '../colony/api';
import { costParts, duration, infrastructureLabel, placeLabel, rate, reasonLabel } from '../colony/format';
import type { useColony } from '../hooks/useColony';
import { Bar, Ico, PanelHead, Pending, Pic } from '../shell/visual';
import { asset, buildingImage, resourceIcon } from '../shell/assets';

type Colony = ReturnType<typeof useColony>;
const conditionNames = { operational: 'Opérationnel', disabled: 'Désactivé (Flux)', damaged: 'Endommagé' } as const;
const familyNames = { point_defense: 'Défense ponctuelle', anti_ship: 'Anti-vaisseaux' } as const;
const shipNames: Record<string, string> = { interceptor: 'intercepteurs', frigate: 'frégates', cruiser: 'croiseurs' };
const roles: Record<string, string> = {
  point_defense: 'Batteries rapides qui déchirent les petites coques.',
  anti_ship_battery: 'Canons lourds pensés pour percer les croiseurs.',
  orbital_platform: 'Plateforme blindée en orbite, redoutable contre les frégates.',
};

/** Matchups read from the server catalogue: × 1,5 and above is strong, below × 1 is weak. */
function matchups(row: Network['catalogue'][string]) {
  const against = Object.entries(row.matchups_bps);
  return {
    strong: against.filter(([, bps]) => bps > 10000).map(([c]) => shipNames[c] ?? c),
    weak: against.filter(([, bps]) => bps < 10000).map(([c]) => shipNames[c] ?? c),
  };
}

function Costs({ option }: { option: Option }) {
  return <div className="d-costs" aria-label="Coût">
    {costParts(option.cost).map(part => <span key={part.key} className="d-cost">
      <img src={asset(resourceIcon[part.key])} alt="" width="17" height="17" /><span className="sr-only">{part.label} </span>{part.value}</span>)}
    <span className="d-cost"><img src={asset('icons/ui/ui-chronometre.svg')} alt="" width="17" height="17" /><span className="sr-only">Durée </span>
      {duration(option.estimated_duration_us ?? option.base_duration_us)}</span>
  </div>;
}

function ModuleOption({ colony, data, option, canBuild }: { colony: Colony; data: Projection; option: Option; canBuild: boolean }) {
  const d = data.defense!;
  const spec = d.catalogue[option.infrastructure_type];
  const orbital = spec.placement === 'orbital';
  const free = orbital ? d.orbital.free_indices : data.sectors.free_indices;
  const [slot, setSlot] = useState(option.sector_index);
  const chosen = slot && free.includes(slot) ? slot : option.sector_index;
  const command = { kind: 'construct' as const, infrastructure_type: option.infrastructure_type, sector_index: chosen ?? 0, target_level: 1 };
  const label = infrastructureLabel(option.infrastructure_type);
  const { strong, weak } = matchups(spec);
  const describe = `def-option-${option.infrastructure_type}`;
  return <li className={`d-bcard d-def-card${option.available ? '' : ' is-locked'}`}>
    <img src={buildingImage(option.infrastructure_type)} alt="" width="420" height="420" />
    <div className="d-bcard-body">
      <h3>{label}</h3>
      <p>{roles[option.infrastructure_type] ?? familyNames[spec.family]}</p>
      <ul className="d-def-tags" aria-label={`Caractéristiques de ${label}`}>
        <li>{familyNames[spec.family]}</li><li>{orbital ? 'Emplacement orbital' : 'Secteur de surface'}</li>
        <li>Coque {spec.hull} · attaque {spec.attack}</li><li>Entretien {spec.upkeep_flux} Flux/h</li>
      </ul>
      <p className="d-note">{strong.length ? `Efficace contre les ${strong.join(', ')}` : ''}{strong.length && weak.length ? ' · ' : ''}{weak.length ? `faible contre les ${weak.join(', ')}` : ''}.</p>
      <Costs option={option} />
      {option.available && free.length > 1 && <label className="sector-select">{orbital ? 'Emplacement' : 'Secteur'}
        <select value={chosen ?? ''} onChange={event => setSlot(Number(event.target.value))}>
          {free.map(index => <option key={index} value={index}>{placeLabel(index, d.orbital.base)}</option>)}
        </select></label>}
      {canBuild && <button type="button" className={`d-btn d-btn-block${option.available ? ' d-primary' : ''}`}
        disabled={!option.available || !!colony.pending || !chosen} aria-describedby={option.reason ? describe : undefined}
        onClick={() => { void colony.command(command); }}>
        <Ico name={option.available ? 'act-construire' : 'act-verrouille'} /><span>Construire {label}</span></button>}
      {option.reason && <p id={describe} className="reason">{option.reason === 'prerequisites_unmet'
        ? `Débloqué par : ${(option.requires ?? []).map(r => `${infrastructureLabel(r.infrastructure_type)} niveau ${r.level}`).join(', ')}.`
        : reasonLabel(option.reason)}</p>}
    </div>
  </li>;
}

/** Onglet Défense (DEF-01, ruleset v0.13): the network as the server reports it, its modules and
 * their state, building and repairing them through the colony queue. Nothing is invented: shields,
 * alert states, sensors and support modules are announced, not simulated. */
export function DefenseTab({ colony, data }: { colony: Colony; data: Projection }) {
  const d = data.defense;
  const pending = (data.incoming ?? []).filter(a => a.state === 'pending');
  if (!d) return <div className="d-tabpanel">
    <section className="d-card d-panel" aria-labelledby="network-title"><PanelHead id="network-title" icon="icons/defense/reseau-defensif.svg" title="Réseau défensif" />
      <Pending what="La défense planétaire existe dans les nouvelles parties (ruleset v0.13). Cette partie garde ses règles d’origine : seules les unités militaires stationnées défendent la colonie." /></section>
  </div>;
  const canBuild = data.permissions.includes('colony.construct');
  const builds = data.options.filter(o => o.action === 'build' && o.infrastructure_type in d.catalogue);
  const repairs = data.options.filter(o => o.action === 'repair');
  const center = data.options.find(o => o.infrastructure_type === d.center);
  const counts = { operational: 0, disabled: 0, damaged: 0 };
  for (const m of d.modules) counts[m.condition] += 1;
  return <div className="d-tabpanel">
    <section className="d-card d-panel" aria-labelledby="network-title">
      <PanelHead id="network-title" icon="icons/defense/reseau-defensif.svg" title="Réseau défensif">
        <span className="d-queue-count">{d.used} / {d.capacity} modules</span></PanelHead>
      <div className="d-def-net">
        <img src={buildingImage(d.center)} alt="" width="160" height="160" />
        <div>
          <h3>{infrastructureLabel(d.center)} {d.center_level ? `· niveau ${d.center_level}` : '· non construit'}</h3>
          <p className="d-note">{d.center_level
            ? `Chaque niveau permet ${d.capacity_per_level} modules. Un module de surface occupe un secteur, un module orbital un emplacement orbital.`
            : center?.reason === 'prerequisites_unmet'
              ? `Construisez d’abord ${(center.requires ?? []).map(r => `${infrastructureLabel(r.infrastructure_type)} niveau ${r.level}`).join(', ')}, puis le Centre de défense dans l’onglet Infrastructures.`
              : 'Construisez le Centre de défense dans l’onglet Infrastructures pour ouvrir le réseau.'}</p>
          <span role="meter" aria-label="Modules du réseau" aria-valuemin={0} aria-valuemax={Math.max(1, d.capacity)} aria-valuenow={d.used}>
            <Bar value={d.capacity ? d.used / d.capacity * 100 : 0} /></span>
          <dl className="d-def-kv">
            <div><dt>Opérationnels</dt><dd>{counts.operational}</dd></div>
            <div><dt>Désactivés</dt><dd>{counts.disabled}</dd></div>
            <div><dt>Endommagés</dt><dd>{counts.damaged}</dd></div>
            <div><dt>Entretien</dt><dd>{rate(d.upkeep_flux_per_hour)} Flux/h</dd></div>
          </dl>
        </div>
      </div>
      {!d.modules.length ? <p className="d-empty">Aucun module construit.</p>
        : <ul className="d-built-list">{d.modules.map(m => {
          const repair = repairs.find(o => o.sector_index === m.sector_index);
          const label = infrastructureLabel(m.infrastructure_type);
          const command = repair && { kind: 'construct' as const, infrastructure_type: repair.infrastructure_type, sector_index: m.sector_index, target_level: repair.target_level };
          const queued = data.queue.some(o => o.sector_index === m.sector_index);
          return <li key={m.sector_index} className={`d-built d-def-module is-${m.condition}`}>
            <img src={buildingImage(m.infrastructure_type)} alt="" width="96" height="72" />
            <div className="d-built-info"><span className="d-inst-top"><b>{label}</b><em className={`d-def-state is-${m.condition}`}>{conditionNames[m.condition]}</em></span>
              <small>{placeLabel(m.sector_index, d.orbital.base)} · {familyNames[d.catalogue[m.infrastructure_type].family]}</small>
              <small>{m.condition === 'damaged' ? 'Ne combat plus et ne coûte plus d’entretien jusqu’à sa réparation.'
                : m.condition === 'disabled' ? 'Désactivé faute de Flux : il se réactive seul quand la production le permet.'
                : `Combat avec la garnison · ${d.catalogue[m.infrastructure_type].upkeep_flux} Flux/h`}</small></div>
            {m.condition === 'damaged' && <div className="d-built-next">{queued ? <span className="muted">Réparation en file.</span> : repair && <>
              <span className="d-built-next-title">Réparation ({d.repair_cost_bps / 100} % du coût, {d.repair_duration_bps / 100} % du temps)</span>
              <Costs option={repair} />{repair.reason && <p className="reason">{reasonLabel(repair.reason)}</p>}</>}</div>}
            {m.condition === 'damaged' && canBuild && command && !queued && <button type="button" className={`d-btn${repair!.available ? ' d-primary' : ''}`}
              disabled={!repair!.available || !!colony.pending} onClick={() => { void colony.command(command); }}>
              <Ico name="act-ameliorer" /><span>Réparer {label}</span></button>}
          </li>;
        })}</ul>}
    </section>
    <section className="d-card d-panel" aria-labelledby="defbuild-title">
      <PanelHead id="defbuild-title" icon="icons/defense/production-defensive.svg" title="Construire un module">
        <span className="d-queue-count">{data.sectors.free} secteur{data.sectors.free > 1 ? 's' : ''} · {d.orbital.free_indices.length} emplacement{d.orbital.free_indices.length > 1 ? 's' : ''} orbitaux libres</span></PanelHead>
      <ul className="d-build-grid option-grid">{builds.map(option => <ModuleOption key={option.infrastructure_type} colony={colony} data={data} option={option} canBuild={canBuild} />)}</ul>
    </section>
    <div className="d-grid-def">
      <section className="d-card d-panel" aria-labelledby="defnext-title"><PanelHead id="defnext-title" icon="icons/defense/def-boucliers.svg" title="Bientôt" />
        <Pending what="Boucliers, états d’alerte, capteurs et réparation automatique arrivent dans les lots suivants (DEF-02/03)." compact /></section>
      <section className="d-card d-panel" aria-labelledby="ops-title"><PanelHead id="ops-title" icon="icons/defense/operations-tactiques.svg" title="Veille du secteur" />
        <p className="d-watch"><i className="d-pulse" aria-hidden="true" /><b>Forces annoncées</b><span>{pending.length ? `${pending.length} force${pending.length > 1 ? 's' : ''} hostile${pending.length > 1 ? 's' : ''} annoncée${pending.length > 1 ? 's' : ''}` : 'Aucune force hostile annoncée'}</span></p>
        <p className="d-note">Les modules opérationnels combattent avec la garnison ; un module perdu devient endommagé, jamais détruit.</p>
      </section>
    </div>
  </div>;
}

/** Side panel « Statut de défense »: the network figures when the ruleset has one. */
export function DefenseSummary({ data }: { data: Projection }) {
  const d = data.defense!;
  const by = (c: string) => d.modules.filter(m => m.condition === c).length;
  return <dl className="d-def-kv">
    <div><dt><Pic src="icons/defense/reseau-defensif.svg" size={22} />Modules</dt><dd>{d.used} / {d.capacity}</dd></div>
    <div><dt>Opérationnels</dt><dd>{by('operational')}</dd></div>
    <div><dt>Endommagés</dt><dd>{by('damaged')}</dd></div>
    <div><dt>Entretien</dt><dd>{rate(d.upkeep_flux_per_hour)} Flux/h</dd></div>
  </dl>;
}
