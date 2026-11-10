import { useEffect, useRef, useState } from "react";
import { useResearch } from "../hooks/useResearch";
import type { Order, Technology } from "../research/api";
import type { Amounts } from "../colony/api";
import {
  duration,
  exactUnits,
  resourceKeys,
  resourceLabels,
  time,
} from "../colony/format";
import { Badge, Button, Panel } from "./ui";
import { Kpis, Thumb, ViewHero, domainImage, technologyImage } from "../shell/view";
import { Bar, PanelHead, Pending } from "../shell/visual";

const domains = [
  ["engineering", "Ingénierie", "⬡"],
  ["energy", "Énergie", "ϟ"],
  ["computation", "Calcul", "⌘"],
  ["xenoscience", "Xénoscience", "✧"],
];
const effects: Record<string, string> = {
  colony_alloys: "coût Alliages des nouveaux ordres Colony",
  colony_flux: "coût Flux des nouveaux ordres Colony",
  research_duration: "durée des nouveaux ordres Research",
  research_data: "coût Données des nouveaux ordres Research",
};
const reasons: Record<string, string> = {
  technology_duplicate: "Déjà acquise ou réservée",
  queue_full: "File pleine ou bloquée",
  prerequisites_unmet: "Prérequis non acquis",
  research_center_required: "Centre de recherche requis dans la colonie (niveau 3 pour les technologies avancées)",
  permission_denied: "Permission manquante",
  funding_unavailable: "Aucune colonie de financement accessible",
  insufficient_resources: "Stocks de financement insuffisants",
  research_unavailable:
    "Research indisponible dans le ruleset de cet univers (v0.1).",
  research_busy: "Événement en attente de reprise. Réessayez plus tard.",
  order_completed: "Cette recherche est déjà terminée.",
  idempotency_conflict: "Intention déjà utilisée. Actualisez.",
  authentication_required: "Session expirée. Retournez au lobby.",
};
function AmountsView({ value }: { value: Amounts }) {
  return (
    <span className="research-amounts">
      {resourceKeys.map((r) => (
        <span key={r}>
          {exactUnits(value[r])} {resourceLabels[r]}
        </span>
      ))}
    </span>
  );
}

