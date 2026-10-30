import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from portal_app.account_security.delivery import deliver_security_one
from portal_app.account_security.models import (
    AccountRevocation,
    EmailChangeRequest,
    PasswordResetRequest,
    SecurityEmail,
    StepUpGrant,
)
from portal_app.account_security.service import AccountSecurity
from portal_app.accounts.models import AccountToken, User
from portal_app.accounts.security import PublicError
from portal_app.main import create_app
from portal_app.sessions.models import PortalSession
from portal_app.sessions.service import csrf

pytestmark = pytest.mark.integration
EMAIL = "security@example.org"
PASSWORD = "C04 current long test password !"
NEW = "C04 different long test password !"
DESTINATION = "new-security@example.org"


@pytest.fixture
def security(accounts):
    accounts.register(EMAIL, PASSWORD, "setup")
    return AccountSecurity(accounts)


def login(security, email=EMAIL, password=PASSWORD):
    security.accounts.test_clock[0] += timedelta(seconds=2)
    service = security.sessions
    raw = service.challenge("peer")
    return service.login(email, password, raw, csrf(raw), None, None, "peer")[0]


def proof(security, raw, action, parameters=None):
    return security.step_up(raw, csrf(raw), PASSWORD, action, parameters, "peer")["proof"]


def mail_payloads(security, kind):
    with security.accounts.factory() as session:
        rows = list(
            session.scalars(
                select(SecurityEmail)
                .where(SecurityEmail.kind == kind, SecurityEmail.state == "pending")
                .order_by(SecurityEmail.created_at)
            )
        )
        return [
            json.loads(security.accounts.cipher().decrypt(row.payload_ciphertext.encode()))
            for row in rows
        ]


def token(security, kind):
    return mail_payloads(security, kind)[-1]["token"]


def begin_email(security, raw, address=DESTINATION):
    ticket = proof(security, raw, "email_change", address)
    security.email_request(raw, csrf(raw), ticket, address, "peer")
    return token(security, "email_old"), token(security, "email_new")


def assert_logged_out(security, *cookies):
    for cookie in cookies:
        with pytest.raises(PublicError, match="authentication_required"):
            security.sessions.read(cookie)


def test_stepup_is_action_parameter_session_bound_and_not_a_password_digest(security):
    raw, other = login(security), login(security)
    ticket = proof(security, raw, "password_change", NEW)
    with security.accounts.factory() as session:
        grant = session.scalar(select(StepUpGrant))
        assert grant.expires_at - grant.created_at == timedelta(minutes=5)
        assert NEW not in grant.parameters_digest and ticket != grant.digest
    for cookie, candidate in ((raw, NEW + "changed"), (other, NEW)):
        with pytest.raises(PublicError, match="invalid_step_up"):
            security.password_change(cookie, csrf(cookie), ticket, candidate, "peer")
    with pytest.raises(PublicError, match="invalid_step_up"):
        security.logout_all(raw, csrf(raw), ticket)
    security.sessions.read(raw)


def test_stepup_exact_expiry_and_rotation_do_not_resurrect_proof(security):
    raw = login(security)
    ticket = proof(security, raw, "logout_all")
    security.accounts.test_clock[0] += timedelta(minutes=5)
    with pytest.raises(PublicError, match="invalid_step_up"):
        security.logout_all(raw, csrf(raw), ticket)


def test_password_change_revokes_every_session_atomically_and_notifies_without_secrets(security):
    raw, other = login(security), login(security)
    old, new = begin_email(security, raw)
    ticket = proof(security, raw, "password_change", NEW)
    response = security.password_change(raw, csrf(raw), ticket, NEW, "peer")
    assert response["reauthentication_required"] and response["game_revocation"] == "pending"
    assert_logged_out(security, raw, other)
    with pytest.raises(PublicError):
        security.email_confirm(old, "peer")
    with pytest.raises(PublicError):
        login(security)
    login(security, password=NEW)
    with security.accounts.factory() as session:
        assert session.scalar(select(AccountRevocation.reason)) == "password_change"
        assert session.scalar(select(AccountRevocation.account_epoch)) == 1
        assert (
            session.scalar(
                select(StepUpGrant)
                .where(StepUpGrant.digest != "")
                .order_by(StepUpGrant.created_at.desc())
                .limit(1)
            )
            is not None
        )
        assert all(
            value is None for value in session.scalars(select(EmailChangeRequest.completed_at))
        )
    payload = mail_payloads(security, "password_changed")[0]
    assert (
        payload["token"] is None
        and PASSWORD not in json.dumps(payload)
        and NEW not in json.dumps(payload)
    )


