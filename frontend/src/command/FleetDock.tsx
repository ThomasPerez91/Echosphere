import { useState } from "react";
import type { MissionView } from "../fleet/api";
import { time } from "../colony/format";
import { fleetLines, kindNames, recallable, systemName } from "./model";
import type { FleetLine, World } from "./model";

const outcomes: Record<string, string> = {
  RECALLED: "Rappel terminé", COLONIZE: "Colonisation terminée", ATTACK: "Attaque terminée",
  INTERCEPTED: "Détruite par une interception en route", SURVEY: "Cartographie terminée", DEPLOY: "Déplacement terminé",
};

/**
 * "Vos flottes": every own fleet with where it is, what it does, where it goes and when, an
 * estimated progress (never a server position), Localiser, a confirmed recall when the server's
 * rule still allows it, and the recent completed missions.
 */
export function FleetDock({ world, now, canCommand, pending, onLocate, onRecall }: {
  world: World; now: number; canCommand: boolean; pending: boolean;
  onLocate: (line: FleetLine) => void; onRecall: (m: MissionView) => Promise<boolean>;
}) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const lines = fleetLines(world, now);
  const done = (world.fleets.missions ?? []).filter((m) => m.status === "completed").slice(0, 8);
  const name = (fleetId: string) => world.fleets.fleets?.find((f) => f.id === fleetId)?.name ?? "Flotte";

  return <section className="cmd-card cmd-dock" aria-labelledby="cmd-dock-title">
    <h2 id="cmd-dock-title">Vos flottes</h2>
    {lines.length === 0 ? <p>Aucune flotte. Produisez des vaisseaux depuis l’écran Flottes.</p> : <ul>{lines.map((l) => {
      const m = l.mission;
      return <li key={l.id}>
        <div className="cmd-dock-head"><strong>{l.name}</strong> <span className={`cmd-chip${l.garrison ? " cmd-chip--warn" : ""}`}>{l.state}</span></div>
        <p className="cmd-help">{l.where}{l.destination ? ` → ${l.destination}` : ""} · {l.units} unité(s)</p>
        {m && l.arrival && <p className="cmd-help">{kindNames[m.kind]}{m.status === "returning" ? " — retour" : ""} · {m.status === "returning" ? "retour prévu" : m.kind === "ATTACK" ? "bataille" : "arrivée"} {time(l.arrival)}</p>}
        {l.progress !== null && <div className="meter cmd-meter" role="progressbar" aria-label={`Avancement estimé de ${l.name}`}
          aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(l.progress * 100)}><span style={{ width: `${Math.round(l.progress * 100)}%` }} /></div>}
        <div className="cmd-dock-actions">
          <button type="button" className="button cmd-ghost cmd-locate" onClick={() => onLocate(l)}>Localiser<span className="visually-hidden"> {l.name}</span></button>
          {m && canCommand && recallable(m, now) && (confirming === m.id
            ? <span className="cmd-confirm-row" role="group" aria-label={`Confirmer le rappel de ${l.name}`}>
              <button type="button" className="button button--primary" disabled={pending}
                onClick={async () => { if (await onRecall(m)) setConfirming(null); }}>Confirmer le rappel</button>
              <button type="button" className="button cmd-ghost" onClick={() => setConfirming(null)}>Garder la mission</button></span>
            : <button type="button" className="button cmd-ghost" disabled={pending} onClick={() => setConfirming(m.id)}>
              Rappeler…<span className="visually-hidden"> {l.name}</span></button>)}
        </div>
        {m && confirming === m.id && <p className="cmd-help">La flotte fait demi-tour ; aucun remboursement du carburant.</p>}
      </li>;
    })}</ul>}
    {done.length > 0 && <details className="cmd-history">
      <summary>Missions terminées ({done.length})</summary>
      <ul>{done.map((m) => <li key={m.id}>
        <strong>{outcomes[m.report?.result.kind ?? m.kind] ?? kindNames[m.kind]}</strong> — {name(m.fleet_id)} · {systemName(world, m.destination?.id)}
        {m.completed_at ? ` · ${time(m.completed_at)}` : ""}</li>)}</ul>
    </details>}
  </section>;
}
