"""Real Accounts roundtrip on an explicitly opted-in disposable database."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine


@pytest.mark.integration
def test_independent_accounts_history_roundtrip():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 and target a dedicated Accounts *_test database")
    settings = Settings()
    if not settings.postgres_db.endswith("_test"):
        pytest.fail("Portal migration tests require a dedicated Accounts *_test database")
    config = Config("alembic.ini")
    engine = create_database_engine(settings)
    try:
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM portal_alembic_version")) == (
                "p0000_portal_baseline"
            )
            assert connection.scalar(text("SHOW timezone")) == "UTC"
        assert inspect(engine).get_table_names() == ["portal_alembic_version"]
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        engine.dispose()
