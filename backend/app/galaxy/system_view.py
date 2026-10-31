"""Detailed projection from authorized Knowledge; no world enrichment or scheduler."""

from uuid import UUID

from sqlalchemy import select

from app.galaxy.models import PlanetKnowledge, RouteKnowledge, SystemKnowledge
from app.galaxy.service import project_system
from app.persistence.models import Colony


def project(session, known, permissions, at):
    result = project_system(session, known, "colony.read" in permissions)
    if known.state == "DETECTED":
        return result
    result.update(
        server_time=at.isoformat(),
        empire_id=str(known.empire_id),
        permissions=[p for p in ("galaxy.read", "colony.read") if p in permissions],
        routes=[],
        presences=[],
        colony_links=[],
    )
    for route in session.scalars(
        select(RouteKnowledge)
        .where(
            RouteKnowledge.universe_id == known.universe_id,
            RouteKnowledge.empire_id == known.empire_id,
            (RouteKnowledge.a_id == known.system_id) | (RouteKnowledge.b_id == known.system_id),
        )
        .order_by(RouteKnowledge.route_id)
    ):
        other_id = route.b_id if route.a_id == known.system_id else route.a_id
        other = session.get(SystemKnowledge, (known.empire_id, other_id))
        if other is None or other.universe_id != known.universe_id:
            continue
        neighbor = {"id": str(other_id), "state": other.state}
        if other.state != "DETECTED":
            neighbor["name"] = other.known_name
        result["routes"].append({"id": str(route.route_id), "neighbor": neighbor})
    observed_ids = (known.observation or {}).get("own_colony_ids", [])
    current = known.state == "MONITORED"
    # Only current authorized OWN entities may supply a link; stale snapshots stay stale.
    colonies = {}
    if current and "colony.read" in permissions and observed_ids:
        planets = {
            p.planet_id: p
            for p in session.scalars(
                select(PlanetKnowledge).where(
                    PlanetKnowledge.universe_id == known.universe_id,
                    PlanetKnowledge.empire_id == known.empire_id,
                    PlanetKnowledge.system_id == known.system_id,
                )
            )
        }
        for colony in session.scalars(
            select(Colony).where(
                Colony.universe_id == known.universe_id,
                Colony.empire_id == known.empire_id,
                Colony.id.in_([UUID(value) for value in observed_ids]),
                Colony.planet_id.in_(planets),
            )
        ):
            planet = planets[colony.planet_id]
            colonies[str(colony.id)] = {
                "colony_id": str(colony.id),
                "planet_id": str(planet.planet_id),
                "name": planet.known_name,
            }
    for identifier in observed_ids:
        presence = {
            "kind": "own_colony",
            "current": current,
            "observed_at": known.last_seen_at.isoformat() if known.last_seen_at else None,
            "colony": colonies.get(identifier),
        }
        result["presences"].append(presence)
        if presence["colony"]:
            result["colony_links"].append(presence["colony"])
    return result
