import { useEffect, useRef, useState } from "react";
import type { FleetView, Protocol } from "../fleet/api";
import { protocols } from "../fleet/protocols";
import { fleetLines, isGarrison, systemName } from "./model";
import type { World } from "./model";

/**
 * Fleets present in one system (09/11/2026 decision): opened from the fleet symbol above the
 * system. Composition, current mission and, for a stationed task fleet, its first-contact protocol
 * (the "mission" it holds there); "Déplacer" hands the map back to the player to pick a
 * destination. A floating, non-modal window: the map stays usable behind it.
 */
export function FleetWindow({ world, system, now, canCommand, pending, onClose, onMove, onProtocol }: {
  world: World; system: string; now: number; canCommand: boolean; pending: boolean;
  onClose: () => void; onMove: (fleet: FleetView) => void;
  /** Absent when this view cannot change protocols (prototype, older rulesets). */
  onProtocol?: (fleet: FleetView, protocol: Protocol | null) => Promise<boolean>;
}) {
  const here = (world.fleets.fleets ?? []).filter((f) => f.status === "STATIONED" && f.system?.id === system);
  const lines = new Map(fleetLines(world, now).map((l) => [l.id, l]));
  const catalogue = world.fleets.catalogue ?? {};
  const frontier = world.fleets.frontier?.protocols ?? [];
  const [choice, setChoice] = useState<Record<string, Protocol | "">>({});
  const [done, setDone] = useState<string | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, [system]);

  return <section className="cmd-fleet-window" role="dialog" aria-modal="false" aria-labelledby="cmd-fleet-window-title"
    onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}>
    <div className="cmd-fleet-window-head">
      <h2 id="cmd-fleet-window-title" ref={title} tabIndex={-1}>Flottes à {systemName(world, system)}</h2>
      <button type="button" className="cmd-ctx-close" aria-label="Fermer la fenêtre des flottes" onClick={onClose}>×</button>
    </div>
    {here.length === 0 ? <p>Aucune de vos flottes n’est stationnée ici.</p> : <ul className="cmd-fleet-window-list">{here.map((f) => {
      const units = Object.entries(f.stacks).filter(([, n]) => n > 0);
      const task = !isGarrison(f);
      const active = f.protocol ?? null;
      const chosen = choice[f.id] ?? (active ?? "");
      return <li key={f.id}>
        <div className="cmd-dock-head"><strong>{f.name}</strong>
          <span className={`cmd-chip${task ? "" : " cmd-chip--warn"}`}>{lines.get(f.id)?.state ?? (task ? "Stationnée" : "En garnison")}</span></div>
        <p className="cmd-help">Composition : {units.length ? units.map(([c, n]) => `${n} ${catalogue[c]?.name ?? c}`).join(", ") : "aucune unité"}</p>
        <p className="cmd-help">Mission : {task
          ? active ? <>{protocols[active].label} — {protocols[active].help}</> : "en attente, sans protocole (ne détecte rien)."
          : "défense de la colonie (garnison)."}</p>
        {canCommand && task && frontier.length > 0 && onProtocol && <form className="cmd-fleet-protocol" onSubmit={async (e) => {
          e.preventDefault();
          const value = chosen === "" ? null : chosen;
          if (await onProtocol(f, value)) setDone(f.id);
        }}>
          <label>Changer de mission
            <select value={chosen} disabled={pending} onChange={(e) => { setChoice({ ...choice, [f.id]: e.target.value as Protocol | "" }); setDone(null); }}>
              <option value="">En attente (aucun protocole)</option>
              {frontier.map((p) => <option key={p} value={p}>{protocols[p].label}</option>)}
            </select></label>
          <button type="submit" className="button" disabled={pending || chosen === (active ?? "")}>Appliquer</button>
          {done === f.id && <span role="status" className="cmd-help">Mission changée.</span>}
        </form>}
        {canCommand && units.length > 0 && <button type="button" className="button button--primary" disabled={pending} onClick={() => onMove(f)}>
          Déplacer…<span className="visually-hidden"> {f.name}</span></button>}
      </li>;
    })}</ul>}
  </section>;
}

/** Destination picking (window reduced in the top-left corner, watermark on the map). */
export function PickBar({ fleet, onCancel }: { fleet: FleetView; onCancel: () => void }) {
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { cancel.current?.focus(); }, []);
  return <div className="cmd-pick-bar" role="status" aria-live="polite">
    <strong>{fleet.name}</strong><span>Choisissez une destination sur la carte</span>
    <button ref={cancel} type="button" className="button cmd-ghost" onClick={onCancel}>Annuler (Échap)</button>
  </div>;
}
