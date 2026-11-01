"""Founding a v0.5+ Colony on a generated planet: a separate initializer, never the start colony.

`initialize_colony` stays the reference starting colony of v0.1-v0.4 (12/2, free stocks and four
infrastructures). A founded colony gets the planet's real capacities, no free infrastructure, the
delivered founding package as its only stock and zero production. It is created inside the
COLONIZE resolution transaction with a brand-new timeline: no existing Colony stream is touched.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.colony.models import ColonyEconomy
from app.colony.service import ColonyError, refresh_effects, rules_for
from app.persistence.models import Colony, Planet
from app.simulation.clock import utc
from app.simulation.production import MICRO_UNITS, RESOURCES, ProductionState
from app.simulation.service import initialize


def found_colony(
    session: Session,
    universe_id: UUID,
    empire_id: UUID,
    planet_id: UUID,
    mission_id: UUID,
    package: dict[str, int],
    at: datetime,
) -> Colony:
    """Create the Colony and its economy at logical date `at`; `package` is in micro-units."""
    rules = rules_for(session, universe_id)
    planet = session.get(Planet, planet_id)
    if rules.colonization is None or planet is None or planet.universe_id != universe_id:
        raise ColonyError("Colonization unavailable for this planet")
    if not set(package) <= RESOURCES or any(type(v) is not int or v < 0 for v in package.values()):
        raise ColonyError("Invalid founding package")
    capacity = rules.colony.base_capacity * MICRO_UNITS
    if any(value > capacity for value in package.values()):
        raise ColonyError("Founding package exceeds new colony storage")
    colony = Colony(
        universe_id=universe_id,
        empire_id=empire_id,
        planet_id=planet_id,
        founded_at=utc(at),
        founding_mission_id=mission_id,
    )
    session.add(colony)
    session.flush()  # uq_colonies_planet: the database refuses any second owner
    initialize(
        session,
        colony.id,
        {r: ProductionState(package.get(r, 0), 0, utc(at), capacity=capacity) for r in RESOURCES},
    )
    session.add(ColonyEconomy(colony_id=colony.id, universe_id=universe_id, next_order_sequence=1))
    session.flush()
    # No infrastructure: production stays 0 and storage the ruleset base capacity.
    refresh_effects(session, colony.id, rules)
    return colony