function Progress({
  order,
  serverTime,
  receivedAt,
}: {
  order: Order;
  serverTime: string;
  receivedAt: number;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  if (!order.started_at || !order.due_at) return null;
  const start = Date.parse(order.started_at),
    end = Date.parse(order.due_at);
  const server = Date.parse(serverTime) + now - receivedAt;
  const percent = Math.max(
    0,
    Math.min(
      100,
      Math.floor(((server - start) * 100) / Math.max(1, end - start)),
    ),
  );
  const left = Math.max(0, Math.ceil((end - server) / 1000));
  return (
    <div className="queue-progress">
      <div
        className="meter"
        role="progressbar"
        aria-label={`Avancement estimé de ${order.name}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <span>
        {left
          ? `${duration(String(left * 1e6))} restantes`
          : "Échéance atteinte, confirmation serveur attendue."}
      </span>
    </div>
  );
}

export function ResearchView({
  universe,
  enabled,
  csrf,
  onSessionLost,
  onEconomyChanged,
}: {
  universe: string;
  enabled: boolean;
  csrf?: string;
  onSessionLost: () => void;
  onEconomyChanged?: () => void;
}) {
  const research = useResearch(universe, enabled, csrf, onSessionLost);
  const p = research.projection;
  const [source, setSource] = useState("");
  const [domain, setDomain] = useState("engineering");
  const [selection, setSelection] = useState<{
    technology?: Technology;
    order?: Order;
  } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const feedbackRef = useRef<HTMLParagraphElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    setSelection(null);
    setSource("");
  }, [p?.empire.id]);
  useEffect(() => {
    if (selection) dialog.current?.showModal();
    else dialog.current?.close();
  }, [selection]);
  function close() {
    setSelection(null);
    trigger.current?.focus();
  }
  const financing = p?.sources.find((s) => s.id === source);
  const affordable =
    selection?.technology &&
    financing &&
    resourceKeys.every(
      (r) =>
        BigInt(financing.stocks[r]) >= BigInt(selection.technology!.cost[r]),
    );
  return (
    <div className="research-screen d-page d-research">
      <ViewHero crumb="Recherche" title="Recherche scientifique" banner="banniere-recherche"
        text="Développez les technologies de votre Empire : une recherche active et une suivante, financées par la colonie de votre choix." />
      <div className="colony-toolbar">
        <label>
          Empire de recherche{" "}
          <select
            disabled={!!research.pending}
            value={research.selectedEmpire}
            onChange={(e) => research.select(e.target.value)}
          >
            {research.empires.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </label>
        <Button disabled={!!research.pending} onClick={research.refresh}>
          Actualiser la recherche
        </Button>
      </div>
      {research.phase === "empty" && (
        <Panel title="Aucun Empire accessible">
          <p>Votre accès ne permet la lecture d’aucune recherche.</p>
        </Panel>
      )}
      {research.phase === "loading" && (
        <p role="status">Chargement de la recherche…</p>
      )}
      {research.phase === "error" && (
        <p role="alert">
          {reasons[research.error ?? ""] ??
            "Recherche indisponible. Réessayez."}
        </p>
      )}
      {research.feedback && (
        <p
          ref={feedbackRef}
          tabIndex={-1}
          role={research.feedback.tone === "success" ? "status" : "alert"}
        >
          {research.feedback.tone === "unknown"
            ? "Réponse incertaine. Réessayez la même action : elle ne sera pas dupliquée."
            : research.feedback.text ||
              reasons[research.feedback.code ?? ""] ||
              "Action refusée. Les données ont été actualisées."}
        </p>
      )}
      {p && (() => {
        const acquiredIds = new Set(p.acquired.map((a) => a.technology_id));
        const active = p.queue.find((o) => o.status === "active") ?? null;
        const domainOf = (id: string) => p.technologies.find((t) => t.id === id)?.domain;
        const tree = p.technologies.filter((t) => t.domain === domain).sort((x, y) => x.tier - y.tier);
        const domainLabel = domains.find(([id]) => id === domain)?.[1] ?? domain;
        return (
        <>
          <Kpis label="Recherche de l’Empire" items={[
            { icon: "icons/sidebar/nav-recherche.svg", value: `${p.queue.filter((o) => o.status === "active").length} / 1`, label: "Recherche active", note: `${p.queue.length} / 2 dans la file`, bar: active ? 100 : 0 },
            { icon: "icons/evenements/evt-recherche-terminee.svg", value: `${p.acquired.length} / ${p.technologies.length}`, label: "Technologies acquises", bar: p.technologies.length ? p.acquired.length / p.technologies.length * 100 : 0 },
            { icon: "icons/actions/action-info.svg", value: domains.length, label: "Domaines de recherche", note: `Empire ${p.empire.name} · ${p.ruleset_version}` },
          ]} />
          <div className="d-view-grid d-rs-grid">
            <div className="d-stack">
              <section className="d-card d-panel" aria-labelledby="research-active-title">
                <PanelHead id="research-active-title" icon="icons/sidebar/nav-recherche.svg" title="Recherche en cours" />
                {active ? <div className="d-rs-active">
                  <Thumb src={technologyImage(active.technology_id)} icon="icons/sidebar/nav-recherche.svg" />
                  <div><strong>{active.name}</strong><span>{domains.find(([id]) => id === domainOf(active.technology_id))?.[1]}</span></div>
                </div> : <p className="d-note">Aucune recherche active : choisissez une technologie dans l’arbre.</p>}
              </section>
              <Panel title="File de recherche">
              <p>
                Coût et durée figés dès l’acceptation, même pour la suivante.
              </p>
              {p.queue.length === 0 && <p>Aucune recherche en cours.</p>}
              {p.queue.map((o, index) => (
                <article key={o.id} className="research-order">
                  <span className="d-rs-rank" aria-hidden="true">{index + 1}</span>
                  <Thumb src={technologyImage(o.technology_id)} icon="icons/sidebar/nav-recherche.svg" />
                  <div className="d-rs-order-main">
                  <Badge tone={o.status === "blocked" ? "warning" : "accent"}>
                    {o.status === "active"
                      ? "Active"
                      : o.status === "blocked"
                        ? "Bloquée"
                        : "Suivante"}
                  </Badge>
                  <h3>{o.name}</h3>
                  <p>
                    {duration(o.duration_us)}
                    {o.due_at
                      ? ` · fin prévue ${time(o.due_at)}`
                      : " · démarre après l’active"}
                  </p>
                  {o.blocked_reason && (
                    <p role="status">
                      Démarrage bloqué : prérequis modifiés. Réservation
                      conservée, annulation possible.
                    </p>
                  )}
                  {o.status === "active" && (
                    <Progress
                      order={o}
                      serverTime={p.server_time}
                      receivedAt={research.receivedAt}
                    />
                  )}
                  <AmountsView value={o.cost} />
                  <p>
                    Financée par{" "}
                    {p.sources.find((s) => s.id === o.colony_id)?.name ??
                      "une colonie sans accès en lecture"}
                  </p>
                  <Button
                    disabled={!o.cancel.available || !!research.pending}
                    onClick={(e) => {
                      trigger.current = e.currentTarget;
                      setSelection({ order: o });
                    }}
                  >
                    Annuler {o.name}
                  </Button>
                  </div>
                </article>
              ))}
              {research.awaiting && (
                <p role="status">
                  Échéance atteinte, confirmation serveur attendue. Actualisez.
                </p>
              )}
              </Panel>
              <Panel title="Financement">
                <label>
                  Colonie payeuse{" "}
                  <select
                    value={source}
                    disabled={!!research.pending}
                    onChange={(e) => setSource(e.target.value)}
                  >
                    <option value="">Choisir une colonie</option>
                    {p.sources.map((s) => (
                      <option value={s.id} key={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
                {financing && (
                  <p>
                    Stocks disponibles :{" "}
                    <AmountsView value={financing.stocks} />
                  </p>
                )}
                <p>
                  Réservation immédiate du coût complet. Aucun nouveau débit au
                  démarrage de la suivante.
                </p>
              </Panel>
            </div>
            <div className="d-stack">
              <section className="d-card d-panel" aria-labelledby="research-domains-title">
                <PanelHead id="research-domains-title" icon="icons/actions/action-info.svg" title="Domaines de recherche" />
                <div className="d-rs-domains" role="group" aria-label="Choisir un domaine">
                  {domains.map(([id, label]) => {
                    const total = p.technologies.filter((t) => t.domain === id).length;
                    const done = p.technologies.filter((t) => t.domain === id && acquiredIds.has(t.id)).length;
                    return <button type="button" key={id} className={`d-rs-domain${domain === id ? " is-current" : ""}`} aria-pressed={domain === id} onClick={() => setDomain(id)}>
                      <Thumb src={domainImage(id)} icon="icons/sidebar/nav-recherche.svg" className="d-thumb--wide" />
                      <strong>{label}</strong><span>{done} / {total} acquises</span>
                      <Bar value={total ? done / total * 100 : 0} />
                    </button>;
                  })}
                </div>
              </section>
              <section className="d-card d-panel" aria-labelledby="research-tree-title">
                <PanelHead id="research-tree-title" icon="icons/actions/action-ameliorer.svg" title={`Arbre de recherche — ${domainLabel}`} />
                <ol className="d-rs-tree">
                  {tree.map((t) => {
                    const known = acquiredIds.has(t.id);
                    const state = known ? "known" : t.available ? "open" : "locked";
                    return (
                      <li className={`research-tech d-rs-node d-rs-node--${state}`} key={t.id}>
                        <Thumb src={technologyImage(t.id)} icon={known ? "icons/evenements/evt-recherche-terminee.svg" : t.available ? "icons/sidebar/nav-recherche.svg" : "icons/actions/action-verrouille.svg"} className="d-thumb--wide" />
                        <h3>
                          {t.name}{" "}
                          {known && <Badge tone="accent">Acquise</Badge>}
                        </h3>
                        <p>
                          −{t.reduction_bps / 100} % net : {effects[t.effect]}
                          . {t.tier === 2 && "Remplace le palier I."}
                        </p>
                        <p>
                          Prérequis :{" "}
                          {t.requires
                            .map(
                              (r) =>
                                p.technologies.find((tech) => tech.id === r)
                                  ?.name ?? r,
                            )
                            .join(", ") || "aucun"}
                        </p>
                        <AmountsView value={t.cost} />
                        <p>
                          Durée effective : {duration(t.duration_us)} · base{" "}
                          {duration(t.base_duration_us)}
                        </p>
                        {!known && <Button
                          disabled={
                            !t.available || !financing || !!research.pending
                          }
                          onClick={(e) => {
                            trigger.current = e.currentTarget;
                            setSelection({ technology: t });
                          }}
                        >
                          {p.queue.length ? "Programmer" : "Rechercher"}{" "}
                          {t.name}
                        </Button>}
                        {t.reason && !known && (
                          <p className="d-rs-reason">{reasons[t.reason] ?? "Indisponible"}</p>
                        )}
                      </li>
                    );
                  })}
                  <li className="d-rs-node d-rs-node--future" aria-label="Technologies suivantes">
                    <Thumb src={null} icon="icons/actions/action-verrouille.svg" className="d-thumb--wide" />
                    <Pending compact what="Paliers suivants de ce domaine." />
                  </li>
                </ol>
              </section>
            </div>
          </div>
        </>
        );
      })()}
      <dialog
        ref={dialog}
        className="research-dialog"
        aria-labelledby="research-confirm-title"
        onClose={() => {
          const target = trigger.current;
          if (target?.isConnected && !target.disabled) target.focus();
          else feedbackRef.current?.focus();
        }}
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
      >
        <h2 id="research-confirm-title">
          {selection?.technology
            ? "Confirmer la recherche"
            : "Confirmer l’annulation"}
        </h2>
        {selection?.technology && (
          <>
            <h3>{selection.technology.name}</h3>
            <p>Colonie payeuse : {financing?.name ?? "aucune"}</p>
            <AmountsView value={selection.technology.cost} />
            <p>
              Durée réservée : {duration(selection.technology.duration_us)}.
              Aucun recalcul ultérieur.
            </p>
            <p>
              Prérequis :{" "}
              {selection.technology.requires
                .map((r) => p?.technologies.find((t) => t.id === r)?.name ?? r)
                .join(", ") || "aucun"}
            </p>
            <p>
              Effet : −{selection.technology.reduction_bps / 100} % net,{" "}
              {effects[selection.technology.effect]}.
            </p>
            {!affordable && (
              <p role="alert">Stocks insuffisants dans cette colonie.</p>
            )}
          </>
        )}
        {selection?.order && (
          <>
            <h3>{selection.order.name}</h3>
            {selection.order.cancel.refunds.map((r) => (
              <div key={r.colony_id}>
                <h4>Colonie destinataire : {r.colony_name}</h4>
                <p>
                  Remboursement théorique :{" "}
                  <AmountsView value={r.theoretical} />
                </p>
                <p>
                  Montant récupérable : <AmountsView value={r.recoverable} />
                </p>
                <p>
                  Perte définitive : <AmountsView value={r.lost} />
                </p>
              </div>
            ))}
            <p>
              Cascade :{" "}
              {selection.order.cancel.also_cancels
                .map((id) => p?.queue.find((o) => o.id === id)?.name ?? id)
                .join(", ") || "aucune"}
              . La suivante indépendante démarre immédiatement si l’active est
              annulée.
            </p>
          </>
        )}
        <div className="colony-actions">
          <Button onClick={close} disabled={!!research.pending}>
            Retour
          </Button>
          <Button
            className="button--primary"
            disabled={
              !!research.pending || (!!selection?.technology && !affordable)
            }
            onClick={async () => {
              if (selection?.technology && source)
                await research.command({
                  kind: "start",
                  technology_id: selection.technology.id,
                  colony_id: source,
                });
              else if (selection?.order)
                await research.command({
                  kind: "cancel",
                  order_id: selection.order.id,
                });
              onEconomyChanged?.();
              close();
            }}
          >
            Confirmer
          </Button>
        </div>
      </dialog>
    </div>
  );
}
