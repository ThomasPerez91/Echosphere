"""Explicit, atomic Game bootstrap. Never imports a recipe or manufactures strategic units,
except the explicit test game (sandbox) whose human Empire starts almost finished."""

from uuid import UUID

from sqlalchemy import select, text

from app.ai.controller import AIDenied, activate
from app.ai.models import AIBootstrap
from app.ai.rules import fingerprint
from app.colony.models import UniverseEconomy
from app.colony.rules import load_ruleset, since
from app.colony.service import configure_universe, initialize_colony
from app.galaxy.models import GalaxySystem, StartingSite
from app.galaxy.service import initialize_empire
from app.galaxy.world import generate_world
from app.persistence.models import Colony, Empire, Universe
from app.simulation.clock import utc
from app.simulation.scheduler import IdempotencyConflict


def pinned(rules):
    """Ruleset digest input; the v0.7 `combat` and v0.8 `relations` keys are omitted when
    absent, so bootstrap receipts recorded before those domains existed replay identically."""
    data = rules.model_dump()
    for key in ("combat", "relations", "frontier", "opportunities"):
        if data.get(key) is None:
            data.pop(key, None)
    return data


def bootstrap(
    session,
    engine,
    universe_id,
    name,
    seed,
    profiles,
    at,
    *,
    rules=None,
    humans=1,
    size=None,
    sandbox=False,
):
    """`rules` permits explicit injected test timings, never runtime defaults from fixtures.
    `humans` human Empires (multi, Q59) take the first starting sites, then the AI profiles.
    galaxy-v1 (v0.6-v0.9) offers at most four sites in total; galaxy-v2 (v0.10, Q61) a map
    `size` with its own Empire cap, at most 10 humans and 30 AI."""
    rules = rules or load_ruleset("v0.6")
    v2 = since(rules.version, "v0.10")
    if v2:
        size = rules.galaxy.default_size if size is None else size
        valid = (
            type(size) is int
            and str(size) in rules.galaxy.sizes
            and 1 <= humans <= rules.galaxy.max_humans
            and 0 <= len(profiles) <= rules.galaxy.max_ai
            and humans + len(profiles) <= rules.galaxy.empire_cap(size)
        )
    else:
        valid = size is None and 0 <= len(profiles) <= 3 and 1 <= humans <= 4
        valid = valid and humans + len(profiles) <= 4
    if (
        not since(rules.version, "v0.6")
        or rules.ai is None
        or not valid
        or any(p not in rules.ai.profiles for p in profiles)
    ):
        raise AIDenied("invalid_bootstrap_configuration")
    request = {
        "name": name,
        "seed": seed,
        "profiles": list(profiles),
        "rules_digest": fingerprint(pinned(rules)),
    }
    if humans != 1:
        # Omitted for one human so receipts recorded before multi replay identically.
        request["humans"] = humans
    if v2:
        request["size"] = size
    if sandbox:
        # Test game (recette 10/11/2026): solo, galaxy-v2 only; omitted otherwise.
        if humans != 1 or not v2:
            raise AIDenied("invalid_bootstrap_configuration")
        request["sandbox"] = True
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
        universe = Universe(id=universe_id, name=name, seed=seed, sandbox=sandbox)
        session.add(universe)
        session.flush()
    if (
        universe.name != name
        or universe.seed != seed
        or universe.sandbox != sandbox
        or session.get(UniverseEconomy, universe_id) is not None
        or session.scalar(select(Empire.id).where(Empire.universe_id == universe_id).limit(1))
    ):
        raise AIDenied("bootstrap_requires_empty_universe")
    if sandbox:
        from app.sandbox.service import sandbox_rules

        rules = sandbox_rules(rules)
    configure_universe(session, universe_id, rules)
    if v2:
        # Exactly one starting site per Empire of this game (Équitable placement, Q61).
        generate_world(
            session, universe_id, system_count=size, starting_site_count=humans + len(profiles)
        )
    else:
        generate_world(session, universe_id)
    # Site quality is never consulted; canonical generator order independent of actor/profile.
    sites = list(
        session.scalars(
            select(StartingSite)
            .join(GalaxySystem, GalaxySystem.system_id == StartingSite.system_id)
            .where(StartingSite.universe_id == universe_id)
            .order_by(GalaxySystem.ordinal)
            .limit(humans + len(profiles))
        )
    )
    if len(sites) < len(profiles) + humans:
        raise AIDenied("insufficient_starting_sites")
    actors = []
    for index, profile in enumerate([*([None] * humans), *profiles]):
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
    if sandbox:
        from app.sandbox.service import prepare

        for actor in actors:
            if actor["profile"] is None:
                prepare(
                    session, universe_id, UUID(actor["empire_id"]), UUID(actor["colony_id"]), at
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
