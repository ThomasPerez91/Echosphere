import { useEffect, useMemo, useRef, useState } from "react";
import type { MissionView } from "../fleet/api";
import { MissionRefused } from "./api";
import type { MissionApi } from "./api";
import { MissionPlanner } from "./MissionPlanner";
import type { QuoteState } from "./copy";
import { StarMap } from "./StarMap";
import type { MapFilter } from "./StarMap";
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
  const [filter, setFilter] = useState<MapFilter>("all");
  const [showRoutes, setShowRoutes] = useState(true);
  const [showNames, setShowNames] = useState(true);
  const [search, setSearch] = useState("");
  const [searchMiss, setSearchMiss] = useState(false);
  const [tab, setTab] = useState<"overview" | "planets" | "routes">("overview");

  const target = selected ? world.galaxy.systems.find((s) => s.id === selected) ?? null : null;
  const ref = selected ? world.fleets.systems?.find((s) => s.id === selected) : undefined;
  const available = selected ? offers(world, selected) : [];
  const candidates = plan && selected ? eligibleFleets(world, plan.offer.kind, selected) : [];
  const fleet = plan?.fleet ? stationed(world).find((f) => f.id === plan.fleet) ?? null : null;
  const missions = (world.fleets.missions ?? []).filter((m) => m.status !== "completed");
  const lines = useMemo(() => fleetLines(world, now), [world, now]);
  const own = (id: string) => !!world.galaxy.systems.find((x) => x.id === id)?.observation?.own_colony_ids.length;
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

  const select = (id: string) => { setSelected(id); setPlan(null); setNotice(null); setTab("overview"); };
  // Search only among this Empire's named systems (a detected signal has no name to find).
  const find = (text: string) => {
    const q = text.trim().toLocaleLowerCase("fr");
    const hit = q ? world.galaxy.systems.find((x) => x.state !== "DETECTED" && x.name?.toLocaleLowerCase("fr").includes(q)) : undefined;
    setSearchMiss(!!q && !hit);
    if (hit) select(hit.id);
  };
  const neighbours = selected ? world.galaxy.routes.filter((r) => r.a_id === selected || r.b_id === selected)
    .map((r) => (r.a_id === selected ? r.b_id : r.a_id)) : [];
  const filters: [MapFilter, string][] = [["all", "Tous"], ["known", "Systèmes connus"], ["own", "Mes colonies"], ["fleets", "Mes flottes"], ["signals", "Signaux"]];
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
    <header className="proto-page-head">
      <div><h1 id="proto-map-title" className="proto-page-title">Galaxie</h1>
        <p><strong>Carte stratégique</strong> des systèmes connus de votre Empire. Touchez un système : ce que vous en savez et les actions possibles s’affichent.</p></div>
      <form className="proto-search" role="search" onSubmit={(e) => { e.preventDefault(); find(search); }}>
        <label className="visually-hidden" htmlFor="proto-search-input">Rechercher un système connu</label>
        <input id="proto-search-input" type="search" placeholder="Rechercher un système…" value={search}
          onChange={(e) => { setSearch(e.target.value); setSearchMiss(false); }} aria-describedby="proto-search-help" />
        <button type="submit" className="button">Chercher</button>
        <span id="proto-search-help" className="proto-help" aria-live="polite">{searchMiss ? "Aucun système connu de ce nom." : ""}</span>
      </form>
    </header>
    <section className="proto-map-panel" aria-labelledby="proto-map-title">
      <div className="proto-map-tools">
        <div className="proto-filters" role="group" aria-label="Filtrer la carte">
          {filters.map(([id, label]) => <button key={id} type="button" className={`proto-filter${filter === id ? " is-active" : ""}`}
            aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}
        </div>
        <div className="proto-switches">
          {([["Routes", showRoutes, setShowRoutes], ["Noms", showNames, setShowNames]] as const).map(([label, on, set]) =>
            <button key={label} type="button" role="switch" aria-checked={on} className="proto-switch" onClick={() => set(!on)}>
              {label}<span className="proto-switch-track" aria-hidden="true"><span /></span></button>)}
        </div>
      </div>
      <StarMap world={world} selected={selected} onSelect={select} missions={missions} now={now} paths={paths}
        filter={filter} showRoutes={showRoutes} showNames={showNames}
        preview={plan && fleet?.system && selected ? { from: fleet.system.id, to: selected, path: quote.status === "ready" ? quote.quote.path : undefined } : null} />
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
        : <section className="proto-card proto-system-card" aria-labelledby="proto-system-title">
          <div className={`proto-hero proto-hero--${own(target.id) ? "own" : target.state.toLowerCase()}`}>
            <span className="proto-hero-star" aria-hidden="true">✦</span>
            <div><h2 id="proto-system-title">{systemName(world, target.id)}</h2>
              <p className="proto-kicker">{target.state === "DETECTED" ? "Signal détecté" : target.state === "MONITORED" ? "Système surveillé" : "Système cartographié"}</p>
              {own(target.id) && <span className="proto-chip proto-chip--own">★ Votre colonie</span>}</div>
          </div>
          <div className="proto-tabs" role="tablist" aria-label="Informations du système">
            {([["overview", "Aperçu"], ["planets", `Planètes (${target.state === "DETECTED" ? "?" : (ref?.planets ?? []).length})`], ["routes", `Routes (${neighbours.length})`]] as const).map(([id, label]) =>
              <button key={id} type="button" role="tab" id={`proto-tab-${id}`} aria-selected={tab === id} aria-controls={`proto-tabpanel-${id}`}
                className="proto-tab" onClick={() => setTab(id)}>{label}</button>)}
          </div>
          {tab === "overview" && <div role="tabpanel" id="proto-tabpanel-overview" aria-labelledby="proto-tab-overview">
            <div className="proto-tiles">
              <div><span>Connaissance</span><strong>{target.state === "DETECTED" ? "Détecté" : target.state === "MONITORED" ? "Surveillé" : "Cartographié"}</strong></div>
              <div><span>Vos flottes ici</span><strong>{fleetsHere.length}</strong></div>
            </div>
            {target.state === "DETECTED" ? <p>Existence et position approximative seulement. Nom, planètes et occupants restent inconnus tant qu’une sonde ne l’a pas cartographié.</p>
              : <p className="proto-help">{(ref?.planets ?? []).length} planète(s) connue(s){fleetsHere.length ? ` · ${fleetsHere.map((f) => f.name).join(", ")}` : ""}.</p>}
            <h3>Actions possibles</h3>
            {available.length === 0 ? <p>Aucune action de flotte possible ici.</p> : <ul className="proto-actions">{available.map((o, i) =>
              <li key={`${o.kind}-${o.planet ?? ""}`}>
                <button type="button" className={`button proto-action${i === available.findIndex((x) => !x.reason) ? " button--primary" : ""}`} disabled={!!o.reason}
                  aria-describedby={`hint-${o.kind}-${o.planet ?? "s"}`} onClick={() => start(o)}>{o.label}</button>
                <p id={`hint-${o.kind}-${o.planet ?? "s"}`} className="proto-help">{o.reason ?? o.hint}</p>
              </li>)}</ul>}
          </div>}
          {tab === "planets" && <div role="tabpanel" id="proto-tabpanel-planets" aria-labelledby="proto-tab-planets">
            {target.state === "DETECTED" ? <p>Structure inconnue : cartographiez ce signal.</p>
              : <ul className="proto-planets" aria-label="Planètes connues">{(ref?.planets ?? []).map((p) =>
                <li key={p.id}><span className="proto-planet-orb" aria-hidden="true" /><div><strong>{p.name}</strong>
                  <span>{p.sector_capacity} secteurs · {p.orbital_capacity} orbitaux</span></div>
                  <span className={`proto-chip${p.colony_id ? " proto-chip--own" : ""}`}>{p.colony_id ? "Votre colonie" : "Occupation inconnue"}</span></li>)}
                {(ref?.planets ?? []).length === 0 && <li>Aucune planète connue.</li>}</ul>}
          </div>}
          {tab === "routes" && <div role="tabpanel" id="proto-tabpanel-routes" aria-labelledby="proto-tab-routes">
            <ul className="proto-routes" aria-label="Routes connues">{neighbours.map((id) =>
              <li key={id}><button type="button" className="button proto-ghost" onClick={() => select(id)}>
                {systemName(world, target.id)} ↔ {systemName(world, id)}</button></li>)}</ul>
            <p className="proto-help">Seules vos routes connues sont listées ; les distances ne sont pas transmises par le serveur.</p>
          </div>}
        </section>}

    </div>
  </div>;
}
