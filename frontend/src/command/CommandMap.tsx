import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { FleetView, MissionView } from "../fleet/api";
import { message } from "../fleet/messages";
import { FleetDock } from "./FleetDock";
import { FleetWindow, PickBar } from "./FleetWindow";
import { MissionPlanner } from "./MissionPlanner";
import { StarMap } from "./StarMap";
import { SystemBrief } from "./SystemBrief";
import { ActionGlyph } from "./ActionGlyph";
import { starTint } from "../galaxy/render";
import type { MapFilter } from "./StarMap";
import { defaultUnits, isGarrison, knownHops, missionPosition, opportunityNames, offers, point, stationed, systemName } from "./model";
import type { ActionOffer, FleetLine, World } from "./model";
import { useMissionFlow } from "./useMissionFlow";
import type { CommandFeedback, MissionApi } from "./types";
import { useMedia } from "../shell/useNow";
import { planetImage } from "../shell/assets";

const resourceNames = { alloys: "Alliages", flux: "Flux", data: "Données" } as const;
const whole = (micro?: string) => micro ? Math.floor(Number(micro) / 1_000_000).toLocaleString("fr-FR") : "?";

/** EXP-01: what this Empire knows of a system's opportunities (signatures, then dated details). */
function OpportunityList({ data }: { data: NonNullable<World["galaxy"]["systems"][number]["opportunities"]> }) {
  return <>
    {data.signatures > 0 ? <p><strong>{data.signatures} signature{data.signatures > 1 ? "s" : ""} inexpliquée{data.signatures > 1 ? "s" : ""}</strong> :
      une prospection par une sonde révélera s’il s’agit de gisements ou de curiosités.</p>
      : data.known.length === 0 ? <p>Aucune ressource ni anomalie détectée dans ce système.</p> : null}
    {data.known.length > 0 && <ul className="cmd-opportunities" aria-label="Opportunités connues">{data.known.map((o) => <li key={o.id}>
      <strong>{opportunityNames[o.kind] ?? o.kind}</strong>{o.tier === "remarkable" && <span className="cmd-chip cmd-chip--own">Remarquable</span>}
      <span className="cmd-help">{o.family === "deposit"
        ? `${resourceNames[o.resource!]} · réserve ${whole(o.reserve)} · débit max ${whole(o.throughput_per_hour)}/h`
        : `Étude ${Math.round((o.study_seconds ?? 0) / 3600)} h · ${whole(o.data)} Données${o.dossier !== undefined ? " · indice de dossier" : ""}`}
        {" "}(observé le {new Date(o.observed_at).toLocaleDateString("fr-FR")})</span></li>)}</ul>}
  </>;
}

/**
 * Galaxy → Fleet → Mission, driven from the map (D-UX-3/4/5). Controlled: `world` is the server's
 * projections (or the prototype fixtures); after an accepted command the container re-reads them,
 * this component never invents a mission. Nothing is sent before the explicit confirmation.
 */
