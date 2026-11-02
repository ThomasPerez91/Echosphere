"""Frontier services (13B, ruleset v0.9). Called inside the Fleet transactions that decide a
movement, under the same Empire Operations stream lock: no new lock, no other stream.

B01 records passages; B02 sets or clears the stationed Fleet protocol. Neither detects,
reveals or engages anything yet (B03+): they only make the logical facts durable.
"""

from sqlalchemy import select

from app.colony.service import ColonyError
from app.frontier.models import FleetPassage
from app.frontier.transit import OUTBOUND, Passage, cancelled, outbound, way_back
from app.galaxy.models import GalaxyRoute


class FrontierError(ColonyError):
    pass


def enabled(rules):
    return getattr(rules, "frontier", None) is not None


def crossed_systems(session, universe_id, origin_id, path):
    """Systems entered along known routes, in order (origin excluded, destination included)."""
    node, systems = origin_id, []
    for route_id in path:
        route = session.get(GalaxyRoute, route_id)
        if route is None or route.universe_id != universe_id:
            raise ValueError("Inconsistent mission path")
        if node not in (route.a_id, route.b_id):
            raise ValueError("Inconsistent mission path")
        node = route.b_id if route.a_id == node else route.a_id
        systems.append(node)
    return systems


def record_outbound(session, rules, mission, path, travel_us):
    if not enabled(rules) or not path:
        return []
    systems = crossed_systems(session, mission.universe_id, mission.origin_id, path)
    passages = outbound(mission.started_at, travel_us, systems)
    for p in passages:
        session.add(row(mission, p))
    session.flush()
    return passages


def planned(session, mission):
    return list(
        session.scalars(
            select(FleetPassage)
            .where(FleetPassage.mission_id == mission.id)
            .order_by(FleetPassage.sequence)
            .with_for_update()
        )
    )


def record_way_back(session, rules, mission, depart_at, progress_at):
    """The mirrored way back; unreached outbound entries are cancelled, never deleted."""
    if not enabled(rules):
        return []
    rows = planned(session, mission)
    if not rows:
        return []
    if any(r.direction != OUTBOUND for r in rows):
        raise ValueError("Way back already recorded")
    passages = [Passage(r.sequence, r.system_id, r.entered_at, r.direction) for r in rows]
    unreached = {p.sequence for p in cancelled(passages, progress_at)}
    for r in rows:
        if r.sequence in unreached:
            r.cancelled_at = progress_at
    back = way_back(passages, mission.origin_id, mission.started_at, depart_at, progress_at)
    for p in back:
        session.add(row(mission, p))
    session.flush()
    return back


def row(mission, p):
    return FleetPassage(
        mission_id=mission.id,
        sequence=p.sequence,
        empire_id=mission.empire_id,
        universe_id=mission.universe_id,
        system_id=p.system_id,
        entered_at=p.entered_at,
        direction=p.direction,
    )


def check_protocol(rules, protocol):
    """None clears the protocol; otherwise it must be enabled by the pinned ruleset."""
    if not enabled(rules):
        raise FrontierError("Frontier absent from pinned ruleset", "frontier_unavailable")
    if protocol is not None and protocol not in rules.frontier.protocols:
        raise FrontierError("Protocol not enabled by this ruleset", "protocol_unavailable")
