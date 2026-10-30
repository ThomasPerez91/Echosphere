import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from portal_app.accounts.models import AccountToken, EmailOutbox, PasswordCredential, User
from portal_app.accounts.security import PublicError
from portal_app.main import create_app

pytestmark = pytest.mark.integration
PASSWORD = "C02 strong test phrase 2026 !"
EMAIL = "player@example.org"


def pending(accounts):
    with accounts.factory() as session:
        row = session.scalar(select(EmailOutbox).where(EmailOutbox.state == "pending"))
        return json.loads(accounts.cipher().decrypt(row.payload_ciphertext.encode()))


def count(accounts, model):
    with accounts.factory() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_registration_is_atomic_and_persists_no_plaintext_secrets(accounts):
    accounts.register(EMAIL, PASSWORD, "peer")
    payload = pending(accounts)
    with accounts.factory() as session:
        user = session.scalar(select(User))
        saved = session.get(PasswordCredential, user.id)
        token = session.scalar(select(AccountToken))
        mail = session.scalar(select(EmailOutbox))
        assert user.email_verified_at is None
        assert saved.password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=1$")
        assert accounts.passwords.hasher.verify(saved.password_hash, PASSWORD)
        assert token.expires_at - token.created_at == timedelta(hours=24)
        assert payload["token"] not in mail.payload_ciphertext
        assert payload["token"] != token.digest
        assert PASSWORD not in mail.payload_ciphertext
        identifier, original_hash = user.id, saved.password_hash
    accounts.register("PLAYER@example.org", "Another strong test phrase 2026 !", "peer")
    assert count(accounts, User) == count(accounts, EmailOutbox) == 1
    with accounts.factory() as session:
        assert session.scalar(select(User.id)) == identifier
        assert session.get(PasswordCredential, identifier).password_hash == original_hash


def test_failure_before_commit_leaves_no_partial_account(accounts, monkeypatch):
    class BrokenCipher:
        def encrypt(self, value):
            raise RuntimeError("synthetic encryption interruption")

    monkeypatch.setattr(accounts, "cipher", lambda: BrokenCipher())
    with pytest.raises(RuntimeError):
        accounts.register(EMAIL, PASSWORD, "peer")
    for model in (User, PasswordCredential, AccountToken, EmailOutbox):
        assert count(accounts, model) == 0


def test_verification_requires_email_token_and_credential_without_session(accounts):
    app = create_app(accounts.settings)
    app.state.accounts = accounts
    origin = {"Origin": accounts.settings.public_origin}
    with TestClient(app) as client:
        response = client.post(
            "/accounts/register", json={"email": EMAIL, "password": PASSWORD}, headers=origin
        )
        duplicate = client.post(
            "/accounts/register", json={"email": EMAIL, "password": PASSWORD}, headers=origin
        )
        assert response.status_code == duplicate.status_code == 202
        assert response.json() == duplicate.json() == {"status": "request_received"}
        assert "set-cookie" not in response.headers
        payload = pending(accounts)
        bad = client.post(
            "/accounts/email/verify",
            json={"token": payload["token"], "password": "Incorrect test password"},
            headers=origin,
        )
        assert bad.status_code == 400
        good = client.post(
            "/accounts/email/verify",
            json={"token": payload["token"], "password": PASSWORD},
            headers=origin,
        )
        assert good.status_code == 200 and good.json() == {"status": "verified"}
        assert "set-cookie" not in good.headers
        replay = client.post(
            "/accounts/email/verify",
            json={"token": payload["token"], "password": PASSWORD},
            headers=origin,
        )
        assert replay.status_code == 400


