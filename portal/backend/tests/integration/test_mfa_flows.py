import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import cbor2
import pyotp
import pytest
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from portal_app.account_security.models import AccountRevocation
from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError
from portal_app.mfa.models import (
    BackupCode,
    MfaChallenge,
    MfaRecoverySession,
    TotpCredential,
    WebAuthnCredential,
)
from portal_app.mfa.service import Mfa, enrollment_parameters
from portal_app.sessions.service import csrf

pytestmark = pytest.mark.integration
EMAIL = "mfa@example.org"
PASSWORD = "MFA test password long 2026 !"


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


class Authenticator:
    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.identifier = uuid4().bytes
        numbers = self.key.public_key().public_numbers()
        self.cose = cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )
        self.count = 0

    def registration(self, accounts, pending, uv=True, origin=None):
        data = (
            hashlib.sha256(accounts.settings.webauthn_rp_id.encode()).digest()
            + bytes([0x45 if uv else 0x41])
            + bytes(4)
        )
        data += bytes(16) + len(self.identifier).to_bytes(2, "big") + self.identifier + self.cose
        client = json.dumps(
            {
                "type": "webauthn.create",
                "challenge": b64(pending.challenge),
                "origin": origin or accounts.settings.public_origin,
                "crossOrigin": False,
            }
        ).encode()
        return {
            "id": b64(self.identifier),
            "rawId": b64(self.identifier),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client),
                "attestationObject": b64(
                    cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": data})
                ),
            },
        }

    def assertion(self, accounts, pending, user_id, uv=True, origin=None, rp=None):
        self.count += 1
        client = json.dumps(
            {
                "type": "webauthn.get",
                "challenge": b64(pending.challenge),
                "origin": origin or accounts.settings.public_origin,
                "crossOrigin": False,
            }
        ).encode()
        data = (
            hashlib.sha256((rp or accounts.settings.webauthn_rp_id).encode()).digest()
            + bytes([5 if uv else 1])
            + self.count.to_bytes(4, "big")
        )
        signature = self.key.sign(data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64(self.identifier),
            "rawId": b64(self.identifier),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64(client),
                "authenticatorData": b64(data),
                "signature": b64(signature),
                "userHandle": b64(user_id.bytes),
            },
        }


@pytest.fixture
def mfa(accounts):
    accounts.register(EMAIL, PASSWORD, "setup")
    return Mfa(accounts)


def pending(mfa, identifier):
    with mfa.accounts.factory() as session:
        return session.get(MfaChallenge, UUID(identifier))


def login(mfa, factor=None):
    raw = mfa.sessions.challenge("peer")
    return mfa.sessions.login(EMAIL, PASSWORD, raw, csrf(raw), None, None, "peer", factor)[0]


def otp(mfa, seed):
    mfa.accounts.test_clock[0] += timedelta(seconds=31)
    return {"totp": pyotp.TOTP(seed).at(mfa.accounts.clock())}


def grant(mfa, raw, action, parameters=None, factor=None):
    return mfa.security.step_up(raw, csrf(raw), PASSWORD, action, parameters, "peer", factor)[
        "proof"
    ]


def totp_enable(mfa):
    raw = login(mfa)
    params = enrollment_parameters("totp", "Application")
    proof = grant(mfa, raw, "mfa_enroll", params)
    start = mfa.begin(raw, csrf(raw), proof, "totp", "Application")
    result = mfa.finish(raw, csrf(raw), start["challenge_id"], otp(mfa, start["secret"]), "peer")
    return start["secret"], result


def enroll_web(mfa, raw, factor=None, replace=None, key=None):
    key = key or Authenticator()
    params = enrollment_parameters("webauthn", "Clef nommée", replace)
    proof = grant(mfa, raw, "mfa_enroll", params, factor)
    start = mfa.begin(raw, csrf(raw), proof, "webauthn", "Clef nommée", replace)
    result = mfa.finish(
        raw,
        csrf(raw),
        start["challenge_id"],
        {"credential": key.registration(mfa.accounts, pending(mfa, start["challenge_id"]))},
        "peer",
    )
    return key, result


