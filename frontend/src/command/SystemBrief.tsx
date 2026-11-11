import { planetImage } from "../shell/assets";
import { opportunityNames, systemFacts, systemName } from "./model";
import type { World } from "./model";

const resourceNames = { alloys: "Alliages", flux: "Flux", data: "Données" } as const;
const whole = (micro?: string) => micro ? Math.floor(Number(micro) / 1_000_000).toLocaleString("fr-FR") : "?";
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n > 1 ? many : one}`;

/**
 * Fiche rapide (11/11/2026): what the Empire knows of the selected system, at a glance in the map's
 * context menu — worlds, opportunities, own fleets, distance — before its possible actions.
 * Occupation is never guessed: a world without an own or observed Colony stays "inconnue".
 */
export function SystemBrief({ world, system }: { world: World; system: string }) {
  const known = world.galaxy.systems.find((s) => s.id === system);
  if (!known) return null;
  if (known.state === "DETECTED") return <p className="cmd-brief-note">Signal seulement : nom, mondes et ressources restent inconnus jusqu’à sa cartographie.</p>;
  const f = systemFacts(world, system);
  const moving = f.incoming.length;
  return <div className="cmd-brief">
    <ul className="cmd-brief-facts" aria-label={`Résumé de ${systemName(world, system)}`}>
      <li><strong>{f.planets.length}</strong><span>{f.planets.length > 1 ? "mondes" : "monde"}</span></li>
      <li><strong>{f.deposits.length + f.curiosities.length}</strong><span>opportunités</span></li>
      <li><strong>{f.fleets.length}</strong><span>{f.fleets.length > 1 ? "flottes ici" : "flotte ici"}</span></li>
      <li><strong>{f.distance ? (f.distance.hops === 0 ? "Ici" : f.distance.hops) : "?"}</strong><span>{f.distance && f.distance.hops > 0 ? (f.distance.hops > 1 ? "sauts" : "saut") : "distance"}</span></li>
    </ul>
    {f.planets.length > 0 && <ul className="cmd-brief-list" aria-label="Mondes connus">{f.planets.slice(0, 4).map((p) =>
      <li key={p.id}><img src={planetImage(p.id)} alt="" width="26" height="26" />
        <span><strong>{p.name}</strong><small>{p.sectors} secteurs · {p.orbitals} orbitaux</small></span>
        <em className={p.own ? "is-own" : p.foreign !== null ? "is-foreign" : ""}>{p.own ? "Votre colonie" : p.foreign !== null ? `Empire ${p.foreign}` : "Occupation inconnue"}</em></li>)}
      {f.planets.length > 4 && <li className="cmd-brief-more">+ {plural(f.planets.length - 4, "autre monde", "autres mondes")}</li>}</ul>}
    {(f.deposits.length > 0 || f.curiosities.length > 0) && <ul className="cmd-brief-list cmd-brief-opps" aria-label="Opportunités connues">
      {f.deposits.slice(0, 3).map((o) => <li key={o.id}><span className="cmd-brief-dot is-deposit" aria-hidden="true" />
        <span><strong>{opportunityNames[o.kind] ?? o.kind}</strong><small>{resourceNames[o.resource!]} · réserve {whole(o.reserve)}</small></span></li>)}
      {f.curiosities.slice(0, 2).map((o) => <li key={o.id}><span className="cmd-brief-dot" aria-hidden="true" />
        <span><strong>{opportunityNames[o.kind] ?? o.kind}</strong><small>{o.studied ? "Déjà étudiée" : `${whole(o.data)} Données à étudier`}</small></span></li>)}
    </ul>}
    {f.signatures !== null && f.signatures > 0 && <p className="cmd-brief-note">{plural(f.signatures, "signature inexpliquée", "signatures inexpliquées")} : à prospecter.</p>}
    {moving > 0 && <p className="cmd-brief-note">{plural(moving, "mission en route", "missions en route")} vers ce système.</p>}
    {f.alerts.length > 0 && <p className="cmd-brief-note is-alert">Attaque annoncée ici.</p>}
  </div>;
}
