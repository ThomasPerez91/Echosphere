import { useEffect, useMemo, useRef, useState } from "react";
import type { MissionView } from "../fleet/api";
import { MissionRefused } from "./api";
import type { MissionApi } from "./api";
import { MissionPlanner } from "./MissionPlanner";
import type { QuoteState } from "./MissionPlanner";
import { StarMap } from "./StarMap";
import { actionLabels, eligibleFleets, engageable, fleetLines, offers, stationed, systemName } from "./model";
import type { ActionOffer, World } from "./model";

type Plan = { offer: ActionOffer; fleet: string | null; units: Record<string, number> };

/**
 * UX03 Galaxy → Fleet → Mission, driven from the map:
 * select a system → see what is known and what can be done → pick an action → pick a fleet →
 * adjust units (all suitable units by default) → server summary (path, duration, cost, risks)
 * → confirm → the mission moves on the map and in the fleet list.
 */
export function CommandMap({ initial, api, now, routeMode }: {
  initial: World; api: MissionApi; now: number; routeMode: "contract" | "extension";
}) {
  const [world, setWorld] = useState(initial);
  const [selected, setSelected] = useState<string | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [quote, setQuote] = useState<QuoteState>({ status: "idle" });
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [paths, setPaths] = useState<Record<string, string[] | undefined>>({});
  const panel = useRef<HTMLDivElement>(null);

  const target = selected ? world.galaxy.systems.find((s) => s.id === selected) ?? null : null;
  const ref = selected ? world.fleets.systems?.find((s) => s.id === selected) : undefined;
  const available = selected ? offers(world, selected) : [];
  const candidates = plan && selected ? eligibleFleets(world, plan.offer.kind, selected) : [];
  const fleet = plan?.fleet ? stationed(world).find((f) => f.id === plan.fleet) ?? null : null;
  const missions = (world.fleets.missions ?? []).filter((m) => m.status !== "completed");
  const lines = useMemo(() => fleetLines(world, now), [world, now]);
  const fleetsHere = selected ? stationed(world).filter((f) => f.system?.id === selected) : [];
  const planKey = plan && fleet && selected ? JSON.stringify([plan.offer.kind, plan.offer.planet, fleet.id, selected, plan.units]) : null;

  // The server summary follows the intention: any change cancels the request in flight.
  useEffect(() => {
    if (!plan || !fleet || !selected || !Object.values(plan.units).some((n) => n > 0)) { setQuote({ status: "idle" }); return; }
    const controller = new AbortController();
    setQuote({ status: "loading" });
    const units = Object.fromEntries(Object.entries(plan.units).filter(([, n]) => n > 0));
    api.preview({ fleet_id: fleet.id, kind: plan.offer.kind, units,
      ...(plan.offer.planet ? { target_planet_id: plan.offer.planet } : { destination_id: selected }) }, controller.signal)
      .then((q) => setQuote({ status: "ready", quote: routeMode === "contract" ? { ...q, path: undefined } : q }))
      .catch((e) => { if (!controller.signal.aborted) setQuote({ status: "error", code: e instanceof MissionRefused ? e.code : "unavailable" }); });
    return () => controller.abort();
    // planKey captures every field of the intention.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planKey, routeMode]);

  const select = (id: string) => { setSelected(id); setPlan(null); setNotice(null); };
  const start = (offer: ActionOffer) => {
    if (!selected) return;
    const choices = eligibleFleets(world, offer.kind, selected);
    const only = choices.length === 1 ? choices[0] : null; // a single candidate is pre-selected
    setPlan({ offer, fleet: only?.id ?? null, units: only ? engageable(world, only, offer.kind) : {} });
    setNotice(null);
  };
  const cancel = () => { setPlan(null); window.setTimeout(() => panel.current?.querySelector<HTMLElement>(".proto-action")?.focus(), 0); };
  const chooseFleet = (id: string) => {
    const f = stationed(world).find((x) => x.id === id)!;
    setPlan((p) => p && { ...p, fleet: id, units: engageable(world, f, p.offer.kind) });
  };

  async function confirm() {
    if (!plan || !fleet || quote.status !== "ready" || !selected) return;
    setPending(true);
    try {
      const units = Object.fromEntries(Object.entries(plan.units).filter(([, n]) => n > 0));
      const mission: MissionView = await api.launch({ fleet_id: fleet.id, kind: plan.offer.kind, units,
        ...(plan.offer.planet ? { target_planet_id: plan.offer.planet } : { destination_id: selected }) }, quote.quote);
      // Local echo of the server's answer; a real client re-reads the fleet projection.
      setWorld((w) => ({ ...w, fleets: { ...w.fleets,
        missions: [mission, ...(w.fleets.missions ?? [])],
        fleets: (w.fleets.fleets ?? []).map((f) => f.id === fleet.id ? { ...f, status: "MOVING" as const, system: null, mission_id: mission.id } : f) } }));
      setPaths((p) => ({ ...p, [mission.id]: quote.quote.path }));
      setPlan(null);
      setNotice(`${actionLabels[mission.kind]} lancé : ${fleet.name} arrive à ${systemName(world, mission.destination?.id)} en ${quote.quote.hops} saut(s). Suivez-la sur la carte et dans « Vos flottes ».`);
    } catch (e) {
      setQuote({ status: "error", code: e instanceof MissionRefused ? e.code : "unavailable" });
    } finally {
      setPending(false);
    }
  }

  return <div className="proto-command">
    <section className="proto-map-panel" aria-labelledby="proto-map-title">
      <div className="proto-map-head"><h2 id="proto-map-title">Galaxie</h2>
        <p className="proto-help">Sélectionnez un système : ses informations connues et les actions possibles s’affichent.</p></div>
      <StarMap world={world} selected={selected} onSelect={select} missions={missions} now={now} paths={paths}
        preview={plan && fleet?.system && selected ? { from: fleet.system.id, to: selected, path: quote.status === "ready" ? quote.quote.path : undefined } : null} />
      <ul className="proto-legend" aria-label="Légende">
        <li><span className="proto-dot proto-dot--known" />Système cartographié</li>
        <li><span className="proto-dot proto-dot--signal" />Signal détecté (inconnu)</li>
        <li><span className="proto-dot proto-dot--own" />Votre colonie</li>
        <li><span className="proto-dot proto-dot--fleet" />Vos flottes stationnées</li>
        <li><span className="proto-dot proto-dot--mission" />Mission en cours</li>
      </ul>
      <details className="proto-list">
        <summary>Liste des systèmes connus</summary>
        <ul>{world.galaxy.systems.map((s) => <li key={s.id}>
          <button type="button" className="button proto-ghost" aria-pressed={selected === s.id} onClick={() => select(s.id)}>
            {systemName(world, s.id)}{s.state === "DETECTED" ? " (position approximative)" : ""}</button></li>)}</ul>
      </details>
    </section>

      <section className="proto-card proto-dock" aria-labelledby="proto-dock-title">
        <h2 id="proto-dock-title">Vos flottes</h2>
        <ul>{lines.map((l) => <li key={l.id}>
          <div><strong>{l.name}</strong> <span className="proto-chip">{l.state}</span></div>
          <p className="proto-help">{l.where}{l.destination ? ` → ${l.destination}` : ""} · {l.units} unité(s)</p>
          <button type="button" className="button proto-ghost proto-locate" onClick={() => {
            const f = world.fleets.fleets?.find((x) => x.id === l.id);
            const m = missions.find((x) => x.id === f?.mission_id);
            const id = f?.system?.id ?? m?.destination?.id;
            if (id) select(id);
          }}>Localiser<span className="visually-hidden"> {l.name}</span></button>
        </li>)}</ul>
      </section>

    <div className="proto-side" ref={panel}>
      {notice && <p className="proto-notice" role="status">{notice}</p>}
      {!target ? <section className="proto-card"><h2>Que voulez-vous faire ?</h2>
        <p>Choisissez un système sur la carte. Les signaux détectés peuvent être cartographiés par une sonde ; les systèmes connus peuvent accueillir vos flottes, être colonisés ou attaqués.</p></section>
        : plan ? <MissionPlanner world={world} target={target.id} offer={plan.offer} fleets={candidates} fleet={fleet} units={plan.units}
          quote={quote} routeMode={routeMode} pending={pending} onFleet={chooseFleet} onUnits={(u) => setPlan((p) => p && { ...p, units: u })}
          onConfirm={confirm} onCancel={cancel} />
        : <section className="proto-card" aria-labelledby="proto-system-title">
          <p className="proto-kicker">{target.state === "DETECTED" ? "Signal" : target.state === "MONITORED" ? "Système surveillé" : "Système cartographié"}</p>
          <h2 id="proto-system-title">{systemName(world, target.id)}</h2>
          {target.state === "DETECTED" ? <p>Existence et position approximative seulement. Nom, planètes et occupants restent inconnus tant qu’une sonde ne l’a pas cartographié.</p>
            : <ul className="proto-planets" aria-label="Planètes connues">{(ref?.planets ?? []).map((p) =>
              <li key={p.id}><strong>{p.name}</strong> · {p.sector_capacity} secteurs · {p.orbital_capacity} orbitaux{p.colony_id ? " · votre colonie" : ""}</li>)}
              {(ref?.planets ?? []).length === 0 && <li>Aucune planète connue.</li>}</ul>}
          {fleetsHere.length > 0 && <p className="proto-help">Vos flottes ici : {fleetsHere.map((f) => f.name).join(", ")}.</p>}
          <h3>Actions possibles</h3>
          {available.length === 0 ? <p>Aucune action de flotte possible ici.</p> : <ul className="proto-actions">{available.map((o) =>
            <li key={`${o.kind}-${o.planet ?? ""}`}>
              <button type="button" className="button proto-action" disabled={!!o.reason} aria-describedby={`hint-${o.kind}-${o.planet ?? "s"}`} onClick={() => start(o)}>{o.label}</button>
              <p id={`hint-${o.kind}-${o.planet ?? "s"}`} className="proto-help">{o.reason ?? o.hint}</p>
            </li>)}</ul>}
        </section>}

    </div>
  </div>;
}
