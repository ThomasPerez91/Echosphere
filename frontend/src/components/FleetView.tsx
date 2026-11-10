import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useFleets } from "../hooks/useFleets";
import { ApiError, previewMission } from "../fleet/api";
import type { Amounts } from "../colony/api";
import type { CombatReport, FleetProjection, Frontier, MissionKind, MissionView, Protocol, Quote, ShipOrder } from "../fleet/api";
import { duration, exactUnits, infrastructureLabel, resourceKeys, resourceLabels, time, units } from "../colony/format";
import { Badge, Button, EmptyState, Panel } from "./ui";
import { message } from "../fleet/messages";
import { protocols } from "../fleet/protocols";
import { Kpis, Thumb, ViewHero, shipImage } from "../shell/view";
import { Bar, PanelHead } from "../shell/visual";

const kindLabels: Record<MissionKind, string> = { DEPLOY: "Déploiement", SURVEY: "Cartographie", RETURN: "Retour", COLONIZE: "Colonisation", ATTACK: "Attaque", PROSPECT: "Prospection", STUDY: "Étude", EXTRACT: "Extraction" };
const outcomeLabels: Record<string, string> = {
  attacker_win: "Victoire de l’attaquant", defender_win: "Victoire du défenseur",
  mutual_destruction: "Destruction mutuelle", unopposed: "Aucune défense militaire", target_unavailable: "Cible indisponible",
  voided_by_pact: "Bataille annulée par un pacte",
};
/** 13B: four distinct postures, described by what they do and never do (Q57). */
const engagementLabels: Record<string, string> = {
  victory: "Victoire", defeat: "Défaite", mutual_destruction: "Destruction mutuelle",
};
const retreatLabels: Record<string, string> = {
  retreated: "Repli effectué", retreat_failed: "Repli impossible : départ refusé",
  retreat_impossible: "Repli impossible : aucune destination accessible", void: "Repli sans objet",
};

