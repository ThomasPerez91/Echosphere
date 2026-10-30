from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError
from portal_app.main import create_app
from portal_app.sessions.models import (
    AccountDevice,
    BrowserProfile,
    LoginChallenge,
    LogoutRequest,
    PortalSession,
)
from portal_app.sessions.service import (
    CHALLENGE_COOKIE,
    PROFILE_COOKIE,
    SESSION_COOKIE,
    Sessions,
    csrf,
)

pytestmark = pytest.mark.integration
PASSWORD = "C03 strong test phrase 2026 !"
EMAIL = "sessions@example.org"


def prepare(accounts):
    accounts.register(EMAIL, PASSWORD, "setup")
    return Sessions(accounts)


def login(service, profile=None, current=None, email=EMAIL):
    raw = service.challenge("peer")
    return service.login(email, PASSWORD, raw, csrf(raw), profile, current, "peer")


def test_secrets_are_hashed_and_profile_is_not_authentication(accounts):
    service = prepare(accounts)
    raw, profile, state = login(service)
    assert state["user"]["email_verified"] is False
    with accounts.factory() as session:
        assert raw not in session.scalar(select(PortalSession.digest))
        assert profile not in session.scalar(select(BrowserProfile.digest))
        assert session.scalar(select(LoginChallenge.consumed_at)) is not None
        assert session.scalar(select(AccountDevice.user_id)) == session.scalar(select(User.id))
    with pytest.raises(PublicError, match="authentication_required"):
        service.read(profile)


def test_automatic_reads_and_client_activity_flags_never_extend_idle(accounts):
    service = prepare(accounts)
    raw, _, state = login(service)
    for _ in range(3):
        accounts.test_clock[0] += timedelta(hours=23)
        assert service.read(raw)["idle_expires_at"] == state["idle_expires_at"]
        assert service.read(raw, devices=True)["idle_expires_at"] == state["idle_expires_at"]
    accounts.test_clock[0] += timedelta(hours=3)
    for kwargs in ({}, {"interaction": True, "proof": csrf(raw)}):
        with pytest.raises(PublicError, match="authentication_required"):
            service.read(raw, **kwargs)


def test_explicit_navigation_only_refreshes_idle_and_absolute_boundary_is_exact(accounts):
    service = prepare(accounts)
    raw, _, initial = login(service)
    for _ in range(6):
        accounts.test_clock[0] += timedelta(days=1)
        state = service.read(raw, interaction=True, proof=csrf(raw))
        assert state["expires_at"] == initial["expires_at"]
    accounts.test_clock[0] += timedelta(days=1)
    with pytest.raises(PublicError, match="authentication_required"):
        service.read(raw, interaction=True, proof=csrf(raw))


def test_reauthentication_rotates_secret_and_csrf_without_extending_absolute_limit(accounts):
    service = prepare(accounts)
    old, profile, before = login(service)
    accounts.test_clock[0] += timedelta(hours=1)
    new, same_profile, after = login(service, profile, old)
    assert new != old and same_profile == profile
    assert before["session_id"] == after["session_id"]
    assert before["expires_at"] == after["expires_at"]
    with pytest.raises(PublicError, match="authentication_required"):
        service.read(old)
    with pytest.raises(PublicError, match="csrf_denied"):
        service.read(new, interaction=True, proof=csrf(old))
    service.read(new, interaction=True, proof=csrf(new))


def test_expired_session_can_only_be_replaced_by_new_password_login(accounts):
    service = prepare(accounts)
    old, profile, initial = login(service)
    accounts.test_clock[0] += timedelta(hours=72)
    new, same_profile, after = login(service, profile, old)
    assert profile == same_profile and initial["session_id"] != after["session_id"]
    assert after["created_at"] != initial["created_at"]
    with pytest.raises(PublicError):
        service.read(old)
    service.read(new)


def test_one_challenge_can_win_only_once_under_concurrent_login(accounts):
    service = prepare(accounts)
    challenge = service.challenge("peer")

    def attempt(_):
        try:
            service.login(EMAIL, PASSWORD, challenge, csrf(challenge), None, None, "peer")
            return "success"
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["login_challenge_expired", "success"]


