"""Explicit atomic generation of a NEW universe; never called at GET/startup/migration."""

import hashlib

from sqlalchemy import select

from app.colony.service import ColonyError, rules_for
from app.galaxy.generator import canonical, generate
from app.galaxy.models import GalaxyPlanet, GalaxyRoute, GalaxySystem, StartingSite, UniverseGalaxy
from app.persistence.models import Planet, StellarSystem, Universe
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
        count = rules.galaxy.system_count if system_count is None else system_count
        sites = (
            rules.galaxy.starting_site_count if starting_site_count is None else starting_site_count
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
        ids = []
        for ordinal, generated in enumerate(result["world"]["systems"]):
            system = StellarSystem(universe_id=universe_id, name=generated["name"])
            session.add(system)
            session.flush()
            ids.append(system.id)
            session.add(
                GalaxySystem(
                    system_id=system.id,
                    universe_id=universe_id,
                    ordinal=ordinal,
                    x=generated["x"],
                    y=generated["y"],
                )
            )
            session.flush()
            for index, data in enumerate(generated["planets"]):
                planet = Planet(
                    universe_id=universe_id,
                    system_id=system.id,
                    name=data["name"],
                    sector_capacity=data["sectors"],
                    orbital_capacity=data["orbitals"],
                )
                session.add(planet)
                session.flush()
                session.add(
                    GalaxyPlanet(
                        planet_id=planet.id,
                        universe_id=universe_id,
                        system_id=system.id,
                        ordinal=index,
                    )
                )
                session.flush()
                if index == 0 and ordinal in result["world"]["starting_sites"]:
                    session.add(
                        StartingSite(
                            planet_id=planet.id, universe_id=universe_id, system_id=system.id
                        )
                    )
        for a, b in result["world"]["routes"]:
            first, second = sorted([ids[a], ids[b]])
            session.add(GalaxyRoute(universe_id=universe_id, a_id=first, b_id=second))
        session.flush()
        return manifest