def web_factor(mfa, raw, key, action, parameters=None):
    opts = mfa.assertion_options(
        raw, csrf(raw), PASSWORD, action, parameters, EMAIL if action == "login" else None, "peer"
    )
    row = pending(mfa, opts["challenge_id"])
    return {
        "challenge_id": opts["challenge_id"],
        "credential": key.assertion(mfa.accounts, row, row.user_id),
    }


def web_login(mfa, key):
    raw = mfa.sessions.challenge("peer")
    factor = web_factor(mfa, raw, key, "login")
    return mfa.sessions.login(EMAIL, PASSWORD, raw, csrf(raw), None, None, "peer", factor)[0]


def test_totp_activation_encrypted_separate_key_global_logout_and_ten_secret_codes(mfa):
    seed, result = totp_enable(mfa)
    assert result["global_logout"] and len(result["backup_codes"]) == 10
    assert all(len(code.replace("-", "")) == 40 for code in result["backup_codes"])
    with mfa.accounts.factory() as session:
        row = session.get(TotpCredential, session.scalar(select(User.id)))
        assert seed not in row.encrypted_secret
        with pytest.raises(InvalidToken):
            mfa.accounts.cipher().decrypt(row.encrypted_secret.encode())
        assert len(list(session.scalars(select(BackupCode)))) == 10
        assert session.scalar(select(User.security_epoch)) == 1
    with pytest.raises(PublicError, match="mfa_required"):
        login(mfa)
    login(mfa, otp(mfa, seed))


def test_totp_replay_and_parallel_login_are_rejected(mfa):
    seed, _ = totp_enable(mfa)
    factor = otp(mfa, seed)

    def attempt(_):
        try:
            login(mfa, factor)
            return "success"
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count("success") == 1 and any(
        code in results for code in ("invalid_mfa", "rate_limited")
    )


def test_extra_webauthn_and_backup_regeneration_preserve_sessions_and_epoch(mfa):
    seed, initial = totp_enable(mfa)
    raw = login(mfa, otp(mfa, seed))
    original = mfa.sessions.read(raw)
    mfa.accounts.test_clock[0] += timedelta(hours=1)
    assert mfa.status(raw)["enabled"]
    assert mfa.sessions.read(raw)["idle_expires_at"] == original["idle_expires_at"]
    key, result = enroll_web(mfa, raw, otp(mfa, seed))
    assert not result["global_logout"] and result["backup_codes"] == []
    mfa.sessions.read(raw)
    proof = grant(mfa, raw, "mfa_backup_codes", None, otp(mfa, seed))
    outcome = mfa.manage(raw, csrf(raw), proof, "mfa_backup_codes", None)
    assert not outcome["global_logout"] and len(outcome["backup_codes"]) == 10
    assert set(initial["backup_codes"]).isdisjoint(outcome["backup_codes"])
    with mfa.accounts.factory() as session:
        assert session.scalar(select(User.security_epoch)) == 1
        assert session.scalar(select(func.count()).select_from(AccountRevocation)) == 1
    state = mfa.sessions.read(raw)
    assert state["expires_at"] == original["expires_at"]
    assert state["idle_expires_at"] == (mfa.accounts.clock() + timedelta(hours=72)).isoformat()
    web_login(mfa, key)


def test_webauthn_real_signatures_origin_rp_uv_and_replay(mfa):
    raw = login(mfa)
    key, _ = enroll_web(mfa, raw)
    for kwargs in (
        {"origin": "https://game.echosphere.localhost:8443"},
        {"rp": "wrong.invalid"},
        {"uv": False},
    ):
        challenge = mfa.sessions.challenge("peer")
        opts = mfa.assertion_options(
            challenge, csrf(challenge), PASSWORD, "login", None, EMAIL, "peer"
        )
        row = pending(mfa, opts["challenge_id"])
        factor = {
            "challenge_id": opts["challenge_id"],
            "credential": key.assertion(mfa.accounts, row, row.user_id, **kwargs),
        }
        with pytest.raises(PublicError, match="invalid_mfa"):
            mfa.sessions.login(
                EMAIL, PASSWORD, challenge, csrf(challenge), None, None, "peer", factor
            )
        mfa.accounts.test_clock[0] += timedelta(seconds=2)
    raw = web_login(mfa, key)
    factor = web_factor(mfa, raw, key, "logout_all")
    proof = grant(mfa, raw, "logout_all", None, factor)
    with pytest.raises(PublicError, match="invalid_mfa"):
        grant(mfa, raw, "logout_all", None, factor)
    mfa.security.logout_all(raw, csrf(raw), proof)


