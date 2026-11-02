"""Trusted narrow application adapter. No arbitrary callback or policy-supplied U/E identity."""

from uuid import UUID

from app.ai.controller import AIDenied, authorize
from app.colony import service as colony
from app.fleet import service as fleet
from app.relations import service as relations
from app.research import service as research

CAPABILITIES = frozenset(
    {
        "colony.read",
        "colony.construct",
        "research.read",
        "research.start",
        "galaxy.read",
        "fleet.read",
        "fleet.build",
        "fleet.command",
        "colony.expand",
        # v0.8 diplomacy only: answer or propose a pact. No rupture, no combat capability.
        "relations.read",
        "relations.negotiate",
    }
)
REQUIRED = {
    "build": {"colony.read", "colony.construct"},
    "research": {"research.read", "research.start", "colony.read"},
    "order": {"fleet.read", "fleet.build", "colony.read"},
    "split": {"fleet.read", "fleet.command"},
    "load": {"fleet.read", "fleet.command", "colony.read"},
    "unload": {"fleet.read", "fleet.command", "colony.read"},
    "launch": {"fleet.read", "fleet.command"},
    "relation": {"relations.read", "relations.negotiate"},
}
# Q18 B8/B10: the policy may answer or propose; it never withdraws or breaks a pact.
RELATION_ACTIONS = {"propose", "accept", "refuse"}


def dispatch(session, engine, controller, candidate, key, at):
    authorize(session, controller)
    operation, b = candidate["operation"], candidate["body"]
    if operation not in REQUIRED or not REQUIRED[operation] <= CAPABILITIES:
        raise AIDenied("ai_operation_denied")
    u, e = controller.universe_id, controller.empire_id
    if "empire_id" in b or "universe_id" in b:
        raise AIDenied("ai_identity_denied")
    uid = lambda value: UUID(value)  # noqa: E731
    if operation == "build":
        row = colony.enqueue(
            session,
            engine,
            u,
            e,
            uid(b["colony_id"]),
            key=key,
            kind=b["kind"],
            sector=b["sector"],
            target_level=b["level"],
            at=at,
        )
        return {"order_id": str(row.id)}
    if operation == "research":
        row = research.start(
            session,
            engine,
            u,
            e,
            uid(b["colony_id"]),
            key=key,
            technology_id=b["technology"],
            at=at,
        )
        return {"order_id": str(row.id)}
    if operation == "order":
        row = fleet.order_ships(
            session, engine, u, e, uid(b["colony_id"]), b["ship"], 1, key=key, at=at
        )
        return {"order_id": str(row.id)}
    if operation == "split":
        return fleet.split(
            session, engine, u, e, uid(b["fleet_id"]), b["units"], {}, key=key, at=at
        )
    if operation == "load":
        return fleet.load(
            session,
            engine,
            u,
            e,
            uid(b["fleet_id"]),
            uid(b["colony_id"]),
            b["cargo"],
            key=key,
            at=at,
        )
    if operation == "relation":
        if b["action"] not in RELATION_ACTIONS:
            raise AIDenied("ai_relation_denied")
        return relations.OPERATIONS[b["action"]](
            session, u, e, uid(b["counterpart_id"]), key=key, at=at
        )
    if operation == "unload":
        return fleet.unload(
            session, engine, u, e, uid(b["fleet_id"]), uid(b["colony_id"]), key=key, at=at
        )
    if b["kind"] not in {"SURVEY", "COLONIZE", "DEPLOY", "RETURN"}:
        raise AIDenied("ai_mission_denied")
    needed = (
        {"galaxy.read", "colony.expand"}
        if b["kind"] == "COLONIZE"
        else ({"galaxy.read"} if b["kind"] == "SURVEY" else set())
    )
    if not needed <= CAPABILITIES:
        raise AIDenied("ai_operation_denied")
    row = fleet.launch(
        session,
        engine,
        u,
        e,
        uid(b["fleet_id"]),
        b["kind"],
        uid(b["destination_id"]) if b.get("destination_id") else None,
        b["units"],
        {},
        key=key,
        at=at,
        target_planet_id=uid(b["planet_id"]) if b.get("planet_id") else None,
        colony_read=True,
    )
    return {"mission_id": str(row.id), "fleet_id": str(row.fleet_id)}