def test_device_cap_is_concurrent_configurable_and_never_evicts(accounts):
    service = prepare(accounts)
    accounts.settings.connected_device_limit = 1

    def attempt(_):
        try:
            return login(service)[0]
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count("device_limit_reached") == 1
    winner = next(raw for raw in results if raw != "device_limit_reached")
    service.read(winner)
    with accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(PortalSession)) == 1


def test_tabs_share_profile_session_and_cookie_removal_does_not_revoke_server_state(accounts):
    service = prepare(accounts)
    first, profile, state = login(service)
    second, _, later = login(service, profile)
    assert later["session_id"] == state["session_id"]
    third, _, _ = login(service)  # cleared cookies means a different browser profile
    listed = service.read(third, devices=True)["sessions"]
    assert len(listed) == 2
    assert service.read(second)["user"] == service.read(third)["user"]
    with pytest.raises(PublicError):
        service.read(first)


def test_logout_scope_is_durable_atomic_idempotent_and_other_devices_survive(accounts):
    service = prepare(accounts)
    first, _, state = login(service)
    second, _, _ = login(service)
    from uuid import UUID

    target = UUID(state["session_id"])
    for _ in range(2):
        outcome = service.logout(second, csrf(second), target)
        assert outcome["game_revocation"] == "pending"
        assert outcome["current_session_closed"] is False
    with pytest.raises(PublicError):
        service.read(first)
    service.read(second)
    with accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(LogoutRequest)) == 1
        assert session.scalar(select(LogoutRequest.state)) == "pending"
        assert session.get(PortalSession, target).revoked_at is not None


def test_cross_account_target_and_silent_account_switch_are_refused(accounts):
    service = prepare(accounts)
    own, profile, state = login(service)
    accounts.register("other@example.org", PASSWORD, "setup")
    other, _, _ = login(service, email="other@example.org")
    from uuid import UUID

    with pytest.raises(PublicError, match="session_not_found"):
        service.logout(other, csrf(other), UUID(state["session_id"]))
    with pytest.raises(PublicError, match="account_switch_requires_logout"):
        login(service, profile, own, email="other@example.org")
    service.read(own)
    service.read(other)


def test_challenge_expiry_and_suspended_account_fail_closed(accounts):
    service = prepare(accounts)
    challenge = service.challenge("peer")
    accounts.test_clock[0] += timedelta(minutes=5)
    with pytest.raises(PublicError, match="login_challenge_expired"):
        service.login(EMAIL, PASSWORD, challenge, csrf(challenge), None, None, "peer")
    raw, _, state = login(service)
    with accounts.factory.begin() as session:
        user = session.scalar(select(User))
        user.status = "suspended"
    with pytest.raises(PublicError, match="invalid_credentials"):
        login(service)
    with pytest.raises(PublicError, match="authentication_required"):
        service.read(raw)


def test_csrf_cookies_api_classification_and_current_logout(accounts):
    prepare(accounts)
    app = create_app(accounts.settings)
    app.state.accounts = accounts
    origin = {"Origin": accounts.settings.public_origin, "Content-Type": "application/json"}
    with TestClient(app, base_url=accounts.settings.public_origin) as client:
        assert client.get("/auth/challenge").status_code == 403
        challenge = client.get("/auth/challenge", headers={"X-Portal-Request": "bootstrap"})
        credentials = {"email": EMAIL, "password": PASSWORD}
        assert client.post("/auth/login", json=credentials, headers=origin).status_code == 403
        proof = {**origin, "X-CSRF-Token": challenge.json()["csrf_token"]}
        result = client.post("/auth/login", json=credentials, headers=proof)
        assert result.status_code == 200
        assert CHALLENGE_COOKIE not in client.cookies
        for value in result.headers.get_list("set-cookie"):
            assert "Secure" in value and "HttpOnly" in value and "SameSite=strict" in value
            assert "Domain=" not in value and "Path=/" in value
        raw = client.cookies[SESSION_COOKIE]
        assert raw not in result.text and client.cookies[PROFILE_COOKIE] not in result.text
        state = result.json()
        accounts.test_clock[0] += timedelta(hours=1)
        # Client-controlled activity values on an automatic read have no effect.
        current = client.get(
            "/auth/session?activity=true&timestamp=999999999999",
            headers={"X-Portal-Request": "bootstrap"},
        )
        assert current.json()["idle_expires_at"] == state["idle_expires_at"]
        assert client.post("/auth/navigation", headers=origin).status_code == 403
        valid = {**origin, "X-CSRF-Token": state["csrf_token"]}
        assert (
            client.post(
                "/auth/navigation",
                headers={**valid, "Origin": "https://game.echosphere.localhost:8443"},
            ).status_code
            == 403
        )
        assert client.post("/auth/navigation", headers=valid).status_code == 200
        assert (
            client.post("/auth/sessions/" + str(uuid4()) + "/logout", headers=valid).status_code
            == 404
        )
        closed = client.post("/auth/logout", headers=valid)
        assert closed.status_code == 200 and closed.json()["game_revocation"] == "pending"
        assert SESSION_COOKIE in client.cookies and PROFILE_COOKIE in client.cookies
        assert not any(header.startswith(SESSION_COOKIE + "=")
                       for header in closed.headers.get_list("set-cookie"))
        assert (
            client.get("/auth/session", headers={"X-Portal-Request": "bootstrap"}).status_code
            == 401
        )


