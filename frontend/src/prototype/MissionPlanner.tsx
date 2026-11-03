import { useEffect, useRef } from "react";
import type { FleetView } from "../fleet/api";
import { duration, resourceKeys, resourceLabels, time, units as amount } from "../colony/format";
import { refusal } from "./copy";
import type { QuoteState } from "./copy";
import { actionLabels, engageable, systemName } from "./model";
import type { ActionOffer, World } from "./model";

const risks: Record<string, string> = {
  SURVEY: "La sonde révèle le système à l’arrivée, puis l’analyse dure le temps indiqué.",
  DEPLOY: "Aucun remboursement après le départ. Rappel possible pendant le trajet seulement.",
  COLONIZE: "L’occupation du monde n’est vérifiée qu’à l’arrivée ; un monde pris fait échouer la mission sans révéler l’occupant.",
  ATTACK: "Défense et occupation adverses restent inconnues jusqu’à la bataille. Seules des unités militaires peuvent être perdues ; ni butin ni conquête.",
};

function Step({ n, label, done, current }: { n: number; label: string; done: boolean; current: boolean }) {
  return <li className={`proto-step${done ? " is-done" : ""}${current ? " is-current" : ""}`} aria-current={current ? "step" : undefined}>
    <span aria-hidden="true">{done ? "✓" : n}</span>{label}</li>;
}

/** Steps 2–4 of the journey, inline in the context panel: fleet, units, server summary, confirm. */
export function MissionPlanner({ world, target, offer, fleets, fleet, units, quote, routeMode, pending, onFleet, onUnits, onConfirm, onCancel }: {
  world: World; target: string; offer: ActionOffer; fleets: FleetView[]; fleet: FleetView | null; units: Record<string, number>;
  quote: QuoteState; routeMode: "contract" | "extension"; pending: boolean;
  onFleet: (id: string) => void; onUnits: (u: Record<string, number>) => void; onConfirm: () => void; onCancel: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, [offer.kind, offer.planet]);
  const catalogue = world.fleets.catalogue ?? {};
  const available = fleet ? engageable(world, fleet, offer.kind) : {};
  const chosen = Object.values(units).some((n) => n > 0);
  const step = !fleet ? 2 : !chosen ? 3 : 4;
  const q = quote.status === "ready" ? quote.quote : null;
  const steps = q?.path && routeMode === "extension" ? q.path : null;

  return <section className="proto-planner" aria-labelledby="proto-planner-title" onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }}>
    <div className="proto-planner-head">
      <h2 id="proto-planner-title" ref={heading} tabIndex={-1}>{offer.label}</h2>
      <button type="button" className="button proto-ghost" onClick={onCancel}>Annuler</button>
    </div>
    <p className="proto-target">Cible : <strong>{systemName(world, target)}</strong></p>
    <ol className="proto-steps" aria-label="Étapes de la mission">
      <Step n={1} label="Cible et action" done current={false} />
      <Step n={2} label="Flotte" done={step > 2} current={step === 2} />
      <Step n={3} label="Unités" done={step > 3} current={step === 3} />
      <Step n={4} label="Vérifier et confirmer" done={false} current={step === 4} />
    </ol>

    <fieldset className="proto-block">
      <legend>Quelle flotte envoyer ?</legend>
      {fleets.length === 0 ? <p>{offer.reason}</p> : <div className="proto-choices">{fleets.map((f) => {
        const engage = engageable(world, f, offer.kind);
        return <label key={f.id} className={`proto-choice${fleet?.id === f.id ? " is-chosen" : ""}`}>
          <input type="radio" name="proto-fleet" checked={fleet?.id === f.id} onChange={() => onFleet(f.id)} />
          <span className="proto-choice-title">{f.name}{f.kind === "GARRISON" && <small> · garnison</small>}</span>
          <span className="proto-choice-meta">À {systemName(world, f.system?.id)} · {Object.entries(engage).map(([c, n]) => `${n} ${catalogue[c]?.name ?? c}`).join(", ")}</span>
        </label>;
      })}</div>}
    </fieldset>

    {fleet && <fieldset className="proto-block">
      <legend>Unités engagées</legend>
      {offer.kind === "COLONIZE" ? <p>1 {catalogue[Object.keys(available)[0]]?.name ?? "colonisateur"}, consommé à la fondation, avec tout le cargo à bord.</p>
        : <>
          <p className="proto-help">Par défaut, toutes les unités adaptées partent. Ajustez si vous voulez en garder sur place.</p>
          {Object.entries(available).map(([c, max]) => {
            const value = units[c] ?? 0;
            return <div key={c} className="proto-stepper" role="group" aria-label={catalogue[c]?.name ?? c}>
              <span className="proto-stepper-label">{catalogue[c]?.name ?? c}</span>
              <button type="button" className="button" aria-label={`Une ${catalogue[c]?.name ?? c} de moins`} disabled={value <= 0}
                onClick={() => onUnits({ ...units, [c]: value - 1 })}>−</button>
              <output aria-live="polite">{value} / {max}</output>
              <button type="button" className="button" aria-label={`Une ${catalogue[c]?.name ?? c} de plus`} disabled={value >= max}
                onClick={() => onUnits({ ...units, [c]: value + 1 })}>+</button>
            </div>;
          })}
        </>}
    </fieldset>}

    {fleet && chosen && <section className="proto-block proto-summary" aria-live="polite" aria-busy={quote.status === "loading"}>
      <h3>Résumé calculé par le serveur</h3>
      {quote.status === "loading" && <p className="proto-loading">Calcul du trajet, de la durée et du coût…</p>}
      {quote.status === "error" && <p role="alert" className="feedback feedback--error">{refusal(quote.code)}</p>}
      {q && <>
        <dl className="proto-facts">
          <div><dt>Trajet</dt><dd>{q.hops === 0 ? "Même système" : `${q.hops} saut${q.hops > 1 ? "s" : ""}`}</dd></div>
          <div><dt>Durée</dt><dd>{duration(q.travel_us)}{q.kind === "SURVEY" ? ` + analyse ${duration(q.survey_us)}` : ""}</dd></div>
          <div><dt>Arrivée</dt><dd>{time(q.travel_arrival_at)}</dd></div>
          {q.battle_at && <div><dt>Bataille</dt><dd>{time(q.battle_at)}</dd></div>}
          <div><dt>Carburant</dt><dd>{resourceKeys.filter((k) => BigInt(q.cost[k]) > 0n).map((k) => `${amount(q.cost[k])} ${resourceLabels[k]}`).join(" · ") || "aucun"}{q.kind === "ATTACK" ? " (aller-retour)" : ""}</dd></div>
        </dl>
        {steps ? <ol className="proto-route-steps" aria-label="Étapes du trajet">{steps.map((id, i) =>
          <li key={id}>{i === 0 ? "Départ" : i === steps.length - 1 ? "Arrivée" : `Étape ${i}`} : {systemName(world, id)}</li>)}</ol>
          : <p className="proto-help">Itinéraire exact calculé par le serveur sur vos routes connues ; la carte montre une ligne directe indicative.</p>}
        {!q.affordable && <p className="feedback feedback--error">Stock probablement insuffisant dans la colonie d’attache.</p>}
        <p className="proto-risk"><strong>À savoir :</strong> {risks[q.kind]}</p>
        <button type="button" className="button button--primary proto-confirm" disabled={pending} onClick={onConfirm}>
          {pending ? "Envoi…" : `Confirmer : ${actionLabels[q.kind].toLowerCase()}`}</button>
      </>}
    </section>}
  </section>;
}
