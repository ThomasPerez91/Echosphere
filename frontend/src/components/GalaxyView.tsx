import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from "react";
import { useGalaxy } from "../hooks/useGalaxy";
import type { KnownSystem, Mission, Option, Projection } from "../galaxy/api";
import type { Amounts } from "../colony/api";
import { duration, exactUnits, resourceKeys, resourceLabels, time } from "../colony/format";
import { Badge, Button, Panel } from "./ui";

const stateLabels = { DETECTED: "Détecté", MAPPED: "Cartographié", MONITORED: "Surveillé" };
const messages: Record<string, string> = {
  accepted: "Expédition acceptée par le serveur. Elle se poursuit même navigateur fermé.",
  galaxy_unavailable: "La galaxie n’est pas disponible pour cet Empire dans cet univers.",
  exploration_active: "La capacité d’expédition de l’Empire est déjà engagée.",
  insufficient_resources: "La colonie source ne dispose pas des ressources nécessaires.",
  permission_denied: "Permission manquante pour cette action.",
  destination_mapped: "Ce système est déjà cartographié.",
  destination_unreachable: "Aucun chemin connu ne permet d’atteindre ce système.",
  system_not_found: "Ce système n’est pas accessible.",
  empire_not_found: "Cet Empire n’est pas accessible.",
  colony_not_found: "Cette colonie source n’est pas accessible.",
  idempotency_conflict: "Intention déjà utilisée pour une autre expédition. Actualisez.",
  exploration_busy: "Événement d’exploration en attente de reprise. Réessayez plus tard.",
  colony_busy: "Le serveur est momentanément occupé. Réessayez plus tard.",
  authentication_required: "Session expirée. Retournez au lobby.",
  invalid_response: "Réponse du serveur inattendue. Actualisez.",
  unavailable: "Le serveur Game est momentanément injoignable.",
};
const message = (code: string) => messages[code] ?? "Action indisponible pour le moment.";

type Box = { x: number; y: number; width: number; height: number };
export type GalaxyContext = { empire: string; selected: string; view: Box | null };
const MIN_SIZE = 150;
const MAX_SIZE = 2400;

function fit(systems: KnownSystem[]): Box {
  if (!systems.length) return { x: 0, y: 0, width: 1000, height: 1000 };
  const xs = systems.map((s) => s.x);
  const ys = systems.map((s) => s.y);
  const width = Math.max(400, Math.max(...xs) - Math.min(...xs) + 240);
  const height = Math.max(400, Math.max(...ys) - Math.min(...ys) + 240);
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
  const cy = (Math.max(...ys) + Math.min(...ys)) / 2;
  return { x: cx - width / 2, y: cy - height / 2, width, height };
}

function zoomed(box: Box, factor: number, cx = box.x + box.width / 2, cy = box.y + box.height / 2): Box {
  const scale = Math.min(MAX_SIZE / box.width, Math.max(MIN_SIZE / box.width, factor));
  return {
    x: cx - (cx - box.x) * scale,
    y: cy - (cy - box.y) * scale,
    width: box.width * scale,
    height: box.height * scale,
  };
}

/** Display-only fan-out of DETECTED markers sharing one approximate cell; no hidden position used. */
function layout(systems: KnownSystem[], unit: number) {
  const cells = new Map<string, KnownSystem[]>();
  for (const s of systems) {
    if (s.state !== "DETECTED") continue;
    const key = `${s.x}:${s.y}`;
    cells.set(key, [...(cells.get(key) ?? []), s]);
  }
  const points = new Map<string, { x: number; y: number; shared: boolean }>();
  for (const s of systems) {
    const group = s.state === "DETECTED" ? cells.get(`${s.x}:${s.y}`)! : [s];
    const index = group.indexOf(s);
    // Vertical first so right-hand labels never overlap; constant on-screen distance.
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / group.length;
    const offset = group.length > 1 ? 20 * unit : 0;
    points.set(s.id, {
      x: s.x + offset * Math.cos(angle),
      y: s.y + offset * Math.sin(angle),
      shared: group.length > 1,
    });
  }
  return points;
}

