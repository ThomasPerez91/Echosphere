"""Pure decisions of the automatic frontier reactions (13B, B05/B06). No database, no clock.

The orchestrator gathers facts at the logical encounter instant `t` and asks these functions;
the same facts always give the same answer, whatever the worker delay.
"""

from datetime import datetime, timedelta

AGGRESSIVE = ("AMBUSH", "INTERCEPTION")
FRIENDLY = "FRIENDLY_CONTACT"
ENGAGEMENT, RETREAT = "engagement", "retreat"


def kind_for(protocol: str) -> str | None:
    if protocol in AGGRESSIVE:
        return ENGAGEMENT
    if protocol == FRIENDLY:
        return RETREAT
    return None


def known_enemy(
    contact_since: datetime | None, hostile_acts: list[datetime], t: datetime, window: timedelta
) -> bool:
    """D4: already identified by a contact at t, and a resolved hostile act against the watcher
    strictly younger than `window` at t (t - window < act <= t). A refused proposal never counts:
    only resolved battles are passed as hostile acts."""
    if contact_since is None or contact_since > t:
        return False
    return any(t - window < act <= t for act in hostile_acts)


def engagement_outcome(
    *,
    pact: bool,
    protocol: str,
    enemy: bool,
    watcher_military: dict[str, int],
    mover_military: dict[str, int],
) -> str | None:
    """None means: fight with the Combat resolver. Otherwise the reason nothing is fought.

    Order matters and is fixed: a pact always prevails (FC12), then AMBUSH's enemy criterion,
    then the forces: no military unit on the watcher side cannot engage, and a purely civilian
    mover is never destroyed by an improvised military rule (D5)."""
    if protocol not in AGGRESSIVE:
        raise ValueError("Only aggressive protocols engage")
    if pact:
        return "pact"
    if protocol == "AMBUSH" and not enemy:
        return "not_enemy"
    if not any(watcher_military.values()):
        return "no_force"
    if not any(mover_military.values()):
        return "no_military_target"
    return None


def rank(encounter_at, mission_id, sequence, watch_fleet_id, kind):
    """Total order of reactions: instant, then engagements before retreats at the same instant
    (a Fleet first meets the aggressive watchers, a friendly one then withdraws), then stable
    identifiers. Simultaneous passages and successive interceptions resolve in this order."""
    order = 0 if kind == ENGAGEMENT else 1
    return (encounter_at, order, str(mission_id), sequence, str(watch_fleet_id))


def subtract(stacks: dict[str, int], losses: dict[str, int]) -> dict[str, int]:
    left = {c: n - losses.get(c, 0) for c, n in stacks.items()}
    if any(v < 0 for v in left.values()) or set(losses) - set(stacks):
        raise ValueError("Losses exceed the engaged units")
    return left


def add(stacks: dict[str, int], extra: dict[str, int]) -> dict[str, int]:
    result = dict(stacks)
    for c, n in extra.items():
        result[c] = result.get(c, 0) + n
    return {c: n for c, n in result.items() if n}
