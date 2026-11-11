"""EXP-01b: opportunities persisted with a v0.10 world and projected under the Fog of War."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.ai.bootstrap import bootstrap
from app.colony.rules import load_ruleset
from app.galaxy import service as galaxy_service
from app.galaxy.api import Galaxy
from app.galaxy.generator_v2 import generate_v2
from app.galaxy.models import (
    GalaxyOpportunity,
    GalaxySystem,
    OpportunityKnowledge,
    UniverseGalaxy,
)
from app.galaxy.opportunities import generate_opportunities
from app.galaxy.world import generate_world
from app.persistence.database import create_session_factory
from app.persistence.models import Empire
from app.simulation.production import MICRO_UNITS
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
V10 = load_ruleset("v0.10")


class Clock:
    def __init__(self):
        self.at = datetime(2099, 1, 1, tzinfo=UTC)

    def now(self):
        return self.at


@pytest.fixture
def world(database_engine):
    factory = create_session_factory(database_engine)
    clock = Clock()
    engine = TimeEngine(factory, clock)
    universe = uuid4()
    with factory.begin() as session:
        result = bootstrap(session, engine, universe, "Opportunités", "exp-seed",
                           ["expansionist"], clock.now(), rules=V10, size=100)
    try:
        yield factory, engine, clock, universe, result
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))


def test_a_v010_world_stores_exactly_the_generated_opportunities(world):
    factory, _, _, universe, _ = world
    expected_world = generate_v2("exp-seed", V10.galaxy, size=100, empires=2)
    expected = generate_opportunities("exp-seed", expected_world["world"], V10.opportunities)
    with factory() as session:
        manifest = session.get(UniverseGalaxy, universe)
        assert manifest.generator_version == "galaxy-v2"
        assert manifest.digest == expected_world["metrics"]["digest"]  # world unchanged by EXP-01
        ordinal = {
            g.system_id: g.ordinal
            for g in session.scalars(
                select(GalaxySystem).where(GalaxySystem.universe_id == universe)
            )
        }
        rows = session.scalars(
            select(GalaxyOpportunity).where(GalaxyOpportunity.universe_id == universe)
        ).all()
        stored = sorted(
            (ordinal[r.system_id], r.ordinal, r.family, r.kind, r.tier, r.resource,
             r.reserve_total, r.reserve_remaining, r.throughput_per_hour, r.study_seconds,
             r.data_reward, r.dossier, r.clue)
            for r in rows
        )

        def micro(value):
            return None if value is None else value * MICRO_UNITS

        wanted = sorted(
            (o["system"], o["index"], o["family"], o["kind"], o["tier"], o.get("resource"),
             micro(o.get("reserve")), micro(o.get("reserve")), micro(o.get("throughput_per_hour")),
             o.get("study_seconds"), micro(o.get("data")), o.get("dossier"), o.get("clue"))
            for o in expected["opportunities"]
        )
        assert stored == wanted and len(stored) > 0
    # Generating again is a no-op: no duplicate, no new identifiers.
    with factory.begin() as session:
        generate_world(session, universe, system_count=100, starting_site_count=2)
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(GalaxyOpportunity).where(
            GalaxyOpportunity.universe_id == universe))
        assert count == len(rows)


def projection(factory, engine, universe, empire, at):
    api = Galaxy.__new__(Galaxy)
    api.engine = engine
    with factory.begin() as session:
        return api.projection(session, universe, empire, ["galaxy.read"], at)


def test_fog_mapping_shows_signatures_only_and_prospection_shows_dated_observed_values(world):
    factory, engine, clock, universe, result = world
    empire = UUID(result["actors"][0]["empire_id"])
    view = projection(factory, engine, universe, empire, clock.now())
    with factory() as session:
        counts = dict(session.execute(
            select(GalaxyOpportunity.system_id, func.count())
            .where(GalaxyOpportunity.universe_id == universe)
            .group_by(GalaxyOpportunity.system_id)
        ).all())
    for system in view["systems"]:
        if system["state"] == "DETECTED":
            assert "opportunities" not in system  # a signal reveals nothing more
            continue
        assert system["opportunities"] == {
            "signatures": counts.get(UUID(system["id"]), 0), "known": []
        }
    # Map one deposit's system (as a survey would; the fairness of start zones is a pure test).
    with factory.begin() as session:
        deposit = session.scalars(
            select(GalaxyOpportunity).where(
                GalaxyOpportunity.universe_id == universe, GalaxyOpportunity.family == "deposit"
            ).order_by(GalaxyOpportunity.id)
        ).first()
        assert deposit is not None
        galaxy_service.map_system(session, universe, empire, deposit.system_id, clock.now())
        session.add(OpportunityKnowledge(
            empire_id=empire, opportunity_id=deposit.id, universe_id=universe,
            observed_at=clock.now(), observed_reserve=deposit.reserve_remaining,
        ))
        # Someone else extracts later: the Empire keeps the value it observed.
        deposit.reserve_remaining -= MICRO_UNITS
    view = projection(factory, engine, universe, empire, clock.now())
    (system,) = [s for s in view["systems"] if s["id"] == str(deposit.system_id)]
    (known,) = system["opportunities"]["known"]
    assert known == {
        "id": str(deposit.id), "family": "deposit", "kind": deposit.kind, "tier": deposit.tier,
        "observed_at": clock.now().isoformat(), "resource": deposit.resource,
        "reserve": str(deposit.reserve_total),
        "throughput_per_hour": str(deposit.throughput_per_hour),
    }
    assert system["opportunities"]["signatures"] == counts[deposit.system_id] - 1
    # Another Empire of the same universe learns nothing from this prospection.
    other = UUID(result["actors"][1]["empire_id"])
    with factory() as session:
        assert session.get(Empire, other).universe_id == universe
    for s in projection(factory, engine, universe, other, clock.now())["systems"]:
        assert s.get("opportunities", {"known": []})["known"] == []


def test_older_rulesets_never_get_opportunities(database_engine):
    factory = create_session_factory(database_engine)
    clock = Clock()
    universe = uuid4()
    try:
        with factory.begin() as session:
            bootstrap(session, TimeEngine(factory, clock), universe, "v0.9", "old-seed", [],
                      clock.now(), rules=load_ruleset("v0.9"))
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(GalaxyOpportunity).where(
                GalaxyOpportunity.universe_id == universe)) == 0
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))