function labels(p: Projection) {
  let signal = 0;
  return new Map(
    p.systems.map((s) => [s.id, s.name ?? `Signal détecté ${++signal}`] as const),
  );
}

function AmountsView({ value }: { value: Amounts }) {
  return (
    <ul className="cost">
      {resourceKeys.map((r) => (
        <li key={r}>
          {exactUnits(value[r])} {resourceLabels[r]}
        </li>
      ))}
    </ul>
  );
}

function Glyph({ state, own = false }: { state: KnownSystem["state"]; own?: boolean }) {
  return (
    <svg className={`galaxy-glyph galaxy-node--${state.toLowerCase()}`} viewBox="-12 -12 24 24" aria-hidden="true">
      {state === "MONITORED" && <circle r={10} className="galaxy-ring" />}
      <circle r={6} className="galaxy-star" />
      {own && <path d="M0 -3 L1 -1 L3 0 L1 1 L0 3 L-1 1 L-3 0 L-1 -1 Z" className="galaxy-own" />}
    </svg>
  );
}

function Countdown({ mission, serverTime, receivedAt }: { mission: Mission; serverTime: string; receivedAt: number }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const start = Date.parse(mission.started_at);
  const end = Date.parse(mission.due_at);
  const server = Date.parse(serverTime) + now - receivedAt;
  const percent = Math.max(0, Math.min(100, Math.floor(((server - start) * 100) / Math.max(1, end - start))));
  const left = Math.max(0, Math.ceil((end - server) / 1000));
  return (
    <div className="queue-progress">
      <div className="meter" role="progressbar" aria-label="Avancement estimé de l’expédition"
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <span>{left ? `${duration(String(left * 1e6))} restantes (estimation locale)` : "Échéance atteinte, confirmation du serveur attendue."}</span>
    </div>
  );
}