function Clock({ start, end, serverTime, receivedAt, label }: {
  start: string; end: string; serverTime: string; receivedAt: number; label: string;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const from = Date.parse(start), to = Date.parse(end);
  const server = Date.parse(serverTime) + now - receivedAt;
  const percent = Math.max(0, Math.min(100, Math.floor(((server - from) * 100) / Math.max(1, to - from))));
  const left = Math.max(0, Math.ceil((to - server) / 1000));
  return <div className="queue-progress">
    <div className="meter" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
      <span style={{ width: `${percent}%` }} />
    </div>
    <span>{left ? `${duration(String(left * 1e6))} restantes (estimation locale)` : "Échéance atteinte, traitement du serveur attendu."}</span>
  </div>;
}

function Composition({ stacks, p }: { stacks: Record<string, number>; p: FleetProjection }) {
  const entries = Object.entries(stacks);
  if (!entries.length) return <p className="muted">Aucune unité.</p>;
  return <ul className="fleet-stacks">{entries.map(([c, n]) => <li key={c}><strong>{n}</strong> {p.catalogue![c]?.name ?? c}</li>)}</ul>;
}

function Cargo({ cargo }: { cargo: Amounts }) {
  const carried = resourceKeys.filter((k) => BigInt(cargo[k]) > 0n);
  if (!carried.length) return <span>vide</span>;
  return <>{carried.map((k) => `${units(cargo[k])} ${resourceLabels[k]}`).join(" · ")}</>;
}

const place = (s: { name?: string; state: string } | null) => s ? (s.name ?? "Signal détecté — structure inconnue") : "—";
function reportTitle(m: MissionView) {
  const result = m.report!.result;
  if (result.kind === "RECALLED") return "Rappel terminé";
  if (result.kind === "COLONIZE") return result.outcome === "founded" ? "Colonie fondée" : "Monde indisponible à l’arrivée";
  if (result.kind === "ATTACK") return result.destroyed ? "Flotte détruite au combat" : `Attaque — ${outcomeLabels[result.outcome ?? ""] ?? "terminée"}`;
  if (result.kind === "INTERCEPTED") return "Flotte détruite par une interception en route";
  return kindLabels[m.kind];
}

type Dialog =
  | { mode: "send"; fleet: string; kind: MissionKind; destination: string; planet: string; units: Record<string, number>;
      cargo: Record<string, number>; quote: Quote | null; quoted: string | null; error: string | null }
  | { mode: "split"; fleet: string; units: Record<string, number>; cargo: Record<string, number> }
  | { mode: "merge"; fleet: string; target: string }
  | { mode: "load"; fleet: string; colony: string; cargo: Record<string, number> }
  | { mode: "unload"; fleet: string; colony: string }
  | { mode: "cancel"; order: ShipOrder }
  | { mode: "recall"; mission: MissionView };

type Send = Extract<Dialog, { mode: "send" }>;
const positive = (values: Record<string, number>) =>
  Object.fromEntries(Object.entries(values).filter(([, v]) => v > 0).sort(([a], [b]) => a.localeCompare(b)));
/** Everything a launch would send: a quote is shown and confirmable only for this exact intention. */
const intentOf = (d: Send) =>
  JSON.stringify([d.fleet, d.kind, d.kind === "RETURN" ? "" : d.destination, d.planet, positive(d.units), positive(d.cargo)]);

function Counter({ label, value, max, onChange }: { label: string; value: number; max: number; onChange: (n: number) => void }) {
  return <label className="galaxy-field fleet-counter">{label}
    <input type="number" inputMode="numeric" min={0} max={max} value={value}
      onChange={(e) => onChange(Math.max(0, Math.min(max, Math.floor(Number(e.target.value) || 0))))} />
    <span className="panel-meta">maximum {max}</span>
  </label>;
}

function Losses({ label, side, p }: { label: string; side: CombatReport["own"]; p: FleetProjection }) {
  const rows = Object.entries(side?.initial ?? {}).filter(([, n]) => n > 0);
  return <div><dt>{label}</dt><dd>{rows.length ? rows.map(([c, n]) =>
    `${p.catalogue![c]?.name ?? c} : ${n} engagés, ${side!.losses[c] ?? 0} perdus, ${side!.survivors[c] ?? 0} survivants`).join(" · ") : "aucune unité militaire"}</dd></div>;
}

/** 13B: detections (anonymous unless identified) and own frontier reports (D3). */
function FrontierPanel({ frontier, p }: { frontier: Frontier; p: FleetProjection }) {
  const forces = (side: CombatReport["own"]) => {
    const rows = Object.entries(side?.initial ?? {}).filter(([, n]) => n > 0);
    return rows.length ? rows.map(([c, n]) =>
      `${p.catalogue![c]?.name ?? c} : ${n} engagés, ${side!.losses[c] ?? 0} perdus, ${side!.survivors[c] ?? 0} survivants`).join(" · ")
      : "aucune unité militaire";
  };
  return <section className="panel" aria-labelledby="frontier-title">
    <div className="panel-head"><h2 id="frontier-title">Frontière</h2>
      <span className="panel-meta">{frontier.detections.length} détection(s)</span></div>
    <p className="panel-meta">Une détection donne le système, l’instant et une signature : l’Empire n’est nommé que s’il vous était déjà connu ou s’il s’est présenté. Ni composition, ni origine, ni destination.</p>
    <h3>Détections</h3>
    {frontier.detections.length === 0 ? <p>Aucune flotte étrangère détectée.</p> : <ul className="fleet-reports">{frontier.detections.map((d) =>
      <li key={d.id}><strong>{d.empire ? `Flotte de ${d.empire.name ?? "Empire connu"}` : "Signature étrangère détectée"}</strong>
        {" — "}{d.role === "watch" ? "entrée dans votre zone surveillée" : "votre flotte en transit a été repérée"} : {place(d.system)}
        {d.friendly && <Badge tone="accent">Contact amical</Badge>}
        <p className="panel-meta">Instant logique {time(d.detected_at)}</p>
      </li>)}</ul>}
    <h3>Rencontres et replis</h3>
    {frontier.encounters.length === 0 ? <p>Aucune rencontre frontalière.</p> : <ul className="fleet-reports">{frontier.encounters.map((e) =>
      e.kind === "retreat" ? <li key={e.id}><strong>{retreatLabels[e.outcome] ?? e.outcome}</strong> — {place(e.system)}
        {e.destination && <> → {place(e.destination)}</>}
        <p className="panel-meta">Force hostile entrée à {time(e.at)}{e.reason ? ` · ${message(e.reason)}` : ""} · carburant normal, aucune téléportation.</p>
      </li> : <li key={e.id} className="combat-report">
        <strong>{e.role === "watcher" ? `${protocols[e.protocol ?? "INTERCEPTION"].label} — ${engagementLabels[e.outcome] ?? e.outcome}` : `Interceptée en route — ${engagementLabels[e.outcome] ?? e.outcome}`}</strong>
        {" — "}{place(e.system)} · contre {e.opponent.name ?? "un Empire"}
        <dl className="fleet-dates"><div><dt>Vos forces</dt><dd>{forces(e.own)}</dd></div>
          <div><dt>Forces adverses</dt><dd>{forces(e.opponent_forces)}</dd></div>
          <div><dt>Rounds</dt><dd>{e.rounds}</dd></div></dl>
        {e.destroyed && <p role="status">Votre flotte a été détruite.</p>}
        <p className="panel-meta">Rencontre à l’instant d’entrée {time(e.at)} · pertes militaires seulement.</p>
      </li>)}</ul>}
  </section>;
}

/** Start of the unit being built: units n come out at started + total x n / quantity. */
function unitStart(o: ShipOrder) {
  const n = (o.delivered ?? 0) + 1, start = Date.parse(o.started_at!), due = Date.parse(o.due_at!);
  if (o.delivered === undefined || o.quantity === 1) return o.started_at!;
  return new Date(start + (due - start) * (n - 1) / n).toISOString();
}

/** Main class of a fleet (most units) for its illustration. */
const mainClass = (stacks: Record<string, number>) => Object.entries(stacks).sort(([, a], [, b]) => b - a)[0]?.[0] ?? "probe";
const count = (stacks: Record<string, number>) => Object.values(stacks).reduce((a, b) => a + b, 0);
const hero = (galaxy?: string) => <ViewHero crumb="Flottes" title="Flottes" banner="banniere-flottes"
  text="Gestion des forces, missions et opérations dans la galaxie ; déplacements et échéances calculés par le serveur.">
  {galaxy && <a className="d-btn d-btn-ghost" href={galaxy}>Carte de commandement <span aria-hidden="true">→</span></a>}
</ViewHero>;

export function FleetView({ universe, enabled, csrf, onSessionLost, onEconomyChanged, target, galaxyHref }: {
  universe: string; enabled: boolean; csrf?: string; onSessionLost: () => void; onEconomyChanged?: () => void; galaxyHref?: string;
  target?: { empire: string; system: string; planet?: string; action?: "colonize" | "attack" };
}) {
  const fleets = useFleets(universe, enabled, csrf, onSessionLost, target?.empire);
  const p = fleets.projection;
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [order, setOrder] = useState<Record<string, { ship: string; quantity: number }>>({});
  const [protocolChoice, setProtocolChoice] = useState<Record<string, Protocol | "">>({});
  const [focus, setFocus] = useState<string | null>(null);
  const box = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const prefilled = useRef(false);
  const quoteGeneration = useRef(0);
  const quoteRequest = useRef<AbortController | null>(null);
  const can = (right: string) => !!p?.permissions.includes(right);

  useEffect(() => {
    if (dialog) { if (!box.current?.open) box.current?.showModal(); }
    else if (box.current?.open) box.current.close();
  }, [dialog]);

  const stationed = p?.available ? p.fleets!.filter((f) => f.status === "STATIONED") : [];
  const moving = p?.available ? p.missions!.filter((m) => m.status !== "completed") : [];
  const reports = p?.available ? p.missions!.filter((m) => m.report).slice(0, 8) : [];

  // Any edit, new request, closing or reopening supersedes the quote in flight.
  const invalidateQuote = () => {
    quoteGeneration.current += 1;
    quoteRequest.current?.abort();
    quoteRequest.current = null;
  };
  useEffect(() => {
    const generation = quoteGeneration, request = quoteRequest;
    return () => { generation.current += 1; request.current?.abort(); };
  }, []);

  // "Envoyer une flotte ici" from Galaxy/System View (one mount per shortcut): useFleets reads the
  // shortcut's Empire first; the dialog opens only on that Empire's projection, never another one,
  // and the prefill is consumed only once it actually opened.
  useEffect(() => {
    if (prefilled.current || !p?.available || !target || p.empire.id !== target.empire || dialog) return;
    const system = p.systems!.find((s) => s.id === target.system);
    if (!system || !p.permissions.includes("fleet.command")) return;
    if (target.planet && target.action === "attack") {
      // "Attaquer…" from System View: a stationed fleet with military units, the same ATTACK flow.
      const military = p.combat?.classes ?? [];
      const fleet = p.fleets!.find((f) => f.status === "STATIONED" && military.some((c) => f.stacks[c]));
      if (!fleet || !system.planets?.some((pl) => pl.id === target.planet) || !p.permissions.includes("combat.attack")) return;
      prefilled.current = true;
      setDialog({ mode: "send", fleet: fleet.id, kind: "ATTACK", destination: "", planet: target.planet,
        units: {}, cargo: {}, quote: null, quoted: null, error: null });
      return;
    }
    if (target.planet) {
      // "Coloniser…" from System View: a fleet carrying a colonizer, the same COLONIZE flow.
      const colonizer = p.colonization?.colonizer_class;
      const fleet = colonizer && p.fleets!.find((f) => f.status === "STATIONED" && f.stacks[colonizer]);
      if (!fleet || !system.planets?.some((pl) => pl.id === target.planet)) return;
      prefilled.current = true;
      setDialog({ mode: "send", fleet: fleet.id, kind: "COLONIZE", destination: "", planet: target.planet,
        units: { [colonizer]: 1 }, cargo: {}, quote: null, quoted: null, error: null });
      return;
    }
    const fleet = p.fleets!.find((f) => f.status === "STATIONED" && Object.keys(f.stacks).length && f.system?.id !== target.system);
    if (!fleet) return;
    prefilled.current = true;
    setDialog({ mode: "send", fleet: fleet.id, kind: system.state === "DETECTED" ? "SURVEY" : "DEPLOY",
      destination: system.id, planet: "", units: {}, cargo: {}, quote: null, quoted: null, error: null });
  }, [p, target, dialog]);

  // Travel arrival changes what the screen offers without any server event (SURVEY analysis
  // starts, recall closes): re-render at the next one locally, no extra read.
  const [phaseTick, setPhaseTick] = useState(0);
  useEffect(() => {
    if (!p?.available) return;
    const now = Date.parse(p.server_time) + (Date.now() - fleets.receivedAt);
    const next = p.missions!
      .filter((m) => m.status === "active" && m.kind !== "RETURN")
      .flatMap((m) => [Date.parse(m.travel_arrival_at), Date.parse(m.due_at)])
      .filter((at) => at > now)
      .sort((x, y) => x - y)[0];
    if (next === undefined) return;
    const timer = window.setTimeout(() => setPhaseTick((n) => n + 1), next - now + 50);
    return () => window.clearTimeout(timer);
  }, [p, fleets.receivedAt, phaseTick]);

  const open = (next: Dialog, event: { currentTarget: HTMLElement }) => {
    invalidateQuote();
    trigger.current = event.currentTarget;
    setDialog(next);
  };
  const close = () => { invalidateQuote(); setDialog(null); window.setTimeout(() => trigger.current?.focus(), 0); };
  /** Edit the mission form: the displayed quote no longer matches and must be recomputed. */
  const edit = (patch: Partial<Send>) => {
    invalidateQuote();
    setDialog((d) => d?.mode === "send" ? { ...d, ...patch, quote: null, quoted: null, error: null } : d);
  };
  const done = (result: unknown) => { if (result) { close(); onEconomyChanged?.(); } };
  const toCargo = (values: Record<string, number>) => Object.fromEntries(Object.entries(values).filter(([, v]) => v > 0));
  /** Server rule: only a task fleet sent whole carries its cargo implicitly (no cargo field). */
  const sentWhole = (d: Send) => {
    const fleet = p?.fleets?.find((f) => f.id === d.fleet);
    return fleet?.kind === "TASK" && JSON.stringify(positive(d.units)) === JSON.stringify(positive(fleet.stacks));
  };
  const target_of = (d: Send) => d.kind === "COLONIZE" || d.kind === "ATTACK" ? { target_planet_id: d.planet }
    : d.kind === "RETURN" ? {} : { destination_id: d.destination };

  async function quote(d: Send) {
    if (!p || !csrf) return;
    invalidateQuote();
    const generation = quoteGeneration.current;
    const controller = new AbortController();
    quoteRequest.current = controller;
    const intent = intentOf(d);
    // A late answer is a complete no-op: newer request, edited form, closed or other dialog.
    const apply = (patch: Pick<Send, "quote" | "quoted" | "error">) => {
      if (generation !== quoteGeneration.current) return false;
      quoteRequest.current = null;
      setDialog((cur) => cur?.mode === "send" && intentOf(cur) === intent ? { ...cur, ...patch } : cur);
      return true;
    };
    try {
      const q = await previewMission(universe, p.empire.id, csrf, {
        fleet_id: d.fleet, kind: d.kind, units: toCargo(d.units), ...target_of(d),
      }, p.permissions.includes("colony.read"), controller.signal);
      apply({ quote: q, quoted: intent, error: null });
    } catch (error) {
      if (apply({ quote: null, quoted: null, error: error instanceof ApiError ? error.code : "unavailable" }) &&
        error instanceof ApiError && error.status === 401)
        onSessionLost();
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!dialog) return;
    if (dialog.mode === "send") {
      // Confirm launches only the exact intention that was quoted; otherwise quote again.
      if (!dialog.quote || dialog.quoted !== intentOf(dialog)) return void quote(dialog);
      done(await fleets.run("/missions", {
        fleet_id: dialog.fleet, kind: dialog.kind, units: toCargo(dialog.units), ...target_of(dialog),
        ...(!sentWhole(dialog) && Object.keys(toCargo(dialog.cargo)).length ? { cargo: toCargo(dialog.cargo) } : {}),
      }, JSON.stringify(dialog)));
    } else if (dialog.mode === "split") {
      done(await fleets.run(`/${dialog.fleet}/split`, { units: toCargo(dialog.units), cargo: toCargo(dialog.cargo) }, JSON.stringify(dialog)));
    } else if (dialog.mode === "merge") {
      done(await fleets.run(`/${dialog.fleet}/merge`, { target_id: dialog.target }, dialog.target));
    } else if (dialog.mode === "load") {
      if (!dialog.colony) return;
      done(await fleets.run(`/${dialog.fleet}/load`, { colony_id: dialog.colony, cargo: toCargo(dialog.cargo) }, JSON.stringify(dialog)));
    } else if (dialog.mode === "unload") {
      if (!dialog.colony) return;
      done(await fleets.run(`/${dialog.fleet}/unload`, { colony_id: dialog.colony }, JSON.stringify([dialog.fleet, dialog.colony])));
    } else if (dialog.mode === "cancel") {
      done(await fleets.run(`/orders/${dialog.order.id}/cancel`, {}, dialog.order.id));
    } else {
      done(await fleets.run(`/missions/${dialog.mission.id}/recall`, {}, dialog.mission.id));
    }
  }

  if (fleets.phase === "loading" || fleets.phase === "idle") return <div className="d-page">{hero(galaxyHref)}<Panel title="Flottes"><p role="status">Lecture de vos flottes…</p></Panel></div>;
  if (fleets.phase === "empty") return <div className="d-page">{hero(galaxyHref)}<Panel title="Aucun Empire"><EmptyState title="Aucune flotte accessible">Votre accès ne comprend aucun Empire avec le droit de lecture des flottes.</EmptyState></Panel></div>;
  if (!p) return <div className="d-page">{hero(galaxyHref)}<Panel title="Flottes indisponibles"><p role="alert">{message(fleets.error ?? "unavailable")}</p><Button onClick={fleets.refresh}>Réessayer</Button></Panel></div>;

  const server = Date.parse(p.server_time) + (Date.now() - fleets.receivedAt);
  const fleetName = (fid: string) => p.fleets?.find((f) => f.id === fid)?.name ?? "Flotte";
  const current = dialog && "fleet" in dialog ? p.fleets?.find((f) => f.id === dialog.fleet) : undefined;

  const allFleets = p.available ? p.fleets! : [];
  const ships = allFleets.reduce((n, f) => n + count(f.stacks), 0);
  const building = p.available ? p.colonies!.reduce((n, c) => n + c.orders.length, 0) : 0;
  const threats = (p.combat?.alerts ?? []).filter((a) => a.state === "pending").length;
  const focused = allFleets.find((f) => f.id === focus) ?? null;
  const focusMission = focused?.mission_id ? p.missions?.find((m) => m.id === focused.mission_id) ?? null : null;
  // Where the fleets are: stationed in a system, or heading to a destination.
  const positions = new Map<string, { name: string; here: number; heading: number }>();
  for (const f of stationed) {
    const key = f.system?.id ?? "?", row = positions.get(key) ?? { name: place(f.system), here: 0, heading: 0 };
    row.here += 1; positions.set(key, row);
  }
  for (const m of moving) {
    const key = m.destination?.id ?? m.origin?.id ?? "?", row = positions.get(key) ?? { name: place(m.destination ?? m.origin), here: 0, heading: 0 };
    row.heading += 1; positions.set(key, row);
  }
  const totals: Record<string, number> = {};
  for (const f of (focused ? [focused] : allFleets)) for (const [c, n] of Object.entries(f.stacks)) totals[c] = (totals[c] ?? 0) + n;
  const biggest = Math.max(1, ...Object.values(totals));

  return <div className="fleet-screen d-page d-fleets">
    {hero(galaxyHref)}
    {p.available && <Kpis label="Vos forces" items={[
      { icon: "icons/stats/stat-flottes.svg", value: allFleets.filter((f) => f.kind === "TASK").length, label: "Flottes opérationnelles" },
      { icon: "icons/sidebar/nav-flottes.svg", value: ships, label: "Vaisseaux" },
      { icon: "icons/actions/action-lancer.svg", value: moving.length, label: "Missions en cours" },
      { icon: "icons/actions/action-construire.svg", value: building, label: "Commandes en production" },
      { icon: "icons/ui/ui-alerte.svg", value: threats, label: "Menaces annoncées" },
    ]} />}
    <div className="colony-toolbar">
      {fleets.empires.length > 1 ? <label className="galaxy-field">Empire
        <select value={fleets.selectedEmpire} disabled={fleets.pending} onChange={(e) => fleets.select(e.target.value)}>
          {fleets.empires.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select></label> : <span className="panel-meta">Empire : {p.empire.name}</span>}
      <span className="panel-meta">État serveur au {time(p.server_time)}</span>
      <Button onClick={fleets.refresh} disabled={fleets.pending}>Actualiser</Button>
    </div>
    <div className="feedback-zone" aria-live="polite">
      {fleets.feedback && <div className={`feedback feedback--${fleets.feedback.tone}`}><p>{message(fleets.feedback.code)}</p>
        <Button onClick={fleets.dismiss}>Masquer</Button></div>}
      {fleets.awaiting && <p className="feedback feedback--unknown">Une échéance est passée ; le traitement du serveur est attendu. Actualisez plus tard.</p>}
    </div>
    {!p.available ? <Panel title="Flottes indisponibles dans cette partie">
      <p>Les règles de cette partie n’incluent pas de flottes ; l’exploration y passe par l’expédition abstraite de la Galaxie.</p></Panel> : <>
      <div className="d-view-grid d-fl-grid">
        <div className="d-stack d-fl-col">
      <section className="panel" aria-labelledby="stationed-title"><div className="panel-head"><h2 id="stationed-title">Flottes stationnées</h2>
        <span className="panel-meta">{stationed.length}</span></div>
        {stationed.length === 0 ? <p>Aucune flotte stationnée. Fabriquez une sonde pour commencer à cartographier.</p> :
          <ul className="fleet-list">{stationed.map((f) => <li key={f.id} className={`fleet-card${focus === f.id ? " is-current" : ""}`}>
            <div className="d-fl-card-top"><Thumb src={shipImage(mainClass(f.stacks))} icon="icons/sidebar/nav-flottes.svg" />
              <div className="panel-head"><h3>{f.name}</h3><Badge tone={f.kind === "GARRISON" ? "accent" : "neutral"}>{f.kind === "GARRISON" ? "Garnison" : "Opérationnelle"}</Badge></div>
              <button type="button" className="d-link-btn" aria-pressed={focus === f.id} aria-label={`Détails de ${f.name}`} onClick={() => setFocus(focus === f.id ? null : f.id)}>Détails</button></div>
            <p>Stationnée : {place(f.system)}</p>
            <Composition stacks={f.stacks} p={p} />
            <p className="panel-meta">Cargo : <Cargo cargo={f.cargo} /> · capacité {units(f.capacity)}</p>
            {p.frontier && f.kind === "TASK" && (() => {
              const active = f.protocol ?? null;
              const chosen = protocolChoice[f.id] ?? (active ?? "");
              return <div className="fleet-protocol">
                <p>Protocole : {active ? <Badge tone={protocols[active].tone}>{protocols[active].label}</Badge> : <span className="muted">aucun</span>}</p>
                {can("fleet.command") && <form className="fleet-protocol-form" onSubmit={async (e) => {
                  e.preventDefault();
                  const value = chosen === "" ? null : chosen;
                  await fleets.run(`/${f.id}/protocol`, { protocol: value }, JSON.stringify([f.id, value]));
                }}>
                  <label className="galaxy-field">Protocole de premier contact
                    <select value={chosen} disabled={fleets.pending} aria-describedby={`protocol-help-${f.id}`}
                      onChange={(e) => setProtocolChoice({ ...protocolChoice, [f.id]: e.target.value as Protocol | "" })}>
                      <option value="">Aucun</option>
                      {p.frontier!.protocols.map((key) => <option key={key} value={key}>{protocols[key].label}</option>)}
                    </select></label>
                  <p id={`protocol-help-${f.id}`} className="panel-meta">{chosen ? protocols[chosen].help : "Sans protocole, la flotte ne détecte rien et ne réagit à aucun passage."}</p>
                  <Button type="submit" disabled={fleets.pending || chosen === (active ?? "")}>Appliquer</Button>
                </form>}
              </div>;
            })()}
            {can("fleet.command") && <div className="fleet-actions">
              {Object.keys(f.stacks).length > 0 && <Button className="button--primary" disabled={fleets.pending}
                onClick={(e) => open({ mode: "send", fleet: f.id, kind: "DEPLOY", destination: "", planet: "", units: {}, cargo: {}, quote: null, quoted: null, error: null }, e)}>Envoyer…</Button>}
              {Object.keys(f.stacks).length > 0 && <Button disabled={fleets.pending} onClick={(e) => open({ mode: "split", fleet: f.id, units: {}, cargo: {} }, e)}>Diviser…</Button>}
              {f.kind === "TASK" && stationed.some((o) => o.id !== f.id && o.system?.id === f.system?.id) &&
                <Button disabled={fleets.pending} onClick={(e) => open({ mode: "merge", fleet: f.id, target: "" }, e)}>Fusionner…</Button>}
              {/* Several own colonies in this system: the player always names the one used. */}
              {f.colonies_here.length > 0 && BigInt(f.capacity) > 0n && <Button disabled={fleets.pending}
                onClick={(e) => open({ mode: "load", fleet: f.id, colony: f.colonies_here.length === 1 ? f.colonies_here[0].id : "", cargo: {} }, e)}>Charger…</Button>}
              {f.colonies_here.length > 0 && resourceKeys.some((k) => BigInt(f.cargo[k]) > 0n) && <Button disabled={fleets.pending}
                onClick={(e) => open({ mode: "unload", fleet: f.id, colony: f.colonies_here.length === 1 ? f.colonies_here[0].id : "" }, e)}>Décharger…</Button>}
            </div>}
          </li>)}</ul>}
      </section>
        </div>
        <div className="d-stack d-fl-col">
        <section className="d-card d-panel" aria-labelledby="positions-title">
          <PanelHead id="positions-title" icon="icons/sidebar/nav-galaxie.svg" title="Position des flottes"
            more={galaxyHref ? { href: galaxyHref, label: "Ouvrir la carte" } : null} />
          {positions.size === 0 ? <p className="d-note">Aucune flotte dans la galaxie.</p> : <ul className="d-rows">{[...positions.entries()].map(([key, row]) =>
            <li key={key} className="d-row"><span className="d-pos-dot" aria-hidden="true" /><span className="d-row-main"><strong>{row.name}</strong>
              <span>{row.here ? `${row.here} flotte${row.here > 1 ? "s" : ""} stationnée${row.here > 1 ? "s" : ""}` : ""}{row.here && row.heading ? " · " : ""}{row.heading ? `${row.heading} en approche` : ""}</span></span></li>)}</ul>}
        </section>
      <section className="panel" aria-labelledby="moving-title"><div className="panel-head"><h2 id="moving-title">Flottes en mission</h2>
        <span className="panel-meta">{moving.length}</span></div>
        {moving.length === 0 ? <p>Aucune flotte en mission.</p> : <ul className="fleet-list">{moving.map((m) => {
          const analysing = m.kind === "SURVEY" && m.status === "active" && server >= Date.parse(m.travel_arrival_at);
          const attack = m.kind === "ATTACK";
          const approaching = attack && m.status === "active" && server >= Date.parse(m.travel_arrival_at);
          const badge = m.status === "returning" ? (attack && !m.recalled_at ? "Retour après la bataille" : "Retour après rappel")
            : analysing ? "Analyse en cours" : approaching ? (server >= Date.parse(m.due_at) ? "Bataille en résolution" : "Approche — bataille prévue")
            : attack ? "Attaque — en route" : kindLabels[m.kind];
          // ATTACK: recall until battle_at; EXTRACT until its end (stops it); others while travelling.
          const recallable = m.status === "active" && m.kind !== "RETURN" &&
            server < Date.parse(attack || m.kind === "EXTRACT" ? m.due_at : m.travel_arrival_at) && (!attack || m.attack?.state === "pending");
          return <li key={m.id} className={`fleet-card${focus === m.fleet_id ? " is-current" : ""}`}>
            <div className="d-fl-card-top"><Thumb src={shipImage(mainClass(m.stacks))} icon="icons/actions/action-lancer.svg" />
              <div className="panel-head"><h3>{fleetName(m.fleet_id)}</h3>
                <Badge tone={attack ? "warning" : "accent"}>{badge}</Badge></div>
              <button type="button" className="d-link-btn" aria-pressed={focus === m.fleet_id} aria-label={`Détails de ${fleetName(m.fleet_id)}`} onClick={() => setFocus(focus === m.fleet_id ? null : m.fleet_id)}>Détails</button></div>
            <p>{place(m.origin)} → {place(m.destination)}{m.target_planet ? ` · monde ${m.target_planet.name}` : ""} · {m.hops} saut(s)</p>
            <Composition stacks={m.stacks} p={p} />
            <dl className="fleet-dates">
              <div><dt>Départ</dt><dd>{time(m.started_at)}</dd></div>
              {m.status === "returning" ? <div><dt>Retour prévu</dt><dd>{time(m.return_at!)}</dd></div> : <>
                <div><dt>{m.kind === "SURVEY" ? "Arrivée dans le système" : "Arrivée"}</dt><dd>{time(m.travel_arrival_at)}</dd></div>
                {m.kind === "SURVEY" && <div><dt>Fin d’analyse</dt><dd>{time(m.due_at)}</dd></div>}
                {attack && <div><dt>Bataille</dt><dd>{time(m.due_at)}</dd></div>}</>}
            </dl>
            <Clock start={m.status === "returning" ? (m.recalled_at ?? m.due_at) : m.started_at} end={m.status === "returning" ? m.return_at! : m.due_at}
              serverTime={p.server_time} receivedAt={fleets.receivedAt} label="Avancement estimé de la mission" />
            {can("fleet.command") && recallable &&
              <Button disabled={fleets.pending} onClick={(e) => open({ mode: "recall", mission: m }, e)}>Rappeler…</Button>}
          </li>;
        })}</ul>}
      </section>
        </div>
        <div className="d-stack d-fl-col">
        <section className="d-card d-panel d-fl-detail" aria-labelledby="fleet-detail-title">
          {focused ? <>
            <PanelHead id="fleet-detail-title" icon="icons/stats/stat-flottes.svg" title={focused.name}>
              <button type="button" className="d-btn" onClick={() => setFocus(null)}>Vue d’ensemble</button></PanelHead>
            <Thumb src={shipImage(mainClass(focused.stacks))} icon="icons/sidebar/nav-flottes.svg" className="d-thumb--wide" />
            <dl className="d-fl-facts">
              <div><dt>Vaisseaux</dt><dd>{count(focused.stacks)}</dd></div>
              <div><dt>Cargo</dt><dd>{units(focused.capacity)}</dd></div>
              <div><dt>Statut</dt><dd>{focused.status === "MOVING" ? "En mission" : focused.kind === "GARRISON" ? "Garnison" : "Stationnée"}</dd></div>
            </dl>
            <h3 className="d-fl-sub">Mission actuelle</h3>
            {focusMission ? <p>{kindLabels[focusMission.kind]} : {place(focusMission.origin)} → {place(focusMission.destination)} · arrivée {time(focusMission.travel_arrival_at)}</p>
              : <p className="d-note">Stationnée : {place(focused.system)}</p>}
            {focused.protocol !== undefined && <p>Protocole : {focused.protocol ? protocols[focused.protocol].label : "aucun"}</p>}
          </> : <PanelHead id="fleet-detail-title" icon="icons/stats/stat-flottes.svg" title="Composition de l’Empire" />}
          <h3 className="d-fl-sub">Composition</h3>
          {Object.keys(totals).length === 0 ? <p className="d-note">Aucun vaisseau.</p> : <ul className="d-fl-comp">{Object.entries(totals).sort(([, a], [, b]) => b - a).map(([c, n]) =>
            <li key={c}><span>{p.catalogue?.[c]?.name ?? c}</span><Bar value={n / biggest * 100} /><b>{n}</b></li>)}</ul>}
          {(() => {
            const classes = Object.keys(totals);
            const power = classes.reduce((n, c) => n + (p.catalogue?.[c]?.attack ?? 0) * totals[c], 0);
            const hull = classes.reduce((n, c) => n + (p.catalogue?.[c]?.hull ?? 0) * totals[c], 0);
            const hops = classes.map((c) => p.catalogue?.[c]?.hop_us).filter((v): v is string => !!v).map(Number);
            return classes.length > 0 && <dl className="d-fl-facts">
              <div><dt>Puissance</dt><dd>{power.toLocaleString("fr-FR")}</dd></div>
              <div><dt>Coque</dt><dd>{hull.toLocaleString("fr-FR")}</dd></div>
              <div><dt>Par saut</dt><dd>{focused && hops.length ? duration(String(Math.max(...hops))) : "—"}</dd></div>
            </dl>;
          })()}
          <p className="d-note">Puissance et coque : attaque et coque cumulées des vaisseaux militaires ; un saut se fait au rythme du plus lent.</p>
          {!focused && <p className="d-note">Choisissez « Détails » sur une flotte pour l’afficher ici.</p>}
        </section>
      {p.combat?.alerts && <section className="panel" aria-labelledby="alerts-title"><div className="panel-head"><h2 id="alerts-title">Menaces annoncées</h2>
        <span className="panel-meta">{p.combat.alerts.filter((a) => a.state === "pending").length}</span></div>
        {p.combat.alerts.length === 0 ? <p>Aucune force hostile annoncée.</p> : <ul className="fleet-list">{p.combat.alerts.map((a) => {
          const system = p.systems!.find((s) => s.id === a.system_id);
          const world = system?.planets?.find((pl) => pl.id === a.planet_id);
          return <li key={a.id} className="fleet-card combat-alert" role={a.state === "pending" ? "alert" : undefined}>
            <div className="panel-head"><h3>{a.state === "pending" ? "Force hostile en approche" : "Menace levée"}</h3>
              <Badge tone={a.state === "pending" ? "danger" : "neutral"}>{a.state === "pending" ? "En attente" : "Annulée"}</Badge></div>
            <p>Cible : {a.opportunity_id ? "votre exploitation du gisement" : world?.name ?? "votre monde"} — {place(system ?? null)}</p>
            <p>Bataille : {time(a.battle_at)}</p>
            <p className="panel-meta">{a.opportunity_id
              ? "Ni l’attaquant, ni son origine, ni sa force ne sont connus avant la bataille. Les escortes de vos extractions à l’œuvre et vos flottes stationnées dans ce système défendront ; des extracteurs sans escorte seraient détruits."
              : "Ni l’attaquant, ni son origine, ni sa force ne sont connus avant la bataille. Seules vos unités militaires stationnées dans ce système à l’échéance combattront."}</p>
          </li>;
        })}</ul>}
      </section>}
        </div>
      </div>
      <div className="d-fl-prod">
      {p.colonies!.map((colony) => {
        const choice = order[colony.id] ?? { ship: Object.keys(p.catalogue!)[0], quantity: 1 };
        const ship = p.catalogue![choice.ship];
        // The colonizer price is Empire-wide and progressive: show the current server quote.
        const colonizer = choice.ship === p.colonization?.colonizer_class;
        const unitCost = colonizer && p.colonization?.colonizer_quote ? p.colonization.colonizer_quote.cost : ship.cost;
        return <section key={colony.id} className="panel fleet-production" aria-labelledby={`production-${colony.id}`}>
          <div className="panel-head"><h2 id={`production-${colony.id}`}>Production — {colony.name}</h2>
            <span className="panel-meta">{colony.orders.length} / {p.queue_limit} ordres</span></div>
          <p className="panel-meta">Les vaisseaux sortent du Chantier orbital un par un et rejoignent aussitôt la garnison.</p>
          {can("fleet.build") && <form className="fleet-order" onSubmit={async (e) => {
            e.preventDefault();
            const quantity = colonizer ? 1 : choice.quantity;
            const result = await fleets.run("/orders", { colony_id: colony.id, ship_class: choice.ship, quantity }, JSON.stringify([colony.id, choice.ship, quantity]));
            if (result) onEconomyChanged?.();
          }}>
            <label className="galaxy-field">Classe
              <select value={choice.ship} onChange={(e) => setOrder({ ...order, [colony.id]: { ...choice, ship: e.target.value } })}>
                {Object.entries(p.catalogue!).map(([key, c]) => <option key={key} value={key}>{c.name}{p.combat?.classes.includes(key) ? " (militaire)" : ""}</option>)}
              </select></label>
            <Counter label="Quantité" value={colonizer ? 1 : choice.quantity} max={colonizer ? 1 : p.max_quantity!} onChange={(n) => setOrder({ ...order, [colony.id]: { ...choice, quantity: Math.max(1, n) } })} />
            <p className="fleet-unit">{colonizer ? "Prix serveur actuel" : "Par unité"} : {resourceKeys.map((k) => `${units(unitCost[k])} ${resourceLabels[k]}`).join(" · ")} · {duration(ship.build_us)} de fabrication · {units(ship.cargo)} de cargo{ship.survey ? " · cartographie" : ""}{p.combat?.classes.includes(choice.ship) ? " · militaire" : ""}</p>
            {!!ship.requires?.length && <p className="fleet-unit">Nécessite : {ship.requires.map((r) => `${infrastructureLabel(r.infrastructure_type)} niveau ${r.level}`).join(", ")} dans la colonie.</p>}
            {colonizer && p.colonization?.colonizer_quote && <p className="panel-meta">Coût progressif : rang {p.colonization.colonizer_quote.rank} (colonies, colonisateurs et ordres en cours), ×{p.colonization.colonizer_quote.multiplier_bps / 10000}. Recalculé et figé par le serveur à la confirmation.</p>}
            <Button className="button--primary" type="submit" disabled={fleets.pending || colony.orders.length >= p.queue_limit!}>Commander</Button>
          </form>}
          {colony.orders.length === 0 ? <p>Aucune production en cours.</p> : <ol className="fleet-list">{colony.orders.map((o) =>
            <li key={o.id} className="fleet-card"><div className="panel-head"><strong>{o.quantity} × {p.catalogue![o.ship_class]?.name ?? o.ship_class}</strong>
              <Badge tone={o.status === "active" ? "accent" : "neutral"}>{o.status === "active" ? "En fabrication" : "En attente"}</Badge></div>
              {o.quantity > 1 && <p className="fleet-unit">{o.delivered ?? 0} / {o.quantity} livrée{(o.delivered ?? 0) > 1 ? "s" : ""} · les unités sortent une à une</p>}
              {o.status === "active" && o.started_at && o.due_at && <Clock start={unitStart(o)} end={o.due_at} serverTime={p.server_time} receivedAt={fleets.receivedAt} label={o.quantity > 1 ? "Avancement de l’unité en fabrication" : "Avancement estimé de la production"} />}
              {o.cancel && <Button onClick={(e) => open({ mode: "cancel", order: o }, e)} disabled={fleets.pending}>Annuler…</Button>}
            </li>)}</ol>}
        </section>;
      })}
      </div>
      <div className="d-view-grid d-fl-more">
      {p.combat?.reports && <section className="panel" aria-labelledby="combat-reports-title"><h2 id="combat-reports-title">Rapports de combat</h2>
        {p.combat.reports.length === 0 ? <p>Aucun rapport de combat.</p> : <ul className="fleet-reports">{p.combat.reports.map((r) => {
          const system = p.systems!.find((s) => s.id === r.target.system_id);
          const world = system?.planets?.find((pl) => pl.id === r.target.planet_id);
          return <li key={`${r.engagement_id}-${r.role}`} className="combat-report">
            <strong>{outcomeLabels[r.outcome]}</strong> — {r.role === "attacker" ? "votre attaque" : "votre défense"} : {world?.name ?? "monde"} · {place(system ?? null)}
            {r.own && <dl className="fleet-dates"><Losses label="Vos forces" side={r.own} p={p} /><Losses label={`Forces adverses (Empire ${r.opponent_empire_id!.slice(0, 8)})`} side={r.opponent} p={p} />
              <div><dt>Rounds</dt><dd>{r.rounds!.length}</dd></div></dl>}
            {r.outcome === "voided_by_pact" && <p>Un pacte de non-agression était actif à l’heure de la bataille : aucun tir, aucune perte. {r.role === "attacker" ? "Votre flotte rentre ; le carburant n’est pas remboursé." : "Votre défense n’a pas été engagée."}</p>}
            <p className="panel-meta">Bataille à {time(r.battle_at)} · traitée par le serveur {time(r.processed_at)} · observation datée, sans surveillance durable.</p>
          </li>;
        })}</ul>}
      </section>}
      {p.frontier && <FrontierPanel frontier={p.frontier} p={p} />}
      <section className="panel" aria-labelledby="reports-title"><h2 id="reports-title">Rapports récents</h2>
        {reports.length === 0 ? <p>Aucun rapport de flotte.</p> : <ul className="fleet-reports">{reports.map((m) => <li key={m.id}>
          <strong>{reportTitle(m)}</strong> — {fleetName(m.fleet_id)} : {place(m.report!.result.kind === "RECALLED" ? m.origin : m.destination)}{m.target_planet ? ` · monde ${m.target_planet.name}` : ""}
          <p className="panel-meta">Observé à l’échéance {time(m.report!.observed_at)} · traité par le serveur {time(m.report!.processed_at)}</p>
        </li>)}</ul>}
      </section>
      </div>
    </>}
    <dialog ref={box} className="research-dialog" aria-labelledby="fleet-dialog-title" onClose={() => { if (dialog) close(); }}>
      {dialog && <form method="dialog" onSubmit={submit}>
        <h2 id="fleet-dialog-title">{{ send: "Envoyer une flotte", split: "Diviser la flotte", merge: "Fusionner", load: "Charger", unload: "Décharger", cancel: "Annuler la production", recall: "Rappeler la flotte" }[dialog.mode]}</h2>
        {renderDialog()}
        <div className="dialog-actions">
          <Button onClick={close}>Fermer</Button>
          <Button className="button--primary" type="submit" disabled={fleets.pending}>{dialog.mode === "send" && (!dialog.quote || dialog.quoted !== intentOf(dialog)) ? "Calculer le devis" : "Confirmer"}</Button>
        </div>
      </form>}
    </dialog>
  </div>;

  function renderDialog(): ReactNode {
    if (!dialog || !p?.available) return null;
    if (dialog.mode === "cancel") {
      const c = dialog.order.cancel!;
      return <><p>Aucun vaisseau partiel n’est créé. Remboursement selon l’état de l’ordre, plafonné par le stockage de la colonie :</p>
        <ul>{resourceKeys.map((k) => <li key={k}>{resourceLabels[k]} : {exactUnits(c.recoverable[k])} récupérés sur {exactUnits(c.theoretical[k])}{BigInt(c.lost[k]) > 0n ? `, ${exactUnits(c.lost[k])} perdus définitivement` : ""}</li>)}</ul>
        <p className="panel-meta">Estimation serveur au {time(p.server_time)} ; le résultat exact est calculé à la confirmation.</p></>;
    }
    if (dialog.mode === "recall") return dialog.mission.kind === "ATTACK"
      ? <p>L’attaque est annulée avant la bataille. {dialog.mission.hops === 0 ? "Même système : la flotte reste stationnée sur place immédiatement." : `Retour vers ${place(dialog.mission.origin)} : chemin déjà parcouru, ou un trajet complet si la flotte est arrivée. Carburant aller-retour déjà payé, sans remboursement.`}</p>
      : <p>La flotte refera le chemin déjà parcouru : retour vers {place(dialog.mission.origin)} sans coût ni remboursement, cargaison conservée. Possible seulement pendant le trajet.</p>;
    if (!current) return <p role="alert">Flotte indisponible. Actualisez.</p>;
    const capacityNote = <p className="panel-meta">Capacité de cargo : {units(current.capacity)} · à bord : <Cargo cargo={current.cargo} /></p>;
    const colonyChoice = (value: string, set: (colony: string) => void) => current.colonies_here.length > 1 ?
      <label className="galaxy-field">Colonie
        <select required value={value} onChange={(e) => set(e.target.value)}>
          <option value="">Choisir…</option>
          {current.colonies_here.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select></label> : <p>Colonie : {current.colonies_here[0]?.name ?? "—"}</p>;
    if (dialog.mode === "unload") {
      const chosen = current.colonies_here.find((c) => c.id === dialog.colony);
      return <>{colonyChoice(dialog.colony, (colony) => setDialog({ ...dialog, colony }))}
        <p>Crédit jusqu’à la capacité de stockage libre de la colonie ; le surplus reste à bord, sans perte.</p>
        {chosen?.unload && <ul>{resourceKeys.filter((k) => BigInt(current.cargo[k]) > 0n).map((k) => <li key={k}>{resourceLabels[k]} : {units(chosen.unload!.credited[k])} crédités, {units(chosen.unload!.kept[k])} conservés à bord</li>)}</ul>}
        <p className="panel-meta">Estimation au {time(p.server_time)}.</p></>;
    }
    if (dialog.mode === "merge") return <label className="galaxy-field">Flotte de destination
      <select required value={dialog.target} onChange={(e) => setDialog({ ...dialog, target: e.target.value })}>
        <option value="">Choisir…</option>
        {stationed.filter((o) => o.id !== current.id && o.system?.id === current.system?.id).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select></label>;
    const cargoInputs = (values: Record<string, number>, max: (k: keyof Amounts) => number, set: (v: Record<string, number>) => void) =>
      <fieldset className="fleet-fieldset"><legend>Cargaison (unités)</legend>{resourceKeys.map((k) =>
        <Counter key={k} label={resourceLabels[k]} value={values[k] ?? 0} max={max(k)} onChange={(n) => set({ ...values, [k]: n })} />)}</fieldset>;
    if (dialog.mode === "load") return <>{colonyChoice(dialog.colony, (colony) => setDialog({ ...dialog, colony }))}{capacityNote}
      {cargoInputs(dialog.cargo, () => Number(BigInt(current.capacity) / 1_000_000n), (cargo) => setDialog({ ...dialog, cargo }))}
      <p className="panel-meta">Prélevé dans le stock de la colonie choisie ; refusé si stock ou capacité insuffisants.</p></>;
    const unitInputs = (values: Record<string, number>, set: (v: Record<string, number>) => void) =>
      <fieldset className="fleet-fieldset"><legend>Unités engagées</legend>{Object.entries(current.stacks).map(([c, n]) =>
        <Counter key={c} label={p.catalogue![c]?.name ?? c} value={values[c] ?? 0} max={n} onChange={(v) => set({ ...values, [c]: v })} />)}</fieldset>;
    const hasCargo = resourceKeys.some((k) => BigInt(current.cargo[k]) > 0n);
    const cargoMax = (k: keyof Amounts) => Number(BigInt(current.cargo[k]) / 1_000_000n);
    if (dialog.mode === "split") return <>{unitInputs(dialog.units, (u) => setDialog({ ...dialog, units: u }))}
      {hasCargo && cargoInputs(dialog.cargo, cargoMax, (cargo) => setDialog({ ...dialog, cargo }))}{capacityNote}
      <p className="panel-meta">Chaque flotte résultante doit pouvoir porter sa cargaison, sinon l’opération est refusée.</p></>;
    const destinations = p.systems!.filter((s) => s.id !== current.system?.id &&
      (dialog.kind === "SURVEY" ? s.state === "DETECTED" : s.state !== "DETECTED"));
    const colonizer = p.colonization?.colonizer_class;
    // COLONIZE is offered only by the pinned ruleset, the rights and a colonizer aboard.
    const canColonize = !!colonizer && !!current.stacks[colonizer] && can("colony.expand") && can("galaxy.read");
    // ATTACK: pinned ruleset, explicit combat rights and military units aboard; civilians never fight.
    const military = p.combat?.classes ?? [];
    const canAttack = military.some((c) => current.stacks[c]) && can("combat.attack") && can("combat.read") && can("galaxy.read");
    const kinds: MissionKind[] = ["DEPLOY", "SURVEY", "RETURN", ...(canColonize ? ["COLONIZE" as const] : []), ...(canAttack ? ["ATTACK" as const] : [])];
    // Worlds from Knowledge only; an own colony is excluded only when colony.read names it.
    const worlds = p.systems!.flatMap((s) => (s.planets ?? []).filter((pl) => !pl.colony_id).map((pl) => ({ ...pl, system: s })));
    // Same rule as the server: only a task fleet sent whole carries its cargo implicitly; any
    // detachment (garrison, or part of a task fleet) sends exactly the cargo chosen here.
    const whole = sentWhole(dialog);
    const aboard = whole ? Object.fromEntries(resourceKeys.map((k) => [k, Number(BigInt(current.cargo[k]) / 1_000_000n)])) : dialog.cargo;
    const minimum = p.colonization?.package_minimum;
    const short = !!minimum && resourceKeys.some((k) => (aboard[k] ?? 0) * 1_000_000 < Number(minimum[k]));
    return <>
      <p>Depuis {place(current.system)} — {current.name}. Trajet et coûts calculés par le serveur sur vos routes connues.</p>
      <fieldset className="fleet-fieldset"><legend>Mission</legend>{kinds.map((k) =>
        <label key={k} className="fleet-choice"><input type="radio" name="kind" checked={dialog.kind === k}
          onChange={() => edit({ kind: k, destination: "", planet: "", units: k === "COLONIZE" && colonizer ? { [colonizer]: 1 } : {} })} /> {kindLabels[k]}</label>)}</fieldset>
      {dialog.kind === "ATTACK" ? <>
        <label className="galaxy-field">Monde visé
          <select required value={dialog.planet} onChange={(e) => edit({ planet: e.target.value })}>
            <option value="">Choisir…</option>
            {worlds.map((w) => <option key={w.id} value={w.id}>{w.name} — {place(w.system)}</option>)}
          </select></label>
        <p className="panel-meta">Occupation et défense non confirmées. Elles ne sont jamais révélées avant la bataille ; un monde sans colonie étrangère fait échouer l’attaque, au même coût.</p>
        <fieldset className="fleet-fieldset"><legend>Unités militaires engagées</legend>{Object.entries(current.stacks).filter(([c]) => military.includes(c)).map(([c, n]) =>
          <Counter key={c} label={p.catalogue![c]?.name ?? c} value={dialog.units[c] ?? 0} max={n} onChange={(v) => edit({ units: { ...dialog.units, [c]: v } })} />)}</fieldset>
      </> : dialog.kind === "COLONIZE" ? <>
        <label className="galaxy-field">Monde visé
          <select required value={dialog.planet} onChange={(e) => edit({ planet: e.target.value })}>
            <option value="">Choisir…</option>
            {worlds.map((w) => <option key={w.id} value={w.id}>{w.name} — {place(w.system)} · {w.sector_capacity} secteurs · {w.orbital_capacity} orbitaux</option>)}
          </select></label>
        <p className="panel-meta">Occupation actuelle inconnue : elle n’est vérifiée qu’à l’arrivée. Un monde indisponible fait échouer la mission sans révéler son occupant.</p>
        <p>Engage exactement 1 {p.catalogue![colonizer!]?.name ?? colonizer}, consommé à la fondation ; conservé avec son cargo en cas d’échec ou de rappel.</p>
      </> : dialog.kind !== "RETURN" ? <label className="galaxy-field">Destination
        <select required value={dialog.destination} onChange={(e) => edit({ destination: e.target.value })}>
          <option value="">Choisir…</option>
          {destinations.map((s) => <option key={s.id} value={s.id}>{place(s)}</option>)}
        </select></label> : <p>Retour vers le système de la colonie d’attache.</p>}
      {dialog.kind !== "COLONIZE" && dialog.kind !== "ATTACK" && unitInputs(dialog.units, (units) => edit({ units }))}
      {hasCargo && !whole && dialog.kind !== "ATTACK" && cargoInputs(dialog.cargo, cargoMax, (cargo) => edit({ cargo }))}
      {dialog.kind === "COLONIZE" && minimum && <p className={short ? "feedback feedback--error" : "panel-meta"}>
        Paquet de fondation (tout le cargo engagé devient le stock initial) : minimum {resourceKeys.map((k) => `${units(minimum[k])} ${resourceLabels[k]}`).join(" · ")}{short ? " — insuffisant, chargez d’abord le colonisateur." : "."}</p>}
      {dialog.error && <p role="alert" className="feedback feedback--error">{message(dialog.error)}</p>}
      {dialog.quote && dialog.quoted === intentOf(dialog) && <div className="fleet-quote" aria-live="polite">
        <p><strong>{dialog.quote.hops} saut(s)</strong> · trajet {duration(dialog.quote.travel_us)}{dialog.quote.kind === "SURVEY" ? ` · analyse ${duration(dialog.quote.survey_us)}` : ""}</p>
        <p>Carburant payé au départ par la colonie d’attache{dialog.quote.kind === "ATTACK" ? " (aller et retour)" : ""} : {resourceKeys.filter((k) => BigInt(dialog.quote!.cost[k]) > 0n).map((k) => `${units(dialog.quote!.cost[k])} ${resourceLabels[k]}`).join(" · ") || "aucun"}</p>
        <p>Arrivée estimée : {time(dialog.quote.travel_arrival_at)}{dialog.quote.kind === "SURVEY" ? ` · cartographie à ${time(dialog.quote.due_at)}` : ""}</p>
        {dialog.quote.kind === "ATTACK" && dialog.quote.battle_at && <p><strong>Bataille : {time(dialog.quote.battle_at)}</strong> · {Object.entries(dialog.quote.units ?? {}).map(([c, n]) => `${n} ${p.catalogue![c]?.name ?? c}`).join(" · ")}</p>}
        {!dialog.quote.affordable && <p className="feedback feedback--error">Stock probablement insuffisant dans la colonie d’attache.</p>}
        <p className="panel-meta">{dialog.quote.kind === "ATTACK" ? "Au moins 24 h entre le départ et la bataille. Rappel possible jusqu’à la bataille ; aucun remboursement. Seules des unités militaires peuvent être perdues ; ni butin ni conquête." : dialog.quote.hops === 0 ? "Même système : aucun trajet, aucun carburant, résolution par le serveur dès sa prise en charge, sans rappel possible." : "Aucun remboursement après le départ. Rappel possible uniquement pendant le trajet."}</p>
      </div>}
    </>;
  }
}
