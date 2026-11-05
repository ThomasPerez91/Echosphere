import { useState } from "react";
import { LiveCommandMap } from "../command/LiveCommandMap";
import "../command/command.css";
import { GalaxyView } from "./GalaxyView";
import type { GalaxyContext } from "./GalaxyView";

export type GalaxyMode = "classic" | "command";
const KEY = "echosphere.galaxy.mode";

const stored = (): GalaxyMode => {
  try { return window.localStorage.getItem(KEY) === "classic" ? "classic" : "command"; } catch { return "command"; }
};

/**
 * Galaxy screen (UX05): the command map redrawn after the mockup is the default view; the classic
 * map stays fully functional one click away. The choice is a per-browser convenience only.
 */
export function GalaxyScreen({ universe, universeName, enabled, csrf, onSessionLost, onEconomyChanged, initialContext, onContextChange }: {
  universe: string; universeName?: string; enabled: boolean; csrf: string | undefined; onSessionLost: () => void; onEconomyChanged?: () => void;
  initialContext?: GalaxyContext; onContextChange: (context: GalaxyContext) => void;
}) {
  const [mode, setMode] = useState<GalaxyMode>(stored);
  const choose = (next: GalaxyMode) => {
    setMode(next);
    try { window.localStorage.setItem(KEY, next); } catch { /* storage unavailable: the choice lasts this visit */ }
  };
  if (!enabled) return null;
  const options: [GalaxyMode, string][] = [["command", "Nouvelle carte de commandement"], ["classic", "Carte classique"]];
  const switcher = <div className="galaxy-mode" role="group" aria-label="Affichage de la galaxie">
    {options.map(([id, label]) => <button key={id} type="button" className={`button galaxy-mode-option${mode === id ? " button--primary" : ""}`}
      aria-pressed={mode === id} onClick={() => choose(id)}>{label}</button>)}
  </div>;
  const subtitle = universeName ? `de ${/^univers\b/i.test(universeName) ? "l’" : "l’univers "}${universeName}` : undefined;
  return <>
    {mode === "command"
      ? <LiveCommandMap universe={universe} enabled={enabled} csrf={csrf} onSessionLost={onSessionLost}
        onEconomyChanged={onEconomyChanged} initialEmpire={initialContext?.empire} toolbar={switcher} subtitle={subtitle}
        systemHref={(empire, system) => `#universe/${universe}/galaxy/system/${empire}/${system}`} />
      : <>{switcher}<GalaxyView initialContext={initialContext} onContextChange={onContextChange} universe={universe} enabled={enabled}
        csrf={csrf} onSessionLost={onSessionLost} onEconomyChanged={onEconomyChanged} /></>}
  </>;
}
