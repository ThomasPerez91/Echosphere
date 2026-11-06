from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_colony_api import ALL, Clock, game, world  # noqa: F401

from app.access.models import GameSession
from app.colony.models import ConstructionOrder
from app.simulation.models import ScheduledEvent
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration


def history(w, colony=None, query=""):
    return w.client.get(
        f"{w.root}/{colony or w.colony}/construction-history{query}",
        headers={"X-Game-Request": "bootstrap"},
    )


def test_completed_facts_keep_logical_dates_without_catchup_or_activity(world):  # noqa: F811
    w = world()
    order = w.build(kind="data_node").json()["order"]
    due_at = w.read().json()["queue"][0]["due_at"]
    with w.game.factory() as session:
        activity = session.scalar(select(GameSession.last_activity_at))
        event_count = session.scalar(select(func.count()).select_from(ScheduledEvent))
    w.advance(minutes=20)
    # A history read cannot settle an overdue construction itself.
    assert history(w).json()["entries"] == []
    engine = TimeEngine(w.game.factory, Clock(w.game))
    while engine.process_next():
        pass
    entry = history(w).json()["entries"]
    assert entry == [
        {
            "id": order["id"],
            "sequence": "1",
            "infrastructure_type": "data_node",
            "sector_index": 5,
            "target_level": 1,
            "completed_at": due_at,
        }
    ]
    assert history(w).json()["entries"] == entry
    with w.game.factory() as session:
        assert session.scalar(select(GameSession.last_activity_at)) == activity
        assert session.scalar(select(func.count()).select_from(ScheduledEvent)) == event_count


@pytest.mark.parametrize("case", ["other_empire", "other_universe", "unknown", "no_read"])
def test_history_does_not_reveal_unreadable_colonies(world, case):  # noqa: F811
    w = world(permissions=["colony.construct"] if case == "no_read" else ALL)
    target = w.colony
    if case == "other_empire":
        target = world(universe=w.universe).colony
    elif case == "other_universe":
        target = world().colony
    elif case == "unknown":
        target = uuid4()
    assert history(w, target).status_code == 404


def test_bounded_cursor_has_no_overlap_and_never_serializes_snapshot(world):  # noqa: F811
    w = world()
    w.build(kind="data_node")
    with w.game.factory.begin() as session:
        original = session.scalar(
            select(ConstructionOrder).where(ConstructionOrder.colony_id == w.colony)
        )
        # Synthetic historical rows test the read contract, not economic progression.
        for sequence in range(2, 56):
            instant = w.game.clock() - timedelta(days=1)
            session.add(
                ConstructionOrder(
                    colony_id=w.colony,
                    universe_id=w.universe,
                    sequence=sequence,
                    idempotency_key=uuid4().hex,
                    infrastructure_type="data_node",
                    sector_index=5,
                    target_level=sequence,
                    status="completed",
                    snapshot=original.snapshot,
                    started_at=instant,
                    due_at=instant,
                    completed_at=instant,
                )
            )
    first = history(w).json()
    assert len(first["entries"]) == 50 and first["next_before_sequence"] == "6"
    second = history(w, query="?before_sequence=6").json()
    assert [e["sequence"] for e in second["entries"]] == ["5", "4", "3", "2"]
    assert second["next_before_sequence"] is None
    assert not ({e["id"] for e in first["entries"]} & {e["id"] for e in second["entries"]})
    assert all("snapshot" not in e and "idempotency_key" not in e for e in first["entries"])
    for invalid in ("0", "-1", "9223372036854775808", "oops"):
        assert history(w, query=f"?before_sequence={invalid}").status_code == 422


def test_history_preserves_bootstrap_origin_and_strict_query_envelope(world):  # noqa: F811
    w = world()
    url = f"{w.root}/{w.colony}/construction-history"
    assert w.client.get(url).status_code == 403
    assert w.client.get(url, headers={
        "X-Game-Request": "bootstrap", "Origin": "https://foreign.example",
    }).status_code == 403
    for query in ("?unknown=1", "?before_sequence=1&before_sequence=2"):
        assert history(w, query=query).status_code == 422
    w.client.cookies.clear()
    assert history(w).status_code == 401
