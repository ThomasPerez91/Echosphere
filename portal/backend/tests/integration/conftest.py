import os
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import text

from portal_app.accounts.security import Passwords
from portal_app.accounts.service import Accounts
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine, create_session_factory


class UncompromisedTestPasswords:
    def compromised(self, value):
        return False


@pytest.fixture(scope="session")
def database_engine():
    if os.getenv("RUN_DB_TESTS") != "1":
        pytest.skip("Set RUN_DB_TESTS=1 and use a dedicated Accounts *_test database")
    settings = Settings()
    if not settings.postgres_db.endswith("_test"):
        pytest.fail("Portal integration tests require a dedicated *_test database")
    engine = create_database_engine(settings)
    command.upgrade(Config("alembic.ini"), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def accounts(database_engine, tmp_path):
    key = tmp_path / "mail.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    settings = Settings(mail_key_file=key, trusted_proxy_host=None)
    current = [datetime(2026, 10, 29, 8, tzinfo=UTC)]
    service = Accounts(
        create_session_factory(database_engine),
        settings,
        Passwords(UncompromisedTestPasswords()),
        clock=lambda: current[0],
    )
    service.test_clock = current
    try:
        yield service
    finally:
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE logout_requests, login_challenges, portal_sessions, account_devices, "
                    "browser_profiles, security_events, abuse_counters, email_outbox, "
                    "account_tokens, password_credentials, users"
                )
            )
