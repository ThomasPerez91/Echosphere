from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from sqlalchemy import delete, select

from app.persistence.database import create_session_factory
from app.persistence.models import Colony, Empire, Planet, StellarSystem, Universe
from app.simulation.models import ColonyTimeline, ResourceBalance, ScheduledEvent
from app.simulation.production import RESOURCES, ProductionState
from app.simulation.service import (
    IdempotencyConflict,
    TimeEngine,
    TimelineError,
    change_rate,
    initialize,
    retry_blocked,
    schedule,
)

pytestmark = pytest.mark.integration
START = datetime(2026, 1, 1, tzinfo=UTC)
HOUR = START + timedelta(hours=1)


@dataclass
class Clock:
    value: datetime = HOUR

    def now(self):
        return self.value


@pytest.fixture
def simulation(database_engine):
    factory = create_session_factory(database_engine)
    created = []

    def make_colony():
        with factory.begin() as session:
            universe = Universe(name="Time test", seed="test-vector")
            session.add(universe)
            session.flush()
            empire = Empire(universe_id=universe.id, name="Test", controller_type="human")
            system = StellarSystem(universe_id=universe.id, name="Test")
            session.add_all([empire, system])
            session.flush()
            planet = Planet(
                universe_id=universe.id,
                system_id=system.id,
                name="Test",
                sector_capacity=12,
                orbital_capacity=2,
            )
            session.add(planet)
            session.flush()
            colony = Colony(universe_id=universe.id, empire_id=empire.id, planet_id=planet.id)
            session.add(colony)
            session.flush()
            initialize(
                session,
                colony.id,
                {resource: ProductionState(0, 1_000_000, START) for resource in RESOURCES},
            )
            created.append((colony.id, planet.id, system.id, empire.id, universe.id))
            return colony.id

    yield factory, Clock(), make_colony
    with factory.begin() as session:
        for colony, planet, system, empire, universe in reversed(created):
            for model in [ScheduledEvent, ResourceBalance, ColonyTimeline]:
                session.execute(delete(model).where(model.colony_id == colony))
            for model, identity in [
                (Colony, colony),
                (Planet, planet),
                (StellarSystem, system),
                (Empire, empire),
                (Universe, universe),
            ]:
                session.execute(delete(model).where(model.id == identity))


def enqueue(
    factory,
    colony,
    key="rate",
    *,
    at=START + timedelta(minutes=30),
    rate=2_000_000,
    kind="RESOURCE_RATE_CHANGE",
):
    with factory.begin() as session:
        event = schedule(
            session,
            colony,
            key=key,
            kind=kind,
            due_at=at,
            payload={"resource": "alloys", "rate_per_hour": rate},
        )
        return event.id


def test_late_processing_uses_logical_event_time_not_poll_time(simulation):
    factory, clock, make = simulation
    colony = make()
    enqueue(factory, colony)
    engine = TimeEngine(factory, clock)
    with factory.begin() as session:
        assert engine.catch_up(session, colony, HOUR).complete
        alloys = session.get(ResourceBalance, (colony, "alloys"))
        data = session.get(ResourceBalance, (colony, "data"))
        assert alloys.stock == 1_500_000
        assert data.stock == 1_000_000
        assert alloys.updated_at == HOUR


def test_idempotency_replays_before_and_after_completion_and_rejects_conflicts(simulation):
    factory, clock, make = simulation
    colony = make()
    identity = enqueue(factory, colony)
    assert enqueue(factory, colony) == identity
    assert TimeEngine(factory, clock).process_next().status == "completed"
    assert enqueue(factory, colony) == identity
    assert TimeEngine(factory, clock).process_next() is None
    with pytest.raises(IdempotencyConflict):
        enqueue(factory, colony, rate=3_000_000)
    with factory() as session:
        assert session.get(ColonyTimeline, colony).next_sequence == 2
        assert session.get(ScheduledEvent, identity).attempts == 1


