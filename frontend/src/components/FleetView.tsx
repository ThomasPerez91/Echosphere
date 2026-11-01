import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useFleets } from "../hooks/useFleets";
import { ApiError, previewMission } from "../fleet/api";
import type { Amounts } from "../colony/api";
import type { FleetProjection, MissionKind, MissionView, Quote, ShipOrder } from "../fleet/api";
import { duration, exactUnits, resourceKeys, resourceLabels, time, units } from "../colony/format";
import { Badge, Button, EmptyState, Panel } from "./ui";

const kindLabels: Record<MissionKind, string> = { DEPLOY: "Déploiement", SURVEY: "Cartographie", RETURN: "Retour" };
const messages: Record<string, string> = {
  accepted: "Ordre accepté par le serveur.",
  insufficient_resources: "Ressources insuffisantes dans la colonie concernée.",
  queue_full: "La file de production de cette colonie est pleine (3 ordres).",
  units_unavailable: "Ces unités ne sont plus disponibles dans la flotte.",
  cargo_capacity: "La cargaison dépasserait la capacité d’une flotte.",
  cargo_unavailable: "Cette cargaison n’est plus à bord.",
  fleet_moving: "Cette flotte est en mission : sa composition ne peut pas changer.",
  fleet_elsewhere: "Les flottes ou la colonie ne sont pas dans le même système.",
  recall_too_late: "Trop tard : la flotte est arrivée ou son analyse a commencé.",
  recall_refused: "Un retour ne peut pas être rappelé.",
  survey_units: "Une cartographie n’engage que des sondes.",
  destination_unmapped: "Destination non cartographiée : envoyez d’abord une sonde.",
  destination_mapped: "Ce système est déjà cartographié.",
  destination_unreachable: "Aucun trajet connu ne mène à ce système.",
  system_not_found: "Ce système n’est pas dans vos connaissances.",
  order_completed: "Cette production est déjà terminée.",
  permission_denied: "Votre accès à cet Empire ne permet pas cette action.",
  fleet_unavailable: "Les flottes n’existent pas dans les règles de cette partie.",
  authentication_required: "Votre session a expiré. Retournez au lobby pour entrer à nouveau.",
  idempotency_conflict: "Cette action a déjà été envoyée avec un autre contenu. Actualisez.",
  fleet_busy: "Des événements de flotte sont en cours de traitement. Réessayez dans un instant.",
  invalid_request: "Action invalide. Actualisez la page.",
};
const message = (code: string) => messages[code] ?? "Service Game indisponible. Réessayer n’enverra pas l’action deux fois.";

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

type Dialog =
  | { mode: "send"; fleet: string; kind: MissionKind; destination: string; units: Record<string, number>; cargo: Record<string, number>; quote: Quote | null; error: string | null }
  | { mode: "split"; fleet: string; units: Record<string, number>; cargo: Record<string, number> }
  | { mode: "merge"; fleet: string; target: string }
  | { mode: "load"; fleet: string; cargo: Record<string, number> }
  | { mode: "unload"; fleet: string }
  | { mode: "cancel"; order: ShipOrder }
  | { mode: "recall"; mission: MissionView };

function Counter({ label, value, max, onChange }: { label: string; value: number; max: number; onChange: (n: number) => void }) {
  return <label className="galaxy-field fleet-counter">{label}
    <input type="number" inputMode="numeric" min={0} max={max} value={value}
      onChange={(e) => onChange(Math.max(0, Math.min(max, Math.floor(Number(e.target.value) || 0))))} />
    <span className="panel-meta">maximum {max}</span>
  </label>;
}