export function CommandMap({ world, now, api, pending = false, feedback = null, toolbar, title = "Galaxie", subtitle, systemHref, backdrop = true }: {
  world: World; now: number; api: MissionApi; pending?: boolean; feedback?: CommandFeedback;
  toolbar?: ReactNode; title?: string; subtitle?: string;
  /** Link to the System View of a known system (Observer / Ouvrir le système). */
  systemHref?: (id: string) => string;
  backdrop?: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const flow = useMissionFlow(world, api, selected, pending);
  const { intent, step, setStep, quote, failed, setFailed, busy, setBusy, candidates, fleet, planKey, ready, path } = flow;
  const [notice, setNotice] = useState<string | null>(null);
  const [filter, setFilter] = useState<MapFilter>("all");
  const [showRoutes, setShowRoutes] = useState(true);
  const [showNames, setShowNames] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [search, setSearch] = useState("");
  const [searchMiss, setSearchMiss] = useState(false);
  const [tab, setTab] = useState<"overview" | "planets" | "routes" | "data">("overview");
  const [focus, setFocus] = useState<{ x: number; y: number; key: number } | null>(null);
  const [menuHidden, setMenuHidden] = useState(false);
  // Fleets on the map (09/11/2026): window of the fleets of one system, then destination picking.
  const [fleetAt, setFleetAt] = useState<string | null>(null);
  const [moving, setMoving] = useState<FleetView | null>(null);
  // Desktop: actions in a context menu next to the system; narrow screens: in the bottom sheet.
  const desktop = useMedia("(min-width: 961px)");
  const panel = useRef<HTMLDivElement>(null);
  const mapPanel = useRef<HTMLElement>(null);

  const canCommand = world.fleets.permissions.includes("fleet.command");
  const target = selected ? world.galaxy.systems.find((s) => s.id === selected) ?? null : null;
  const ref = selected ? world.fleets.systems?.find((s) => s.id === selected) : undefined;
  const available = selected ? offers(world, selected) : [];
  const missions = (world.fleets.missions ?? []).filter((m) => m.status !== "completed");
  const own = (id: string) => !!world.galaxy.systems.find((x) => x.id === id)?.observation?.own_colony_ids.length;
  const fleetsHere = selected ? stationed(world).filter((f) => f.system?.id === selected) : [];
  // Picking: Escape (or right click on the map) cancels and restores the fleet window.
  useEffect(() => {
    if (!moving) return;
    const key = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); setMoving(null); } };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [moving]);
  const openFleets = (id: string) => { setMoving(null); setFleetAt(id); };
  const pick = (id: string) => {
    const f = moving!;
    const name = systemName(world, id);
    if (f.system?.id === id) { setNotice(`${f.name} est déjà à ${name} : choisissez un autre système.`); return; }
    const offer = offers(world, id).find((o) => o.kind === "DEPLOY");
    if (!offer) { setNotice(`${name} n’est qu’un signal : cartographiez-le avant d’y envoyer une flotte.`); return; }
    setMoving(null); setFleetAt(null); setNotice(null);
    setSelected(id); setMenuHidden(true); setTab("overview"); setFailed(false);
    // A task fleet moves as it is (summary next); a garrison chooses what it detaches.
    flow.begin({ offer, fleet: f.id, units: defaultUnits(world, f, "DEPLOY") }, isGarrison(f) ? "units" : "summary");
  };
  const select = (id: string) => {
    setSelected(id); setMenuHidden(false); flow.stop(); setNotice(null); setTab("overview"); setFailed(false);
    // Narrow screens: keep the map in view above the bottom sheet that now holds the system.
    if (window.matchMedia?.("(max-width: 960px)").matches)
      window.setTimeout(() => mapPanel.current?.querySelector(".cmd-map")?.scrollIntoView?.({ block: "start" }), 0);
  };
  const close = () => { setSelected(null); flow.stop(); window.setTimeout(() => mapPanel.current?.querySelector<SVGElement>(".cmd-map")?.focus(), 0); };
  const start = (offer: ActionOffer) => { flow.start(offer); setNotice(null); };
  const cancel = () => { flow.stop(); window.setTimeout(() => document.querySelector<HTMLElement>(".cmd-action")?.focus(), 0); };
  const find = (text: string) => {
    const q = text.trim().toLocaleLowerCase("fr");
    const hit = q ? world.galaxy.systems.find((x) => x.state !== "DETECTED" && x.name?.toLocaleLowerCase("fr").includes(q)) : undefined;
    setSearchMiss(!!q && !hit);
    if (hit) { select(hit.id); const p = point(world, hit.id); if (p) setFocus({ ...p, key: Date.now() }); }
  };
  const locate = (line: FleetLine) => {
    const f = world.fleets.fleets?.find((x) => x.id === line.id);
    if (f?.system) {
      select(f.system.id);
      const p = point(world, f.system.id);
      if (p) setFocus({ ...p, key: Date.now() });
      return;
    }
    const m = line.mission;
    const p = m ? missionPosition(world, m, now) : null;
    if (p) {
      setFocus({ ...p, key: Date.now() });
      setNotice(`Carte centrée sur la position estimée de ${line.name} (estimation visuelle entre ses dates de départ et d’arrivée, pas une position transmise par le serveur).`);
    } else setNotice(`${line.name} n’a pas de position représentable sur votre carte.`);
  };

  async function confirm() {
    const label = await flow.confirm();
    if (!label) return;
    setSelected(null); // back to the map; the mission appears from the re-read projections
    setNotice(`${label} Suivez-la sur la carte et dans « Vos flottes ».`);
    window.setTimeout(() => mapPanel.current?.scrollIntoView?.({ block: "start" }), 0);
  }
  const recall = async (m: MissionView) => {
    setBusy(true);
    const ok = await api.recall(m).finally(() => setBusy(false));
    if (ok) setNotice(`Rappel confirmé : ${world.fleets.fleets?.find((f) => f.id === m.fleet_id)?.name ?? "la flotte"} fait demi-tour.`);
    return ok;
  };
  const distance = selected ? knownHops(world, selected) : null;
  const neighbours = selected ? world.galaxy.routes.filter((r) => r.a_id === selected || r.b_id === selected)
    .map((r) => (r.a_id === selected ? r.b_id : r.a_id)) : [];
  const filters: [MapFilter, string][] = [["all", "Tous"], ["known", "Systèmes connus"], ["own", "Mes colonies"], ["fleets", "Mes flottes"], ["signals", "Signaux"]];

  const stateName = (state: string) => state === "DETECTED" ? "Signal détecté" : state === "MONITORED" ? "Système surveillé" : "Système cartographié";
  const actions = <>{!canCommand ? <p>Votre accès ne permet pas de commander les flottes de cet Empire.</p>
    : available.length === 0 ? <p>Aucune action de flotte possible ici.</p> : <ul className="cmd-actions">{available.map((o, i) =>
      <li key={`${o.kind}-${o.planet ?? ""}`}>
        <button type="button" className={`button cmd-action${i === available.findIndex((x) => !x.reason) ? " button--primary" : ""}`} disabled={!!o.reason}
          aria-describedby={`hint-${o.kind}-${o.planet ?? "s"}`} onClick={() => start(o)}><ActionGlyph kind={o.kind} />{o.label}</button>
        <p id={`hint-${o.kind}-${o.planet ?? "s"}`} className="cmd-help">{o.reason ?? o.hint}</p>
      </li>)}</ul>}</>;
  const survey = available.find((o) => o.kind === "SURVEY" && !o.reason);
  const menu = desktop && target && !intent && !menuHidden ? <section className="cmd-ctx-card" aria-labelledby="cmd-ctx-title">
    <div className="cmd-ctx-head"><div><strong id="cmd-ctx-title"><span className="cmd-dot" aria-hidden="true"
      style={{ background: target.state === "DETECTED" ? "var(--map-detected)" : `rgb(${starTint(target.id).join(",")})` }} />{systemName(world, target.id)}</strong><small>{own(target.id) ? "Votre colonie" : stateName(target.state)}</small></div>
      <button type="button" className="cmd-ctx-close" aria-label="Fermer le menu du système" onClick={() => setMenuHidden(true)}>×</button></div>
    <SystemBrief world={world} system={target.id} />
    <h3>Actions possibles</h3>
    {actions}
    {systemHref && target.state !== "DETECTED" && <a className="cmd-ctx-link" href={systemHref(target.id)}>Ouvrir le système <span aria-hidden="true">→</span></a>}
  </section> : null;

  return <div className="cmd-command">
    <header className="cmd-page-head">
      <div className="cmd-page-id"><h1 id="cmd-map-title" className="cmd-page-title" tabIndex={-1}>{title}</h1>
        <p><strong>Carte stratégique</strong> {subtitle ?? "des systèmes connus de votre Empire"}</p></div>
      <div className="cmd-page-tools">
        <form className="cmd-search" role="search" onSubmit={(e) => { e.preventDefault(); find(search); }}>
          <label className="visually-hidden" htmlFor="cmd-search-input">Rechercher un système connu</label>
          <input id="cmd-search-input" type="search" placeholder="Rechercher un système…" value={search}
            onChange={(e) => { setSearch(e.target.value); setSearchMiss(false); }} aria-describedby="cmd-search-help" />
          <button type="submit" className="button">Chercher</button>
          <span id="cmd-search-help" className="cmd-help" aria-live="polite">{searchMiss ? "Aucun système connu de ce nom." : ""}</span>
        </form>
        {toolbar}
      </div>
    </header>
    <section className="cmd-map-panel" aria-labelledby="cmd-map-title" ref={mapPanel}>
      {notice && <p className="cmd-notice" role="status">{notice}<button type="button" className="button cmd-ghost" onClick={() => setNotice(null)}>Fermer</button></p>}
      <div className="cmd-map-tools">
        <div className="cmd-filters" role="group" aria-label="Filtrer la carte">
          {filters.map(([id, label]) => <button key={id} type="button" className={`cmd-filter${filter === id ? " is-active" : ""}`}
            aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}
          {["Alliés", "Neutres", "Hostiles"].map((label) => <button key={label} type="button" className="cmd-filter is-pending" disabled
            title="Implémentation backend nécessaire : la Knowledge ne qualifie pas encore les systèmes d’autres Empires">{label}</button>)}
        </div>
        <div className="cmd-switches">
          {([["Routes", showRoutes, setShowRoutes], ["Noms", showNames, setShowNames], ["Légende", showLegend, setShowLegend]] as const).map(([label, on, set]) =>
            <button key={label} type="button" role="switch" aria-checked={on} className="cmd-switch" onClick={() => set(!on)}>
              {label}<span className="cmd-switch-track" aria-hidden="true"><span /></span></button>)}
          {([["Régions", "Régions"], ["Influence", "Vue d’influence"]] as const).map(([label, what]) =>
            <button key={label} type="button" role="switch" aria-checked={false} className="cmd-switch is-pending" disabled title={`${what} : implémentation backend nécessaire`}>
              {label}<span className="cmd-switch-track" aria-hidden="true"><span /></span></button>)}
        </div>
      </div>
      <StarMap world={world} selected={selected} onSelect={moving ? pick : select} missions={missions} now={now}
        onFleets={openFleets} picking={!!moving} onCancelPick={() => setMoving(null)}
        overlay={moving ? <PickBar fleet={moving} onCancel={() => setMoving(null)} />
          : fleetAt ? <FleetWindow world={world} system={fleetAt} now={now} canCommand={canCommand} pending={pending || busy}
            onClose={() => setFleetAt(null)} onMove={(f) => { setMoving(f); setNotice(null); }}
            onProtocol={api.protocol ? async (f, p) => { setBusy(true); try { return await api.protocol!(f.id, p); } finally { setBusy(false); } } : undefined} />
          : null}
        filter={filter} showRoutes={showRoutes} showNames={showNames} showLegend={showLegend} focus={focus} backdrop={backdrop} menu={menu}
        preview={intent && fleet?.system && selected && step === "summary" ? { from: fleet.system.id, to: ready?.destination_id ?? selected, path } : null} />
      <details className="cmd-list">
        <summary>Liste des systèmes connus</summary>
        <ul>{world.galaxy.systems.map((s) => <li key={s.id}>
          <button type="button" className="button cmd-ghost" aria-pressed={selected === s.id} onClick={() => select(s.id)}>
            {systemName(world, s.id)}{s.state === "DETECTED" ? " (position approximative)" : ""}</button></li>)}</ul>
      </details>
    </section>

    <FleetDock world={world} now={now} canCommand={canCommand} pending={pending || busy} onLocate={locate} onRecall={recall} />

    <div className={`cmd-side${target ? " has-selection" : ""}`} ref={panel}>
      {!target ? <section className="cmd-card"><h2>Que voulez-vous faire ?</h2>
        <p>Choisissez un système sur la carte. Un signal détecté peut être cartographié par une sonde ; un système connu peut accueillir vos flottes, être colonisé ou attaqué.</p></section>
        : intent ? <>
          <MissionPlanner world={world} target={target.id} offer={intent.offer} fleets={candidates} fleet={fleet} units={intent.units}
            hours={intent.hours} onHours={(h) => flow.update({ hours: h })}
            comeBack={intent.comeBack} onComeBack={(back) => flow.update({ comeBack: back })}
            step={step} quoteKey={planKey} quote={quote} path={path} pending={pending || busy} onFleet={flow.chooseFleet}
            onUnits={(u) => flow.update({ units: u })} onStep={setStep} onConfirm={confirm} onCancel={cancel} />
          {failed && feedback && feedback.tone !== "success" && <p role="alert" className={`feedback feedback--${feedback.tone === "unknown" ? "error" : feedback.tone}`}>
            {feedback.tone === "unknown" ? "Résultat non confirmé. Confirmez à nouveau : la même intention est réutilisée, sans double envoi." : message(feedback.code)}</p>}
        </>
        : <section className="cmd-card cmd-system-card" aria-labelledby="cmd-system-title">
          <div className={`cmd-hero cmd-hero--${own(target.id) ? "own" : target.state.toLowerCase()}`}>
            <span className="cmd-hero-star" aria-hidden="true">✦</span>
            <div><h2 id="cmd-system-title">{systemName(world, target.id)}</h2>
              <p className="cmd-kicker">{stateName(target.state)}</p>
              {own(target.id) && <span className="cmd-chip cmd-chip--own">★ Votre colonie</span>}</div>
            <button type="button" className="button cmd-ghost cmd-close" onClick={close}>Retour à la carte</button>
          </div>
          <div className="cmd-tabs" role="tablist" aria-label="Informations du système">
            {([["overview", "Aperçu"], ["planets", `Planètes (${target.state === "DETECTED" ? "?" : (ref?.planets ?? []).length})`], ["routes", `Routes (${neighbours.length})`], ["data", "Données"]] as const).map(([id, label]) =>
              <button key={id} type="button" role="tab" id={`cmd-tab-${id}`} aria-selected={tab === id} aria-controls={`cmd-tabpanel-${id}`}
                className="cmd-tab" onClick={() => setTab(id)}>{label}</button>)}
          </div>
          {tab === "overview" && <div role="tabpanel" id="cmd-tabpanel-overview" aria-labelledby="cmd-tab-overview">
            <div className="cmd-tiles">
              <div><span>Connaissance</span><strong>{target.state === "DETECTED" ? "Détecté" : target.state === "MONITORED" ? "Surveillé" : "Cartographié"}</strong></div>
              <div><span>Vos flottes ici</span><strong>{fleetsHere.length}</strong></div>
              <div><span>Distance</span>{distance
                ? <strong title={`Plus court chemin sur vos routes connues depuis ${systemName(world, distance.from)}`}>{distance.hops === 0 ? "Ici" : `${distance.hops} saut${distance.hops > 1 ? "s" : ""}`}</strong>
                : <strong className="cmd-na" title="Aucune route connue ne relie ce système à vos colonies">Inconnue</strong>}</div>
              <div><span>Planètes connues</span><strong>{target.state === "DETECTED" ? "?" : (ref?.planets ?? []).length}</strong></div>
            </div>
            {target.state === "DETECTED" ? <p>Existence et position approximative seulement. Nom, planètes et occupants restent inconnus tant qu’une sonde ne l’a pas cartographié.</p>
              : <p className="cmd-help">{(ref?.planets ?? []).length} planète(s) connue(s){fleetsHere.length ? ` · ${fleetsHere.map((f) => f.name).join(", ")}` : ""}.</p>}
            {!desktop && <><h3>Actions possibles</h3>{actions}</>}
            {desktop && menuHidden && <button type="button" className="button cmd-ghost" onClick={() => setMenuHidden(false)}>Afficher les actions sur la carte</button>}
          </div>}
          {tab === "planets" && <div role="tabpanel" id="cmd-tabpanel-planets" aria-labelledby="cmd-tab-planets">
            {target.state === "DETECTED" ? <p>Structure inconnue : cartographiez ce signal.</p>
              : <ul className="cmd-planets" aria-label="Planètes connues">{(ref?.planets ?? []).map((p) =>
                <li key={p.id}><img className="cmd-planet-img" src={planetImage(p.id)} alt="" width="36" height="36" /><div><strong>{p.name}</strong>
                  <span>{p.sector_capacity} secteurs · {p.orbital_capacity} orbitaux</span></div>
                  <span className={`cmd-chip${p.colony_id ? " cmd-chip--own" : ""}`}>{p.colony_id ? "Votre colonie" : "Occupation inconnue"}</span></li>)}
                {(ref?.planets ?? []).length === 0 && <li>Aucune planète connue.</li>}</ul>}
          </div>}
          {tab === "routes" && <div role="tabpanel" id="cmd-tabpanel-routes" aria-labelledby="cmd-tab-routes">
            <ul className="cmd-routes" aria-label="Routes connues">{neighbours.map((id) =>
              <li key={id}><button type="button" className="button cmd-ghost" onClick={() => select(id)}>
                {systemName(world, target.id)} ↔ {systemName(world, id)}</button></li>)}</ul>
            <p className="cmd-help">Seules vos routes connues sont listées. {distance ? `À ${distance.hops} saut${distance.hops > 1 ? "s" : ""} de ${systemName(world, distance.from)} par ces routes ; la durée exacte figure dans le résumé du serveur avant tout envoi.` : "Aucune route connue ne le relie encore à vos colonies."}</p>
          </div>}
          {tab === "data" && <div role="tabpanel" id="cmd-tabpanel-data" aria-labelledby="cmd-tab-data">
            {target.opportunities ? <OpportunityList data={target.opportunities} />
              : target.state === "DETECTED" ? <p>Un signal ne révèle rien de plus : cartographiez-le d’abord.</p>
              : <div className="d-pending"><strong>Implémentation backend nécessaire</strong><span>Ressources et anomalies : univers créés avant les règles v0.10.</span></div>}
          </div>}
          <div className="cmd-system-actions">
            {systemHref && target.state !== "DETECTED" ? <a className="button cmd-ghost" href={systemHref(target.id)}>Observer</a>
              : <button type="button" className="button cmd-ghost" disabled title="Un signal doit d’abord être cartographié">Observer</button>}
            <button type="button" className="button cmd-ghost" disabled={!survey || !canCommand} onClick={() => survey && start(survey)}>Explorer</button>
            {systemHref && target.state !== "DETECTED" ? <a className="button button--primary" href={systemHref(target.id)}>Ouvrir le système</a>
              : <button type="button" className="button button--primary" disabled>Ouvrir le système</button>}
          </div>
        </section>}
    </div>
  </div>;
}