def test_invalid_registration_cannot_activate_mfa(mfa):
    raw = login(mfa)
    params = enrollment_parameters("webauthn", "Clef")
    start = mfa.begin(raw, csrf(raw), grant(mfa, raw, "mfa_enroll", params), "webauthn", "Clef")
    key = Authenticator()
    with pytest.raises(PublicError, match="invalid_mfa"):
        mfa.finish(
            raw,
            csrf(raw),
            start["challenge_id"],
            {
                "credential": key.registration(
                    mfa.accounts, pending(mfa, start["challenge_id"]), uv=False
                )
            },
            "peer",
        )
    with mfa.accounts.factory() as session:
        assert not session.scalar(select(User.mfa_enabled))
        assert session.scalar(select(func.count()).select_from(WebAuthnCredential)) == 0


def test_totp_replacement_and_disable_revoke_globally(mfa):
    seed, _ = totp_enable(mfa)
    raw = login(mfa, otp(mfa, seed))
    params = enrollment_parameters("totp", "Remplacement")
    start = mfa.begin(
        raw,
        csrf(raw),
        grant(mfa, raw, "mfa_enroll", params, otp(mfa, seed)),
        "totp",
        "Remplacement",
    )
    outcome = mfa.finish(raw, csrf(raw), start["challenge_id"], otp(mfa, start["secret"]), "peer")
    assert outcome["global_logout"]
    with pytest.raises(PublicError):
        mfa.sessions.read(raw)
    raw = login(mfa, otp(mfa, start["secret"]))
    proof = grant(mfa, raw, "mfa_disable", None, otp(mfa, start["secret"]))
    assert mfa.manage(raw, csrf(raw), proof, "mfa_disable", None)["global_logout"]
    login(mfa)
    with mfa.accounts.factory() as session:
        assert not session.scalar(select(User.mfa_enabled))
        assert session.scalar(select(func.count()).select_from(BackupCode)) == 0


def test_recovery_code_once_limited_session_no_portal_and_new_factor(mfa):
    seed, result = totp_enable(mfa)
    challenge = mfa.sessions.challenge("peer")
    recovery = mfa.recover(
        EMAIL, PASSWORD, result["backup_codes"][0], challenge, csrf(challenge), "peer"
    )
    with pytest.raises(PublicError):
        mfa.sessions.read(recovery)
    with mfa.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(TotpCredential)) == 0
        row = session.scalar(select(MfaRecoverySession))
        assert row.expires_at - row.created_at == timedelta(minutes=15)
    start = mfa.begin(recovery, csrf(recovery), None, "totp", "Restaurée", recovery=True)
    outcome = mfa.finish(
        recovery, csrf(recovery), start["challenge_id"], otp(mfa, start["secret"]), "peer", True
    )
    assert outcome["global_logout"] and len(outcome["backup_codes"]) == 10
    with mfa.accounts.factory() as session, pytest.raises(PublicError):
        mfa.recovery_locked(session, recovery)
    login(mfa, otp(mfa, start["secret"]))


def test_recovery_exact_15_minutes_and_no_email_password_bypass(mfa):
    _, result = totp_enable(mfa)
    challenge = mfa.sessions.challenge("peer")
    recovery = mfa.recover(
        EMAIL, PASSWORD, result["backup_codes"][0], challenge, csrf(challenge), "peer"
    )
    mfa.accounts.test_clock[0] += timedelta(minutes=15)
    with pytest.raises(PublicError, match="invalid_recovery"):
        mfa.begin(recovery, csrf(recovery), None, "totp", "Trop tard", recovery=True)
    challenge = mfa.sessions.challenge("peer")
    with pytest.raises(PublicError, match="invalid_recovery"):
        mfa.recover(EMAIL, PASSWORD, result["backup_codes"][0], challenge, csrf(challenge), "peer")