def test_followups_at_same_instant_have_stable_sequence(simulation):
    factory, clock, make = simulation
    colony = make()
    enqueue(factory, colony, "parent", kind="PARENT")
    enqueue(factory, colony, "already-queued", rate=3_000_000)

    def parent(session, event):
        schedule(
            session,
            event.colony_id,
            key="child",
            kind="RESOURCE_RATE_CHANGE",
            due_at=event.due_at,
            payload={"resource": "alloys", "rate_per_hour": 4_000_000},
        )

    engine = TimeEngine(
        factory, clock, handlers={"PARENT": parent, "RESOURCE_RATE_CHANGE": change_rate}
    )
    with factory.begin() as session:
        assert engine.catch_up(session, colony, HOUR).processed == 3
        assert session.get(ResourceBalance, (colony, "alloys")).stock == 2_500_000
        rows = session.scalars(
            select(ScheduledEvent)
            .where(ScheduledEvent.colony_id == colony)
            .order_by(ScheduledEvent.sequence)
        ).all()
        assert [row.idempotency_key for row in rows] == ["parent", "already-queued", "child"]


def test_failed_handler_rolls_back_resources_and_children_before_retry(simulation):
    factory, clock, make = simulation
    colony = make()
    identity = enqueue(factory, colony, kind="BROKEN")

    def broken(session, event):
        session.get(ResourceBalance, (colony, "alloys")).stock = 999
        schedule(
            session,
            colony,
            key="must-rollback",
            kind="RESOURCE_RATE_CHANGE",
            due_at=event.due_at,
            payload={},
        )
        raise RuntimeError("Sensitive handler details must not be persisted")

    engine = TimeEngine(factory, clock, handlers={"BROKEN": broken}, max_attempts=2)
    assert engine.process_next().status == "pending"
    assert engine.process_next() is None  # Backoff, no repeated spin.
    with factory() as session:
        assert session.get(ResourceBalance, (colony, "alloys")).stock == 0
        timeline = session.get(ColonyTimeline, colony)
        assert timeline.settled_at == START and timeline.next_sequence == 2
        assert session.get(ScheduledEvent, identity).error_code == "handler_failed"
        assert (
            session.scalars(select(ScheduledEvent).where(ScheduledEvent.colony_id == colony))
            .all()
            .__len__()
            == 1
        )
    clock.value += timedelta(seconds=30)
    assert engine.process_next().status == "blocked"


def test_blocked_head_gates_later_events_until_explicit_repair(simulation):
    factory, clock, make = simulation
    colony = make()
    identity = enqueue(factory, colony, "unknown", kind="NEW_VERSION")
    enqueue(factory, colony, "later", at=START + timedelta(minutes=45), rate=3_000_000)
    engine = TimeEngine(factory, clock, max_attempts=1)
    assert engine.process_next().status == "blocked"
    assert engine.process_next() is None
    with factory.begin() as session:
        assert not engine.catch_up(session, colony, HOUR).complete
        assert session.get(ColonyTimeline, colony).settled_at == START
        retry_blocked(session, identity, clock.now())
    repaired = TimeEngine(
        factory, clock, handlers={"NEW_VERSION": change_rate, "RESOURCE_RATE_CHANGE": change_rate}
    )
    with factory.begin() as session:
        assert repaired.catch_up(session, colony, HOUR).complete
        assert session.get(ResourceBalance, (colony, "alloys")).stock == 1_750_000


class ProcessCrash(BaseException):
    pass


def test_crash_before_commit_replays_and_after_commit_does_not_duplicate(simulation):
    factory, clock, make = simulation
    colony = make()
    identity = enqueue(factory, colony)

    def crash(session, event):
        change_rate(session, event)
        session.flush()
        raise ProcessCrash()

    engine = TimeEngine(factory, clock, handlers={"RESOURCE_RATE_CHANGE": crash})
    with pytest.raises(ProcessCrash):
        engine.process_next()
    with factory() as session:
        assert session.get(ScheduledEvent, identity).attempts == 0
        assert session.get(ColonyTimeline, colony).settled_at == START
    restarted = TimeEngine(factory, clock)
    assert restarted.process_next().status == "completed"
    # Recreate the processor after the commit to model process loss after acknowledgement.
    assert TimeEngine(factory, clock).process_next() is None
    with factory() as session:
        assert session.get(ScheduledEvent, identity).attempts == 1
        assert session.get(ResourceBalance, (colony, "alloys")).stock == 500_000


