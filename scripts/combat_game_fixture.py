"""Test-only helpers for the disposable Combat recipe; refused outside its *_test Game DB.

The universe is provisioned by Portal and started by the real operator CLI with the unchanged
v0.7 ruleset (one human, one AI). After that start this module never writes gameplay state
directly: `drive` advances an injected test clock through the real TimeEngine and AI
Orchestrator, and plays the human only through the Fleet service (production, SURVEY, ATTACK).
The recipe driver may read world truth to choose which system to survey next; Knowledge itself
comes from real SURVEY missions only. Combat is left to the real combat-worker processes.
"""

import json
from collections import deque
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.ai.models import AIBootstrap
from app.ai.orchestrator import Orchestrator
from app.colony.service import ColonyError
from app.combat.models import CombatEngagement, CombatReport
from app.combat.resolver import resolve
from app.combat.service import alerts_for
from app.control.models import EmpireBinding, GamePrincipal
from app.core.config import Settings
from app.fleet import service as fleets
from app.fleet.models import Fleet, FleetMission, FleetReport, ShipOrder
from app.galaxy.models import GalaxyRoute, PlanetKnowledge, SystemKnowledge
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Planet
from app.simulation.models import ResourceBalance, StreamFence
from app.simulation.service import TimeEngine
from sqlalchemy import func, select, text

DATABASE = "echosphere_combat_game_test"
STRIKES = ({"frigate": 4}, {"interceptor": 4})


def factory():
    settings = Settings()
    assert settings.postgres_db == DATABASE, "Combat fixture is restricted to its test DB"
    engine = create_database_engine(settings)
    return engine, create_session_factory(engine)


class TestClock:
    def __init__(self, at):
        self.at = at

    def now(self):
        return self.at


def actors(session, universe_id):
    return session.get(AIBootstrap, universe_id).result["actors"]


def path(session, universe_id, origin, target):
    """World-truth shortest route, used only to pick the next system to survey."""
    edges = {}
    for r in session.scalars(select(GalaxyRoute).where(GalaxyRoute.universe_id == universe_id)):
        edges.setdefault(r.a_id, []).append(r.b_id)
        edges.setdefault(r.b_id, []).append(r.a_id)
    previous, queue = {origin: None}, deque([origin])
    while queue:
        node = queue.popleft()
        for nxt in sorted(edges.get(node, []), key=str):
            if nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    route, node = [], target
    while node is not None:
        route.append(node)
        node = previous[node]
    return list(reversed(route))


def stocks(session, colony_id):
    return {
        r: session.get(ResourceBalance, (colony_id, r)).stock for r in ("alloys", "flux", "data")
    }