def test_mfa_email_change_only_new_confirmation_with_strong_stepup(mfa):
    seed, _ = totp_enable(mfa)
    raw = login(mfa, otp(mfa, seed))
    address = "mfa-new@example.org"
    proof = grant(mfa, raw, "email_change", address, otp(mfa, seed))
    mfa.security.email_request(raw, csrf(raw), proof, address, "peer")
    from portal_app.account_security.models import SecurityEmail

    with mfa.accounts.factory() as session:
        assert (
            session.scalar(select(SecurityEmail.id).where(SecurityEmail.kind == "email_old"))
            is None
        )
        mail = session.scalar(select(SecurityEmail).where(SecurityEmail.kind == "email_new"))
        payload = json.loads(mfa.accounts.cipher().decrypt(mail.payload_ciphertext.encode()))
    assert mfa.security.email_confirm(payload["token"], "peer")["status"] == "email_changed"
    with mfa.accounts.factory() as session:
        assert session.scalar(select(User.mfa_enabled))


def test_production_privileged_policy_requires_two_webauthn_and_never_totp(mfa):
    raw = login(mfa)
    key, _ = enroll_web(mfa, raw)
    with mfa.accounts.factory.begin() as session:
        session.scalar(select(User)).platform_privileged = True
    mfa.accounts.settings.production = True
    with pytest.raises(PublicError, match="additional_proof_required"):
        web_login(mfa, key)
    mfa.accounts.settings.production = False
    raw = web_login(mfa, key)
    factor = web_factor(
        mfa, raw, key, "mfa_enroll", enrollment_parameters("webauthn", "Clef nommée")
    )
    second, _ = enroll_web(mfa, raw, factor)
    mfa.accounts.settings.production = True
    web_login(mfa, second)


def test_webauthn_cap_replacement_and_foreign_factor_scope(mfa):
    mfa.accounts.settings.security_subject_limit = 100
    mfa.accounts.settings.security_ip_limit = 100
    raw = login(mfa)
    key, _ = enroll_web(mfa, raw)
    raw = web_login(mfa, key)
    for _ in range(4):
        params = enrollment_parameters("webauthn", "Clef nommée")
        enroll_web(mfa, raw, web_factor(mfa, raw, key, "mfa_enroll", params))
    params = enrollment_parameters("webauthn", "Sixième")
    proof = grant(mfa, raw, "mfa_enroll", params, web_factor(mfa, raw, key, "mfa_enroll", params))
    with pytest.raises(PublicError, match="factor_limit_reached"):
        mfa.begin(raw, csrf(raw), proof, "webauthn", "Sixième")
    mfa.accounts.register("other@example.org", PASSWORD, "setup-other")
    challenge = mfa.sessions.challenge("other-peer")
    other = mfa.sessions.login(
        "other@example.org", PASSWORD, challenge, csrf(challenge), None, None, "other-peer"
    )[0]
    foreign_key, _ = enroll_web(mfa, other)
    with mfa.accounts.factory() as session:
        foreign = session.scalar(
            select(WebAuthnCredential.id).where(
                WebAuthnCredential.credential_id == foreign_key.identifier
            )
        )
    params = {"kind": "webauthn", "id": str(foreign)}
    proof = grant(mfa, raw, "mfa_remove", params, web_factor(mfa, raw, key, "mfa_remove", params))
    with pytest.raises(PublicError, match="factor_not_found"):
        mfa.manage(raw, csrf(raw), proof, "mfa_remove", params)
    with mfa.accounts.factory() as session:
        identifier = session.scalar(
            select(WebAuthnCredential.id).where(
                WebAuthnCredential.credential_id.not_in([key.identifier, foreign_key.identifier])
            )
        )
    params = enrollment_parameters("webauthn", "Clef nommée", identifier)
    new, result = enroll_web(
        mfa, raw, web_factor(mfa, raw, key, "mfa_enroll", params), replace=str(identifier)
    )
    assert result["global_logout"]
    web_login(mfa, new)
    with mfa.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(WebAuthnCredential)) == 6


