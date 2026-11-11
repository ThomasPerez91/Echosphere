import type { ReactNode } from "react";
import { message } from "../fleet/messages";
import { time } from "../colony/format";
import { Button, Panel } from "../components/ui";
import { CommandMap } from "./CommandMap";
import { useCommandWorld } from "./useCommandWorld";

/** Production container of the command map (UX04), over `useCommandWorld`. */
export function LiveCommandMap({ universe, enabled, csrf, onSessionLost, onEconomyChanged, initialEmpire, onEmpireChange, toolbar: extra, subtitle, systemHref }: {
  universe: string; enabled: boolean; csrf: string | undefined; onSessionLost: () => void;
  onEconomyChanged?: () => void; initialEmpire?: string; onEmpireChange?: (empire: string) => void;
  /** Extra controls shown in the page header (e.g. the classic-map switch). */
  toolbar?: ReactNode; subtitle?: string;
  systemHref?: (empire: string, system: string) => string;
}) {
  const { galaxy, fleets, g, f, world, now, api, synced } = useCommandWorld(universe, enabled, csrf, onSessionLost, onEconomyChanged, initialEmpire, onEmpireChange);

  if (!enabled) return null;
  // Until the map is drawn, the page keeps its heading and the switch to the classic map.
  const head = <header className="cmd-page-head"><div><h1 className="cmd-page-title" tabIndex={-1}>Galaxie</h1>
    <p><strong>Carte stratégique</strong> {subtitle ?? "des systèmes connus de votre Empire"}.</p></div>{extra}</header>;
  if (galaxy.phase === "loading" || galaxy.phase === "idle")
    return <div className="cmd-root cmd-live">{head}<p className="panel" role="status">Chargement des connaissances de l’Empire…</p></div>;
  if (galaxy.phase === "empty")
    return <div className="cmd-root cmd-live">{head}<Panel title="Aucune galaxie accessible"><p>Aucun Empire ne vous donne accès à la galaxie dans cet univers.</p></Panel></div>;
  if (!g) return <div className="cmd-root cmd-live">{head}<Panel title="Galaxie indisponible">
    <p role="alert">{galaxy.error === "galaxy_unavailable" ? "La galaxie n’est pas disponible pour cet Empire dans cet univers." : message(galaxy.error ?? "unavailable")}</p>
    <Button onClick={galaxy.refresh}>Réessayer</Button></Panel></div>;

  const controls = <>
    {galaxy.empires.length > 1 ? <label className="galaxy-field">Empire
      <select value={galaxy.selectedEmpire} disabled={galaxy.pending || fleets.pending} onChange={(e) => galaxy.select(e.target.value)}>
        {galaxy.empires.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
      </select></label> : null}
    <span className="panel-meta cmd-meta">{galaxy.empires.length > 1 ? "" : `${g.empire.name} · `}connaissances au {time(g.server_time)}</span>
    <Button onClick={() => { galaxy.refresh(); fleets.refresh(); }} disabled={fleets.pending}>Actualiser</Button>
  </>;
  const toolbar = <div className="cmd-toolbar">{extra}{controls}</div>;

  if (!world) {
    const loadingFleets = fleets.phase === "loading" || fleets.phase === "idle" || (f && f.empire.id !== g.empire.id && !fleets.error);
    return <div className="cmd-root cmd-live">{head}<div className="cmd-toolbar cmd-toolbar--solo">{controls}</div>
      {loadingFleets ? <p className="panel" role="status">Chargement des flottes de l’Empire…</p>
        : <Panel title="Flottes indisponibles">
          <p role="alert">{f && !f.available ? "Les flottes ne sont pas disponibles pour cet Empire dans cet univers."
            : message(fleets.error ?? "unavailable")}</p>
          <p className="cmd-help">La carte de commandement a besoin de la galaxie et des flottes du même Empire. La carte classique reste disponible.</p>
          <Button onClick={() => { synced.current = null; fleets.select(g.empire.id); }}>Réessayer</Button></Panel>}
    </div>;
  }

  return <div className="cmd-root cmd-live">
    {fleets.awaiting && <p className="cmd-help" role="status">Une échéance est passée : en attente de la confirmation du serveur.</p>}
    <CommandMap world={world} now={now} api={api} pending={fleets.pending} feedback={fleets.feedback} toolbar={toolbar}
      subtitle={subtitle} systemHref={systemHref ? (id) => systemHref(g.empire.id, id) : undefined} />
  </div>;
}