def test_reset_request_is_generic_latest_only_and_does_not_revoke_before_success(security):
    raw = login(security)
    security.reset_request(EMAIL, "peer")
    first = token(security, "password_reset")
    security.reset_request("unknown@example.org", "peer")
    security.sessions.read(raw)
    security.reset_request(EMAIL, "peer")
    second = token(security, "password_reset")
    assert first != second
    with pytest.raises(PublicError, match="invalid_recovery"):
        security.reset_confirm(first, NEW, "peer")
    result = security.reset_confirm(second, NEW, "peer")
    assert result["status"] == "password_reset"
    assert_logged_out(security, raw)
    with pytest.raises(PublicError, match="invalid_recovery"):
        security.reset_confirm(second, NEW, "peer")
    with security.accounts.factory() as session:
        assert not any(session.scalars(select(PasswordResetRequest.active)))
        assert session.scalar(select(User.email_verified_at)) is None  # reset is not verification
    login(security, password=NEW)


def test_reset_exact_30_minutes_refused_without_changing_credentials(security):
    security.reset_request(EMAIL, "peer")
    secret = token(security, "password_reset")
    security.accounts.test_clock[0] += timedelta(minutes=30)
    with pytest.raises(PublicError, match="invalid_recovery"):
        security.reset_confirm(secret, NEW, "peer")
    login(security)


def test_two_concurrent_resets_succeed_once(security):
    security.reset_request(EMAIL, "peer")
    secret = token(security, "password_reset")

    def attempt(_):
        try:
            security.reset_confirm(secret, NEW, "peer")
            return "success"
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["invalid_recovery", "success"]
    with security.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(AccountRevocation)) == 1


def test_email_confirmation_both_sides_same_request_identity_stable_global_logout(security):
    raw, other = login(security), login(security)
    security.reset_request(EMAIL, "peer")
    reset = token(security, "password_reset")
    with security.accounts.factory() as session:
        identifier = session.scalar(select(User.id))
    old, new = begin_email(security, raw)
    assert security.email_confirm(new, "peer")["status"] == "additional_confirmation_required"
    with security.accounts.factory() as session:
        assert session.get(User, identifier).email == EMAIL
    result = security.email_confirm(old, "peer")
    assert result["status"] == "email_changed" and result["game_revocation"] == "pending"
    assert_logged_out(security, raw, other)
    with security.accounts.factory() as session:
        assert session.get(User, identifier).email == DESTINATION
        assert session.get(User, identifier).email_verified_at is not None
        assert not any(session.scalars(select(AccountToken.active)))
        assert not any(session.scalars(select(PasswordResetRequest.active)))
    with pytest.raises(PublicError):
        security.reset_confirm(reset, NEW, "peer")
    with pytest.raises(PublicError):
        login(security)
    login(security, email=DESTINATION)
    for kind in ("email_changed_old", "email_changed_new"):
        payload = mail_payloads(security, kind)[0]
        assert payload["token"] is None and PASSWORD not in json.dumps(payload)


def test_email_reissue_cancels_both_old_links_and_confirmed_side(security):
    raw = login(security)
    old1, new1 = begin_email(security, raw)
    security.email_confirm(old1, "peer")
    old2, new2 = begin_email(security, raw, "third@example.org")
    for obsolete in (old1, new1):
        with pytest.raises(PublicError, match="invalid_email_confirmation"):
            security.email_confirm(obsolete, "peer")
    assert security.email_confirm(new2, "peer")["status"] == "additional_confirmation_required"
    with security.accounts.factory() as session:
        assert session.scalar(select(User.email)) == EMAIL
    assert security.email_confirm(old2, "peer")["status"] == "email_changed"


