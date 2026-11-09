import { useEffect, useRef } from "react";
import type { FleetView } from "../fleet/api";
import { duration, resourceKeys, resourceLabels, time, units as amount } from "../colony/format";
import { refusal, risks } from "./copy";
import type { QuoteState } from "./copy";
import { actionLabels, engageable, isGarrison, systemName } from "./model";
import type { ActionOffer, World } from "./model";

export type PlannerStep = "fleet" | "units" | "summary";
const order: PlannerStep[] = ["fleet", "units", "summary"];
const titles: Record<PlannerStep, string> = { fleet: "Quelle flotte envoyer ?", units: "Quelles unités engager ?", summary: "Vérifier et confirmer" };

/**
 * One decision at a time (all screen sizes): fleet → units → server summary → confirm, with
 * visible Back/Continue. The map stays the context; nothing is sent before the explicit confirm.
 */
export const EXTRACT_HOURS = { initial: 8, max: 24 }; // UI bounds only: the server applies the ruleset

export function MissionPlanner({ world, target, offer, fleets, fleet, units, hours = EXTRACT_HOURS.initial, onHours, step, quoteKey, quote, path, pending, onFleet, onUnits, onStep, onConfirm, onCancel }: {
  world: World; target: string; offer: ActionOffer; fleets: FleetView[]; fleet: FleetView | null; units: Record<string, number>;
  hours?: number; onHours?: (h: number) => void;
  step: PlannerStep; quoteKey: string | null; quote: QuoteState; path: string[] | undefined; pending: boolean;
  onFleet: (id: string) => void; onUnits: (u: Record<string, number>) => void; onStep: (s: PlannerStep) => void;
  onConfirm: () => void; onCancel: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, [step, offer.kind, offer.planet]);
  const catalogue = world.fleets.catalogue ?? {};
  const name = (c: string) => catalogue[c]?.name ?? c;
  const available = fleet ? engageable(world, fleet, offer.kind) : {};
  const engaged = Object.values(units).reduce((a, n) => a + n, 0);
  const total = Object.values(available).reduce((a, n) => a + n, 0);
  const index = order.indexOf(step);
  const q = quote.status === "ready" && quote.key === quoteKey ? quote.quote : null;
  const fixed = offer.kind === "COLONIZE" && fleet && !isGarrison(fleet);
  const back = () => (index === 0 ? onCancel() : onStep(order[index - 1]));

  return <section className="cmd-planner" aria-labelledby="cmd-planner-title" onKeyDown={(e) => { if (e.key === "Escape") onCancel(); }}>
    <div className="cmd-planner-head">
      <div><p className="cmd-kicker">Nouvelle mission</p>
        <h2 id="cmd-planner-title">{offer.label}</h2>
        <p className="cmd-target">Cible : <strong>{systemName(world, target)}</strong>{fleet ? <> · Flotte : <strong>{fleet.name}</strong></> : null}</p></div>
      <button type="button" className="button cmd-ghost" onClick={onCancel}>Annuler</button>
    </div>
    <ol className="cmd-steps" aria-label="Étapes de la mission">
      {order.map((s, i) => <li key={s} className={`cmd-step${i < index ? " is-done" : ""}${i === index ? " is-current" : ""}`}
        aria-current={i === index ? "step" : undefined}><span aria-hidden="true">{i < index ? "✓" : i + 1}</span>{titles[s]}</li>)}
    </ol>

    <div className="cmd-block">
      <h3 ref={heading} tabIndex={-1}>{titles[step]}</h3>

      {step === "fleet" && (fleets.length === 0 ? <p>{offer.reason}</p> : <fieldset className="cmd-fieldset">
        <legend className="visually-hidden">Flottes éligibles</legend>
        <div className="cmd-choices">{fleets.map((f) => {
          const engage = engageable(world, f, offer.kind);
          return <label key={f.id} className={`cmd-choice${fleet?.id === f.id ? " is-chosen" : ""}`}>
            <input type="radio" name="cmd-fleet" checked={fleet?.id === f.id} onChange={() => onFleet(f.id)} />
            <span className="cmd-choice-title">{f.name}{isGarrison(f) && <span className="cmd-chip cmd-chip--warn">Garnison — détachement</span>}</span>
            <span className="cmd-choice-meta">À {systemName(world, f.system?.id)} · {Object.entries(engage).map(([c, n]) => `${n} ${name(c)}`).join(", ")}</span>
          </label>;
        })}</div>
        {fleet && isGarrison(fleet) && <p className="cmd-help">Une garnison défend sa colonie : vous choisirez à l’étape suivante les seules unités à détacher.</p>}
      </fieldset>)}

      {step === "units" && fleet && <>
        {fixed ? <p>1 {name(Object.keys(available)[0] ?? "colonizer")}, consommé à la fondation ; tout le cargo à bord devient le stock initial.</p> : <>
          <p className="cmd-help">{isGarrison(fleet) ? "Aucune unité n’est détachée d’office : le reste de la garnison continue de défendre la colonie."
            : offer.kind === "ATTACK" ? "Choisissez la composition militaire engagée ; les vaisseaux civils ne combattent jamais."
            : offer.kind === "SURVEY" ? "Une sonde suffit pour cartographier ; ajoutez-en seulement si vous le souhaitez."
            : "Présélection : la flotte part telle qu’elle est. Retirez les unités que vous voulez laisser sur place."}</p>
          {Object.entries(available).map(([c, max]) => {
            const value = units[c] ?? 0;
            return <div key={c} className="cmd-stepper" role="group" aria-label={name(c)}>
              <span className="cmd-stepper-label">{name(c)}</span>
              <button type="button" className="button" aria-label={`Une ${name(c)} de moins`} disabled={value <= 0}
                onClick={() => onUnits({ ...units, [c]: value - 1 })}>−</button>
              <output aria-live="polite">{value} / {max}</output>
              <button type="button" className="button" aria-label={`Une ${name(c)} de plus`} disabled={value >= max}
                onClick={() => onUnits({ ...units, [c]: value + 1 })}>+</button>
            </div>;
          })}
          <p className="cmd-help" aria-live="polite">{engaged} unité(s) engagée(s) sur {total}.</p>
          {offer.kind === "EXTRACT" && <div className="cmd-stepper" role="group" aria-label="Durée d’extraction">
            <span className="cmd-stepper-label">Durée d’extraction</span>
            <button type="button" className="button" aria-label="Une heure de moins" disabled={hours <= 1} onClick={() => onHours?.(hours - 1)}>−</button>
            <output aria-live="polite">{hours} h</output>
            <button type="button" className="button" aria-label="Une heure de plus" disabled={hours >= EXTRACT_HOURS.max} onClick={() => onHours?.(hours + 1)}>+</button>
          </div>}
        </>}
      </>}

      {step === "summary" && <div aria-live="polite" aria-busy={quote.status === "loading"}>
        {quote.status === "loading" && <p className="cmd-loading">Le serveur calcule le trajet, la durée et le coût…</p>}
        {quote.status === "error" && quote.key === quoteKey && <p role="alert" className="feedback feedback--error">{refusal(quote.code)}</p>}
        {q && <>
          <dl className="cmd-facts">
            <div><dt>Départ</dt><dd>{systemName(world, fleet?.system?.id)}</dd></div>
            <div><dt>Destination</dt><dd>{systemName(world, q.destination_id)}</dd></div>
            <div><dt>Sauts</dt><dd>{q.hops === 0 ? "0 (même système)" : q.hops}</dd></div>
            <div><dt>Durée</dt><dd>{duration(q.travel_us)}{["SURVEY", "PROSPECT", "STUDY"].includes(q.kind) ? ` + analyse ${duration(q.survey_us)}` : q.kind === "EXTRACT" ? ` + extraction ${duration(q.survey_us)}` : ""}</dd></div>
            <div><dt>Arrivée</dt><dd>{time(q.travel_arrival_at)}</dd></div>
            {q.battle_at && <div><dt>Bataille</dt><dd>{time(q.battle_at)}</dd></div>}
            <div><dt>Carburant</dt><dd>{resourceKeys.filter((k) => BigInt(q.cost[k]) > 0n).map((k) => `${amount(q.cost[k])} ${resourceLabels[k]}`).join(" · ") || "aucun"}{q.kind === "ATTACK" ? " (aller-retour)" : ""}</dd></div>
            <div><dt>Unités</dt><dd>{Object.entries(units).filter(([, n]) => n > 0).map(([c, n]) => `${n} ${name(c)}`).join(", ")}</dd></div>
          </dl>
          {path ? <ol className="cmd-route-steps" aria-label="Étapes du trajet">{path.map((id, i) =>
            <li key={`${id}-${i}`}>{i === 0 ? "Départ" : i === path.length - 1 ? "Arrivée" : `Étape ${i}`} : {systemName(world, id)}</li>)}</ol>
            : <p className="cmd-help">Trajet de {q.hops} saut{q.hops > 1 ? "s" : ""} calculé par le serveur sur vos routes connues. Les étapes ne sont pas encore transmises :
              la ligne sur la carte relie seulement le départ à la destination, à titre indicatif.</p>}
          {!q.affordable && <p className="feedback feedback--error">Stock probablement insuffisant dans la colonie d’attache.</p>}
          <p className="cmd-risk"><strong>À savoir :</strong> {risks[q.kind]}</p>
        </>}
      </div>}
    </div>

    <div className="cmd-nav">
      <button type="button" className="button cmd-ghost" onClick={back}>{index === 0 ? "Retour aux actions" : "Retour"}</button>
      {step !== "summary" ? <button type="button" className="button button--primary"
        disabled={step === "fleet" ? !fleet : engaged === 0} onClick={() => onStep(order[index + 1])}>Continuer</button>
        : <button type="button" className="button button--primary cmd-confirm" disabled={!q || pending} onClick={onConfirm}>
          {pending ? "Envoi…" : `Confirmer : ${actionLabels[offer.kind].toLowerCase()}`}</button>}
    </div>
  </section>;
}
