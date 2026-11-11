"""Test-only helpers for the disposable 13B frontier recipe; refused outside its *_test Game DB.

The universe is provisioned by Portal and started by the real operator CLI with ruleset v0.9
(one human, `economic_cautious`, `expansionist`). Unlike the Combat/Relations recipes, this one
**places** test-only Fleets, Knowledge and funds in its disposable database (exactly like the
PostgreSQL integration tests), so that the thirteen 13B situations can be staged quickly and
reproducibly. Every *decision* then goes through the real code: Fleet service commands (the
human, and scripted test movers of AI Empires), `FrontierOrchestrator`, `CombatOrchestrator`,
the AI `Orchestrator` (pact answer) and `TimeEngine`, on an injected clock in the past; the last
scenario is resolved by the real `worker` and `combat-worker` processes on the system clock.
Nothing here is a gameplay rule; outputs are JSON proofs read back from durable state.
"""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.ai.controller import authorize
from app.ai.models import AIBootstrap, AIController
from app.ai.observation import collect
from app.ai.orchestrator import Orchestrator
from app.colony.service import rules_for
from app.combat.orchestrator import CombatOrchestrator
from app.core.config import Settings
from app.fleet import service as fleets
from app.fleet.models import Fleet, FleetMission, FleetReport, FleetStack
from app.frontier import service as frontier
from app.frontier.models import FleetPassage, FrontierDetection, FrontierEncounter
from app.frontier.orchestrator import FrontierOrchestrator
from app.galaxy import service as galaxy
from app.galaxy.models import GalaxyRoute
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Planet, StellarSystem, Universe
from app.relations import service as relations
from app.relations.models import RelationContact, RelationPact
from app.simulation.models import ResourceBalance, StreamFence
from app.simulation.service import TimeEngine
from sqlalchemy import func, select

FRONTIER_DATABASE = "echosphere_frontier_game_test"
M = 1_000_000
SCENARIOS = (
    "detection",
    "friendly",
    "ambush",
    "interception_weak",
    "pact",
    "civilian",
    "destroyed",
    "losses",
)


def frontier_factory():
    settings = Settings()
    assert settings.postgres_db == FRONTIER_DATABASE, "Frontier fixture is restricted to its DB"
    engine = create_database_engine(settings)
    return engine, create_session_factory(engine)


class TestClock:
    def __init__(self, at):
        self.at = at

    def now(self):
        return self.at


def emit(value):
    print(json.dumps(value, default=str))


def provisioned(universe_id):
    import time

    engine, sessions = frontier_factory()
    for _ in range(60):
        with sessions() as s:
            universe = s.get(Universe, UUID(universe_id))
            if universe is not None:
                break
        time.sleep(0.5)
    else:
        raise RuntimeError("Universe was not provisioned through the control plane")
    engine.dispose()
    emit({"name": universe.name, "seed": universe.seed})


def actors(s, u):
    human, cautious, bold = s.get(AIBootstrap, u).result["actors"]
    return human, cautious, bold


def home(s, actor):
    return s.get(Planet, s.get(Colony, UUID(actor["colony_id"])).planet_id).system_id


def place(s, actor, system, units):
    """Test-only placement of an operational Fleet in the disposable database."""
    fleet = Fleet(
        empire_id=UUID(actor["empire_id"]),
        universe_id=s.get(Colony, UUID(actor["colony_id"])).universe_id,
        home_colony_id=UUID(actor["colony_id"]),
        kind="TASK",
        status="STATIONED",
        system_id=system,
        name="Recette 13B",
    )
    s.add(fleet)
    s.flush()
    for ship, count in units.items():
        s.add(FleetStack(fleet_id=fleet.id, ship_class=ship, count=count))
    s.flush()
    return fleet.id


def stage_pairs(s, u, homes, count):
    """Disjoint (watched system, neighbour) pairs away from every home system, stable order."""
    used, pairs = set(homes), []
    for route in s.scalars(
        select(GalaxyRoute).where(GalaxyRoute.universe_id == u).order_by(GalaxyRoute.id)
    ):
        a, b = route.a_id, route.b_id
        if a in used or b in used:
            continue
        pairs.append((a, b))
        used |= {a, b}
        if len(pairs) == count:
            return pairs
    raise RuntimeError("Galaxy too small for the frontier recipe")


