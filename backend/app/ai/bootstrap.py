"""Explicit, atomic Game bootstrap. Never imports a recipe or manufactures strategic units."""

from sqlalchemy import select, text

from app.ai.controller import AIDenied, activate
from app.ai.models import AIBootstrap
from app.ai.rules import fingerprint
from app.colony.models import UniverseEconomy
from app.colony.rules import load_ruleset
from app.colony.service import configure_universe, initialize_colony
from app.galaxy.models import GalaxySystem, StartingSite
from app.galaxy.service import initialize_empire
from app.galaxy.world import generate_world
from app.persistence.models import Colony, Empire, Universe
from app.simulation.clock import utc
from app.simulation.scheduler import IdempotencyConflict


def bootstrap(session, engine, universe_id, name, seed, profiles, at, *, rules=None):
    """`rules` permits explicit injected test timings, never runtime defaults from fixtures."""
    rules = rules or load_ruleset("v0.6")
    if (
        rules.version != "v0.6"
        or rules.ai is None
        or not 0 <= len(profiles) <= 3
        or any(p not in rules.ai.profiles for p in profiles)
    ):
        raise AIDenied("invalid_bootstrap_configuration")
    request = {
        "name": name,
        "seed": seed,
        "profiles": list(profiles),
        "rules_digest": fingerprint(rules.model_dump()),
    }
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(universe_id.bytes[:8], signed=True)},
    )
    existing = session.get(AIBootstrap, universe_id)
    if existing is not None:
        if existing.request_digest != fingerprint(request):
            raise IdempotencyConflict("Bootstrap intention differs from the published world")
        return existing.result
    universe = session.get(Universe, universe_id)
    if universe is None:
        universe = Universe(id=universe_id, name=name, seed=seed)
        session.add(universe)
        session.flush()
    if (
        universe.name != name
        or universe.seed != seed
        or session.get(UniverseEconomy, universe_id) is not None
        or session.scalar(select(Empire.id).where(Empire.universe_id == universe_id).limit(1))
    ):
        raise AIDenied("bootstrap_requires_empty_universe")
    configure_universe(session, universe_id, rules)
    generate_world(session, universe_id)
    # Site quality is never consulted; canonical generator order independent of actor/profile.
    sites = list(
        session.scalars(
            select(StartingSite)
            .join(GalaxySystem, GalaxySystem.system_id == StartingSite.system_id)
            .where(StartingSite.universe_id == universe_id)
            .order_by(GalaxySystem.ordinal)
            .limit(4)
        )
    )
    if len(sites) < len(profiles) + 1:
        raise AIDenied("insufficient_starting_sites")
    actors = []
    for index, profile in enumerate([None, *profiles]):
        empire = Empire(
            universe_id=universe_id,
            name=f"Empire {index + 1}",
            controller_type="human" if profile is None else "ai",
        )
        session.add(empire)
        session.flush()
        colony = Colony(
            universe_id=universe_id, empire_id=empire.id, planet_id=sites[index].planet_id
        )
        session.add(colony)
        session.flush()
        initialize_colony(session, universe_id, empire.id, colony.id, utc(at))
        initialize_empire(session, engine, universe_id, empire.id, colony.id, utc(at))
        controller = activate(session, universe_id, empire.id, profile, at) if profile else None
        actors.append(
            {
                "empire_id": str(empire.id),
                "colony_id": str(colony.id),
                "controller_id": str(controller.id) if controller else None,
                "profile": profile,
                "site_ordinal": index,
            }
        )
    result = {"universe_id": str(universe_id), "started_at": utc(at).isoformat(), "actors": actors}
    session.add(
        AIBootstrap(
            universe_id=universe_id,
            request=request,
            request_digest=fingerprint(request),
            result=result,
        )
    )
    session.flush()
    return result
