/**
 * UX03 — presentation model of the Galaxy → Fleet → Mission journey. Pure functions only.
 *
 * Nothing here decides a game rule. Which actions are *offered* mirrors exactly what the current
 * Fleet screen already offers (src/components/FleetView.tsx: mission kinds, destinations, worlds,
 * military and colonizer units); paths, durations, costs, eligibility and outcomes are always the
 * server's answer (mission preview, then the command). A refused action shows the server's reason.
 */
import type { KnownSystem, Route } from "../galaxy/api";
import type { FleetProjection, FleetView, MissionKind, MissionView } from "../fleet/api";

export type MapAction = Exclude<MissionKind, "RETURN">;
export type ActionOffer = { kind: MapAction; label: string; hint: string; planet?: string; reason: string | null };

export const actionLabels: Record<MissionKind, string> = {
  SURVEY: "Cartographier", DEPLOY: "Déplacer une flotte", COLONIZE: "Coloniser", ATTACK: "Attaquer", RETURN: "Rentrer",
};
/** Moving-fleet wording per mission kind (the player reads what the fleet is doing). */
export const travelLabels: Record<MissionKind, string> = {
  SURVEY: "Cartographie — en route", DEPLOY: "En déplacement", COLONIZE: "Colonisation — en route",
  ATTACK: "Attaque — en route", RETURN: "Retour en cours",
};
export const actionHints: Record<MapAction, string> = {
  SURVEY: "Une sonde se rend sur ce signal et révèle le système (nom, planètes, routes).",
  DEPLOY: "La flotte se rend dans ce système et y reste stationnée.",
  COLONIZE: "Un colonisateur fonde une colonie sur ce monde, si personne ne l’occupe à l’arrivée.",
  ATTACK: "Des vaisseaux militaires attaquent ce monde ; la bataille a lieu au plus tôt 24 h après le départ.",
};

export type World = { fleets: FleetProjection; galaxy: { systems: KnownSystem[]; routes: Route[] } };

const can = (w: World, right: string) => w.fleets.permissions.includes(right);
export const stationed = (w: World) => (w.fleets.fleets ?? []).filter((f) => f.status === "STATIONED");
const surveyClasses = (w: World) => Object.entries(w.fleets.catalogue ?? {}).filter(([, c]) => c.survey).map(([k]) => k);
const military = (w: World) => w.fleets.combat?.classes ?? [];
const colonizer = (w: World) => w.fleets.colonization?.colonizer_class ?? null;

/** Units a fleet can engage for an action (the same unit families the current screen offers). */
export function engageable(w: World, fleet: FleetView, kind: MissionKind): Record<string, number> {
  const pick = (classes: string[]) => Object.fromEntries(Object.entries(fleet.stacks).filter(([c, n]) => n > 0 && classes.includes(c)));
  if (kind === "SURVEY") return pick(surveyClasses(w));
  if (kind === "ATTACK") return pick(military(w));
  if (kind === "COLONIZE") { const c = colonizer(w); return c && fleet.stacks[c] ? { [c]: 1 } : {}; }
  return Object.fromEntries(Object.entries(fleet.stacks).filter(([, n]) => n > 0));
}

/** Stationed fleets that could carry out `kind` towards `system` (the server re-checks everything). */
export function eligibleFleets(w: World, kind: MissionKind, system: string): FleetView[] {
  if (!can(w, "fleet.command")) return [];
  return stationed(w).filter((f) => Object.keys(engageable(w, f, kind)).length > 0 && ((kind !== "DEPLOY" && kind !== "SURVEY") || f.system?.id !== system));
}