def neighbours(s, u, system):
    routes = select(GalaxyRoute).where(
        GalaxyRoute.universe_id == u, (GalaxyRoute.a_id == system) | (GalaxyRoute.b_id == system)
    )
    return [r.b_id if r.a_id == system else r.a_id for r in s.scalars(routes.order_by(GalaxyRoute.id))]


def settle(sessions, clock, until, step=timedelta(minutes=5)):
    """Advance the injected clock, alternating the three real orchestrators like the workers."""
    engine = TimeEngine(sessions, clock)
    entries = FrontierOrchestrator(sessions, clock)
    battles = CombatOrchestrator(sessions, clock)
    while clock.at < until:
        clock.at = min(until, clock.at + step)
        for _ in range(1000):
            moved = engine.process_next() is not None
            moved |= entries.process_next() is not None
            moved |= battles.process_next() is not None
            if not moved:
                break


def setup(universe_id):
    """Knowledge, funds and Fleets for every scenario; one launch per scenario at T0."""
    engine, sessions = frontier_factory()
    u = UUID(universe_id)
    with sessions() as s:
        bootstrap = s.get(AIBootstrap, u).result
    clock = TestClock(datetime.fromisoformat(bootstrap["started_at"]) + timedelta(hours=1))
    timeline = TimeEngine(sessions, clock)
    staged = {}
    with sessions.begin() as s:
        human, cautious, bold = actors(s, u)
        everyone = (human, cautious, bold)
        homes = [home(s, a) for a in everyone]
        for system in s.scalars(select(StellarSystem.id).where(StellarSystem.universe_id == u)):
            for actor in everyone:  # test-only knowledge: every Empire may route anywhere
                galaxy.map_system(s, u, UUID(actor["empire_id"]), system, clock.at)
        for actor in everyone:  # test-only funds; every spending still goes through services
            for r in ("alloys", "flux", "data"):
                s.get(ResourceBalance, (UUID(actor["colony_id"]), r)).stock = 9_000 * M
        # The retreat scenario's "previous system": next to bold's home, outside every watched
        # pair, so that neither the friendly Fleet's way home nor the human's 1-hop ATTACK from
        # there ever crosses another scenario's protocol (a real encounter would change them).
        spare = next(n for n in neighbours(s, u, homes[2]) if n not in homes)
        pairs = stage_pairs(s, u, [*homes, spare], len(SCENARIOS))
    plan = {
        # name: (watcher, protocol, watcher units, mover, mover units)
        # cautious and bold never met: anonymous both ways, then a voluntary introduction.
        "detection": (cautious, "SURVEILLANCE", {"interceptor": 1}, bold, {"frigate": 1}),
        "friendly": (cautious, "FRIENDLY_CONTACT", {"interceptor": 1}, bold, {"frigate": 1}),
        "ambush": (bold, "AMBUSH", {"frigate": 6}, human, {"interceptor": 1}),
        "interception_weak": (human, "INTERCEPTION", {"interceptor": 1}, bold, {"frigate": 4}),
        "pact": (human, "INTERCEPTION", {"frigate": 6}, cautious, {"interceptor": 1}),
        "civilian": (human, "INTERCEPTION", {"frigate": 6}, bold, {"freighter": 1}),
        "destroyed": (human, "INTERCEPTION", {"frigate": 6}, bold, {"interceptor": 1}),
        "losses": (human, "INTERCEPTION", {"interceptor": 1}, bold, {"frigate": 3}),
    }
    # Ambush prerequisite (D4): a real resolved hostile act of the human against `bold`, by a
    # real ATTACK resolved by the Combat orchestrator, before the ambush entry.
    with sessions.begin() as s:
        raid = place(s, human, homes[0], {"interceptor": 2})
        planet = s.get(Colony, UUID(bold["colony_id"])).planet_id
        attack = fleets.launch(
            s, timeline, u, UUID(human["empire_id"]), raid, "ATTACK", None,
            {"interceptor": 2}, None, key="recipe:13b:raid", at=clock.at,
            target_planet_id=planet,
        )
        staged["raid"] = {"mission_id": str(attack.id), "battle_at": attack.due_at.isoformat()}
    settle(sessions, clock, attack.due_at + timedelta(minutes=5))
    # Pact prerequisite: the human proposes; the real AI policy answers on its own turn.
    with sessions.begin() as s:
        h, c = UUID(human["empire_id"]), UUID(cautious["empire_id"])
        relations.record_contact(s, u, h, c, "presence", clock.at)
        relations.record_contact(s, u, c, h, "presence", clock.at)
        relations.propose(s, u, h, c, key="recipe:13b:pact", at=clock.at)
    runner = Orchestrator(sessions, clock)
    for _ in range(36):
        settle(sessions, clock, clock.at + timedelta(minutes=10))
        runner.process_next(controller_id=UUID(cautious["controller_id"]))
        with sessions() as s:
            if s.scalar(select(func.count()).select_from(RelationPact).where(
                RelationPact.universe_id == u
            )):
                break
    t0, arrivals = clock.at, []
    for name, (watcher, protocol, w_units, mover, m_units) in plan.items():
        watched, neighbour = pairs[SCENARIOS.index(name)]
        with sessions.begin() as s:
            watch = place(s, watcher, watched, w_units)
            fleets.set_protocol(
                s, timeline, u, UUID(watcher["empire_id"]), watch, protocol,
                key=f"recipe:13b:{name}:protocol", at=t0,
            )
            moving = place(s, mover, neighbour, m_units)
            mission = fleets.launch(
                s, timeline, u, UUID(mover["empire_id"]), moving, "DEPLOY", watched, m_units,
                None, key=f"recipe:13b:{name}:move", at=t0,
            )
            staged[name] = {
                "watch_fleet_id": str(watch),
                "mover_fleet_id": str(mission.fleet_id),
                "mission_id": str(mission.id),
                "system_id": str(watched),
                "arrival_at": mission.travel_arrival_at.isoformat(),
            }
            arrivals.append(mission.travel_arrival_at)
    # Friendly retreat (success): `bold` comes home by a real move, then watches it; the human
    # attacks its planet from afar. Local attack + impossible retreat: `cautious` watches its own
    # home where it never moved from; a human Fleet already there attacks at 0 hop (the pact is
    # only checked at battle_at, Q18: the retreat at launch happens anyway).
    with sessions.begin() as s:
        friend = place(s, bold, spare, {"interceptor": 1})
        back = fleets.launch(
            s, timeline, u, UUID(bold["empire_id"]), friend, "DEPLOY", homes[2],
            {"interceptor": 1}, None, key="recipe:13b:friend:home", at=t0,
        )
        staged["retreat"] = {"watch_fleet_id": str(friend), "previous": str(spare)}
    settle(sessions, clock, back.travel_arrival_at + timedelta(minutes=2))
    with sessions.begin() as s:
        fleets.set_protocol(
            s, timeline, u, UUID(bold["empire_id"]), friend, "FRIENDLY_CONTACT",
            key="recipe:13b:friend:protocol", at=clock.at,
        )
        stay = place(s, cautious, homes[1], {"interceptor": 1})
        fleets.set_protocol(
            s, timeline, u, UUID(cautious["empire_id"]), stay, "FRIENDLY_CONTACT",
            key="recipe:13b:local:protocol", at=clock.at,
        )
    # C04: a protocol covers only what happens strictly after its start; attack a minute later.
    settle(sessions, clock, clock.at + timedelta(minutes=1))
    with sessions.begin() as s:
        far = place(s, human, spare, {"frigate": 2})  # 1 hop from bold's home
        strike = fleets.launch(
            s, timeline, u, UUID(human["empire_id"]), far, "ATTACK", None, {"frigate": 2}, None,
            key="recipe:13b:friend:attack", at=clock.at,
            target_planet_id=s.get(Colony, UUID(bold["colony_id"])).planet_id,
        )
        staged["retreat"]["attack_id"] = str(strike.id)
        local = place(s, human, homes[1], {"frigate": 1})
        hit = fleets.launch(
            s, timeline, u, UUID(human["empire_id"]), local, "ATTACK", None, {"frigate": 1},
            None, key="recipe:13b:local:attack", at=clock.at,
            target_planet_id=s.get(Colony, UUID(cautious["colony_id"])).planet_id,
        )
        staged["local"] = {
            "watch_fleet_id": str(stay),
            "attack_id": str(hit.id),
            "launched_at": hit.started_at.isoformat(),
        }
    settle(sessions, clock, max(*arrivals, strike.travel_arrival_at) + timedelta(minutes=5))
    # B08: what each AI would choose for a fresh stationed operational Fleet at home (own facts
    # only): `bold` was attacked recently by a known Empire without pact -> AMBUSH; `cautious`
    # never ambushes and is under an announced attack -> SURVEILLANCE.
    with sessions.begin() as s:
        for actor, index in ((cautious, 1), (bold, 2)):
            place(s, actor, homes[index], {"interceptor": 1})
    postures = {}
    with sessions() as s:
        for actor in (cautious, bold):
            c = s.get(AIController, UUID(actor["controller_id"]))
            obs = collect(s, c, authorize(s, c), clock.at)[0]
            postures[actor["profile"]] = {
                "protocols": sorted(
                    x["body"]["protocol"] for x in obs["candidates"] if x["operation"] == "protocol"
                ),
                "postures": obs.get("frontier", []),
            }
    staged["ai_postures"] = postures
    staged["clock"] = clock.at.isoformat()
    with sessions.begin() as s:
        s.get(AIBootstrap, u).result = s.get(AIBootstrap, u).result | {"recipe_13b": staged}
    engine.dispose()
    emit({"staged": sorted(staged)})