def test_webauthn_proof_is_bound_to_action_parameters_and_exact_expiry(mfa):
    key, _ = enroll_web(mfa, login(mfa))
    raw = web_login(mfa, key)
    factor = web_factor(mfa, raw, key, "email_change", "approved@example.org")
    with pytest.raises(PublicError, match="invalid_mfa"):
        grant(mfa, raw, "email_change", "other@example.org", factor)
    mfa.accounts.test_clock[0] += timedelta(seconds=2)
    # The failed transaction did not consume a proof authorized for the correct parameters.
    grant(mfa, raw, "email_change", "approved@example.org", factor)
    factor = web_factor(mfa, raw, key, "logout_all")
    mfa.accounts.test_clock[0] += timedelta(minutes=5)
    with pytest.raises(PublicError, match="invalid_mfa"):
        grant(mfa, raw, "logout_all", None, factor)


def test_initial_activation_rolls_back_factors_codes_and_revocation_together(mfa):
    from sqlalchemy import event

    raw = login(mfa)
    params = enrollment_parameters("totp", "Application")
    start = mfa.begin(raw, csrf(raw), grant(mfa, raw, "mfa_enroll", params), "totp", "Application")

    def interrupt(session, context, instances):
        if any(isinstance(row, AccountRevocation) for row in session.new):
            raise RuntimeError("synthetic MFA outbox interruption")

    factor = otp(mfa, start["secret"])
    event.listen(mfa.accounts.factory.class_, "before_flush", interrupt)
    try:
        with pytest.raises(RuntimeError, match="synthetic MFA"):
            mfa.finish(raw, csrf(raw), start["challenge_id"], factor, "peer")
    finally:
        event.remove(mfa.accounts.factory.class_, "before_flush", interrupt)
    mfa.sessions.read(raw)
    with mfa.accounts.factory() as session:
        assert not session.scalar(select(User.mfa_enabled))
        assert session.scalar(select(func.count()).select_from(BackupCode)) == 0
        assert session.scalar(select(func.count()).select_from(TotpCredential)) == 0
    assert mfa.finish(raw, csrf(raw), start["challenge_id"], factor, "peer")["global_logout"]


def test_privileged_recovery_requires_webauthn_and_never_restores_privileges(mfa):
    key, initial = enroll_web(mfa, login(mfa))
    with mfa.accounts.factory.begin() as session:
        session.scalar(select(User)).platform_privileged = True
    challenge = mfa.sessions.challenge("peer")
    recovery = mfa.recover(
        EMAIL, PASSWORD, initial["backup_codes"][0], challenge, csrf(challenge), "peer"
    )
    with pytest.raises(PublicError, match="additional_proof_required"):
        mfa.begin(recovery, csrf(recovery), None, "totp", "Interdit", recovery=True)
    start = mfa.begin(recovery, csrf(recovery), None, "webauthn", "Restauré", recovery=True)
    new = Authenticator()
    result = mfa.finish(
        recovery,
        csrf(recovery),
        start["challenge_id"],
        {"credential": new.registration(mfa.accounts, pending(mfa, start["challenge_id"]))},
        "peer",
        True,
    )
    assert result["privileged_recovery_blocked"]
    with pytest.raises(PublicError, match="support_recovery_required"):
        web_login(mfa, new)


def test_progressive_cooldown_early_retry_does_not_extend_and_prune_erases_seeds(mfa):
    from portal_app.accounts.models import SecurityEvent
    from portal_app.delivery.worker import prune
    from portal_app.mfa.models import AuthFailure

    raw = login(mfa)
    params = enrollment_parameters("totp", "Application")
    start = mfa.begin(raw, csrf(raw), grant(mfa, raw, "mfa_enroll", params), "totp", "Application")
    for expected in (100, 200, 400, 800, 1000):
        with pytest.raises(PublicError, match="reauthentication_required"):
            mfa.security.step_up(raw, csrf(raw), "Wrong password", "logout_all", None, "peer")
        with mfa.accounts.factory() as session:
            until = session.scalar(select(AuthFailure.retry_after))
            assert until - mfa.accounts.clock() == timedelta(milliseconds=expected)
        with pytest.raises(PublicError, match="rate_limited"):
            grant(mfa, raw, "logout_all")
        with mfa.accounts.factory() as session:
            assert session.scalar(select(AuthFailure.retry_after)) == until
        mfa.accounts.test_clock[0] = until
    with mfa.accounts.factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(SecurityEvent)
                .where(SecurityEvent.kind == "stepup_failed")
            )
            == 5
        )
    mfa.accounts.test_clock[0] += timedelta(minutes=5)
    prune(mfa.accounts)
    assert pending(mfa, start["challenge_id"]).encrypted_secret is None


