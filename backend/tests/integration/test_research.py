"""Research transactions on PostgreSQL, real sessions/control permissions and shared worker."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import func, select
from test_colony_api import colony_in, game, set_access, world  # noqa: F401

from app.access.models import GameSession
from app.colony.rules import load_ruleset
from app.colony.service import enqueue, initialize_colony
from app.persistence.models import Colony, Planet
from app.research import service as r
from app.research.models import AcquiredTechnology, EmpireResearch, ResearchOrder
from app.simulation.models import ResourceBalance, ScheduledEvent
from app.simulation.scheduler import IdempotencyConflict
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
ALL = ["colony.read", "research.read", "research.start", "research.cancel"]


def make(world, permissions=ALL):
    return world(permissions=permissions, rules=load_ruleset("v0.2"))


def start(w, tech="engineering_1", key=None, colony=None):
    with w.game.factory.begin() as s:
        return r.start(
            s,
            TimeEngine(w.game.factory, w.app.state.clock),
            w.universe,
            w.empire,
            colony or w.colony,
            key=key or uuid4().hex,
            technology_id=tech,
            at=w.game.clock(),
        )


def cancel(w, order):
    with w.game.factory.begin() as s:
        return r.cancel(
            s,
            TimeEngine(w.game.factory, w.app.state.clock),
            w.universe,
            w.empire,
            order,
            at=w.game.clock(),
        )


def read(w):
    return w.client.get(
        f"/game/{w.universe}/research/{w.empire}", headers={"X-Game-Request": "bootstrap"}
    )


def send(w, tech="engineering_1", key=None, colony=None, **extra):
    return w.client.post(
        f"/game/{w.universe}/research/{w.empire}/orders",
        headers=w.headers(),
        json={
            "technology_id": tech,
            "colony_id": str(colony or w.colony),
            "idempotency_key": key or uuid4().hex,
            **extra,
        },
    )


def second_colony(w):
    with w.game.factory.begin() as s:
        old = s.get(Colony, w.colony)
        planet = s.get(Planet, old.planet_id)
        new = Planet(
            universe_id=w.universe,
            system_id=planet.system_id,
            name="Second source",
            sector_capacity=12,
            orbital_capacity=2,
        )
        s.add(new)
        s.flush()
        c = Colony(universe_id=w.universe, empire_id=w.empire, planet_id=new.id)
        s.add(c)
        s.flush()
        initialize_colony(s, w.universe, w.empire, c.id, w.game.clock())
        return c.id


def test_paid_queue_frozen_duration_logical_worker_and_no_second_debit(world):
    w = make(world)
    a = start(w, "computation_1")
    b = start(w, "engineering_1")
    assert b.snapshot["duration_us"] == 120_000_000 and b.started_at is None
    stock = w.stock("data")
    w.advance(minutes=3)
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next()  # no HTTP/page needed
    with w.game.factory() as s:
        first, following = s.get(ResearchOrder, a.id), s.get(ResearchOrder, b.id)
        assert first.completed_at == a.due_at == following.started_at
        assert following.due_at - following.started_at == timedelta(seconds=120)
        assert s.scalar(select(func.count()).select_from(AcquiredTechnology)) == 1
    assert w.stock("data") == stock  # no completion/activation debit
    with w.game.factory.begin() as s:
        q = r.quote(s, w.universe, w.empire, "energy_1", w.colony)
        assert q.duration_us == 114_000_000
    w.advance(minutes=3)
    assert engine.process_next()
    assert not engine.process_next()
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(AcquiredTechnology)) == 2


def test_dependency_cascade_two_sources_and_capped_receipt_replay(world):
    w = make(world)
    other = second_colony(w)
    a = start(w)
    b = start(w, "engineering_2", colony=other)
    with w.game.factory.begin() as s:
        for cid in [w.colony, other]:
            for resource in ["alloys", "flux", "data"]:
                bal = s.get(ResourceBalance, (cid, resource))
                bal.stock = bal.capacity - (7 if resource == "data" else 0)
    body = read(w).json()
    preview = body["queue"][0]["cancel"]
    assert preview["also_cancels"] == [str(b.id)] and len(preview["refunds"]) == 2
    assert all(int(x["recoverable"]["data"]) == 7 for x in preview["refunds"])
    receipt = cancel(w, a.id)
    assert receipt.refunded == {"alloys": 0, "flux": 0, "data": 7}
    assert cancel(w, a.id).refunded == receipt.refunded
    with w.game.factory() as s:
        assert s.get(ResearchOrder, b.id).status == "cancelled"
        assert all(
            s.get(ResourceBalance, (other, x)).stock == s.get(ResourceBalance, (other, x)).capacity
            for x in ["alloys", "flux", "data"]
        )


def test_independent_survives_cancel_at_logical_time_and_queued_full_refund(world):
    w = make(world)
    a = start(w)
    b = start(w, "energy_1")
    w.advance(seconds=10)
    cancel(w, a.id)
    with w.game.factory() as s:
        b = s.get(ResearchOrder, b.id)
        assert b.status == "active" and b.started_at == w.game.clock()
    assert cancel(w, b.id).refunded["data"] == 160_000_000
    c = start(w)
    d = start(w, "energy_1")
    assert cancel(w, d.id).refunded["data"] == 200_000_000
    with w.game.factory() as s:
        assert s.get(ResearchOrder, c.id).status == "active"


def test_duplicates_prerequisites_full_and_idempotent_completed(world):
    w = make(world)
    with pytest.raises(r.ResearchError, match="prerequisites"):
        start(w, "engineering_2")
    a = start(w, key="stable")
    assert start(w, key="stable").id == a.id
    with pytest.raises(IdempotencyConflict):
        start(w, "energy_1", key="stable")
    with pytest.raises(r.ResearchError, match="already"):
        start(w)
    start(w, "energy_1")
    with pytest.raises(r.ResearchError, match="full"):
        start(w, "xenoscience_1")
    w.advance(minutes=10)
    assert read(w).status_code == 200
    assert start(w, key="stable").id == a.id
    with pytest.raises(r.ResearchError, match="already"):
        start(w)


def test_colony_effect_replaces_tier_and_existing_construction_stays_paid(world):
    w = make(world)

    def build(key, sector):
        with w.game.factory.begin() as s:
            return enqueue(
                s,
                TimeEngine(w.game.factory, w.app.state.clock),
                w.universe,
                w.empire,
                w.colony,
                key=key,
                kind="data_node",
                sector=sector,
                target_level=1,
                at=w.game.clock(),
            )

    old = build("before", 5)
    start(w)
    w.advance(minutes=3)
    read(w)
    first = build("first", 6)
    assert first.snapshot["quote"]["cost"]["alloys"] == 237_500_000
    assert old.snapshot["quote"]["cost"]["alloys"] == 250_000_000
    # Fund II from another explicit colony; no pooled treasury.
    other = second_colony(w)
    start(w, "engineering_2", colony=other)
    w.advance(minutes=6)
    read(w)
    final = build("second", 7)
    assert final.snapshot["quote"]["cost"]["alloys"] == 225_000_000
    with w.game.factory.begin() as s:
        assert r.bonuses(s, w.empire)["colony_alloys"] == 1000


def test_business_block_preserves_reservation_and_manual_cancel(world, monkeypatch):
    w = make(world)
    a = start(w)
    b = start(w, "engineering_2")
    # Inject a gameplay precondition refusal, without corrupting the persisted definition.
    monkeypatch.setattr(r, "activation_block_reason", lambda *_: "prerequisites_changed")
    w.advance(minutes=3)
    assert read(w).status_code == 200
    with w.game.factory() as s:
        assert s.get(ResearchOrder, a.id).status == "completed"
        assert s.get(ResearchOrder, b.id).status == "blocked"
    assert cancel(w, b.id).refunded["data"] == 400_000_000


@pytest.mark.parametrize("corruption", ["shape", "definition"])
def test_technical_corruption_retries_without_partial_acquisition(world, corruption):
    w = make(world)
    a = start(w)
    b = start(w, "energy_1")
    with w.game.factory.begin() as s:
        row = s.get(ResearchOrder, b.id)
        if corruption == "shape":
            row.snapshot = {"corrupt": True}
        else:
            snapshot = dict(row.snapshot)
            snapshot["technology"] = {**snapshot["technology"], "requires": ["xenoscience_1"]}
            row.snapshot = snapshot
    assert read(w).status_code == 503  # Technical refusal even before the event is due.
    w.advance(minutes=3)
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next()
    with w.game.factory() as s:
        assert s.get(ResearchOrder, a.id).status == "active"
        assert s.scalar(select(func.count()).select_from(AcquiredTechnology)) == 0
        event = s.scalar(
            select(ScheduledEvent).where(ScheduledEvent.event_type == "RESEARCH_COMPLETE")
        )
        assert event.attempts == 1 and event.status == "pending"
    assert read(w).status_code == 503


@pytest.mark.parametrize(
    "permissions,read_status,start_status",
    [
        (["colony.read"], 404, 404),
        (["research.start", "colony.read"], 404, 404),
        (["research.read", "colony.read"], 200, 403),
        (["research.read", "research.start"], 200, 404),
        (["research.read", "research.start", "colony.read"], 200, 200),
    ],
)
def test_permissions_independent_no_construct_needed(world, permissions, read_status, start_status):
    w = make(world, permissions)
    assert read(w).status_code == read_status
    result = send(w)
    assert result.status_code == start_status
    if start_status == 200:
        oid = result.json()["order"]["id"]
        assert (
            w.client.post(
                f"/game/{w.universe}/research/{w.empire}/orders/{oid}/cancel",
                json={},
                headers=w.headers(),
            ).status_code
            == 403
        )


def test_api_strict_scope_csrf_no_read_activity_and_expiry(world):
    w = make(world)
    with w.game.factory() as s:
        before = s.scalar(select(GameSession.last_activity_at))
    w.advance(minutes=1)
    assert read(w).status_code == 200
    with w.game.factory() as s:
        assert s.scalar(select(GameSession.last_activity_at)) == before
    assert send(w, extra=True).status_code == 422
    assert send(w, colony=uuid4()).status_code == 404
    root = f"/game/{w.universe}/research/{w.empire}/orders"
    assert (
        w.client.post(
            root, json={}, headers={"Origin": w.game.settings.game_public_origin}
        ).status_code
        == 403
    )
    assert (
        w.client.get(
            f"/game/{w.universe}/research/{uuid4()}", headers={"X-Game-Request": "bootstrap"}
        ).status_code
        == 404
    )
    w.advance(hours=3)
    assert send(w).status_code == 401


def test_old_ruleset_stays_unavailable(world):
    w = world(permissions=ALL)
    assert read(w).json()["error"]["code"] == "research_unavailable"
    with w.game.factory() as s:
        assert s.get(EmpireResearch, w.empire) is None


def test_simultaneous_participants_one_key_one_debit_and_queue_limit(world):
    w = make(world)
    start(w)
    barrier = Barrier(2)

    def submit(tech):
        barrier.wait()
        try:
            return start(w, tech).status
        except r.ResearchError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, ["energy_1", "xenoscience_1"]))
    assert sorted(results) == ["queue_full", "queued"]
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(ResearchOrder)) == 2


def test_migration_head_matches_metadata_and_populated_downgrade_refused(world, migration_config):
    w = make(world)
    start(w)
    command.check(migration_config)
    with pytest.raises(RuntimeError, match="populated Research"):
        command.downgrade(migration_config, "0006_game_sessions")
    command.upgrade(migration_config, "head")


def test_same_key_concurrent_acceptance_is_one_debit(world):
    w = make(world)
    barrier = Barrier(2)

    def submit(_):
        barrier.wait()
        return start(w, key="simultaneous").id

    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    assert w.stock("data") == 550_000_000


def test_research_and_colony_concurrent_spending_share_one_locked_balance(world):
    w = make(world)
    with w.game.factory.begin() as s:
        s.get(ResourceBalance, (w.colony, "alloys")).stock = 250_000_000
    barrier = Barrier(2)

    def submit(kind):
        barrier.wait()
        try:
            if kind == "research":
                start(w)
            else:
                with w.game.factory.begin() as s:
                    enqueue(
                        s,
                        TimeEngine(w.game.factory, w.app.state.clock),
                        w.universe,
                        w.empire,
                        w.colony,
                        key="race",
                        kind="data_node",
                        sector=5,
                        target_level=1,
                        at=w.game.clock(),
                    )
            return "accepted"
        except r.ColonyError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, ["research", "colony"]))
    assert sorted(results) == ["accepted", "insufficient_resources"]
    assert w.stock("alloys") in (0, 150_000_000)


def test_new_research_cost_only_receives_acquired_xenoscience_and_queue_never_reprices(world):
    w = make(world)
    other = second_colony(w)
    a = start(w, "xenoscience_1")
    b = start(w, "energy_1", colony=other)
    assert b.snapshot["cost"]["data"] == 200_000_000
    w.advance(seconds=120)
    assert read(w).status_code == 200
    with w.game.factory() as s:
        assert s.get(ResearchOrder, a.id).status == "completed"
        assert s.get(ResearchOrder, b.id).snapshot["cost"]["data"] == 200_000_000
    new = start(w, "engineering_1")
    assert new.snapshot["cost"]["data"] == 190_000_000


def test_two_workers_acquire_exactly_once_and_deadline_cancel_refused(world):
    w = make(world)
    a = start(w)
    w.advance(seconds=120)
    barrier = Barrier(2)

    def worker(_):
        barrier.wait()
        return TimeEngine(w.game.factory, w.app.state.clock).process_next()

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(worker, range(2)))
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(AcquiredTechnology)) == 1
        assert s.get(ResearchOrder, a.id).completed_at == a.due_at
    with pytest.raises(r.ResearchError, match="Completed"):
        cancel(w, a.id)


def test_two_shared_participants_observe_same_queue_and_distinct_http_keys(world):
    from test_colony_api import enter

    from app.access.http import cookie_name

    w = make(world)
    participant, membership = uuid4(), uuid4()
    set_access(
        w.game,
        participant,
        w.universe,
        membership,
        [{"empire_id": str(w.empire), "permissions": ALL}],
    )
    raw, _, _ = enter(w.game, (participant, w.universe, membership))
    response = send(w, key="shared_intention")
    assert response.status_code == 200
    w.client.cookies.set(cookie_name(w.universe), raw)
    w.raw = raw  # CSRF belongs to the newly selected participant session.
    assert len(read(w).json()["queue"]) == 1
    response = send(w, key="shared_intention", tech="energy_1")
    # New participant's identically named intention is not another participant's replay.
    assert response.status_code == 200 and response.json()["order"]["status"] == "queued"


def test_cascade_same_source_allocates_capacity_only_once(world):
    w = make(world)
    a = start(w)
    b = start(w, "engineering_2")
    with w.game.factory.begin() as s:
        bal = s.get(ResourceBalance, (w.colony, "data"))
        bal.stock = bal.capacity - 200_000_000
    receipt = cancel(w, a.id)
    assert receipt.refunded["data"] == 160_000_000
    with w.game.factory() as s:
        assert s.get(ResearchOrder, b.id).refunded["data"] == 40_000_000
        bal = s.get(ResourceBalance, (w.colony, "data"))
        assert bal.stock == bal.capacity
    assert cancel(w, a.id).refunded["data"] == 160_000_000


def test_foreign_financing_refused_by_service_api_and_database(world):
    from sqlalchemy.exc import IntegrityError

    w = make(world)
    foreign = world(permissions=ALL, rules=load_ruleset("v0.2"), universe=w.universe)
    assert send(w, colony=foreign.colony).status_code == 404
    with pytest.raises(r.ColonyError, match="Colony unavailable"):
        start(w, colony=foreign.colony)
    row = start(w)
    with pytest.raises(IntegrityError), w.game.factory.begin() as s:
        s.get(ResearchOrder, row.id).colony_id = foreign.colony
        s.flush()


def test_downgrade_refuses_research_grants_even_without_domain_rows(world, migration_config):
    make(world)
    with pytest.raises(RuntimeError, match="live Research grants"):
        command.downgrade(migration_config, "0006_game_sessions")
    command.upgrade(migration_config, "head")