def outcomes(s, mission_id):
    return [
        r.outcome
        for r in s.scalars(
            select(FrontierEncounter)
            .where(FrontierEncounter.mission_id == UUID(mission_id))
            .order_by(FrontierEncounter.encounter_at, FrontierEncounter.id)
        )
    ]


def proof(universe_id):
    """Every staged scenario, read back from durable state (internal truth for the recipe)."""
    engine, sessions = frontier_factory()
    u = UUID(universe_id)
    with sessions() as s:
        _, cautious, bold = actors(s, u)
        staged = s.get(AIBootstrap, u).result["recipe_13b"]
        result = {"ruleset": rules_for(s, u).version, "scenarios": {}}
        for name in SCENARIOS:
            row = staged[name]
            mission = s.get(FleetMission, UUID(row["mission_id"]))
            mover = s.get(Fleet, UUID(row["mover_fleet_id"]))
            detections = list(
                s.scalars(
                    select(FrontierDetection).where(
                        FrontierDetection.mission_id == mission.id,
                        FrontierDetection.watch_fleet_id == UUID(row["watch_fleet_id"]),
                    )
                )
            )
            result["scenarios"][name] = {
                "outcomes": outcomes(s, row["mission_id"]),
                "mover_status": mover.status,
                "mover_units": fleets.stacks_of(s, mover.id),
                "mission_status": mission.status,
                "intercepted_report": bool(
                    (report := s.get(FleetReport, mission.id))
                    and report.result.get("kind") == "INTERCEPTED"
                ),
                "detections": sorted(d.role for d in detections),
                "identified": sorted(d.identified for d in detections),
            }
    with sessions.begin() as s:  # what a Relations read does: materialise the introductions
        for actor in (cautious, bold):
            frontier.materialise_introductions(s, u, UUID(actor["empire_id"]), datetime.now(UTC))
    with sessions() as s:
        retreat = s.scalars(
            select(FrontierEncounter).where(
                FrontierEncounter.watch_fleet_id == UUID(staged["retreat"]["watch_fleet_id"]),
                FrontierEncounter.kind == "retreat",
            )
        ).all()
        local = s.scalars(
            select(FrontierEncounter).where(
                FrontierEncounter.watch_fleet_id == UUID(staged["local"]["watch_fleet_id"]),
                FrontierEncounter.kind == "retreat",
            )
        ).all()
        result["retreat"] = {
            "outcomes": [r.outcome for r in retreat],
            "destination_is_previous": [
                (r.result or {}).get("destination_id") == staged["retreat"]["previous"]
                for r in retreat
            ]
            == [True],
        }
        result["local"] = {
            "outcomes": [r.outcome for r in local],
            "at_launch": [r.encounter_at.isoformat() for r in local]
            == [staged["local"]["launched_at"]],
            "passage": [
                (p.direction, p.sequence)
                for p in s.scalars(
                    select(FleetPassage).where(
                        FleetPassage.mission_id == UUID(staged["local"]["attack_id"])
                    )
                )
            ],
        }
        result["ai_postures"] = staged["ai_postures"]
        result["frontier_contacts"] = s.scalar(
            select(func.count())
            .select_from(RelationContact)
            .where(RelationContact.universe_id == u, RelationContact.first_source == "frontier")
        )
        # Nothing due may be left open at the staged instant; later entries (ways back, the
        # retreat still travelling) legitimately wait for their own instant.
        at = datetime.fromisoformat(staged["clock"])
        unresolved = FleetPassage.state.in_(["pending", "blocked"])
        result["open_entries"] = s.scalar(
            select(func.count())
            .select_from(FleetPassage)
            .where(FleetPassage.universe_id == u, unresolved, FleetPassage.entered_at <= at)
        )
        result["future_entries"] = s.scalar(
            select(func.count())
            .select_from(FleetPassage)
            .where(FleetPassage.universe_id == u, unresolved, FleetPassage.entered_at > at)
        )
        result["open_fences"] = s.scalar(
            select(func.count())
            .select_from(StreamFence)
            .where(
                StreamFence.universe_id == u,
                StreamFence.released_at.is_(None),
                StreamFence.owner.like("frontier%"),
                StreamFence.fence_at < at,
            )
        )
    engine.dispose()
    emit(result)