def test_email_deadline_shared_and_not_extended_by_first_confirmation(security):
    raw = login(security)
    old, new = begin_email(security, raw)
    security.accounts.test_clock[0] += timedelta(minutes=50)
    security.email_confirm(old, "peer")
    security.accounts.test_clock[0] += timedelta(minutes=10)
    with pytest.raises(PublicError, match="invalid_email_confirmation"):
        security.email_confirm(new, "peer")
    with security.accounts.factory() as session:
        assert session.scalar(select(User.email)) == EMAIL


def test_email_change_requires_requesting_session_still_valid(security):
    raw = login(security)
    old, new = begin_email(security, raw)
    security.sessions.logout(raw, csrf(raw))
    with pytest.raises(PublicError, match="invalid_email_confirmation"):
        security.email_confirm(old, "peer")


def test_existing_destination_never_merges_accounts_or_changes_identity(security):
    security.accounts.register(DESTINATION, PASSWORD, "setup")
    raw = login(security)
    old, new = begin_email(security, raw)
    security.email_confirm(old, "peer")
    with pytest.raises(PublicError, match="email_change_unavailable"):
        security.email_confirm(new, "peer")
    with security.accounts.factory() as session:
        assert set(session.scalars(select(User.email))) == {EMAIL, DESTINATION}
        assert session.scalar(select(func.count()).select_from(AccountRevocation)) == 0
    security.sessions.read(raw)


def test_concurrent_email_confirmations_commit_once(security):
    raw = login(security)
    old, new = begin_email(security, raw)

    def confirm(secret):
        return security.email_confirm(secret, "peer")["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, (old, new))) == [
            "additional_confirmation_required",
            "email_changed",
        ]
    with security.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(AccountRevocation)) == 1


def test_reset_cancels_pending_email_and_outstanding_stepups(security):
    raw = login(security)
    old, new = begin_email(security, raw)
    proof(security, raw, "logout_all")
    security.reset_request(EMAIL, "peer")
    security.reset_confirm(token(security, "password_reset"), NEW, "peer")
    with pytest.raises(PublicError):
        security.email_confirm(new, "peer")
    with security.accounts.factory() as session:
        assert all(
            grant.consumed_at or grant.revoked_at for grant in session.scalars(select(StepUpGrant))
        )


def test_sensitive_change_and_notice_failure_roll_back_every_effect(security, monkeypatch):
    raw, other = login(security), login(security)
    ticket = proof(security, raw, "password_change", NEW)
    monkeypatch.setattr(
        security,
        "mail",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic mail failure")),
    )
    with pytest.raises(RuntimeError):
        security.password_change(raw, csrf(raw), ticket, NEW, "peer")
    security.sessions.read(raw)
    security.sessions.read(other)
    with security.accounts.factory() as session:
        assert session.scalar(select(User.security_epoch)) == 0
        assert session.scalar(select(func.count()).select_from(AccountRevocation)) == 0
        assert session.scalar(select(StepUpGrant.consumed_at)) is None
    login(security)


def test_logout_all_distinct_action_covers_every_device_and_replay_refused(security):
    raw, other = login(security), login(security)
    ticket = proof(security, raw, "logout_all")
    response = security.logout_all(raw, csrf(raw), ticket)
    assert response["game_revocation"] == "pending"
    assert_logged_out(security, raw, other)
    with pytest.raises(PublicError):
        security.logout_all(raw, csrf(raw), ticket)
    with security.accounts.factory() as session:
        assert session.scalar(select(AccountRevocation.reason)) == "logout_all"
        assert session.scalar(select(User.security_epoch)) == 1


@pytest.mark.parametrize("flag", ["mfa_enabled", "platform_privileged"])
def test_future_mfa_and_privileged_policy_never_falls_back_to_password_only(security, flag):
    raw = login(security)
    security.reset_request(EMAIL, "peer")
    reset = token(security, "password_reset")
    ticket = proof(security, raw, "logout_all")
    with security.accounts.factory.begin() as session:
        setattr(session.scalar(select(User)), flag, True)
    for operation in (
        lambda: proof(security, raw, "logout_all"),
        lambda: security.logout_all(raw, csrf(raw), ticket),
        lambda: login(security),
    ):
        with pytest.raises(PublicError, match="additional_proof_required|mfa_required"):
            operation()
    security.reset_confirm(reset, NEW, "peer")
    with security.accounts.factory() as session:
        assert getattr(session.scalar(select(User)), flag)
        assert session.scalar(select(User.security_epoch)) == 1
    with pytest.raises(PublicError, match="additional_proof_required|mfa_required"):
        login(security, password=NEW)