export function GalaxyView({
  universe,
  enabled,
  csrf,
  onSessionLost,
  onEconomyChanged,
  initialContext,
  onContextChange,
}: {
  universe: string;
  enabled: boolean;
  csrf?: string;
  onSessionLost: () => void;
  onEconomyChanged?: () => void;
  initialContext?: GalaxyContext;
  onContextChange?: (context: GalaxyContext) => void;
}) {
  const galaxy = useGalaxy(universe, enabled, csrf, onSessionLost, initialContext?.empire);
  const p = galaxy.projection;
  const [selected, setSelected] = useState("");
  const [source, setSource] = useState("");
  const [view, setView] = useState<Box | null>(null);
  const [confirming, setConfirming] = useState<Option | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const feedbackRef = useRef<HTMLParagraphElement>(null);
  const map = useRef<SVGSVGElement>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const drag = useRef<{ pointer: number; x: number; y: number; box: Box } | null>(null);

  const contextChanged = useRef(onContextChange);
  contextChanged.current = onContextChange;
  const initial = useRef(initialContext);
  const empireId = p?.empire.id;
  useEffect(() => {
    if (!empireId) return;
    const saved = initial.current?.empire === empireId ? initial.current : undefined;
    setSelected(saved?.selected ?? "");
    setSource("");
    setView(saved?.view ?? null);
    setConfirming(null);
  }, [empireId]);

  useEffect(() => {
    if (p && selected && view) contextChanged.current?.({ empire: p.empire.id, selected, view });
  }, [p, selected, view]);

  useEffect(() => {
    if (!p) return;
    setView((old) => old ?? fit(p.systems));
    setSelected((old) => {
      if (old && p.systems.some((s) => s.id === old)) return old;
      // Default to the Empire's own monitored system, never to a guessed target.
      return p.systems.find((s) => s.observation?.own_colony_ids.length)?.id ?? "";
    });
  }, [p]);

  useEffect(() => {
    if (confirming) dialog.current?.showModal();
    else dialog.current?.close();
  }, [confirming]);

  useEffect(() => {
    if (galaxy.feedback) feedbackRef.current?.focus();
  }, [galaxy.feedback]);

  const mounted = p !== null;
  // Wheel zoom must be non-passive to keep the page from scrolling while the pointer is on the map.
  useEffect(() => {
    const element = map.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      const box = viewRef.current;
      if (!box) return;
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      const scale = Math.max(box.width / rect.width, box.height / rect.height);
      const cx = box.x + box.width / 2 + (event.clientX - rect.left - rect.width / 2) * scale;
      const cy = box.y + box.height / 2 + (event.clientY - rect.top - rect.height / 2) * scale;
      setView(zoomed(box, event.deltaY > 0 ? 1.15 : 1 / 1.15, cx, cy));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => element.removeEventListener("wheel", wheel);
  }, [mounted]);

  const box = view ?? (p ? fit(p.systems) : null);
  const unit = box ? Math.max(box.width, box.height) / 640 : 1;
  const points = useMemo(() => (p ? layout(p.systems, unit) : new Map()), [p, unit]);
  const names = useMemo(() => (p ? labels(p) : new Map<string, string>()), [p]);

  if (!enabled) return null;
  if (galaxy.phase === "loading" || galaxy.phase === "idle")
    return <p className="panel" role="status">Chargement des connaissances de l’Empire…</p>;
  if (galaxy.phase === "empty")
    return <Panel title="Galaxie"><p>Aucun Empire ne vous donne accès à la galaxie dans cet univers.</p></Panel>;
  if (!p)
    return (
      <Panel title="Galaxie indisponible">
        <p role="alert">{message(galaxy.error ?? "unavailable")}</p>
        <Button onClick={galaxy.refresh}>Réessayer</Button>
      </Panel>
    );

  const system = p.systems.find((s) => s.id === selected);
  const active = p.missions.find((m) => m.status === "active");
  const own = (s: KnownSystem) => !!s.observation?.own_colony_ids.length;
  const choices = p.options.filter((o) => o.destination_id === selected);
  const option = choices.find((o) => o.colony_id === source) ?? choices[0];
  const sourceName = (id: string) => p.sources.find((s) => s.id === id)?.name ?? "Colonie";
  if (!box) return null;
  const canStart = ["galaxy.read", "exploration.read", "exploration.start", "colony.read"].every((r) =>
    p.permissions.includes(r),
  );

  const pan = (dx: number, dy: number) =>
    setView((old) => (old ? { ...old, x: old.x + old.width * dx, y: old.y + old.height * dy } : old));
  const onMapKey = (event: ReactKeyboardEvent<SVGSVGElement>) => {
    const keys: Record<string, () => void> = {
      ArrowLeft: () => pan(-0.1, 0),
      ArrowRight: () => pan(0.1, 0),
      ArrowUp: () => pan(0, -0.1),
      ArrowDown: () => pan(0, 0.1),
      "+": () => setView((old) => old && zoomed(old, 1 / 1.25)),
      "=": () => setView((old) => old && zoomed(old, 1 / 1.25)),
      "-": () => setView((old) => old && zoomed(old, 1.25)),
      "0": () => setView(fit(p.systems)),
    };
    if (keys[event.key]) {
      event.preventDefault();
      keys[event.key]();
    }
  };
  const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if ((event.target as Element).closest(".galaxy-node") || !view) return;
    drag.current = { pointer: event.pointerId, x: event.clientX, y: event.clientY, box: view };
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // Capture is a convenience; panning still follows moves over the map without it.
    }
  };
  const onPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    const start = drag.current;
    if (!start || start.pointer !== event.pointerId) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const scale = Math.max(start.box.width / rect.width, start.box.height / rect.height);
    setView({
      ...start.box,
      x: start.box.x - (event.clientX - start.x) * scale,
      y: start.box.y - (event.clientY - start.y) * scale,
    });
  };
  const endDrag = () => {
    drag.current = null;
  };
  const confirm = async () => {
    if (!confirming) return;
    const ok = await galaxy.start({ colony_id: confirming.colony_id, destination_id: confirming.destination_id });
    setConfirming(null);
    if (ok) onEconomyChanged?.();
  };

  return (
    <div className="galaxy-screen">
      <div className="colony-toolbar">
        {galaxy.empires.length > 1 ? (
          <label className="galaxy-field">
            Empire
            <select value={galaxy.selectedEmpire} disabled={galaxy.pending} onChange={(e) => galaxy.select(e.target.value)}>
              {galaxy.empires.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select>
          </label>
        ) : (
          <span className="panel-meta">Empire : {p.empire.name}</span>
        )}
        <span className="panel-meta">Connaissances au {time(p.server_time)}</span>
        <Button onClick={galaxy.refresh} disabled={galaxy.pending}>Actualiser</Button>
      </div>
      <div className="feedback-zone" aria-live="polite">
        {galaxy.feedback && (
          <div className={`feedback feedback--${galaxy.feedback.tone}`}>
            <p ref={feedbackRef} tabIndex={-1}>
              {galaxy.feedback.tone === "unknown"
                ? "Résultat non confirmé. Relancez la même expédition : la même intention est réutilisée, sans double paiement."
                : message(galaxy.feedback.code)}
            </p>
            <Button onClick={galaxy.dismiss}>Fermer</Button>
          </div>
        )}
        {galaxy.error && p && <p className="notice" role="alert">{message(galaxy.error)}</p>}
        {galaxy.awaiting && (
          <p className="notice">L’échéance est passée ; le serveur n’a pas encore confirmé l’achèvement. Actualisez plus tard.</p>
        )}
      </div>

      <div className="galaxy-layout">
        <section className="panel galaxy-map-panel" aria-labelledby="galaxy-map-title">
          <div className="panel-head">
            <h2 id="galaxy-map-title">Carte des connaissances</h2>
            <div className="galaxy-controls" role="group" aria-label="Commandes de la carte">
              <Button aria-label="Zoom avant" onClick={() => setView((old) => old && zoomed(old, 1 / 1.25))}>+</Button>
              <Button aria-label="Zoom arrière" onClick={() => setView((old) => old && zoomed(old, 1.25))}>−</Button>
              <Button onClick={() => setView(fit(p.systems))}>Recentrer</Button>
            </div>
          </div>
          <svg
            ref={map}
            className="galaxy-map"
            role="group"
            tabIndex={0}
            aria-label="Carte des systèmes connus. Flèches pour déplacer, plus et moins pour zoomer, zéro pour recentrer."
            aria-describedby="galaxy-legend"
            viewBox={`${box.x} ${box.y} ${box.width} ${box.height}`}
            onKeyDown={onMapKey}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          >
            <rect x={box.x} y={box.y} width={box.width} height={box.height} className="galaxy-backdrop" />
            {p.routes.map((r) => {
              const a = points.get(r.a_id)!;
              const b = points.get(r.b_id)!;
              const partial = [r.a_id, r.b_id].some((id) => p.systems.find((s) => s.id === id)?.state === "DETECTED");
              return (
                <line key={r.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  className={partial ? "galaxy-route galaxy-route--partial" : "galaxy-route"}
                  strokeWidth={1.5 * unit} strokeDasharray={partial ? `${6 * unit} ${5 * unit}` : undefined} />
              );
            })}
            {p.systems.map((s) => {
              const at = points.get(s.id)!;
              const name = names.get(s.id)!;
              return (
                <g key={s.id} role="button" tabIndex={0}
                  className={`galaxy-node galaxy-node--${s.state.toLowerCase()}${selected === s.id ? " is-selected" : ""}`}
                  aria-pressed={selected === s.id}
                  aria-label={`${name}, ${stateLabels[s.state]}${own(s) ? ", votre colonie" : ""}${at.shared ? ", position approximative partagée" : ""}`}
                  onClick={() => setSelected(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      e.stopPropagation();
                      setSelected(s.id);
                    }
                  }}>
                  <circle cx={at.x} cy={at.y} r={22 * unit} className="galaxy-hit" />
                  {selected === s.id && <circle cx={at.x} cy={at.y} r={17 * unit} className="galaxy-selection" strokeWidth={2 * unit} />}
                  {s.state === "MONITORED" && <circle cx={at.x} cy={at.y} r={12 * unit} className="galaxy-ring" strokeWidth={1.5 * unit} />}
                  <circle cx={at.x} cy={at.y} r={(s.state === "DETECTED" ? 6 : 7.5) * unit} className="galaxy-star"
                    strokeWidth={1.5 * unit} strokeDasharray={s.state === "DETECTED" ? `${3 * unit} ${2 * unit}` : undefined} />
                  <text x={at.x + 14 * unit} y={at.y + 4.5 * unit} fontSize={12.5 * unit}>{name}</text>
                </g>
              );
            })}
          </svg>
          <ul id="galaxy-legend" className="galaxy-legend" aria-label="Légende">
            <li><Glyph state="DETECTED" /> Détecté : existence et position approximative</li>
            <li><Glyph state="MAPPED" /> Cartographié : structure connue</li>
            <li><Glyph state="MONITORED" own /> Surveillé : observation actuelle de votre colonie</li>
            <li><span className="galaxy-dash" aria-hidden="true" /> Route vers un système seulement détecté</li>
          </ul>
          <p className="galaxy-note">Seules les connaissances de cet Empire sont affichées ; les systèmes inconnus ne sont jamais transmis.</p>
        </section>

        <aside className="panel galaxy-detail" aria-labelledby="galaxy-detail-title" aria-live="polite">
          {!system ? (
            <><h2 id="galaxy-detail-title">Détail</h2><p>Sélectionnez un système sur la carte ou dans la liste.</p></>
          ) : (
            <>
              <div className="panel-head">
                <h2 id="galaxy-detail-title">{names.get(system.id)}</h2>
                <Badge tone={system.state === "DETECTED" ? "neutral" : "accent"}>{stateLabels[system.state]}</Badge>
              </div>
              {system.state === "DETECTED" ? (
                <>
                  <p>Signal détecté le {time(system.discovered_at)}. Position approximative ; nom, planètes et capacités inconnus.</p>
                  {galaxy.pending ? <p role="status">Commande en cours…</p> : null}
                  {!canStart && <p className="reason">Droits Galaxie, Exploration et lecture Colonie requis pour lancer une expédition.</p>}
                  {choices.length > 1 && (
                    <label className="galaxy-field">
                      Colonie source
                      <select value={option?.colony_id ?? ""} disabled={galaxy.pending} onChange={(e) => setSource(e.target.value)}>
                        {choices.map((o) => <option key={o.colony_id} value={o.colony_id}>{sourceName(o.colony_id)}</option>)}
                      </select>
                    </label>
                  )}
                  {option ? (
                    <div className="option-card option-card--compact">
                      <h3>Expédition d’étude</h3>
                      <p className="option-meta">Depuis {sourceName(option.colony_id)} · {option.hops} saut{option.hops > 1 ? "s" : ""} aller · {duration(option.duration_us)} aller-retour et étude</p>
                      <AmountsView value={option.cost} />
                      {option.reason && <p className="reason">{message(option.reason)}</p>}
                      <button ref={trigger} type="button" className="button button--primary" disabled={galaxy.pending || !!option.reason}
                        onClick={() => setConfirming(option)}>
                        Préparer l’expédition
                      </button>
                    </div>
                  ) : (
                    canStart && <p>Aucun chemin connu depuis vos colonies autorisées.</p>
                  )}
                </>
              ) : (
                <>
                  <p>
                    {system.state === "MONITORED" && system.last_seen_at
                      ? `Observation actuelle par votre présence locale (${time(system.last_seen_at)}).`
                      : system.last_seen_at
                        ? `Structure connue ; dernière observation dynamique le ${time(system.last_seen_at)}.`
                        : `Structure cartographiée le ${time(system.mapped_at!)} ; aucune surveillance actuelle.`}
                  </p>
                  {own(system) && <p><Badge tone="accent">Votre colonie</Badge></p>}
                  <a className="button button--primary" href={`#universe/${universe}/galaxy/system/${p.empire.id}/${system.id}`}>Voir le système</a>
                  <h3 className="galaxy-subtitle">Planètes connues ({system.planets!.length})</h3>
                  <ul className="galaxy-planets">
                    {system.planets!.map((planet) => (
                      <li key={planet.id}><strong>{planet.name}</strong><span>{planet.sector_capacity} secteurs · {planet.orbital_capacity} orbitaux</span></li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </aside>
      </div>

      <section className="panel" aria-labelledby="galaxy-list-title">
        <div className="panel-head">
          <h2 id="galaxy-list-title">Systèmes connus</h2>
          <span className="panel-meta">{p.systems.length} connus</span>
        </div>
        <ul className="galaxy-list">
          {p.systems.map((s) => (
            <li key={s.id}>
              <button type="button" className="galaxy-list-item" aria-pressed={selected === s.id} onClick={() => setSelected(s.id)}>
                <Glyph state={s.state} own={own(s)} />
                <span>{names.get(s.id)}</span>
                <span className="panel-meta">{stateLabels[s.state]}{s.planets ? ` · ${s.planets.length} planètes` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel" aria-labelledby="galaxy-missions-title">
        <div className="panel-head">
          <h2 id="galaxy-missions-title">Expéditions</h2>
          <span className="panel-meta">{active ? "Capacité engagée" : "Capacité disponible"}</span>
        </div>
        {!p.permissions.includes("exploration.read") ? (
          <p>Le droit de lecture Exploration est requis pour consulter les expéditions.</p>
        ) : !p.missions.length ? (
          <p>Aucune expédition pour cet Empire.</p>
        ) : (
          <ul className="queue-list">
            {p.missions.map((m) => (
              <li key={m.id} className="queue-item">
                <div className="queue-title">
                  <strong>{names.get(m.destination_id)}</strong>
                  <Badge tone={m.status === "active" ? "warning" : "accent"}>{m.status === "active" ? "En cours" : "Terminée"}</Badge>
                  <span>Échéance {time(m.due_at)}</span>
                </div>
                {m.status === "active" && (
                  <Countdown mission={m} serverTime={p.server_time} receivedAt={galaxy.receivedAt} />
                )}
                {m.report && (
                  <details>
                    <summary>Rapport d’exploration</summary>
                    <p>
                      {m.report.discoveries.system.name} cartographié : {m.report.discoveries.system.planets?.length ?? 0} planète(s),{" "}
                      {m.report.discoveries.neighbors.filter((n) => n.new).length} nouveau(x) signal(aux) détecté(s),{" "}
                      {m.report.discoveries.path.length} saut(s) aller.
                    </p>
                    <p className="panel-meta">Observé à l’échéance {time(m.report.observed_at)} · traité par le serveur {time(m.report.processed_at)}</p>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <dialog ref={dialog} className="research-dialog" aria-labelledby="expedition-title"
        onClose={() => { setConfirming(null); trigger.current?.focus(); }}>
        {confirming && (
          <>
            <h2 id="expedition-title">Engager l’expédition vers {names.get(confirming.destination_id)} ?</h2>
            <p>Colonie source : {sourceName(confirming.colony_id)} · {confirming.hops} saut{confirming.hops > 1 ? "s" : ""} aller · durée {duration(confirming.duration_us)}</p>
            <AmountsView value={confirming.cost} />
            <p>Le coût est débité immédiatement et en totalité. Aucune annulation, aucun rappel, aucun remboursement. Le résultat est confirmé par le serveur à l’échéance, même navigateur fermé.</p>
            <div className="confirm">
              <Button onClick={() => setConfirming(null)}>Retour</Button>
              <Button className="button--primary" disabled={galaxy.pending} onClick={() => void confirm()}>Confirmer l’expédition</Button>
            </div>
          </>
        )}
      </dialog>
    </div>
  );
}
