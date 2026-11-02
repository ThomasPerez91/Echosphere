"""Relations services (Q18, ruleset v0.8). Same commands for humans (HTTP) and AI (dispatcher).

Locks: a negotiation command locks only the pair row, never an Operations, Research or Colony
stream, so it can never invert the Combat order (streams → engagement → pair). Every decision
compares server logical dates; nothing is scheduled and nothing depends on worker order:
- a proposal is open while `at < proposal_expires_at` (expiry needs no event);
- a pact covers `at` while `accepted_at <= at < ends_at` (`ends_at` NULL = no notice yet).

Fog: a contact is created only from a legitimate own observation (a Combat report naming the
opponent, or a foreign Colony in a system MONITORED by an own Colony). It reveals the Empire,
and for presence the planet and observation date only.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.colony.service import ColonyError, rules_for
from app.galaxy.models import PlanetKnowledge, SystemKnowledge
from app.persistence.models import Colony, Empire, Planet
from app.relations.models import RelationContact, RelationEvent, RelationPact, RelationPair
from app.relations.rules import NO_AGREEMENT, PACT, cooled_down, pair, proposal_open
from app.simulation.clock import utc
from app.simulation.scheduler import IdempotencyConflict

HISTORY_LIMIT = 50
RELATION_LIMIT = 500


class RelationError(ColonyError):
    pass


def relations_rules(session, universe_id):
    rules = rules_for(session, universe_id)
    if rules.relations is None:
        raise RelationError("Relations absent from pinned ruleset", "relations_unavailable")
    return rules


def check_key(key):
    if not key or len(key) > 160:
        raise RelationError("Invalid intent", "invalid_request")


# --- Facts written by trusted paths (Combat orchestrator, monitoring refresh) --------------------


def ensure_pair(session, universe_id, a, b):
    """Create the pair row if absent, then lock it. Callers hold no lock taken after a pair."""
    low, high = pair(a, b)
    session.execute(
        insert(RelationPair)
        .values(low_empire_id=low, high_empire_id=high, universe_id=universe_id)
        .on_conflict_do_nothing(index_elements=["low_empire_id", "high_empire_id"])
    )
    return locked_pair(session, universe_id, low, high)


def locked_pair(session, universe_id, low, high, *, share=False):
    query = select(RelationPair).where(
        RelationPair.low_empire_id == low,
        RelationPair.high_empire_id == high,
        RelationPair.universe_id == universe_id,
    )
    query = query.with_for_update(read=share).execution_options(populate_existing=True)
    return session.scalar(query)


def record_contact(session, universe_id, observer, observed, source, at, planet_id=None):
    """Oriented, durable, never forgotten. Re-observation only moves dates forward (and an
    earlier first observation backward), so out-of-order logical writes converge."""
    at = utc(at)
    session.execute(
        insert(RelationContact)
        .values(
            observer_empire_id=observer,
            observed_empire_id=observed,
            universe_id=universe_id,
            first_source=source,
            first_seen_at=at,
            last_seen_at=at,
            presence_planet_id=planet_id,
            presence_observed_at=at if planet_id else None,
        )
        .on_conflict_do_nothing(index_elements=["observer_empire_id", "observed_empire_id"])
    )
    c = RelationContact
    values = {
        "last_seen_at": func.greatest(c.last_seen_at, at),
        "first_source": case((c.first_seen_at > at, source), else_=c.first_source),
        "first_seen_at": func.least(c.first_seen_at, at),
    }
    if planet_id is not None:
        newer = or_(c.presence_observed_at.is_(None), c.presence_observed_at <= at)
        values["presence_planet_id"] = case((newer, planet_id), else_=c.presence_planet_id)
        values["presence_observed_at"] = case((newer, at), else_=c.presence_observed_at)
    session.execute(
        update(c)
        .where(
            c.observer_empire_id == observer,
            c.observed_empire_id == observed,
            c.universe_id == universe_id,
        )
        .values(**values)
    )


def record_hostile(row: RelationPair, actor: UUID, at: datetime):
    """Q18 B4: hostility is a dated fact per side (the last one), never a relation state."""
    at = utc(at)
    if actor == row.low_empire_id:
        if row.last_hostile_by_low_at is None or row.last_hostile_by_low_at < at:
            row.last_hostile_by_low_at = at
    elif actor == row.high_empire_id:
        if row.last_hostile_by_high_at is None or row.last_hostile_by_high_at < at:
            row.last_hostile_by_high_at = at
    else:
        raise ValueError("Hostile actor outside the pair")


def covering_pact(session, low, high, at):
    """The pact protecting the logical instant `at`, if any (accepted_at <= at < ends_at)."""
    return session.scalar(
        select(RelationPact)
        .where(
            RelationPact.low_empire_id == low,
            RelationPact.high_empire_id == high,
            RelationPact.accepted_at <= at,
            or_(RelationPact.ends_at.is_(None), RelationPact.ends_at > at),
        )
        .order_by(RelationPact.accepted_at.desc())
        .limit(1)
    )


def observe_presences(session, universe_id, empire_id, system_ids, at):
    """Q18 B3: foreign Colonies existing at `at` in systems MONITORED by an own Colony."""
    if not system_ids:
        return
    rows = session.execute(
        select(Colony.empire_id, Colony.planet_id)
        .join(Planet, Planet.id == Colony.planet_id)
        .where(
            Colony.universe_id == universe_id,
            Colony.empire_id != empire_id,
            Planet.system_id.in_(sorted(system_ids, key=str)),
            or_(Colony.founded_at.is_(None), Colony.founded_at <= at),
        )
        .order_by(Colony.empire_id, Colony.planet_id)
    ).all()
    for owner, planet_id in rows:
        record_contact(session, universe_id, empire_id, owner, "presence", at, planet_id)


# --- Negotiation commands -------------------------------------------------------------------------


def counterpart_empire(session, universe_id, empire_id, counterpart_id):
    if counterpart_id == empire_id:
        raise RelationError("A relation needs another Empire", "invalid_request")
    row = session.scalar(
        select(Empire).where(Empire.id == counterpart_id, Empire.universe_id == universe_id)
    )
    if row is None:
        raise RelationError("Unknown relation", "relation_not_found")
    return row


def knows(session, universe_id, observer, observed):
    return (
        session.scalar(
            select(RelationContact.observed_empire_id).where(
                RelationContact.observer_empire_id == observer,
                RelationContact.observed_empire_id == observed,
                RelationContact.universe_id == universe_id,
            )
        )
        is not None
    )


def replay(session, empire_id, key, kind, counterpart_id):
    event = session.scalar(
        select(RelationEvent).where(
            RelationEvent.actor_empire_id == empire_id, RelationEvent.idempotency_key == key
        )
    )
    if event is None:
        return None
    other = event.high_empire_id if event.low_empire_id == empire_id else event.low_empire_id
    if event.kind != kind or other != counterpart_id:
        raise IdempotencyConflict("Relation intention reused")
    return receipt(event)


def receipt(event):
    return {"event_id": str(event.id), "kind": event.kind, "at": event.at.isoformat()} | (
        event.details or {}
    )


def journal(session, row, actor, kind, at, key, details):
    event = RelationEvent(
        universe_id=row.universe_id,
        low_empire_id=row.low_empire_id,
        high_empire_id=row.high_empire_id,
        actor_empire_id=actor,
        kind=kind,
        at=at,
        idempotency_key=key,
        details=details,
    )
    try:
        with session.begin_nested():
            session.add(event)
            session.flush()
    except IntegrityError:
        # Same key concurrently used on another pair: one intention, one effect.
        raise IdempotencyConflict("Relation intention reused") from None
    return receipt(event)


def cooldown_of(row, empire_id):
    return row.low_cooldown_until if empire_id == row.low_empire_id else row.high_cooldown_until


def command(session, universe_id, empire_id, counterpart_id, key, kind, at, *, create=False):
    """Shared prologue: ruleset, identity, pair lock, then idempotent replay under that lock."""
    check_key(key)
    rules = relations_rules(session, universe_id)
    counterpart_empire(session, universe_id, empire_id, counterpart_id)
    if create:
        if not knows(session, universe_id, empire_id, counterpart_id):
            # Never reveal whether an unknown Empire exists: same refusal as an unknown id.
            raise RelationError("Unknown relation", "relation_not_found")
        row = ensure_pair(session, universe_id, empire_id, counterpart_id)
    else:
        low, high = pair(empire_id, counterpart_id)
        row = locked_pair(session, universe_id, low, high)
        if row is None:
            raise RelationError("Unknown relation", "relation_not_found")
    done = replay(session, empire_id, key, kind, counterpart_id)
    return rules.relations, row, done, utc(at)


def propose(session, universe_id, empire_id, counterpart_id, *, key, at):
    terms, row, done, at = command(
        session, universe_id, empire_id, counterpart_id, key, "proposed", at, create=True
    )
    if done is not None:
        return done
    if covering_pact(session, row.low_empire_id, row.high_empire_id, at) is not None:
        raise RelationError("A pact is already active", "pact_active")
    if proposal_open(row.proposal_expires_at, at):
        raise RelationError("A proposal is already open for this pair", "proposal_open")
    if not cooled_down(cooldown_of(row, empire_id), at):
        raise RelationError("Recently refused proposal", "proposal_cooldown")
    expires = at + terms.proposal_ttl
    row.proposal_by_empire_id, row.proposed_at, row.proposal_expires_at = empire_id, at, expires
    return journal(
        session,
        row,
        empire_id,
        "proposed",
        at,
        key,
        {"counterpart_id": str(counterpart_id), "expires_at": expires.isoformat()},
    )


def incoming(row, empire_id, at):
    return (
        proposal_open(row.proposal_expires_at, at)
        and row.proposal_by_empire_id is not None
        and row.proposal_by_empire_id != empire_id
    )


def withdraw(session, universe_id, empire_id, counterpart_id, *, key, at):
    _, row, done, at = command(
        session, universe_id, empire_id, counterpart_id, key, "withdrawn", at
    )
    if done is not None:
        return done
    if not proposal_open(row.proposal_expires_at, at) or row.proposal_by_empire_id != empire_id:
        raise RelationError("No open proposal of yours", "proposal_missing")
    clear_proposal(row)
    return journal(
        session, row, empire_id, "withdrawn", at, key, {"counterpart_id": str(counterpart_id)}
    )


def clear_proposal(row):
    row.proposal_by_empire_id = row.proposed_at = row.proposal_expires_at = None


def accept(session, universe_id, empire_id, counterpart_id, *, key, at):
    _, row, done, at = command(
        session, universe_id, empire_id, counterpart_id, key, "accepted", at
    )
    if done is not None:
        return done
    if not incoming(row, empire_id, at):
        raise RelationError("No open proposal to answer", "proposal_missing")
    if covering_pact(session, row.low_empire_id, row.high_empire_id, at) is not None:
        raise RelationError("A pact is already active", "pact_active")
    pact = RelationPact(
        universe_id=universe_id,
        low_empire_id=row.low_empire_id,
        high_empire_id=row.high_empire_id,
        proposed_by_empire_id=counterpart_id,
        accepted_by_empire_id=empire_id,
        accepted_at=at,
    )
    session.add(pact)
    clear_proposal(row)
    session.flush()
    return journal(
        session,
        row,
        empire_id,
        "accepted",
        at,
        key,
        {"counterpart_id": str(counterpart_id), "pact_id": str(pact.id)},
    )


def refuse(session, universe_id, empire_id, counterpart_id, *, key, at):
    terms, row, done, at = command(
        session, universe_id, empire_id, counterpart_id, key, "refused", at
    )
    if done is not None:
        return done
    if not incoming(row, empire_id, at):
        raise RelationError("No open proposal to answer", "proposal_missing")
    until = at + terms.refusal_cooldown
    if counterpart_id == row.low_empire_id:
        row.low_cooldown_until = until
    else:
        row.high_cooldown_until = until
    clear_proposal(row)
    return journal(
        session,
        row,
        empire_id,
        "refused",
        at,
        key,
        {"counterpart_id": str(counterpart_id), "cooldown_until": until.isoformat()},
    )


def terminate(session, universe_id, empire_id, counterpart_id, *, key, at):
    terms, row, done, at = command(
        session, universe_id, empire_id, counterpart_id, key, "notice", at
    )
    if done is not None:
        return done
    pact = covering_pact(session, row.low_empire_id, row.high_empire_id, at)
    if pact is None:
        raise RelationError("No active pact", "pact_missing")
    if pact.ends_at is not None:
        raise RelationError("Notice already given", "notice_pending")
    ends = at + terms.notice
    pact.notice_by_empire_id, pact.notice_at, pact.ends_at = empire_id, at, ends
    session.flush()
    return journal(
        session,
        row,
        empire_id,
        "notice",
        at,
        key,
        {
            "counterpart_id": str(counterpart_id),
            "pact_id": str(pact.id),
            "ends_at": ends.isoformat(),
        },
    )


OPERATIONS = {
    "propose": propose,
    "withdraw": withdraw,
    "accept": accept,
    "refuse": refuse,
    "terminate": terminate,
}


# --- Projection (read-only; no catch-up, no write) ----------------------------------------------


def iso(value):
    return value.isoformat() if value else None


def side_view(row, empire_id, at, pact):
    mine_low = empire_id == row.low_empire_id
    proposal = None
    if proposal_open(row.proposal_expires_at, at):
        proposal = {
            "direction": "sent" if row.proposal_by_empire_id == empire_id else "received",
            "proposed_at": iso(row.proposed_at),
            "expires_at": iso(row.proposal_expires_at),
        }
    cooldown = cooldown_of(row, empire_id)
    actions = []
    if pact is None:
        if proposal is None and cooled_down(cooldown, at):
            actions.append("propose")
        elif proposal and proposal["direction"] == "sent":
            actions.append("withdraw")
        elif proposal:
            actions += ["accept", "refuse"]
    elif pact.ends_at is None:
        actions.append("terminate")
    return {
        "state": PACT if pact else NO_AGREEMENT,
        "pact": None
        if pact is None
        else {
            "accepted_at": iso(pact.accepted_at),
            "notice": None
            if pact.ends_at is None
            else {
                "by": "self" if pact.notice_by_empire_id == empire_id else "counterpart",
                "at": iso(pact.notice_at),
                "ends_at": iso(pact.ends_at),
            },
        },
        "proposal": proposal,
        "cooldown_until": iso(cooldown) if not cooled_down(cooldown, at) else None,
        "hostility": {
            "by_self_at": iso(
                row.last_hostile_by_low_at if mine_low else row.last_hostile_by_high_at
            ),
            "by_counterpart_at": iso(
                row.last_hostile_by_high_at if mine_low else row.last_hostile_by_low_at
            ),
        },
        "actions": actions,
    }


def project(session, universe_id, empire_id, at):
    """Own contacts and own pairs only; never another Empire's knowledge or holdings."""
    rules = relations_rules(session, universe_id)
    at = utc(at)
    contacts = {
        c.observed_empire_id: c
        for c in session.scalars(
            select(RelationContact)
            .where(
                RelationContact.universe_id == universe_id,
                RelationContact.observer_empire_id == empire_id,
            )
            .order_by(RelationContact.observed_empire_id)
            .limit(RELATION_LIMIT)
        )
    }
    pairs = {}
    for row in session.scalars(
        select(RelationPair)
        .where(
            RelationPair.universe_id == universe_id,
            or_(RelationPair.low_empire_id == empire_id, RelationPair.high_empire_id == empire_id),
        )
        .order_by(RelationPair.low_empire_id, RelationPair.high_empire_id)
        .limit(RELATION_LIMIT)
    ):
        other = row.high_empire_id if row.low_empire_id == empire_id else row.low_empire_id
        pairs[other] = row
    ids = sorted(set(contacts) | set(pairs), key=str)
    names = (
        {e.id: e.name for e in session.scalars(select(Empire).where(Empire.id.in_(ids)))}
        if ids
        else {}
    )
    relations = []
    for other in ids:
        row, contact = pairs.get(other), contacts.get(other)
        pact = (
            covering_pact(session, row.low_empire_id, row.high_empire_id, at) if row else None
        )
        view = (
            side_view(row, empire_id, at, pact)
            if row
            else {
                "state": NO_AGREEMENT,
                "pact": None,
                "proposal": None,
                "cooldown_until": None,
                "hostility": {"by_self_at": None, "by_counterpart_at": None},
                "actions": ["propose"],
            }
        )
        if contact is None and "propose" in view["actions"]:
            view["actions"].remove("propose")  # proposing needs our own contact
        relations.append(
            {
                "empire": {"id": str(other), "name": names.get(other)},
                "contact": contact_view(session, empire_id, contact),
                **view,
            }
        )
    history = session.scalars(
        select(RelationEvent)
        .where(
            RelationEvent.universe_id == universe_id,
            or_(
                RelationEvent.low_empire_id == empire_id,
                RelationEvent.high_empire_id == empire_id,
            ),
        )
        .order_by(RelationEvent.at.desc(), RelationEvent.id)
        .limit(HISTORY_LIMIT)
    )
    terms = rules.relations
    return {
        "at": at.isoformat(),
        "terms": {
            "proposal_ttl_seconds": terms.proposal_ttl_seconds,
            "refusal_cooldown_seconds": terms.refusal_cooldown_seconds,
            "notice_seconds": terms.notice_seconds,
        },
        "relations": relations,
        "history": [
            {
                "id": str(e.id),
                "at": e.at.isoformat(),
                "kind": e.kind,
                "actor": "self" if e.actor_empire_id == empire_id else "counterpart",
                "counterpart_id": str(
                    e.high_empire_id if e.low_empire_id == empire_id else e.low_empire_id
                ),
                **{k: v for k, v in (e.details or {}).items() if k != "counterpart_id"},
            }
            for e in history
        ],
    }


def contact_view(session, empire_id, contact):
    if contact is None:
        return None
    presence = None
    if contact.presence_planet_id is not None:
        # Names come from the observer's own Knowledge only (the system is MONITORED by it).
        planet = session.get(PlanetKnowledge, (empire_id, contact.presence_planet_id))
        system = (
            session.get(SystemKnowledge, (empire_id, planet.system_id)) if planet else None
        )
        presence = {
            "planet_id": str(contact.presence_planet_id),
            "planet_name": planet.known_name if planet else None,
            "system_id": str(planet.system_id) if planet else None,
            "system_name": system.known_name if system else None,
            "observed_at": iso(contact.presence_observed_at),
        }
    return {
        "first_source": contact.first_source,
        "first_seen_at": iso(contact.first_seen_at),
        "last_seen_at": iso(contact.last_seen_at),
        "presence": presence,
    }
