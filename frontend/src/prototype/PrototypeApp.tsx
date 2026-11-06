import { useEffect, useMemo, useRef, useState } from "react";
import { CommandMap } from "../command/CommandMap";
import type { World } from "../command/model";
import { fixtureApi } from "./api";
import { fleetFixture, galaxyFixture, SERVER_TIME } from "./fixtures";
import { directions } from "./directions";
import type { Direction } from "./directions";

/**
 * Prototype chrome only: explicit fixture banner, art-direction switch, route-contract switch and
 * a demo clock around the production CommandMap. Nothing here is a production setting.
 */
export function PrototypeApp({ startDirection = "orbital", speed: initialSpeed = 1, tick = 1000, latencyMs = 350 }: {
  startDirection?: Direction; speed?: number; tick?: number; latencyMs?: number;
}) {
  const [direction, setDirection] = useState<Direction>(startDirection);
  const [routeMode, setRouteMode] = useState<"contract" | "extension">("extension");
  const [speed, setSpeed] = useState(initialSpeed);
  const origin = useRef({ server: Date.parse(SERVER_TIME), local: Date.now(), speed: initialSpeed });
  const [now, setNow] = useState(origin.current.server);
  const [world, setWorld] = useState<World>(() => ({ fleets: fleetFixture(), galaxy: galaxyFixture() }));
  const current = useRef({ world, now, routeMode });
  current.current = { world, now, routeMode };
  const api = useMemo(() => fixtureApi(() => current.current.world, (w) => { current.current.world = w; setWorld(w); },
    () => current.current.now, { latencyMs, withPath: () => current.current.routeMode === "extension" }), [latencyMs]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const o = origin.current;
      setNow(o.server + (Date.now() - o.local) * o.speed);
    }, tick);
    return () => window.clearInterval(timer);
  }, [tick]);
  const changeSpeed = (value: number) => {
    origin.current = { server: current.current.now, local: Date.now(), speed: value };
    setSpeed(value);
  };

  const nav = ["Empire", "Galaxie", "Colonies", "Recherche", "Flottes", "Rapports", "Diplomatie"];
  return <div className="cmd-root proto-root" data-direction={direction}>
    <div className="proto-shell">
      <aside className="proto-sidebar" aria-label="Navigation (aperçu)">
        <p className="proto-brand"><span aria-hidden="true">◈</span> ECHOSPHERE</p>
        <p className="proto-sidebar-caption">CENTRE DE COMMANDEMENT</p>
        <ul>{nav.map((item) => <li key={item}><span className={`proto-nav${item === "Galaxie" ? " is-current" : ""}`}
          aria-current={item === "Galaxie" ? "page" : undefined}>{item}</span></li>)}</ul>
        <p className="cmd-help">Navigation d’aperçu (UX01) : seule Galaxie est jouable dans ce prototype.</p>
      </aside>
      <div className="proto-workspace">
        <header className="proto-bar">
          <div className="proto-context"><span className="proto-pill">Univers de démonstration</span>
            <span className="proto-pill">Aube Prime · système Aube</span></div>
          <p className="proto-banner" role="note">Prototype UX03 — données fictives, aucune commande envoyée au serveur.</p>
          <details className="proto-settings">
            <summary>Réglages du prototype</summary>
            <div className="proto-controls">
              <label>Direction artistique
                <select value={direction} onChange={(e) => setDirection(e.target.value as Direction)}>
                  {directions.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
                </select></label>
              <label>Trajet affiché
                <select value={routeMode} onChange={(e) => setRouteMode(e.target.value as "contract" | "extension")}>
                  <option value="extension">Étapes (extension API proposée UX-API-01)</option>
                  <option value="contract">Contrat actuel (nombre de sauts seulement)</option>
                </select></label>
              <label>Horloge de démonstration
                <select value={speed} onChange={(e) => changeSpeed(Number(e.target.value))}>
                  <option value={1}>Temps réel</option>
                  <option value={60}>× 60</option>
                  <option value={600}>× 600</option>
                </select></label>
            </div>
          </details>
        </header>
        <main className="proto-main"><CommandMap world={world} api={api} now={now} /></main>
      </div>
    </div>
  </div>;
}