def drive(universe_id, hours):
    engine, sessions = factory()
    universe_id = UUID(universe_id)
    with sessions() as s:
        bootstrap = s.get(AIBootstrap, universe_id).result
        human, ai = bootstrap["actors"][0], bootstrap["actors"][1]
        h, hc = UUID(human["empire_id"]), UUID(human["colony_id"])
        target = s.get(Colony, UUID(ai["colony_id"])).planet_id
        target_system = s.get(Planet, target).system_id
        home = s.get(Planet, s.get(Colony, hc).planet_id).system_id
        route = path(s, universe_id, home, target_system)
    started = datetime.fromisoformat(bootstrap["started_at"])
    end = min(started + timedelta(hours=hours), datetime.now(UTC) - timedelta(seconds=600))
    clock = TestClock(started)
    processor, runner = TimeEngine(sessions, clock), Orchestrator(sessions, clock)
    log, launched, step = [], None, 0

    def act(label, call):
        try:
            with sessions.begin() as s:
                result = call(s)
            log.append([clock.at.isoformat(), label])
            return result
        except ColonyError as error:
            if label.startswith("attack"):
                log.append([clock.at.isoformat(), label, error.code])
            return None

    while clock.at + timedelta(seconds=600) <= end:
        clock.at += timedelta(seconds=600)
        step += 1
        while processor.process_next() is not None:
            pass
        runner.process_next(controller_id=UUID(ai["controller_id"]))
        if launched:
            continue
        with sessions() as s:
            garrison = s.scalar(
                select(Fleet).where(Fleet.home_colony_id == hc, Fleet.kind == "GARRISON")
            )
            held = fleets.stacks_of(s, garrison.id) if garrison else {}
            ordered = {
                o.ship_class for o in s.scalars(select(ShipOrder).where(ShipOrder.empire_id == h))
            }
            known = s.get(PlanetKnowledge, (h, target)) is not None
            probes = list(
                s.scalars(
                    select(Fleet)
                    .where(Fleet.empire_id == h, Fleet.status == "STATIONED")
                    .order_by(Fleet.created_at, Fleet.id)
                )
            )
            probes = [(f.id, f.system_id) for f in probes if fleets.stacks_of(s, f.id).get("probe")]
            mapped = {
                k.system_id
                for k in s.scalars(select(SystemKnowledge).where(SystemKnowledge.empire_id == h))
                if k.state != "DETECTED"
            }
            surveying = s.scalar(
                select(func.count()).where(
                    FleetMission.empire_id == h,
                    FleetMission.kind == "SURVEY",
                    FleetMission.status == "active",
                )
            )
        # Production through the common service, retried while funds are short.
        for ship, quantity in (("probe", 1), ("frigate", 4), ("interceptor", 4)):
            if ship not in ordered:
                act(
                    f"order {quantity} {ship}",
                    lambda s, ship=ship, quantity=quantity: fleets.order_ships(
                        s,
                        processor,
                        universe_id,
                        h,
                        hc,
                        ship,
                        quantity,
                        key=f"recipe-order-{ship}",
                        at=clock.at,
                    ),
                )
        # SURVEY step by step along the world-truth route; Knowledge only from the missions.
        if not known and probes and not surveying:
            fleet_id, where = probes[0]
            nxt = next((sys for sys in route if sys not in mapped), None)
            if nxt is not None:
                act(
                    "survey",
                    lambda s, fleet_id=fleet_id, nxt=nxt: fleets.launch(
                        s,
                        processor,
                        universe_id,
                        h,
                        fleet_id,
                        "SURVEY",
                        nxt,
                        {"probe": 1},
                        None,
                        key=f"recipe-survey-{nxt}",
                        at=clock.at,
                    ),
                )
        ready = held.get("frigate", 0) >= 4 and held.get("interceptor", 0) >= 4
        affordable = False
        if known and ready:
            # Both round trips paid at one instant: wait for real production to cover the quotes.
            with sessions() as s:
                quotes = [
                    fleets.preview(
                        s,
                        universe_id,
                        h,
                        garrison.id,
                        "ATTACK",
                        None,
                        units,
                        clock.at,
                        target,
                        True,
                    )
                    for units in STRIKES
                ]
                funds = fleets.estimated_balances(s, hc, clock.at)
                affordable = all(
                    funds[r].stock >= sum(q["cost"][r] for q in quotes)
                    for r in ("alloys", "flux", "data")
                )
        if known and ready and affordable and clock.at + timedelta(hours=28) <= end:
            # Two attacks at one frozen instant on the same world: equal battle_at, rank by id.
            missions = []
            for i, units in enumerate(STRIKES):
                mission = act(
                    f"attack {units}",
                    lambda s, units=units, i=i, source=garrison.id: fleets.launch(
                        s,
                        processor,
                        universe_id,
                        h,
                        source,
                        "ATTACK",
                        None,
                        units,
                        None,
                        key=f"recipe-attack-{i}",
                        at=clock.at,
                        target_planet_id=target,
                    ),
                )
                missions.append(str(mission.id) if mission else None)
            assert all(missions), log
            launched = {"at": clock.at.isoformat(), "missions": missions}
    engine.dispose()
    print(
        json.dumps(
            {
                "steps": step,
                "virtual_end": clock.at.isoformat(),
                "launched": launched,
                "log": log[-12:],
                "route_hops": len(route) - 1,
            }
        )
    )


