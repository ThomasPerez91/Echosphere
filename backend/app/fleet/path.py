"""UX-API-01: ordered systems of a mission route, from data the server already holds.

Pure functions only (no database): the callers pass the route endpoints read from the Empire's
own RouteKnowledge and the set of systems the Empire knows. Nothing here chooses or repairs a
route: an inconsistent chain gives None and the API then omits `path` rather than inventing one.
"""

from collections.abc import Collection, Iterable, Sequence
from uuid import UUID


def systems_along(origin: UUID, endpoints: Iterable[tuple[UUID, UUID] | None]) -> list[UUID] | None:
    """Origin, then the system reached through each route in order; None if a route is missing
    or does not touch the current system. Zero routes give `[origin]` (0-hop mission)."""
    node, systems = origin, [origin]
    for pair in endpoints:
        if pair is None:
            return None
        a, b = pair
        if node == a:
            node = b
        elif node == b:
            node = a
        else:
            return None
        systems.append(node)
    return systems


def public_path(
    systems: Sequence[UUID] | None, destination: UUID, hops: int, known: Collection[UUID]
) -> list[str] | None:
    """`path` as exposed: hops + 1 systems ending at the destination, every one known to the
    Empire (Fog of War). Anything else is withheld (None), never trimmed or patched."""
    if systems is None or len(systems) != hops + 1 or systems[-1] != destination:
        return None
    if any(system not in known for system in systems):
        return None
    return [str(system) for system in systems]