/** What the selected system offers, with a reason in plain words when it cannot be done now. */
export function offers(w: World, systemId: string): ActionOffer[] {
  const known = w.galaxy.systems.find((s) => s.id === systemId);
  const ref = w.fleets.systems?.find((s) => s.id === systemId);
  if (!known || !can(w, "fleet.command")) return [];
  const result: ActionOffer[] = [];
  const reasonFor = (kind: MissionKind, missing: string) => eligibleFleets(w, kind, systemId).length ? null : missing;
  if (known.state === "DETECTED") {
    result.push({ kind: "SURVEY", label: actionLabels.SURVEY, hint: actionHints.SURVEY,
      reason: reasonFor("SURVEY", "Aucune sonde stationnée : produisez une Sonde depuis l’écran Flottes.") });
    return result;
  }
  result.push({ kind: "DEPLOY", label: actionLabels.DEPLOY, hint: actionHints.DEPLOY,
    reason: reasonFor("DEPLOY", "Aucune flotte stationnée ailleurs ne peut s’y rendre.") });
  for (const planet of ref?.planets ?? []) {
    if (planet.colony_id) continue; // own colony (named only with colony.read)
    if (colonizer(w) && can(w, "colony.expand") && can(w, "galaxy.read")) {
      result.push({ kind: "COLONIZE", label: `${actionLabels.COLONIZE} ${planet.name}`, hint: actionHints.COLONIZE, planet: planet.id,
        reason: reasonFor("COLONIZE", "Aucun colonisateur stationné.") });
    }
    if (military(w).length && can(w, "combat.attack") && can(w, "combat.read") && can(w, "galaxy.read")) {
      result.push({ kind: "ATTACK", label: `${actionLabels.ATTACK} ${planet.name}`, hint: actionHints.ATTACK, planet: planet.id,
        reason: reasonFor("ATTACK", "Aucune flotte stationnée avec des vaisseaux militaires.") });
    }
  }
  return result;
}

export type Point = { x: number; y: number };
export const point = (w: World, id: string): Point | null => {
  const s = w.galaxy.systems.find((x) => x.id === id);
  return s ? { x: s.x, y: s.y } : null;
};

/** Display name under Fog of War: a DETECTED system is only a signal, never named. */
export function systemName(w: World, id: string | null | undefined) {
  if (!id) return "—";
  const s = w.galaxy.systems.find((x) => x.id === id);
  if (!s) return "Système hors de vos connaissances";
  return s.state === "DETECTED" ? "Signal détecté" : s.name ?? "Système connu";
}

/**
 * Where to draw a moving fleet: a *display estimate* along the server path when known (proposed
 * UX-API-01), otherwise on the straight origin→destination line, from the server's own dates —
 * exactly like the existing progress bars (local estimation, server confirms on arrival).
 */
export function missionPosition(w: World, m: MissionView, now: number, path?: string[]): Point | null {
  const from = Date.parse(m.started_at), to = Date.parse(m.status === "returning" && m.return_at ? m.return_at : m.travel_arrival_at);
  const ratio = Math.max(0, Math.min(1, (now - from) / Math.max(1, to - from)));
  const nodes = (path?.length ? path : [m.origin?.id, m.destination?.id]).map((id) => (id ? point(w, id) : null));
  if (nodes.some((n) => !n) || nodes.length < 2) return null;
  const pts = nodes as Point[];
  const segment = Math.min(pts.length - 2, Math.floor(ratio * (pts.length - 1)));
  const local = ratio * (pts.length - 1) - segment;
  const a = pts[segment], b = pts[segment + 1];
  return { x: a.x + (b.x - a.x) * local, y: a.y + (b.y - a.y) * local };
}

export type FleetLine = { id: string; name: string; where: string; state: string; destination: string | null; units: number };

/** One line per own fleet: where it is, what it does, where it goes — the "find my fleets" list. */
export function fleetLines(w: World, now: number): FleetLine[] {
  const missions = w.fleets.missions ?? [];
  return (w.fleets.fleets ?? []).map((f) => {
    const units = Object.values(f.stacks).reduce((a, b) => a + b, 0);
    const m = missions.find((x) => x.id === f.mission_id && x.status !== "completed");
    if (f.status === "STATIONED" || !m) return { id: f.id, name: f.name, where: systemName(w, f.system?.id), state: f.kind === "GARRISON" ? "En garnison" : "Stationnée", destination: null, units };
    const arrived = now >= Date.parse(m.travel_arrival_at);
    const state = m.status === "returning" ? "Retour en cours" : m.kind === "SURVEY" && arrived ? "Cartographie en cours"
      : m.kind === "ATTACK" && arrived ? "Sur place — bataille à venir"
      : arrived ? "Arrivée — confirmation du serveur attendue" : travelLabels[m.kind];
    return { id: f.id, name: f.name, where: `Entre ${systemName(w, m.origin?.id)} et ${systemName(w, m.destination?.id)}`, state, destination: systemName(w, m.status === "returning" ? m.origin?.id : m.destination?.id), units };
  });
}
