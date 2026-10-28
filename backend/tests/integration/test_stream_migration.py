"""Exercise populated 0002 -> 0003 -> 0002 -> 0003, not only empty DDL."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command

pytestmark = pytest.mark.integration


def test_populated_stream_migration_preserves_history_and_economy(
    database_engine, migration_config
):
    anchor = datetime(2026, 1, 1, tzinfo=UTC)
    ids = {name: uuid4() for name in ["universe", "empire", "system", "planet", "colony", "event"]}
    command.downgrade(migration_config, "0002_colony_time")
    legacy = sa.MetaData()
    legacy.reflect(bind=database_engine)
    try:
        with database_engine.begin() as connection:
            connection.execute(
                legacy.tables["universes"]
                .insert()
                .values(id=ids["universe"], name="Migration fixture", seed="legacy")
            )
            connection.execute(
                legacy.tables["empires"]
                .insert()
                .values(
                    id=ids["empire"],
                    universe_id=ids["universe"],
                    name="Legacy",
                    controller_type="human",
                )
            )
            connection.execute(
                legacy.tables["stellar_systems"]
                .insert()
                .values(id=ids["system"], universe_id=ids["universe"], name="Legacy")
            )
            connection.execute(
                legacy.tables["planets"]
                .insert()
                .values(
                    id=ids["planet"],
                    universe_id=ids["universe"],
                    system_id=ids["system"],
                    name="Legacy",
                    sector_capacity=12,
                    orbital_capacity=2,
                )
            )
            connection.execute(
                legacy.tables["colonies"]
                .insert()
                .values(
                    id=ids["colony"],
                    universe_id=ids["universe"],
                    empire_id=ids["empire"],
                    planet_id=ids["planet"],
                )
            )
            connection.execute(
                legacy.tables["colony_timelines"]
                .insert()
                .values(colony_id=ids["colony"], settled_at=anchor, next_sequence=7)
            )
            for resource in ["alloys", "flux", "data"]:
                connection.execute(
                    legacy.tables["resource_balances"]
                    .insert()
                    .values(
                        colony_id=ids["colony"],
                        resource=resource,
                        stock=123,
                        rate_per_hour=456,
                        remainder=77,
                        capacity=None,
                        updated_at=anchor,
                    )
                )
            connection.execute(
                legacy.tables["scheduled_events"]
                .insert()
                .values(
                    id=ids["event"],
                    colony_id=ids["colony"],
                    sequence=6,
                    idempotency_key="legacy-key",
                    event_type="RESOURCE_RATE_CHANGE",
                    payload={"resource": "alloys", "rate_per_hour": 2},
                    due_at=anchor + timedelta(hours=1),
                    next_attempt_at=anchor + timedelta(hours=2),
                    status="blocked",
                    attempts=3,
                    completed_at=None,
                    error_code="handler_failed",
                )
            )
        command.upgrade(migration_config, "head")
        command.check(migration_config)
        with database_engine.connect() as connection:
            event = (
                connection.execute(
                    sa.text("SELECT * FROM scheduled_events WHERE id=:id"), {"id": ids["event"]}
                )
                .mappings()
                .one()
            )
            assert event["universe_id"] == ids["universe"]
            assert event["stream_id"] == ids["colony"]  # Only the legacy backfill uses equal UUIDs.
            assert event["sequence"] == 6 and event["idempotency_key"] == "legacy-key"
            assert event["status"] == "blocked" and event["attempts"] == 3
            assert event["payload"] == {"resource": "alloys", "rate_per_hour": 2}
            assert event["error_code"] == "handler_failed"
            assert event["next_attempt_at"] == anchor + timedelta(hours=2)
            stream = (
                connection.execute(
                    sa.text("SELECT * FROM event_streams WHERE id=:id"), {"id": ids["colony"]}
                )
                .mappings()
                .one()
            )
            assert stream["cursor_at"] == anchor and stream["next_sequence"] == 7
        command.downgrade(migration_config, "0002_colony_time")
        with database_engine.connect() as connection:
            event = (
                connection.execute(
                    sa.text("SELECT * FROM scheduled_events WHERE id=:id"), {"id": ids["event"]}
                )
                .mappings()
                .one()
            )
            assert event["colony_id"] == ids["colony"]
            assert event["sequence"] == 6 and event["status"] == "blocked"
            balance = (
                connection.execute(
                    sa.text("""
                SELECT * FROM resource_balances WHERE colony_id=:id AND resource='alloys'
            """),
                    {"id": ids["colony"]},
                )
                .mappings()
                .one()
            )
            assert (balance["stock"], balance["rate_per_hour"], balance["remainder"]) == (
                123,
                456,
                77,
            )
            assert balance["updated_at"] == anchor
        command.upgrade(migration_config, "head")
        command.check(migration_config)
    finally:
        command.upgrade(migration_config, "head")
        with database_engine.begin() as connection:
            for table, column, key in [
                ("scheduled_events", "id", "event"),
                ("resource_balances", "colony_id", "colony"),
                ("colony_timelines", "colony_id", "colony"),
                ("event_streams", "id", "colony"),
                ("colonies", "id", "colony"),
                ("planets", "id", "planet"),
                ("stellar_systems", "id", "system"),
                ("empires", "id", "empire"),
                ("universes", "id", "universe"),
            ]:
                connection.execute(
                    sa.text(f"DELETE FROM {table} WHERE {column}=:id"), {"id": ids[key]}
                )
