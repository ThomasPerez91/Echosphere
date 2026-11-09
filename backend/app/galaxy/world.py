"""Explicit atomic generation of a NEW universe; never called at GET/startup/migration."""

import hashlib
from uuid import uuid4

from sqlalchemy import select

from app.colony.service import ColonyError, rules_for
from app.galaxy.generator import canonical, generate
from app.galaxy.generator_v2 import GalaxyRulesV2, generate_v2
from app.galaxy.models import (
    GalaxyOpportunity,
    GalaxyPlanet,
    GalaxyRoute,
    GalaxySystem,
    StartingSite,
    UniverseGalaxy,
)
from app.galaxy.opportunities import generate_opportunities
from app.persistence.models import Planet, StellarSystem, Universe
from app.simulation.production import MICRO_UNITS
from app.simulation.scheduler import IdempotencyConflict


def generate_world(session, universe_id, *, system_count=None, starting_site_count=None):
    with session.begin_nested():
        universe = session.scalar(
            select(Universe).where(Universe.id == universe_id).with_for_update()
        )
        if universe is None:
            raise ColonyError("Universe unavailable", "galaxy_unavailable")
        rules = rules_for(session, universe_id)
        if rules.galaxy is None:
            raise ColonyError("Pinned ruleset has no galaxy", "galaxy_unavailable")
        v2 = isinstance(rules.galaxy, GalaxyRulesV2)
        if v2:
            count = rules.galaxy.default_size if system_count is None else system_count
            sites = (
                rules.galaxy.empire_cap(count) if starting_site_count is None
                else starting_site_count
            )
        else:
            count = rules.galaxy.system_count if system_count is None else system_count
            sites = (
                rules.galaxy.starting_site_count if starting_site_count is None
                else starting_site_count
            )
        existing = session.get(UniverseGalaxy, universe_id)
        if existing is not None:
            if (
                existing.inputs["system_count"],
                existing.inputs["starting_site_count"],
                existing.inputs["seed"],
                existing.inputs["data"],
            ) != (count, sites, universe.seed, rules.galaxy.model_dump()):
                raise IdempotencyConflict("Generated world cannot be replaced")
            return existing
        if (
            session.scalar(
                select(StellarSystem.id).where(StellarSystem.universe_id == universe_id).limit(1)
            )
            is not None
        ):
            raise ColonyError("Existing worlds require explicit adoption", "galaxy_unavailable")
        if v2:
            result = generate_v2(universe.seed, rules.galaxy, size=count, empires=sites)
        else:
            result = generate(
                universe.seed, rules.galaxy, system_count=count, starting_site_count=sites
            )
        manifest = UniverseGalaxy(
            universe_id=universe_id,
            generator_version=rules.galaxy.galaxy_generator_version,
            inputs=result["inputs"],
            digest=hashlib.sha256(canonical(result["world"]).encode()).hexdigest(),
        )
        session.add(manifest)
        session.flush()
        # Explicit identifiers and one flush per table: a 2 000-system world is a few batched
        # INSERTs, not tens of thousands of round trips inside the start transaction.
        world = result["world"]
        ids = [uuid4() for _ in world["systems"]]
        session.add_all(
            StellarSystem(id=ids[n], universe_id=universe_id, name=generated["name"])
            for n, generated in enumerate(world["systems"])
        )
        session.flush()
        session.add_all(
            GalaxySystem(
                system_id=ids[n], universe_id=universe_id, ordinal=n,
                x=generated["x"], y=generated["y"],
            )
            for n, generated in enumerate(world["systems"])
        )
        session.flush()
        planets = []
        for n, generated in enumerate(world["systems"]):
            for index, data in enumerate(generated["planets"]):
                planets.append((n, index, uuid4(), data))
        session.add_all(
            Planet(
                id=planet_id, universe_id=universe_id, system_id=ids[n], name=data["name"],
                sector_capacity=data["sectors"], orbital_capacity=data["orbitals"],
            )
            for n, _, planet_id, data in planets
        )
        session.flush()
        session.add_all(
            GalaxyPlanet(
                planet_id=planet_id, universe_id=universe_id, system_id=ids[n], ordinal=index
            )
            for n, index, planet_id, _ in planets
        )
        session.flush()
        sites = set(world["starting_sites"])
        session.add_all(
            StartingSite(planet_id=planet_id, universe_id=universe_id, system_id=ids[n])
            for n, index, planet_id, _ in planets
            if index == 0 and n in sites
        )
        session.add_all(
            GalaxyRoute(universe_id=universe_id, a_id=min(ids[a], ids[b]), b_id=max(ids[a], ids[b]))
            for a, b in world["routes"]
        )
        session.flush()
        if rules.opportunities is not None:
            # EXP-01 (v0.10): opportunities layered on this exact world, same seed.
            generated = generate_opportunities(universe.seed, world, rules.opportunities)
            session.add_all(
                GalaxyOpportunity(
                    universe_id=universe_id, system_id=ids[o["system"]], ordinal=o["index"],
                    family=o["family"], kind=o["kind"], tier=o["tier"],
                    resource=o.get("resource"),
                    reserve_total=o["reserve"] * MICRO_UNITS if "reserve" in o else None,
                    reserve_remaining=o["reserve"] * MICRO_UNITS if "reserve" in o else None,
                    throughput_per_hour=o["throughput_per_hour"] * MICRO_UNITS
                    if "throughput_per_hour" in o else None,
                    study_seconds=o.get("study_seconds"),
                    data_reward=o["data"] * MICRO_UNITS if "data" in o else None,
                    dossier=o.get("dossier"), clue=o.get("clue"),
                )
                for o in generated["opportunities"]
            )
            session.flush()
        return manifest