def test_bounded_catchup_never_projects_past_unprocessed_event(simulation):
    factory, clock, make = simulation
    colony = make()
    enqueue(factory, colony, "one", at=START + timedelta(minutes=1))
    enqueue(factory, colony, "two", at=START + timedelta(minutes=2), rate=3_000_000)
    engine = TimeEngine(factory, clock)
    with factory.begin() as session:
        result = engine.catch_up(session, colony, HOUR, limit=1)
        assert not result.complete and result.processed == 1
        assert session.get(ColonyTimeline, colony).settled_at == START + timedelta(minutes=1)
    with factory.begin() as session:
        assert engine.catch_up(session, colony, HOUR).complete
        assert session.get(ResourceBalance, (colony, "alloys")).stock == 2_950_000


def test_future_event_is_not_executed_early_and_backdated_schedule_rejected(simulation):
    factory, clock, make = simulation
    colony = make()
    enqueue(factory, colony, at=HOUR + timedelta(hours=1))
    engine = TimeEngine(factory, clock)
    assert engine.process_next() is None
    with factory.begin() as session:
        assert engine.catch_up(session, colony, HOUR).complete
    with pytest.raises(TimelineError, match="before"):
        enqueue(factory, colony, "past", at=START)
    with factory.begin() as session, pytest.raises(TimelineError, match="future"):
        engine.catch_up(session, colony, HOUR + timedelta(seconds=1))


def test_two_workers_cannot_execute_successors_while_same_colony_locked(simulation):
    factory, clock, make = simulation
    colony = make()
    enqueue(factory, colony, "hold", kind="HOLD")
    enqueue(factory, colony, "next", rate=3_000_000)
    entered, release = Event(), Event()

    def hold(session, event):
        entered.set()
        assert release.wait(5), "Test coordinator did not release the handler"

    first = TimeEngine(factory, clock, handlers={"HOLD": hold})
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first.process_next)
        try:
            assert entered.wait(5)
            assert TimeEngine(factory, clock).process_next() is None
        finally:
            release.set()
        assert future.result(timeout=10).status == "completed"
    assert TimeEngine(factory, clock).process_next().status == "completed"
    with factory() as session:
        rows = session.scalars(
            select(ScheduledEvent).where(ScheduledEvent.colony_id == colony)
        ).all()
        assert [event.attempts for event in rows] == [1, 1]


def test_other_colonies_progress_while_one_is_locked(simulation):
    factory, clock, make = simulation
    first_colony, other_colony = make(), make()
    enqueue(factory, first_colony, "hold", kind="HOLD", at=START)
    other = enqueue(factory, other_colony, at=START + timedelta(minutes=1))
    entered, release = Event(), Event()

    def hold(session, event):
        entered.set()
        assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(TimeEngine(factory, clock, handlers={"HOLD": hold}).process_next)
        try:
            assert entered.wait(5)
            assert TimeEngine(factory, clock).process_next().event_id == other
        finally:
            release.set()
        assert future.result(timeout=10).status == "completed"


@pytest.mark.parametrize("bad_rate", [-1, 1.5, True])
def test_invalid_rate_event_cannot_mutate_resource_state(simulation, bad_rate):
    factory, clock, make = simulation
    colony = make()
    enqueue(factory, colony, rate=bad_rate)
    assert TimeEngine(factory, clock, max_attempts=1).process_next().status == "blocked"
    with factory() as session:
        row = session.get(ResourceBalance, (colony, "alloys"))
        assert row.stock == 0 and row.rate_per_hour == 1_000_000
        assert session.get(ColonyTimeline, colony).settled_at == START
