import { useState } from "react";
import { useRelations } from "../hooks/useRelations";
import type { HistoryEntry, Relation, RelationAction } from "../relations/api";
import { duration, time } from "../colony/format";
import { Badge, Button, EmptyState, Panel } from "./ui";
import { Kpis, Thumb, ViewHero } from "../shell/view";
import { PanelHead, Pending, Pic } from "../shell/visual";

const hero = <ViewHero crumb="Relations" title="Relations diplomatiques" banner="banniere-diplomatie"
  text="Gérez vos relations avec les civilisations rencontrées, négociez des pactes et suivez l’évolution des contacts dans la galaxie." />;

const messages: Record<string, string> = {
  propose: "Proposition de pacte envoyée.",
  withdraw: "Proposition retirée.",
  accept: "Pacte de non-agression conclu.",
  refuse: "Proposition refusée.",
  terminate: "Rupture notifiée : le pacte reste actif jusqu’à la fin du préavis.",
  relation_not_found: "Cet Empire ne fait pas partie de vos contacts.",
  proposal_open: "Une proposition est déjà ouverte entre vos deux Empires.",
  proposal_missing: "Cette proposition n’est plus ouverte (expirée, retirée ou déjà traitée).",
  proposal_cooldown: "Votre précédente proposition a été refusée récemment : patientez avant d’en envoyer une autre.",
  pact_active: "Un pacte est déjà actif avec cet Empire.",
  pact_missing: "Aucun pacte actif avec cet Empire.",
  notice_pending: "La rupture de ce pacte est déjà notifiée.",
  relations_unavailable: "Les règles de cette partie n’incluent pas les relations.",
  permission_denied: "Votre accès à cet Empire ne permet pas de négocier.",
  authentication_required: "Votre session a expiré. Retournez au lobby pour entrer à nouveau.",
  idempotency_conflict: "Cette action a déjà été envoyée avec un autre contenu. Actualisez.",
  invalid_request: "Action invalide. Actualisez la page.",
};
const message = (code: string) => messages[code] ?? "Service Game indisponible. Réessayer n’enverra pas l’action deux fois.";

const actionLabels: Record<RelationAction, string> = {
  propose: "Proposer un pacte", withdraw: "Retirer la proposition", accept: "Accepter le pacte",
  refuse: "Refuser", terminate: "Rompre le pacte…",
};
const historyLabels: Record<HistoryEntry["kind"], [string, string]> = {
  proposed: ["Vous avez proposé un pacte", "Proposition de pacte reçue"],
  withdrawn: ["Vous avez retiré votre proposition", "Proposition retirée par l’autre Empire"],
  accepted: ["Vous avez accepté le pacte", "Votre proposition a été acceptée"],
  refused: ["Vous avez refusé la proposition", "Votre proposition a été refusée"],
  notice: ["Vous avez notifié la rupture du pacte", "L’autre Empire a notifié la rupture du pacte"],
};

const sourceLabels: Record<NonNullable<Relation["contact"]>["first_source"], string> = {
  combat: "Rencontré au combat", presence: "Présence observée", diplomacy: "Présenté par une proposition de pacte",
};

function status(r: Relation) {
  if (r.pact?.notice) return { label: "Pacte en préavis", tone: "warning" as const };
  if (r.pact) return { label: "Pacte actif", tone: "accent" as const };
  return { label: "Sans accord", tone: "neutral" as const };
}

function Facts({ r }: { r: Relation }) {
  return <dl className="fleet-dates">
    {r.contact ? <>
      <div><dt>Contact</dt><dd>{sourceLabels[r.contact.first_source]} · {time(r.contact.first_seen_at)}</dd></div>
      {r.contact.presence && <div><dt>Présence observée</dt><dd>{r.contact.presence.planet_name ?? "Monde"}{r.contact.presence.system_name ? ` — ${r.contact.presence.system_name}` : ""} · {time(r.contact.presence.observed_at)}</dd></div>}
    </> : <div><dt>Contact</dt><dd>Aucun contact propre</dd></div>}
    {r.pact && <div><dt>Pacte depuis</dt><dd>{time(r.pact.accepted_at)}</dd></div>}
    {r.pact?.notice && <div><dt>Fin du pacte</dt><dd>{time(r.pact.notice.ends_at)} ({r.pact.notice.by === "self" ? "rupture notifiée par vous" : "rupture notifiée par l’autre Empire"})</dd></div>}
    {r.proposal && <div><dt>{r.proposal.direction === "sent" ? "Proposition envoyée" : "Proposition reçue"}</dt><dd>Expire {time(r.proposal.expires_at)}</dd></div>}
    {r.cooldown_until && <div><dt>Nouvelle proposition possible</dt><dd>{time(r.cooldown_until)}</dd></div>}
    <div><dt>Dernier acte hostile reçu</dt><dd>{r.hostility.by_counterpart_at ? time(r.hostility.by_counterpart_at) : "Aucun"}</dd></div>
    <div><dt>Dernier acte hostile de votre part</dt><dd>{r.hostility.by_self_at ? time(r.hostility.by_self_at) : "Aucun"}</dd></div>
  </dl>;
}

