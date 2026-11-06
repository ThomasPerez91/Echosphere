import type { HistoryEntry } from '../colony/api';
import { infrastructureLabel } from '../colony/format';
import type { FleetProjection } from '../fleet/api';
import type { Projection as ResearchProjection } from '../research/api';
import type { RelationsProjection } from '../relations/api';

export type Category = 'construction' | 'mission' | 'combat' | 'frontier' | 'research' | 'diplomacy';
export type Tone = 'green' | 'amber' | 'blue' | 'red';
/** One dated fact reported by the server; never a client-side prediction. */
export type ReportEvent = { key: string; category: Category; tone: Tone; icon: string; title: string; text: string; at: string; href?: string };

export const categoryLabels: Record<Category, string> = {
  construction: 'Constructions', mission: 'Missions', combat: 'Combats', frontier: 'Frontière', research: 'Recherche', diplomacy: 'Diplomatie',
};

const outcomes: Record<string, string> = {
  attacker_win: 'victoire de l’attaquant', defender_win: 'victoire du défenseur', mutual_destruction: 'destruction mutuelle',
  unopposed: 'aucune défense militaire', target_unavailable: 'cible indisponible', voided_by_pact: 'annulée par un pacte',
};

export function constructionEvents(entries: HistoryEntry[], colony: { id: string; name: string }): ReportEvent[] {
  return entries.map(e => ({
    key: `construction-${e.id}`, category: 'construction', tone: 'green', icon: 'icons/evenements/evt-construction-terminee.svg',
    title: e.target_level > 1 ? `${infrastructureLabel(e.infrastructure_type)} — niveau ${e.target_level}` : `${infrastructureLabel(e.infrastructure_type)} construit`,
    text: `${colony.name} · secteur ${e.sector_index + 1}`, at: e.completed_at,
  }));
}

export function missionEvents(f: FleetProjection | null): ReportEvent[] {
  const fleetName = (id: string) => f?.fleets?.find(x => x.id === id)?.name ?? 'Flotte';
  return (f?.missions ?? []).filter(m => m.status === 'completed' && m.completed_at).map((m): ReportEvent => {
    const kind = m.report?.result.kind ?? m.kind;
    const where = m.destination?.name ?? 'système inconnu';
    const base = { key: `mission-${m.id}`, at: m.completed_at! };
    if (kind === 'INTERCEPTED') return { ...base, category: 'combat', tone: 'red', icon: 'icons/evenements/evt-combat.svg', title: 'Flotte interceptée', text: `${fleetName(m.fleet_id)} — ${where}` };
    if (m.kind === 'ATTACK') return { ...base, category: 'mission', tone: 'red', icon: 'icons/evenements/evt-combat.svg', title: 'Attaque terminée', text: `${fleetName(m.fleet_id)} — ${where}` };
    if (m.kind === 'COLONIZE' && m.report?.result.colony_id) return { ...base, category: 'mission', tone: 'green', icon: 'icons/evenements/evt-nouvelle-colonie.svg', title: 'Nouvelle colonie établie', text: where };
    if (m.kind === 'COLONIZE') return { ...base, category: 'mission', tone: 'amber', icon: 'icons/evenements/evt-nouvelle-colonie.svg', title: 'Colonisation sans fondation', text: `${fleetName(m.fleet_id)} — ${where}` };
    if (m.kind === 'SURVEY') return { ...base, category: 'mission', tone: 'blue', icon: 'icons/evenements/evt-decouverte.svg', title: 'Système cartographié', text: where };
    return { ...base, category: 'mission', tone: 'green', icon: 'icons/evenements/evt-flotte-revenue.svg', title: m.recalled_at ? 'Flotte revenue' : 'Flotte arrivée', text: `${fleetName(m.fleet_id)} — ${where}` };
  });
}

export function combatEvents(f: FleetProjection | null): ReportEvent[] {
  return (f?.combat?.reports ?? []).map(r => {
    const system = f?.systems?.find(s => s.id === r.target.system_id);
    const world = system?.planets?.find(p => p.id === r.target.planet_id);
    return {
      key: `combat-${r.engagement_id}-${r.role}`, category: 'combat' as const, tone: (r.outcome === 'voided_by_pact' ? 'amber' : 'red') as Tone,
      icon: 'icons/evenements/evt-combat.svg', title: r.role === 'attacker' ? 'Rapport de bataille — votre attaque' : 'Rapport de bataille — votre défense',
      text: `${world?.name ?? 'Monde'}${system?.name ? ` · ${system.name}` : ''} — ${outcomes[r.outcome] ?? 'terminée'}`, at: r.processed_at,
    };
  });
}

export function frontierEvents(f: FleetProjection | null): ReportEvent[] {
  const fr = f?.frontier;
  if (!fr) return [];
  const where = (s: { name?: string | null } | null) => s?.name ?? 'système non identifié';
  return [
    ...fr.detections.map((d): ReportEvent => ({ key: `detection-${d.id}`, category: 'frontier', tone: d.friendly ? 'blue' : 'amber', icon: 'icons/evenements/evt-passivite-anormale.svg',
      title: d.friendly ? 'Contact amical détecté' : 'Flotte étrangère détectée', text: `${where(d.system)}${d.empire ? ` · ${d.empire.name}` : ' · signature anonyme'}`, at: d.detected_at })),
    ...fr.encounters.map((e): ReportEvent => e.kind === 'engagement'
      ? { key: `encounter-${e.id}`, category: 'frontier', tone: 'red', icon: 'icons/evenements/evt-combat.svg', title: 'Engagement frontalier', text: `${where(e.system)} · ${e.opponent.name}`, at: e.at }
      : { key: `retreat-${e.id}`, category: 'frontier', tone: e.outcome === 'retreated' ? 'amber' : 'red', icon: 'icons/evenements/evt-flotte-revenue.svg',
        title: e.outcome === 'retreated' ? 'Repli effectué' : 'Repli impossible', text: where(e.system), at: e.at }),
  ];
}

export function researchEvents(r: ResearchProjection | null): ReportEvent[] {
  const techName = (id: string) => r?.technologies.find(t => t.id === id)?.name ?? id;
  return (r?.acquired ?? []).map(a => ({ key: `research-${a.technology_id}`, category: 'research', tone: 'blue', icon: 'icons/evenements/evt-recherche-terminee.svg',
    title: 'Recherche terminée', text: techName(a.technology_id), at: a.acquired_at }));
}

export function relationEvents(rel: RelationsProjection | null): ReportEvent[] {
  const counterpart = (id: string) => rel?.relations.find(x => x.empire.id === id)?.empire.name ?? 'un Empire';
  return (rel?.history ?? []).map(h => ({ key: `relation-${h.id}`, category: 'diplomacy', tone: 'amber', icon: 'icons/evenements/evt-contact-diplomatique.svg',
    title: h.kind === 'accepted' ? 'Pacte conclu' : h.kind === 'proposed' ? 'Proposition de pacte' : h.kind === 'refused' ? 'Pacte refusé' : h.kind === 'notice' ? 'Préavis de fin de pacte' : 'Proposition retirée',
    text: counterpart(h.counterpart_id), at: h.at }));
}

export const newestFirst = (a: ReportEvent, b: ReportEvent) => Date.parse(b.at) - Date.parse(a.at) || a.key.localeCompare(b.key);
