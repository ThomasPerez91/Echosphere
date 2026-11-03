import { useEffect, useMemo, useRef, useState } from "react";
import { fixtureApi } from "./api";
import { CommandMap } from "./CommandMap";
import { fleetFixture, galaxyFixture, SERVER_TIME } from "./fixtures";
import type { World } from "./model";

export const directions = [
  { id: "orbital", label: "A — Console orbitale (recommandée)" },
  { id: "atlas", label: "B — Atlas stellaire" },
  { id: "tactical", label: "C — Pont tactique" },
] as const;
export type Direction = (typeof directions)[number]["id"];

/**
 * Prototype chrome only: explicit fixture banner, art-direction switch, route-contract switch and
 * a demo clock. Nothing here is a production setting; the production shell is untouched.
 */
export function PrototypeApp({ startDirection = "orbital", speed: initialSpeed = 1, tick = 1000 }: {
  startDirection?: Direction; speed?: number; tick?: number;
}) {
  const [direction, setDirection] = useState<Direction>(startDirection);
  const [routeMode, setRouteMode] = useState<"contract" | "extension">("extension");
  const [speed, setSpeed] = useState(initialSpeed);
  const origin = useRef({ server: Date.parse(SERVER_TIME), local: Date.now(), speed: initialSpeed });
  const [now, setNow] = useState(origin.current.server);
  const world = useRef<World>({ fleets: fleetFixture(), galaxy: galaxyFixture() });
  const clock = useRef(now);
  clock.current = now;
  const api = useMemo(() => fixtureApi(() => world.current, () => clock.current), []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const o = origin.current;
      setNow(o.server + (Date.now() - o.local) * o.speed);
    }, tick);
    return () => window.clearInterval(timer);
  }, [tick]);
  const changeSpeed = (value: number) => {
    origin.current = { server: clock.current, local: Date.now(), speed: value };
    setSpeed(value);
  };

  return <div className="proto-root" data-direction={direction}>
    <header className="proto-bar">
      <div><p className="proto-kicker">Echosphere · prototype UX03</p>
        <h1>Envoyer une flotte depuis la carte</h1></div>
      <p className="proto-banner" role="note">Données fictives explicites, aucune commande envoyée au serveur.</p>
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
    </header>
    <main className="proto-main"><CommandMap initial={world.current} api={api} now={now} routeMode={routeMode} /></main>
  </div>;
}