def test_invalid_credentials_are_generic_and_login_quota_is_independent(accounts):
    service = prepare(accounts)
    accounts.settings.login_account_limit = 1
    challenge = service.challenge("peer")
    for email in (EMAIL, "unknown@example.org"):
        accounts.test_clock[0] += timedelta(seconds=2)
        with pytest.raises(PublicError, match="invalid_credentials"):
            service.login(
                email, "Wrong password with spaces", challenge, csrf(challenge), None, None, "peer"
            )
    with pytest.raises(PublicError, match="rate_limited"):
        service.login(EMAIL, PASSWORD, challenge, csrf(challenge), None, None, "peer")
    with accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(PortalSession)) == 0


def test_logout_intention_and_session_revoke_roll_back_together(accounts):
    from sqlalchemy import event

    service = prepare(accounts)
    raw, _, _ = login(service)

    def interrupted(session, context, instances):
        if any(isinstance(row, LogoutRequest) for row in session.new):
            raise RuntimeError("synthetic outbox interruption")

    event.listen(accounts.factory.class_, "before_flush", interrupted)
    try:
        with pytest.raises(RuntimeError, match="synthetic outbox"):
            service.logout(raw, csrf(raw))
    finally:
        event.remove(accounts.factory.class_, "before_flush", interrupted)
    service.read(raw)
    with accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(LogoutRequest)) == 0


def test_populated_sessions_downgrade_is_refused_without_data_loss(accounts):
    from alembic import command
    from alembic.config import Config

    service = prepare(accounts)
    raw, _, _ = login(service)
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(Config("alembic.ini"), "p0001_accounts_registration")
    service.read(raw)
    command.check(Config("alembic.ini"))


def test_logout_intention_cannot_bind_another_accounts_session_in_sql(accounts):
    from sqlalchemy.exc import IntegrityError

    service = prepare(accounts)
    _, _, first = login(service)
    accounts.register("other@example.org", PASSWORD, "setup")
    _, _, other = login(service, email="other@example.org")
    from uuid import UUID

    with pytest.raises(IntegrityError), accounts.factory.begin() as session:
        target = session.get(PortalSession, UUID(other["session_id"]))
        session.add(
            LogoutRequest(
                user_id=target.user_id,
                device_id=target.device_id,
                portal_session_id=UUID(first["session_id"]),
                device_epoch=1,
                created_at=accounts.clock(),
                state="pending",
            )
        )


def test_logout_epoch_is_monotonic_and_replay_does_not_target_later_logins(accounts):
    service = prepare(accounts)
    first, profile, state = login(service)
    control, _, _ = login(service)
    from uuid import UUID

    target = UUID(state["session_id"])
    service.logout(control, csrf(control), target)
    later, _, _ = login(service, profile)
    service.logout(control, csrf(control), target)
    with accounts.factory() as session:
        device = session.get(AccountDevice, session.get(PortalSession, target).device_id)
        assert device.revocation_epoch == 1
        assert session.scalar(select(LogoutRequest.device_epoch)) == 1
    service.read(later)
    service.logout(later, csrf(later))
    with accounts.factory() as session:
        assert sorted(session.scalars(select(LogoutRequest.device_epoch))) == [1, 2]
