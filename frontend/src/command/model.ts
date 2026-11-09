/**
 * Command map — presentation model of the Galaxy → Fleet → Mission journey. Pure functions only.
 *
 * Nothing here decides a game rule. Which actions are *offered* mirrors what the Fleet screen
 * already offers (mission kinds, destinations, worlds, military and colonizer units); paths,
 * durations, costs, eligibility and outcomes are always the server's answer (mission preview,
 * then the command). Default units follow D-UX-4/D-UX-5 (validated 03/11/2026): one probe, exactly
 * one colonizer, a task fleet's own composition for a move, an explicit choice for an attack, and
 * never anything taken automatically from a garrison.
 */
import type { KnownSystem, Route } from "../galaxy/api";
import type { FleetProjection, FleetView, MissionKind, MissionView } from "../fleet/api";
import type { CommandQuote } from "./types";

export type MapAction = Exclude<MissionKind, "RETURN">;
export type ActionOffer = { kind: MapAction; label: string; hint: string; planet?: string; reason: string | null };

export const actionLabels: Record<MissionKind, string> = {
  SURVEY: "Cartographier", DEPLOY: "Déplacer une flotte", COLONIZE: "Coloniser", ATTACK: "Attaquer", RETURN: "Rentrer",
};
export const kindNames: Record<MissionKind, string> = {
  SURVEY: "Cartographie", DEPLOY: "Déplacement", COLONIZE: "Colonisation", ATTACK: "Attaque", RETURN: "Retour",
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
export const isGarrison = (f: FleetView) => f.kind === "GARRISON";

/** Maximum units of each class a fleet can engage for an action (same families as the Fleet screen). */
export function engageable(w: World, fleet: FleetView, kind: MissionKind): Record<string, number> {
  const pick = (classes: string[]) => Object.fromEntries(Object.entries(fleet.stacks).filter(([c, n]) => n > 0 && classes.includes(c)));
  if (kind === "SURVEY") return pick(surveyClasses(w));
  if (kind === "ATTACK") return pick(military(w));
  if (kind === "COLONIZE") { const c = colonizer(w); return c && fleet.stacks[c] ? { [c]: 1 } : {}; }
  return Object.fromEntries(Object.entries(fleet.stacks).filter(([, n]) => n > 0));
}

/** D-UX-4/5 defaults: shown and editable; a garrison never loses units without an explicit choice. */
export function defaultUnits(w: World, fleet: FleetView, kind: MissionKind): Record<string, number> {
  if (isGarrison(fleet) || kind === "ATTACK") return {};
  const max = engageable(w, fleet, kind);
  if (kind === "SURVEY") { const [first] = Object.keys(max); return first ? { [first]: 1 } : {}; }
  return max; // COLONIZE: exactly one colonizer; DEPLOY: the task fleet moves as it is
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
    if (can(w, "galaxy.read")) result.push({ kind: "SURVEY", label: actionLabels.SURVEY, hint: actionHints.SURVEY,
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

/**
 * Shortest number of jumps from the nearest own colony, over the routes this Empire knows (the
 * same graph the server uses for paths). Null when no known route links the system to a colony.
 */
export function knownHops(w: World, target: string): { hops: number; from: string } | null {
  const starts = w.galaxy.systems.filter((s) => s.observation?.own_colony_ids.length).map((s) => s.id);
  const next = new Map<string, string[]>();
  for (const r of w.galaxy.routes) {
    next.set(r.a_id, [...(next.get(r.a_id) ?? []), r.b_id]);
    next.set(r.b_id, [...(next.get(r.b_id) ?? []), r.a_id]);
  }
  const origin = new Map(starts.map((id) => [id, id]));
  let frontier = starts, hops = 0;
  while (frontier.length) {
    const hit = frontier.find((id) => id === target);
    if (hit) return { hops, from: origin.get(hit)! };
    const following: string[] = [];
    for (const id of frontier) for (const n of next.get(id) ?? []) {
      if (!origin.has(n)) { origin.set(n, origin.get(id)!); following.push(n); }
    }
    frontier = following; hops += 1;
  }
  return null;
}

/** Display name under Fog of War: a DETECTED system is only a signal, never named. */
export function systemName(w: World, id: string | null | undefined) {
  if (!id) return "—";
  const s = w.galaxy.systems.find((x) => x.id === id);
  if (!s) return "Système hors de vos connaissances";
  return s.state === "DETECTED" ? "Signal détecté" : s.name ?? "Système connu";
}

/**
 * UX-API-01 is not live yet: a `path` is used only when the server sent one that is coherent
 * (known systems, `hops + 1` entries, from origin to destination). Never repaired, never guessed.
 */
export function serverPath(w: World, quote: CommandQuote | null | undefined, origin: string | null | undefined): string[] | undefined {
  const path = quote?.path;
  if (!quote || !Array.isArray(path) || path.length !== quote.hops + 1) return undefined;
  if (path[0] !== origin || path[path.length - 1] !== quote.destination_id) return undefined;
  return path.every((id) => w.galaxy.systems.some((s) => s.id === id)) ? path : undefined;
}

const progressOf = (m: MissionView, now: number) => {
  const from = Date.parse(m.status === "returning" ? (m.recalled_at ?? m.due_at) : m.started_at);
  const to = Date.parse(m.status === "returning" && m.return_at ? m.return_at : m.travel_arrival_at);
  return Math.max(0, Math.min(1, (now - from) / Math.max(1, to - from)));
};

/**
 * The line of a mission on the map. `server`: the systems served in `missions[].path`, all
 * present on this map (0 hop = one point, no line). Otherwise `estimated`: departure and
 * destination joined directly, the real route being unknown here.
 */
export type MissionRoute = { points: Point[]; kind: "server" | "estimated" };

export function missionRoute(w: World, m: MissionView): MissionRoute | null {
  const served = m.path?.map((id) => point(w, id));
  if (served?.length && served.every(Boolean)) return { points: served as Point[], kind: "server" };
  const ends = [m.origin?.id, m.destination?.id].map((id) => (id ? point(w, id) : null));
  if (ends.some((n) => !n)) return null;
  const pts = ends as Point[];
  return { points: pts[0].x === pts[1].x && pts[0].y === pts[1].y ? [pts[0]] : pts, kind: "estimated" };
}

/** Accessible label of a mission line; a return always mirrors the outbound route (engine v0.9). */
export function missionRouteLabel(m: MissionView, route: MissionRoute) {
  if (m.status === "returning") return route.kind === "server" ? "Retour estimé en miroir de l’aller" : "Retour estimé en miroir de l’aller (tracé direct, trajet réel inconnu)";
  return route.kind === "server" ? "Trajet de la mission" : "Départ et destination de la mission (tracé estimé, trajet réel inconnu)";
}

/**
 * Where to draw a moving fleet: a purely visual estimate from the server's dates, along the
 * route above. A returning fleet goes back from the point it had reached (recall) or from the
 * destination.
 */
export function missionPosition(w: World, m: MissionView, now: number): Point | null {
  const route = missionRoute(w, m);
  if (!route) return null;
  const pts = route.points;
  if (pts.length === 1) return pts[0];
  let ratio = progressOf(m, now);
  if (m.status === "returning") {
    const reached = m.recalled_at
      ? Math.max(0, Math.min(1, (Date.parse(m.recalled_at) - Date.parse(m.started_at)) / Math.max(1, Date.parse(m.travel_arrival_at) - Date.parse(m.started_at))))
      : 1;
    ratio = reached * (1 - ratio);
  }
  const segment = Math.min(pts.length - 2, Math.floor(ratio * (pts.length - 1)));
  const local = ratio * (pts.length - 1) - segment;
  const a = pts[segment], b = pts[segment + 1];
  return { x: a.x + (b.x - a.x) * local, y: a.y + (b.y - a.y) * local };
}

/** ATTACK: recall until battle_at; every other mission only while travelling (Fleet screen rule). */
export function recallable(m: MissionView, now: number) {
  const attack = m.kind === "ATTACK";
  return m.status === "active" && m.kind !== "RETURN" && now < Date.parse(attack ? m.due_at : m.travel_arrival_at)
    && (!attack || m.attack?.state === "pending");
}

export type FleetLine = {
  id: string; name: string; garrison: boolean; where: string; state: string; destination: string | null; units: number;
  mission: MissionView | null; arrival: string | null; progress: number | null;
};

/** One line per own fleet: where it is, what it does, where it goes and when — "find my fleets". */
export function fleetLines(w: World, now: number): FleetLine[] {
  const missions = w.fleets.missions ?? [];
  return (w.fleets.fleets ?? []).map((f) => {
    const units = Object.values(f.stacks).reduce((a, b) => a + b, 0);
    const m = missions.find((x) => x.id === f.mission_id && x.status !== "completed") ?? null;
    const base = { id: f.id, name: f.name, garrison: isGarrison(f), units, mission: m };
    if (f.status === "STATIONED" || !m) return { ...base, where: systemName(w, f.system?.id), state: isGarrison(f) ? "En garnison" : "Stationnée", destination: null, arrival: null, progress: null };
    const arrived = now >= Date.parse(m.travel_arrival_at);
    const returning = m.status === "returning";
    const state = returning ? (m.recalled_at ? "Retour après rappel" : "Retour")
      : m.kind === "SURVEY" && arrived ? (now >= Date.parse(m.due_at) ? "Cartographie — résultat attendu du serveur" : "Cartographie en cours")
      : m.kind === "ATTACK" && arrived ? "Sur place — bataille à venir"
      : arrived ? "Arrivée — confirmation du serveur attendue" : `${kindNames[m.kind]} en route`;
    return { ...base, where: `Entre ${systemName(w, m.origin?.id)} et ${systemName(w, m.destination?.id)}`, state,
      destination: systemName(w, returning ? m.origin?.id : m.destination?.id),
      arrival: returning ? m.return_at : m.kind === "ATTACK" ? m.due_at : m.travel_arrival_at, progress: progressOf(m, now) };
  });
}
