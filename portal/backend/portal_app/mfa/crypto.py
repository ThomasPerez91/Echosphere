"""MFA primitives. Caller holds User lock for every proof consumption."""

import re
import secrets
from uuid import UUID

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from webauthn import base64url_to_bytes, verify_authentication_response
from webauthn.helpers.exceptions import WebAuthnException

from portal_app.accounts.security import PublicError
from portal_app.mfa.models import MfaChallenge, TotpCredential, WebAuthnCredential


def cipher(accounts):
    try:
        return Fernet(accounts.settings.mfa_key_file.read_bytes().strip())
    except (OSError, ValueError):
        raise PublicError("temporarily_unavailable", 503) from None


def decrypt(accounts, encrypted):
    try:
        return cipher(accounts).decrypt(encrypted.encode()).decode()
    except (InvalidToken, UnicodeError):
        raise PublicError("temporarily_unavailable", 503) from None


def verify_totp(secret, code, now, previous=-1):
    if not isinstance(code, str) or re.fullmatch(r"\d{6}", code, flags=re.ASCII) is None:
        raise PublicError("invalid_mfa", 403)
    current = int(now.timestamp()) // 30
    otp = pyotp.TOTP(secret, digits=6, interval=30)
    matches = [
        step
        for step in (current - 1, current, current + 1)
        if step > previous and secrets.compare_digest(otp.generate_otp(step), code)
    ]
    if not matches:
        raise PublicError("invalid_mfa", 403)
    return max(matches)


def web_count(session, user):
    return session.scalar(
        select(func.count())
        .select_from(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == user.id)
    )


def validate_rp(accounts):
    from urllib.parse import urlsplit

    if accounts.settings.webauthn_rp_id != urlsplit(accounts.settings.public_origin).hostname:
        raise PublicError("temporarily_unavailable", 503)


def policy(session, user, accounts, assurance=None):
    if user.privilege_recovery_required:
        raise PublicError("support_recovery_required", 403)
    if user.platform_privileged:
        required = 2 if accounts.settings.production else 1
        if (
            not user.mfa_enabled
            or web_count(session, user) < required
            or assurance not in (None, "webauthn")
        ):
            raise PublicError("additional_proof_required", 403)
    elif user.mfa_enabled and assurance == "password":
        raise PublicError("additional_proof_required", 403)


def challenge_valid(row, user, context, now, purpose):
    if (
        row is None
        or row.user_id != user.id
        or row.purpose != purpose
        or row.used_at
        or now >= row.expires_at
        or row.epoch != user.security_epoch
        or not secrets.compare_digest(row.context_digest, context)
    ):
        raise PublicError("invalid_mfa", 403)


def verify_factor(session, user, accounts, supplied, context):
    policy(session, user, accounts)
    if not user.mfa_enabled and not user.platform_privileged:
        return "password"
    if supplied is None:
        raise PublicError("mfa_required", 403)
    now = accounts.clock()
    if isinstance(supplied, dict) and set(supplied) == {"totp"}:
        if user.platform_privileged:
            raise PublicError("invalid_mfa", 403)
        stored = session.get(TotpCredential, user.id)
        if stored is None:
            raise PublicError("invalid_mfa", 403)
        stored.last_step = verify_totp(
            decrypt(accounts, stored.encrypted_secret), supplied["totp"], now, stored.last_step
        )
        return "totp"
    try:
        if not isinstance(supplied, dict) or set(supplied) != {"challenge_id", "credential"}:
            raise PublicError("invalid_mfa", 403)
        pending = session.get(MfaChallenge, UUID(supplied["challenge_id"]))
        challenge_valid(pending, user, context, now, "assert")
        data = supplied["credential"]
        credential_id = base64url_to_bytes(data["id"])
        stored = session.scalar(
            select(WebAuthnCredential).where(
                WebAuthnCredential.user_id == user.id,
                WebAuthnCredential.credential_id == credential_id,
            )
        )
        if stored is None:
            raise PublicError("invalid_mfa", 403)
        handle = data.get("response", {}).get("userHandle")
        if handle is not None and base64url_to_bytes(handle) != user.id.bytes:
            raise PublicError("invalid_mfa", 403)
        validate_rp(accounts)
        checked = verify_authentication_response(
            credential=data,
            expected_challenge=pending.challenge,
            expected_rp_id=accounts.settings.webauthn_rp_id,
            expected_origin=accounts.settings.public_origin,
            credential_public_key=stored.public_key,
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True,
        )
        pending.used_at, stored.sign_count = now, checked.new_sign_count
        return "webauthn"
    except (WebAuthnException, ValueError, KeyError, TypeError, AttributeError):
        raise PublicError("invalid_mfa", 403) from None