def test_recovery_cookie_has_no_normal_api_authority_and_csrf_is_required(mfa):
    from fastapi.testclient import TestClient

    from portal_app.api.mfa import RECOVERY_COOKIE
    from portal_app.main import create_app
    from portal_app.sessions.service import SESSION_COOKIE

    _, initial = totp_enable(mfa)
    app = create_app(mfa.accounts.settings)
    app.state.accounts = mfa.accounts
    origin = {"Origin": mfa.accounts.settings.public_origin}
    with TestClient(app, base_url=mfa.accounts.settings.public_origin) as client:
        challenge = client.get("/auth/challenge", headers={"X-Portal-Request": "bootstrap"})
        body = {"email": EMAIL, "password": PASSWORD, "backup_code": initial["backup_codes"][0]}
        assert client.post("/mfa/recovery/start", headers=origin, json=body).status_code == 403
        result = client.post(
            "/mfa/recovery/start",
            json=body,
            headers={
                **origin,
                "X-CSRF-Token": challenge.json()["csrf_token"],
            },
        )
        assert result.status_code == 200 and SESSION_COOKIE not in client.cookies
        assert RECOVERY_COOKIE in client.cookies
        assert (
            "Secure" in result.headers["set-cookie"] and "HttpOnly" in result.headers["set-cookie"]
        )
        assert (
            client.get("/auth/sessions", headers={"X-Portal-Request": "bootstrap"}).status_code
            == 401
        )
        assert (
            client.get("/mfa/status", headers={"X-Portal-Request": "bootstrap"}).status_code == 401
        )
        headers = {**origin, "X-CSRF-Token": result.json()["csrf_token"]}
        assert (
            client.post(
                "/security/step-up",
                headers=headers,
                json={
                    "current_password": PASSWORD,
                    "action": "logout_all",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/mfa/recovery/enroll/begin",
                headers=headers,
                json={
                    "kind": "totp",
                    "name": "Restauré",
                },
            ).status_code
            == 200
        )


def test_concurrent_backup_recovery_consumes_once(mfa):
    _, result = totp_enable(mfa)
    challenges = [mfa.sessions.challenge("peer") for _ in range(2)]

    def recover(raw):
        try:
            mfa.recover(EMAIL, PASSWORD, result["backup_codes"][0], raw, csrf(raw), "peer")
            return "success"
        except PublicError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(recover, challenges))
    assert results.count("success") == 1
    assert any(code in results for code in ("invalid_recovery", "rate_limited"))
    with mfa.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(MfaRecoverySession)) == 1


def test_mfa_notice_does_not_claim_global_logout_for_an_added_factor(mfa):
    from portal_app.account_security.delivery import build_security_message
    from portal_app.account_security.models import SecurityEmail

    seed, initial = totp_enable(mfa)
    raw = login(mfa, otp(mfa, seed))
    enroll_web(mfa, raw, otp(mfa, seed))
    with mfa.accounts.factory() as session:
        row = session.scalar(select(SecurityEmail).where(SecurityEmail.kind == "mfa_changed"))
        payload = json.loads(mfa.accounts.cipher().decrypt(row.payload_ciphertext.encode()))
        body = build_security_message(
            row, payload, mfa.accounts.settings.public_origin
        ).get_content()
    assert "MFA" in body and "nouvelle connexion" not in body
    assert seed not in body and all(code not in body for code in initial["backup_codes"])
