import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.persistence.database import create_database_engine


@pytest.fixture(scope="session")
def migration_config():
    return Config("alembic.ini")


@pytest.fixture(scope="session")
def database_engine(migration_config):
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 and use a dedicated PostgreSQL database ending in _test")
    settings = Settings()
    if not settings.postgres_db.endswith("_test"):
        pytest.fail("Integration tests may migrate/downgrade only a dedicated *_test database")
    engine = create_database_engine(settings)
    command.upgrade(migration_config, "head")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(database_engine):
    # Even an application-level commit/rollback remains inside the test's outer transaction.
    with database_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
