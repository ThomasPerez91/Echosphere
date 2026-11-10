"""A4 (v0.12) on real PostgreSQL: the study completing a dossier pays its reward into the hold
and reveals (DETECTED) the remarkable systems of the region; the plan checks room for both."""

# ruff: noqa: F811
from uuid import UUID

import pytest
from sqlalchemy import select
from test_colony_api import Clock, game  # noqa: F401
from test_exploitation import study
from test_fleet import FULL, fleets, launch, view, worker  # noqa: F401

from app.colony.rules import load_ruleset
from app.fleet.service import add_units, colony_system, garrison_for
from app.galaxy.models import GalaxyOpportunity, GalaxyRoute, SystemKnowledge
from app.persistence.models import Colony
from app.simulation.production import MICRO_UNITS

pytestmark = pytest.mark.integration


def region(w):
    """Home system, two clues of one dossier there and a remarkable deposit two routes away in
    a system this Empire does not know (test world data, not a game fixture)."""
    with w.game.factory.begin() as s:
        colony = s.get(Colony, w.colony)
        home = colony_system(s, colony)
        links = {}
        for a, b in s.execute(
            select(GalaxyRoute.a_id, GalaxyRoute.b_id).where(GalaxyRoute.universe_id == w.universe)
        ):
            links.setdefault(a, set()).add(b)
            links.setdefault(b, set()).add(a)
        known = set(
            s.scalars(
                select(SystemKnowledge.system_id).where(SystemKnowledge.empire_id == w.empire)
            )
        )
        far = next(n for m in links[home] for n in links[m] if n not in known and n != home)
        count = len(
            s.scalars(select(GalaxyOpportunity.id).where(GalaxyOpportunity.system_id == home)).all()
        )
        clues = [
            GalaxyOpportunity(
                universe_id=w.universe,
                system_id=home,
                ordinal=count + i,
                family="curiosity",
                kind="anomaly",
                tier="common",
                study_seconds=600,
                data_reward=100 * MICRO_UNITS,
                dossier=90,
                clue=i,
            )
            for i in range(2)
        ]
        others = len(
            s.scalars(select(GalaxyOpportunity.id).where(GalaxyOpportunity.system_id == far)).all()
        )
        prize = GalaxyOpportunity(
            universe_id=w.universe,
            system_id=far,
            ordinal=others,
            family="deposit",
            kind="metal_belt",
            tier="remarkable",
            resource="alloys",
            reserve_total=9000 * MICRO_UNITS,
            reserve_remaining=9000 * MICRO_UNITS,
            throughput_per_hour=200 * MICRO_UNITS,
        )
        s.add_all([*clues, prize])
        add_units(s, garrison_for(s, colony).id, {"probe": 3, "freighter": 6})
        s.flush()
        return home, far, [c.id for c in clues]


def test_completing_a_dossier_pays_its_reward_and_reveals_the_region(fleets):
    w = fleets(permissions=FULL, ruleset="v0.12")
    reward = load_ruleset("v0.12").opportunities.dossiers.reward_data * MICRO_UNITS
    home, far, (first, last) = region(w)
    garrison = next(f for f in view(w).json()["fleets"] if f["kind"] == "GARRISON")
    assert launch(w, garrison["id"], "PROSPECT", home, {"probe": 1}).status_code == 200
    w.advance(minutes=31)
    worker(w)
    assert study(w, garrison["id"], first, {"probe": 1, "freighter": 1}).status_code == 200
    w.advance(minutes=11)
    worker(w)
    # The last clue: the hold must carry the curiosity's Data and the dossier reward.
    short = study(w, garrison["id"], last, {"probe": 1, "freighter": 4})
    assert short.status_code == 409 and short.json()["error"]["code"] == "cargo_insufficient"
    sent = study(w, garrison["id"], last, {"probe": 1, "freighter": 5})
    assert sent.status_code == 200, sent.json()
    w.advance(minutes=11)
    worker(w)
    projection = view(w).json()
    mission = next(
        m for m in projection["missions"] if m["id"] == sent.json()["result"]["mission_id"]
    )
    dossier = mission["report"]["result"]["dossier"]
    assert dossier["complete"] is True and dossier["studied"] == dossier["clues"] == 2
    assert dossier["reward_data"] == str(reward) and str(far) in dossier["revealed"]
    fleet = next(f for f in projection["fleets"] if f["id"] == mission["fleet_id"])
    assert fleet["cargo"]["data"] == str(100 * MICRO_UNITS + reward)
    with w.game.factory() as s:
        # Every revealed system is a remarkable one, now DETECTED (the generated world may hold
        # other remarkable opportunities in the same region).
        for system in dossier["revealed"]:
            assert s.get(SystemKnowledge, (w.empire, UUID(system))).state == "DETECTED"