def test_resend_is_non_enumerable_and_invalidates_old_urls(accounts):
    accounts.register(EMAIL, PASSWORD, "peer")
    old = pending(accounts)["token"]
    accounts.resend(EMAIL, "Incorrect test password", "peer")
    assert pending(accounts)["token"] == old
    accounts.resend(EMAIL, PASSWORD, "peer")
    new = pending(accounts)["token"]
    assert new != old
    with pytest.raises(PublicError, match="invalid_verification"):
        accounts.verify(old, PASSWORD, "peer")
    accounts.verify(new, PASSWORD, "peer")
    with accounts.factory() as session:
        assert session.scalar(select(User.email_verified_at)) is not None
        assert list(session.scalars(select(AccountToken.active))) == [False, False]
        assert (
            session.scalar(
                select(EmailOutbox.payload_ciphertext).where(EmailOutbox.state == "pending")
            )
            is None
        )


def test_expiry_is_absolute_and_server_controlled(accounts):
    accounts.register(EMAIL, PASSWORD, "peer")
    token = pending(accounts)["token"]
    accounts.test_clock[0] += timedelta(hours=24)
    with pytest.raises(PublicError, match="invalid_verification"):
        accounts.verify(token, PASSWORD, "peer")
    with accounts.factory() as session:
        assert session.scalar(select(User.email_verified_at)) is None


def test_simultaneous_registration_creates_one_identity_and_one_delivery(accounts):
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: accounts.register(EMAIL, PASSWORD, "peer"), range(2)))
    assert count(accounts, User) == count(accounts, PasswordCredential) == 1
    assert count(accounts, EmailOutbox) == count(accounts, AccountToken) == 1


def test_simultaneous_verification_is_consumed_once(accounts):
    accounts.register(EMAIL, PASSWORD, "peer")
    token = pending(accounts)["token"]

    def verify(_):
        try:
            accounts.verify(token, PASSWORD, "peer")
            return "verified"
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(verify, range(2))) == ["invalid_verification", "verified"]


def test_resend_racing_confirmation_never_combines_generations(accounts):
    accounts.register(EMAIL, PASSWORD, "peer")
    token = pending(accounts)["token"]

    def confirm():
        try:
            accounts.verify(token, PASSWORD, "peer")
        except PublicError as error:
            assert error.code == "invalid_verification"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(accounts.resend, EMAIL, PASSWORD, "peer")
        second = pool.submit(confirm)
        first.result()
        second.result()
    with accounts.factory() as session:
        verified = session.scalar(select(User.email_verified_at))
        active = session.scalar(
            select(func.count()).select_from(AccountToken).where(AccountToken.active)
        )
        assert active == (0 if verified else 1)


def test_unknown_resend_same_response_and_forged_forwarded_ip_is_not_trusted(accounts):
    accounts.settings.registration_ip_limit = 1
    app = create_app(accounts.settings)
    app.state.accounts = accounts
    with TestClient(app) as client:
        first = client.post(
            "/accounts/email/resend",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"Origin": accounts.settings.public_origin, "X-Forwarded-For": "1.2.3.4"},
        )
        second = client.post(
            "/accounts/email/resend",
            json={"email": EMAIL, "password": PASSWORD},
            headers={"Origin": accounts.settings.public_origin, "X-Forwarded-For": "5.6.7.8"},
        )
        assert first.status_code == 202 and first.json() == {"status": "request_received"}
        assert second.status_code == 429
        assert count(accounts, User) == 0


def test_rate_limit_is_atomic_for_unknown_accounts(accounts):
    accounts.settings.email_request_limit = 2

    def consume(_):
        try:
            accounts.limit("email", "peer", "unknown@example.org")
            return "accepted"
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sorted(pool.map(consume, range(3))) == ["accepted", "accepted", "rate_limited"]


def test_populated_accounts_migration_refuses_destructive_downgrade(accounts):
    from alembic import command
    from alembic.config import Config

    accounts.register(EMAIL, PASSWORD, "peer")
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(Config("alembic.ini"), "p0000_portal_baseline")
    assert count(accounts, User) == count(accounts, EmailOutbox) == 1
    command.check(Config("alembic.ini"))