export function RelationsView({ universe, enabled, csrf, onSessionLost }: {
  universe: string; enabled: boolean; csrf: string | undefined; onSessionLost: () => void;
}) {
  const relations = useRelations(universe, enabled, csrf, onSessionLost);
  const [confirm, setConfirm] = useState<string | null>(null);
  const p = relations.projection;

  if (relations.phase === "loading" || relations.phase === "idle") return <div className="d-page">{hero}<Panel title="Relations"><p role="status">Lecture de vos relations…</p></Panel></div>;
  if (relations.phase === "unavailable") return <div className="d-page">{hero}<Panel title="Relations indisponibles dans cette partie">
    <p>Les règles de cette partie n’incluent pas les relations entre civilisations.</p></Panel></div>;
  if (relations.phase === "empty") return <div className="d-page">{hero}<Panel title="Aucun Empire"><EmptyState title="Aucune relation accessible">Votre accès ne comprend aucun Empire avec le droit de lecture des relations.</EmptyState></Panel></div>;
  if (!p) return <div className="d-page">{hero}<Panel title="Relations indisponibles"><p role="alert">{message(relations.error ?? "unavailable")}</p><Button onClick={relations.refresh}>Réessayer</Button></Panel></div>;

  const names = Object.fromEntries(p.relations.map((r) => [r.empire.id, r.empire.name]));
  const received = p.relations.filter((r) => r.proposal?.direction === "received");
  const ending = p.relations.filter((r) => r.pact?.notice?.by === "counterpart");
  const act = async (r: Relation, action: RelationAction) => {
    setConfirm(null);
    await relations.run(r.empire.id, action);
  };

  const pacts = p.relations.filter((r) => r.pact);
  return <div className="fleet-screen relations-screen d-page d-relations">
    {hero}
    <Kpis label="Diplomatie" items={[
      { icon: "icons/sidebar/nav-relations.svg", value: p.relations.length, label: "Civilisations connues" },
      { icon: "icons/evenements/evt-contact-diplomatique.svg", value: pacts.length, label: "Pactes en vigueur" },
      { icon: "icons/ui/ui-messages.svg", value: received.length, label: "Propositions reçues" },
      { icon: "icons/ui/ui-alerte.svg", value: ending.length, label: "Ruptures notifiées" },
    ]} />
    <nav className="d-rel-tabs" aria-label="Sections de la diplomatie">
      <a href="#contacts-title" className="d-tab is-current">Civilisations</a><a href="#relation-pacts-title" className="d-tab">Accords</a>
      <a href="#relations-history-title" className="d-tab">Historique</a></nav>
    <div className="colony-toolbar">
      {relations.empires.length > 1 ? <label className="galaxy-field">Empire
        <select value={relations.selectedEmpire} disabled={relations.pending} onChange={(e) => relations.select(e.target.value)}>
          {relations.empires.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select></label> : <span className="panel-meta">Empire : {relations.empires[0]?.name ?? "—"}</span>}
      <span className="panel-meta">État serveur au {time(p.at)}</span>
      <Button onClick={relations.refresh} disabled={relations.pending}>Actualiser</Button>
    </div>
    <div className="feedback-zone" aria-live="polite">
      {relations.feedback && <div className={`feedback feedback--${relations.feedback.tone}`}><p>{message(relations.feedback.code)}</p>
        <Button onClick={relations.dismiss}>Masquer</Button></div>}
    </div>
    {(received.length > 0 || ending.length > 0) && <section className="panel" aria-labelledby="relation-alerts-title">
      <h2 id="relation-alerts-title">Alertes diplomatiques</h2>
      <ul className="fleet-reports">
        {received.map((r) => <li key={`p-${r.empire.id}`}><strong>{r.empire.name}</strong> vous propose un pacte de non-agression · expire {time(r.proposal!.expires_at)}</li>)}
        {ending.map((r) => <li key={`n-${r.empire.id}`}><strong>{r.empire.name}</strong> a notifié la rupture du pacte · fin {time(r.pact!.notice!.ends_at)}</li>)}
      </ul>
    </section>}
    <div className="d-view-grid d-rel-grid">
    <section className="panel" aria-labelledby="contacts-title">
      <div className="panel-head"><h2 id="contacts-title">Civilisations connues</h2><span className="panel-meta">{p.relations.length}</span></div>
      <p className="panel-meta">Un pacte de non-agression annule toute bataille entre signataires à l’heure de la bataille. Il ne partage aucune information. Proposition valable {duration(String(p.terms.proposal_ttl_seconds * 1e6))} · préavis de rupture {duration(String(p.terms.notice_seconds * 1e6))} · après un refus, {duration(String(p.terms.refusal_cooldown_seconds * 1e6))} avant de reproposer.</p>
      {p.relations.length === 0 ? <EmptyState title="Aucun contact">Vous découvrez un autre Empire au combat ou en observant l’une de ses colonies dans un système surveillé par l’une des vôtres.</EmptyState>
        : <ul className="fleet-list">{p.relations.map((r) => {
          const s = status(r);
          return <li key={r.empire.id} className="fleet-card" aria-labelledby={`relation-${r.empire.id}`}>
            <div className="d-fl-card-top"><Thumb src={null} icon="icons/sidebar/nav-relations.svg" />
              <div className="panel-head"><h3 id={`relation-${r.empire.id}`}>{r.empire.name}</h3><Badge tone={s.tone}>{s.label}</Badge></div></div>
            <Facts r={r} />
            {r.actions.length > 0 && <div className="relation-actions">
              {r.actions.map((a) => a === "terminate" ? (confirm === r.empire.id
                ? <div key={a} className="feedback feedback--unknown" role="group" aria-label={`Confirmer la rupture avec ${r.empire.name}`}>
                  <p>Le pacte restera actif pendant le préavis, puis prendra fin. Confirmer ?</p>
                  <Button className="button--danger" disabled={relations.pending} onClick={() => void act(r, "terminate")}>Confirmer la rupture</Button>
                  <Button disabled={relations.pending} onClick={() => setConfirm(null)}>Annuler</Button>
                </div>
                : <Button key={a} disabled={relations.pending} onClick={() => setConfirm(r.empire.id)}>{actionLabels[a]}</Button>)
                : <Button key={a} className={a === "accept" || a === "propose" ? "button--primary" : ""} disabled={relations.pending}
                  onClick={() => void act(r, a)}>{actionLabels[a]}</Button>)}
            </div>}
          </li>;
        })}</ul>}
    </section>
    <div className="d-stack">
      <section className="d-card d-panel" aria-labelledby="relation-pacts-title">
        <PanelHead id="relation-pacts-title" icon="icons/evenements/evt-contact-diplomatique.svg" title={`Accords en vigueur (${pacts.length})`} />
        {pacts.length === 0 ? <p className="d-note">Aucun pacte en vigueur.</p> : <ul className="d-rows">{pacts.map((r) =>
          <li key={r.empire.id} className="d-row"><Pic src="icons/evenements/evt-contact-diplomatique.svg" size={32} />
            <span className="d-row-main"><strong>Pacte de non-agression</strong><span>{r.empire.name} · depuis {time(r.pact!.accepted_at)}</span></span>
            <span className="d-row-side"><b className={r.pact!.notice ? "d-tone-amber" : "d-tone-green"}>{r.pact!.notice ? "Préavis" : "Actif"}</b>
              {r.pact!.notice && <span>fin {time(r.pact!.notice.ends_at)}</span>}</span></li>)}</ul>}
        <Pending compact what="Accords de recherche et accords commerciaux." />
      </section>
      <section className="d-card d-panel" aria-labelledby="relation-profile-title">
        <PanelHead id="relation-profile-title" icon="icons/actions/action-info.svg" title="Profil et évaluation" />
        <Pending compact what="Score de relation, éthique, orientation, puissance estimée et évaluation des civilisations." />
      </section>
      <section className="panel" aria-labelledby="relations-history-title"><h2 id="relations-history-title">Historique</h2>
        {p.history.length === 0 ? <p>Aucune négociation.</p> : <ol className="fleet-reports d-rel-timeline">{p.history.map((h) =>
          <li key={h.id}><strong>{historyLabels[h.kind][h.actor === "self" ? 0 : 1]}</strong> — {names[h.counterpart_id] ?? "Empire"}
            <p className="panel-meta">{time(h.at)}{h.kind === "proposed" && h.expires_at ? ` · expiration ${time(h.expires_at)}` : ""}{h.kind === "notice" && h.ends_at ? ` · fin du pacte ${time(h.ends_at)}` : ""}</p>
          </li>)}</ol>}
      </section>
    </div>
    </div>
  </div>;
}