class Receiver:
    def __init__(self, fail=False):
        self.messages, self.fail = [], fail

    def send(self, message):
        self.messages.append(message)
        if self.fail:
            raise OSError("private SMTP recipient must not be logged")


def test_security_email_retry_uses_original_deadline_and_stable_id(security, caplog):
    security.reset_request(EMAIL, "peer")
    receiver = Receiver(True)
    assert deliver_security_one(security.accounts, receiver)
    with security.accounts.factory() as session:
        pending = session.scalar(select(SecurityEmail))
        deadline = pending.expires_at
        assert pending.payload_ciphertext is not None and pending.attempts == 1
    security.accounts.test_clock[0] += timedelta(seconds=3)
    receiver.fail = False
    assert deliver_security_one(security.accounts, receiver)
    assert receiver.messages[0]["Message-ID"] == receiver.messages[1]["Message-ID"]
    with security.accounts.factory() as session:
        sent = session.scalar(select(SecurityEmail))
        assert sent.payload_ciphertext is None and sent.expires_at == deadline
    assert "private SMTP" not in caplog.text


def test_expired_security_email_never_delivered_and_notification_has_no_token(security):
    security.reset_request(EMAIL, "peer")
    security.accounts.test_clock[0] += timedelta(minutes=30)
    receiver = Receiver()
    assert deliver_security_one(security.accounts, receiver) and not receiver.messages
    raw = login(security)
    ticket = proof(security, raw, "password_change", NEW)
    security.password_change(raw, csrf(raw), ticket, NEW, "peer")
    assert deliver_security_one(security.accounts, receiver)
    message = receiver.messages[0].get_content()
    assert NEW not in message and PASSWORD not in message
    assert "#reset-password=" not in message and "#security-alert" in message


def test_security_api_origin_csrf_and_generic_reset_response_without_cookie_login(security):
    accounts = security.accounts
    login(security)
    app = create_app(accounts.settings)
    app.state.accounts = accounts
    origin = {"Origin": accounts.settings.public_origin}
    with TestClient(app, base_url=accounts.settings.public_origin) as client:
        for email in (EMAIL, "unknown@example.org"):
            request = client.post(
                "/security/password/reset/request", json={"email": email}, headers=origin
            )
            assert request.status_code == 202 and request.json() == {"status": "request_received"}
            assert "set-cookie" not in request.headers
        secret = token(security, "password_reset")
        result = client.post(
            "/security/password/reset/confirm",
            json={"token": secret, "new_password": NEW},
            headers=origin,
        )
        assert result.status_code == 200
        # Clearing a status-only receipt is not a login cookie issuance.
        assert not any(header.startswith("__Host-portal-session=")
                       for header in result.headers.get_list("set-cookie"))
        assert "__Host-portal-session" not in client.cookies
        assert secret not in result.text and NEW not in result.text
        invalid = client.post(
            "/security/step-up",
            json={"action": "logout_all", "current_password": PASSWORD},
            headers=origin,
        )
        assert invalid.status_code == 403 and PASSWORD not in invalid.text


def test_global_revocation_refuses_an_older_password_login_in_flight(security, monkeypatch):
    from threading import Event

    raw = login(security)
    ticket = proof(security, raw, "logout_all")
    checked, resume = Event(), Event()
    original = security.accounts.passwords.verify

    def pause(value, saved):
        result = original(value, saved)
        checked.set()
        assert resume.wait(10)
        return result

    monkeypatch.setattr(security.accounts.passwords, "verify", pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        attempted = pool.submit(login, security)
        assert checked.wait(10)
        try:
            security.logout_all(raw, csrf(raw), ticket)
        finally:
            resume.set()
        with pytest.raises(PublicError, match="invalid_credentials"):
            attempted.result()
    with security.accounts.factory() as session:
        assert not any(value is None for value in session.scalars(select(PortalSession.revoked_at)))


def test_two_security_workers_do_not_send_the_same_pending_email(security):
    security.reset_request(EMAIL, "peer")
    receiver = Receiver()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: deliver_security_one(security.accounts, receiver), range(2)))
    assert len(receiver.messages) == 1