def resume_stage(universe_id):
    """Worker interruption: a real entry made due in the past while both workers are stopped."""
    engine, sessions = frontier_factory()
    u = UUID(universe_id)
    with sessions() as s:
        _, _, bold = actors(s, u)
        staged = s.get(AIBootstrap, u).result["recipe_13b"]
        watched = UUID(staged["detection"]["system_id"])
        neighbour = s.scalar(
            select(GalaxyRoute.b_id).where(GalaxyRoute.universe_id == u, GalaxyRoute.a_id == watched)
        ) or s.scalar(
            select(GalaxyRoute.a_id).where(GalaxyRoute.universe_id == u, GalaxyRoute.b_id == watched)
        )
    at = datetime.now(UTC) - timedelta(hours=2)
    clock = TestClock(datetime.fromisoformat(staged["clock"]))
    settle(sessions, clock, at)  # everything before is settled on the injected clock
    with sessions.begin() as s:
        moving = place(s, bold, neighbour, {"freighter": 1})
        mission = fleets.launch(
            s, TimeEngine(sessions, clock), u, UUID(bold["empire_id"]), moving, "DEPLOY",
            watched, {"freighter": 1}, None, key=f"recipe:13b:resume:{uuid4().hex}", at=at,
        )
        entry = frontier.planned(s, mission)[-1]
        result = {
            "mission_id": str(mission.id),
            "entered_at": entry.entered_at.isoformat(),
            "due_in_past": entry.entered_at < datetime.now(UTC),
        }
    engine.dispose()
    emit(result)


def resume_state(universe_id, mission_id):
    engine, sessions = frontier_factory()
    with sessions() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        entry = s.scalars(
            select(FleetPassage)
            .where(FleetPassage.mission_id == mission.id)
            .order_by(FleetPassage.sequence.desc())
        ).first()
        fleet = s.get(Fleet, mission.fleet_id)
        result = {
            "entry_state": entry.state,
            "detections": s.scalar(
                select(func.count())
                .select_from(FrontierDetection)
                .where(FrontierDetection.mission_id == mission.id)
            ),
            "fleet_status": fleet.status,
            "arrived": fleet.status == "STATIONED" and fleet.system_id == mission.destination_id,
        }
    engine.dispose()
    emit(result)