export function FleetView({ universe, enabled, csrf, onSessionLost, onEconomyChanged, target }: {
  universe: string; enabled: boolean; csrf?: string; onSessionLost: () => void; onEconomyChanged?: () => void;
  target?: { empire: string; system: string };
}) {
  const fleets = useFleets(universe, enabled, csrf, onSessionLost);
  const p = fleets.projection;
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [order, setOrder] = useState<Record<string, { ship: string; quantity: number }>>({});
  const box = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const prefilled = useRef(false);
  const can = (right: string) => !!p?.permissions.includes(right);

  useEffect(() => {
    if (dialog) { if (!box.current?.open) box.current?.showModal(); }
    else if (box.current?.open) box.current.close();
  }, [dialog]);

  const stationed = p?.available ? p.fleets!.filter((f) => f.status === "STATIONED") : [];
  const moving = p?.available ? p.missions!.filter((m) => m.status !== "completed") : [];
  const reports = p?.available ? p.missions!.filter((m) => m.report).slice(0, 8) : [];

  // "Envoyer une flotte ici" from Galaxy/System View: same flow, destination prefilled once.
  useEffect(() => {
    if (prefilled.current || !p?.available || !target || p.empire.id !== target.empire) return;
    prefilled.current = true;
    const fleet = p.fleets!.find((f) => f.status === "STATIONED" && Object.keys(f.stacks).length && f.system?.id !== target.system);
    const system = p.systems!.find((s) => s.id === target.system);
    if (!fleet || !system || !p.permissions.includes("fleet.command")) return;
    setDialog({ mode: "send", fleet: fleet.id, kind: system.state === "DETECTED" ? "SURVEY" : "DEPLOY",
      destination: system.id, units: {}, cargo: {}, quote: null, error: null });
  }, [p, target]);

  const open = (next: Dialog, event: { currentTarget: HTMLElement }) => { trigger.current = event.currentTarget; setDialog(next); };
  const close = () => { setDialog(null); window.setTimeout(() => trigger.current?.focus(), 0); };
  const done = (result: unknown) => { if (result) { close(); onEconomyChanged?.(); } };
  const toCargo = (values: Record<string, number>) => Object.fromEntries(Object.entries(values).filter(([, v]) => v > 0));

  async function quote(d: Extract<Dialog, { mode: "send" }>) {
    if (!p || !csrf) return;
    try {
      const q = await previewMission(universe, p.empire.id, csrf, {
        fleet_id: d.fleet, kind: d.kind, units: toCargo(d.units),
        ...(d.kind === "RETURN" ? {} : { destination_id: d.destination }),
      }, p.permissions.includes("colony.read"), new AbortController().signal);
      setDialog({ ...d, quote: q, error: null });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) onSessionLost();
      setDialog({ ...d, quote: null, error: error instanceof ApiError ? error.code : "unavailable" });
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!dialog) return;
    if (dialog.mode === "send") {
      if (!dialog.quote) return void quote(dialog);
      done(await fleets.run("/missions", {
        fleet_id: dialog.fleet, kind: dialog.kind, units: toCargo(dialog.units),
        ...(dialog.kind === "RETURN" ? {} : { destination_id: dialog.destination }),
        ...(Object.keys(toCargo(dialog.cargo)).length ? { cargo: toCargo(dialog.cargo) } : {}),
      }, JSON.stringify(dialog)));
    } else if (dialog.mode === "split") {
      done(await fleets.run(`/${dialog.fleet}/split`, { units: toCargo(dialog.units), cargo: toCargo(dialog.cargo) }, JSON.stringify(dialog)));
    } else if (dialog.mode === "merge") {
      done(await fleets.run(`/${dialog.fleet}/merge`, { target_id: dialog.target }, dialog.target));
    } else if (dialog.mode === "load") {
      const fleet = p!.fleets!.find((f) => f.id === dialog.fleet)!;
      done(await fleets.run(`/${dialog.fleet}/load`, { colony_id: fleet.colony_here, cargo: toCargo(dialog.cargo) }, JSON.stringify(dialog)));
    } else if (dialog.mode === "unload") {
      const fleet = p!.fleets!.find((f) => f.id === dialog.fleet)!;
      done(await fleets.run(`/${dialog.fleet}/unload`, { colony_id: fleet.colony_here }, dialog.fleet));
    } else if (dialog.mode === "cancel") {
      done(await fleets.run(`/orders/${dialog.order.id}/cancel`, {}, dialog.order.id));
    } else {
      done(await fleets.run(`/missions/${dialog.mission.id}/recall`, {}, dialog.mission.id));
    }
  }

  if (fleets.phase === "loading" || fleets.phase === "idle") return <Panel title="Flottes"><p role="status">Lecture de vos flottes…</p></Panel>;
  if (fleets.phase === "empty") return <Panel title="Aucun Empire"><EmptyState title="Aucune flotte accessible">Votre accès ne comprend aucun Empire avec le droit de lecture des flottes.</EmptyState></Panel>;
  if (!p) return <Panel title="Flottes indisponibles"><p role="alert">{message(fleets.error ?? "unavailable")}</p><Button onClick={fleets.refresh}>Réessayer</Button></Panel>;

  const server = Date.parse(p.server_time) + (Date.now() - fleets.receivedAt);
  const fleetName = (fid: string) => p.fleets?.find((f) => f.id === fid)?.name ?? "Flotte";
  const current = dialog && "fleet" in dialog ? p.fleets?.find((f) => f.id === dialog.fleet) : undefined;

  return <div className="fleet-screen">
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
      {p.colonies!.map((colony) => {
        const choice = order[colony.id] ?? { ship: Object.keys(p.catalogue!)[0], quantity: 1 };
        const ship = p.catalogue![choice.ship];
        return <section key={colony.id} className="panel fleet-production" aria-labelledby={`production-${colony.id}`}>
          <div className="panel-head"><h2 id={`production-${colony.id}`}>Production — {colony.name}</h2>
            <span className="panel-meta">{colony.orders.length} / {p.queue_limit} ordres</span></div>
          <p className="panel-meta">Capacité de fabrication de base de la colonie : aucun secteur ni emplacement orbital utilisé. Le lot entier apparaît dans la garnison à la fin.</p>
          {can("fleet.build") && <form className="fleet-order" onSubmit={async (e) => {
            e.preventDefault();
            const result = await fleets.run("/orders", { colony_id: colony.id, ship_class: choice.ship, quantity: choice.quantity }, JSON.stringify([colony.id, choice]));
            if (result) onEconomyChanged?.();
          }}>
            <label className="galaxy-field">Classe
              <select value={choice.ship} onChange={(e) => setOrder({ ...order, [colony.id]: { ...choice, ship: e.target.value } })}>
                {Object.entries(p.catalogue!).map(([key, c]) => <option key={key} value={key}>{c.name}</option>)}
              </select></label>
            <Counter label="Quantité" value={choice.quantity} max={p.max_quantity!} onChange={(n) => setOrder({ ...order, [colony.id]: { ...choice, quantity: Math.max(1, n) } })} />
            <p className="fleet-unit">Par unité : {resourceKeys.map((k) => `${units(ship.cost[k])} ${resourceLabels[k]}`).join(" · ")} · {duration(ship.build_us)} de fabrication · {units(ship.cargo)} de cargo{ship.survey ? " · cartographie" : ""}</p>
            <Button className="button--primary" type="submit" disabled={fleets.pending || colony.orders.length >= p.queue_limit!}>Commander</Button>
          </form>}
          {colony.orders.length === 0 ? <p>Aucune production en cours.</p> : <ol className="fleet-list">{colony.orders.map((o) =>
            <li key={o.id} className="fleet-card"><div className="panel-head"><strong>{o.quantity} × {p.catalogue![o.ship_class]?.name ?? o.ship_class}</strong>
              <Badge tone={o.status === "active" ? "accent" : "neutral"}>{o.status === "active" ? "En fabrication" : "En attente"}</Badge></div>
              {o.status === "active" && o.started_at && o.due_at && <Clock start={o.started_at} end={o.due_at} serverTime={p.server_time} receivedAt={fleets.receivedAt} label="Avancement estimé de la production" />}
              {o.cancel && <Button onClick={(e) => open({ mode: "cancel", order: o }, e)} disabled={fleets.pending}>Annuler…</Button>}
            </li>)}</ol>}
        </section>;
      })}
      <section className="panel" aria-labelledby="stationed-title"><div className="panel-head"><h2 id="stationed-title">Flottes stationnées</h2>
        <span className="panel-meta">{stationed.length}</span></div>
        {stationed.length === 0 ? <p>Aucune flotte stationnée. Fabriquez une sonde pour commencer à cartographier.</p> :
          <ul className="fleet-list">{stationed.map((f) => <li key={f.id} className="fleet-card">
            <div className="panel-head"><h3>{f.name}</h3><Badge tone={f.kind === "GARRISON" ? "accent" : "neutral"}>{f.kind === "GARRISON" ? "Garnison" : "Opérationnelle"}</Badge></div>
            <p>Stationnée : {place(f.system)}</p>
            <Composition stacks={f.stacks} p={p} />
            <p className="panel-meta">Cargo : <Cargo cargo={f.cargo} /> · capacité {units(f.capacity)}</p>
            {can("fleet.command") && <div className="fleet-actions">
              {Object.keys(f.stacks).length > 0 && <Button className="button--primary" disabled={fleets.pending}
                onClick={(e) => open({ mode: "send", fleet: f.id, kind: "DEPLOY", destination: "", units: {}, cargo: {}, quote: null, error: null }, e)}>Envoyer…</Button>}
              {Object.keys(f.stacks).length > 0 && <Button disabled={fleets.pending} onClick={(e) => open({ mode: "split", fleet: f.id, units: {}, cargo: {} }, e)}>Diviser…</Button>}
              {f.kind === "TASK" && stationed.some((o) => o.id !== f.id && o.system?.id === f.system?.id) &&
                <Button disabled={fleets.pending} onClick={(e) => open({ mode: "merge", fleet: f.id, target: "" }, e)}>Fusionner…</Button>}
              {f.colony_here && BigInt(f.capacity) > 0n && <Button disabled={fleets.pending} onClick={(e) => open({ mode: "load", fleet: f.id, cargo: {} }, e)}>Charger…</Button>}
              {f.unload && <Button disabled={fleets.pending} onClick={(e) => open({ mode: "unload", fleet: f.id }, e)}>Décharger…</Button>}
            </div>}
          </li>)}</ul>}
      </section>
      <section className="panel" aria-labelledby="moving-title"><div className="panel-head"><h2 id="moving-title">Flottes en mission</h2>
        <span className="panel-meta">{moving.length}</span></div>
        {moving.length === 0 ? <p>Aucune flotte en mission.</p> : <ul className="fleet-list">{moving.map((m) => {
          const analysing = m.kind === "SURVEY" && m.status === "active" && server >= Date.parse(m.travel_arrival_at);
          return <li key={m.id} className="fleet-card">
            <div className="panel-head"><h3>{fleetName(m.fleet_id)}</h3>
              <Badge tone="accent">{m.status === "returning" ? "Retour après rappel" : analysing ? "Analyse en cours" : kindLabels[m.kind]}</Badge></div>
            <p>{place(m.origin)} → {place(m.destination)} · {m.hops} saut(s)</p>
            <Composition stacks={m.stacks} p={p} />
            <dl className="fleet-dates">
              <div><dt>Départ</dt><dd>{time(m.started_at)}</dd></div>
              {m.status === "returning" ? <div><dt>Retour prévu</dt><dd>{time(m.return_at!)}</dd></div> : <>
                <div><dt>{m.kind === "SURVEY" ? "Arrivée dans le système" : "Arrivée"}</dt><dd>{time(m.travel_arrival_at)}</dd></div>
                {m.kind === "SURVEY" && <div><dt>Fin d’analyse</dt><dd>{time(m.due_at)}</dd></div>}</>}
            </dl>
            <Clock start={m.status === "returning" ? m.recalled_at! : m.started_at} end={m.status === "returning" ? m.return_at! : m.due_at}
              serverTime={p.server_time} receivedAt={fleets.receivedAt} label="Avancement estimé de la mission" />
            {can("fleet.command") && m.status === "active" && m.kind !== "RETURN" && server < Date.parse(m.travel_arrival_at) &&
              <Button disabled={fleets.pending} onClick={(e) => open({ mode: "recall", mission: m }, e)}>Rappeler…</Button>}
          </li>;
        })}</ul>}
      </section>
      <section className="panel" aria-labelledby="reports-title"><h2 id="reports-title">Rapports récents</h2>
        {reports.length === 0 ? <p>Aucun rapport de flotte.</p> : <ul className="fleet-reports">{reports.map((m) => <li key={m.id}>
          <strong>{m.report!.result.kind === "RECALLED" ? "Rappel terminé" : kindLabels[m.kind]}</strong> — {fleetName(m.fleet_id)} : {place(m.report!.result.kind === "RECALLED" ? m.origin : m.destination)}
          <p className="panel-meta">Observé à l’échéance {time(m.report!.observed_at)} · traité par le serveur {time(m.report!.processed_at)}</p>
        </li>)}</ul>}
      </section>
    </>}
    <dialog ref={box} className="research-dialog" aria-labelledby="fleet-dialog-title" onClose={() => { if (dialog) close(); }}>
      {dialog && <form method="dialog" onSubmit={submit}>
        <h2 id="fleet-dialog-title">{{ send: "Envoyer une flotte", split: "Diviser la flotte", merge: "Fusionner", load: "Charger", unload: "Décharger", cancel: "Annuler la production", recall: "Rappeler la flotte" }[dialog.mode]}</h2>
        {renderDialog()}
        <div className="dialog-actions">
          <Button onClick={close}>Fermer</Button>
          <Button className="button--primary" type="submit" disabled={fleets.pending}>{dialog.mode === "send" && !dialog.quote ? "Calculer le devis" : "Confirmer"}</Button>
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
    if (dialog.mode === "recall") return <p>La flotte refera le chemin déjà parcouru : retour vers {place(dialog.mission.origin)} sans coût ni remboursement, cargaison conservée. Possible seulement pendant le trajet.</p>;
    if (!current) return <p role="alert">Flotte indisponible. Actualisez.</p>;
    const capacityNote = <p className="panel-meta">Capacité de cargo : {units(current.capacity)} · à bord : <Cargo cargo={current.cargo} /></p>;
    if (dialog.mode === "unload") return <><p>Crédit jusqu’à la capacité de stockage libre de la colonie ; le surplus reste à bord, sans perte.</p>
      <ul>{resourceKeys.filter((k) => BigInt(current.cargo[k]) > 0n).map((k) => <li key={k}>{resourceLabels[k]} : {units(current.unload!.credited[k])} crédités, {units(current.unload!.kept[k])} conservés à bord</li>)}</ul>
      <p className="panel-meta">Estimation au {time(p.server_time)}.</p></>;
    if (dialog.mode === "merge") return <label className="galaxy-field">Flotte de destination
      <select required value={dialog.target} onChange={(e) => setDialog({ ...dialog, target: e.target.value })}>
        <option value="">Choisir…</option>
        {stationed.filter((o) => o.id !== current.id && o.system?.id === current.system?.id).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
      </select></label>;
    const cargoInputs = (values: Record<string, number>, max: (k: keyof Amounts) => number, set: (v: Record<string, number>) => void) =>
      <fieldset className="fleet-fieldset"><legend>Cargaison (unités)</legend>{resourceKeys.map((k) =>
        <Counter key={k} label={resourceLabels[k]} value={values[k] ?? 0} max={max(k)} onChange={(n) => set({ ...values, [k]: n })} />)}</fieldset>;
    if (dialog.mode === "load") return <>{capacityNote}{cargoInputs(dialog.cargo, () => Number(BigInt(current.capacity) / 1_000_000n), (cargo) => setDialog({ ...dialog, cargo }))}
      <p className="panel-meta">Prélevé dans le stock de la colonie présente dans ce système ; refusé si stock ou capacité insuffisants.</p></>;
    const unitInputs = (values: Record<string, number>, set: (v: Record<string, number>) => void) =>
      <fieldset className="fleet-fieldset"><legend>Unités engagées</legend>{Object.entries(current.stacks).map(([c, n]) =>
        <Counter key={c} label={p.catalogue![c]?.name ?? c} value={values[c] ?? 0} max={n} onChange={(v) => set({ ...values, [c]: v })} />)}</fieldset>;
    const hasCargo = resourceKeys.some((k) => BigInt(current.cargo[k]) > 0n);
    const cargoMax = (k: keyof Amounts) => Number(BigInt(current.cargo[k]) / 1_000_000n);
    if (dialog.mode === "split") return <>{unitInputs(dialog.units, (u) => setDialog({ ...dialog, units: u }))}
      {hasCargo && cargoInputs(dialog.cargo, cargoMax, (cargo) => setDialog({ ...dialog, cargo }))}{capacityNote}
      <p className="panel-meta">Chaque flotte résultante doit pouvoir porter sa cargaison, sinon l’opération est refusée.</p></>;
    const reset = { quote: null, error: null };
    const destinations = p.systems!.filter((s) => s.id !== current.system?.id &&
      (dialog.kind === "SURVEY" ? s.state === "DETECTED" : s.state !== "DETECTED"));
    return <>
      <p>Depuis {place(current.system)} — {current.name}. Trajet et coûts calculés par le serveur sur vos routes connues.</p>
      <fieldset className="fleet-fieldset"><legend>Mission</legend>{(["DEPLOY", "SURVEY", "RETURN"] as MissionKind[]).map((k) =>
        <label key={k} className="fleet-choice"><input type="radio" name="kind" checked={dialog.kind === k}
          onChange={() => setDialog({ ...dialog, kind: k, destination: "", ...reset })} /> {kindLabels[k]}</label>)}</fieldset>
      {dialog.kind !== "RETURN" ? <label className="galaxy-field">Destination
        <select required value={dialog.destination} onChange={(e) => setDialog({ ...dialog, destination: e.target.value, ...reset })}>
          <option value="">Choisir…</option>
          {destinations.map((s) => <option key={s.id} value={s.id}>{place(s)}</option>)}
        </select></label> : <p>Retour vers le système de la colonie d’attache.</p>}
      {unitInputs(dialog.units, (u) => setDialog({ ...dialog, units: u, ...reset }))}
      {hasCargo && current.kind === "GARRISON" && cargoInputs(dialog.cargo, cargoMax, (cargo) => setDialog({ ...dialog, cargo, ...reset }))}
      {dialog.error && <p role="alert" className="feedback feedback--error">{message(dialog.error)}</p>}
      {dialog.quote && <div className="fleet-quote" aria-live="polite">
        <p><strong>{dialog.quote.hops} saut(s)</strong> · trajet {duration(dialog.quote.travel_us)}{dialog.quote.kind === "SURVEY" ? ` · analyse ${duration(dialog.quote.survey_us)}` : ""}</p>
        <p>Carburant payé au départ par la colonie d’attache : {resourceKeys.filter((k) => BigInt(dialog.quote!.cost[k]) > 0n).map((k) => `${units(dialog.quote!.cost[k])} ${resourceLabels[k]}`).join(" · ") || "aucun"}</p>
        <p>Arrivée estimée : {time(dialog.quote.travel_arrival_at)}{dialog.quote.kind === "SURVEY" ? ` · cartographie à ${time(dialog.quote.due_at)}` : ""}</p>
        {!dialog.quote.affordable && <p className="feedback feedback--error">Stock probablement insuffisant dans la colonie d’attache.</p>}
        <p className="panel-meta">Aucun remboursement après le départ. Rappel possible uniquement pendant le trajet.</p>
      </div>}
    </>;
  }
}