def proof(universe_id):
    engine, sessions = factory()
    universe_id = UUID(universe_id)
    with sessions() as s:
        bootstrap = s.get(AIBootstrap, universe_id).result
        human, ai = bootstrap["actors"][0], bootstrap["actors"][1]
        h, a = UUID(human["empire_id"]), UUID(ai["empire_id"])
        engagements = []
        for e in s.scalars(
            select(CombatEngagement)
            .where(CombatEngagement.universe_id == universe_id)
            .order_by(CombatEngagement.battle_at, CombatEngagement.started_at, CombatEngagement.id)
        ):
            mission = s.get(FleetMission, e.mission_id)
            fleet = s.get(Fleet, mission.fleet_id)
            row = {
                "id": str(e.id),
                "state": e.state,
                "battle_at": e.battle_at.isoformat(),
                "started_at": e.started_at.isoformat(),
                "defender_bound": e.defender_empire_id == a,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
                "mission_status": mission.status,
                "fleet_status": fleet.status,
                "fleet_system_is_origin": fleet.system_id == mission.origin_id,
                "fleet_report": (r.result if (r := s.get(FleetReport, mission.id)) else None),
                "reports": sorted(
                    r.role
                    for r in s.scalars(
                        select(CombatReport).where(CombatReport.engagement_id == e.id)
                    )
                ),
            }
            if e.state == "resolved":
                row["outcome"] = e.result["outcome"]
                row["defender_force"] = {
                    c: sum(u.get(c, 0) for u in e.snapshot["defender"]["fleets"].values())
                    for c in ("interceptor", "frigate", "cruiser")
                }
                row["defender_losses"] = (
                    e.result["combat"]["losses"]["defender"] if e.result["combat"] else None
                )
                row["replay_exact"] = (
                    resolve(e.snapshot["spec"]) == e.result["combat"]
                    if e.snapshot["spec"]
                    else None
                )
            engagements.append(row)
        launch_at = min((e["started_at"] for e in engagements), default=None)
        result = {
            "now": datetime.now(UTC).isoformat(),
            "engagements": engagements,
            "open_fences": s.scalar(select(func.count()).where(StreamFence.released_at.is_(None))),
            "ai_alerts": [
                {k: v for k, v in x.items() if k in ("planet_id", "battle_at", "state")}
                for x in alerts_for(s, universe_id, a)
            ],
            "ai_interceptor_orders_after_alert": s.scalar(
                select(func.count()).where(
                    ShipOrder.empire_id == a,
                    ShipOrder.ship_class == "interceptor",
                    ShipOrder.accepted_at >= datetime.fromisoformat(launch_at),
                    ShipOrder.idempotency_key.like(f"ai:{ai['controller_id']}:%"),
                )
            )
            if launch_at
            else 0,
            "ai_interceptors_held_before_alert": s.scalar(
                select(func.coalesce(func.sum(ShipOrder.quantity), 0)).where(
                    ShipOrder.empire_id == a,
                    ShipOrder.ship_class == "interceptor",
                    ShipOrder.status == "completed",
                    ShipOrder.due_at <= datetime.fromisoformat(launch_at),
                )
            )
            if launch_at
            else 0,
            "ai_attacks": s.scalar(
                select(func.count()).where(
                    FleetMission.empire_id == a, FleetMission.kind == "ATTACK"
                )
            ),
            "ai_colony": {
                "stocks": stocks(s, UUID(ai["colony_id"])),
                "buildings": s.scalar(
                    text("SELECT count(*) FROM colony_infrastructures WHERE colony_id = :c"),
                    {"c": ai["colony_id"]},
                ),
            },
            "principals": s.scalar(select(func.count()).select_from(GamePrincipal)),
            "bound_empires": sorted(str(x) for x in s.scalars(select(EmpireBinding.empire_id))),
            "human_empire": str(h),
            "human_colony": human["colony_id"],
        }
    engine.dispose()
    print(json.dumps(result))


def colony_snapshot(universe_id):
    """AI colony state frozen before the battle: Combat must never touch it."""
    engine, sessions = factory()
    with sessions() as s:
        ai = actors(s, UUID(universe_id))[1]
        rows = s.execute(
            text(
                "SELECT sector_index, infrastructure_type, level FROM colony_infrastructures "
                "WHERE colony_id = :c ORDER BY sector_index"
            ),
            {"c": ai["colony_id"]},
        ).all()
        research = s.execute(
            text("SELECT technology_id FROM acquired_technologies WHERE empire_id = :e ORDER BY 1"),
            {"e": ai["empire_id"]},
        ).all()
    engine.dispose()
    print(json.dumps({"buildings": [list(r) for r in rows], "research": [r[0] for r in research]}))


def expire(universe_id):
    """Simulates reaching the absolute deadline: moves it just after the last activity."""
    engine, sessions = factory()
    with sessions.begin() as s:
        count = s.execute(
            text(
                "UPDATE game_sessions SET expires_at = last_activity_at + interval '1 millisecond' "
                "WHERE universe_id = :universe AND revoked_at IS NULL"
            ),
            {"universe": universe_id},
        ).rowcount
    engine.dispose()
    assert count == 1, "Exactly one live recipe session expected"
    print(json.dumps({"expired": count}))


def provisioned(universe_id):
    import time

    from app.persistence.models import Universe

    engine, sessions = factory()
    for _ in range(60):
        with sessions() as s:
            universe = s.get(Universe, UUID(universe_id))
            if universe is not None:
                break
        time.sleep(0.5)
    else:
        raise RuntimeError("Universe was not provisioned through the control plane")
    engine.dispose()
    print(json.dumps({"name": universe.name, "seed": universe.seed}))
