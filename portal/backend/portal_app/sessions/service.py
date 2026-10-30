"""Password login, immutable deadlines and durable device logout intentions."""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from sqlalchemy import func, select, update

from portal_app.accounts.models import PasswordCredential, SecurityEvent, User
from portal_app.accounts.security import PublicError, normalize_email, token_digest
from portal_app.sessions.models import (
    AccountDevice,
    BrowserProfile,
    LoginChallenge,
    LogoutRequest,
    PortalSession,
)

SESSION_COOKIE = "__Host-portal-session"
PROFILE_COOKIE = "__Host-portal-device"
CHALLENGE_COOKIE = "__Host-portal-login"


def valid_secret(raw):
    return isinstance(raw, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", raw) is not None


def csrf(raw):
    if not valid_secret(raw):
        raise PublicError("csrf_denied", 403)
    return hmac.new(raw.encode(), b"echosphere:portal:csrf:v1", hashlib.sha256).hexdigest()


def check_csrf(raw, supplied):
    if (
        not isinstance(supplied, str)
        or re.fullmatch(r"[a-f0-9]{64}", supplied) is None
        or not hmac.compare_digest(csrf(raw), supplied)
    ):
        raise PublicError("csrf_denied", 403)


def alive(row, now):
    return (
        row is not None
        and row.revoked_at is None
        and now < min(row.expires_at, row.last_activity_at + timedelta(hours=72))
    )


class Sessions:
    def __init__(self, accounts):
        self.accounts = accounts

    def challenge(self, peer):
        self.accounts.limit("login_start", peer, peer)
        raw = secrets.token_urlsafe(32)
        now = self.accounts.clock()
        with self.accounts.factory.begin() as session:
            session.add(
                LoginChallenge(
                    digest=token_digest(raw), created_at=now, expires_at=now + timedelta(minutes=5)
                )
            )
        return raw

    def login(
        self, email, password, challenge_raw, proof, profile_raw, current_raw, peer, factor=None
    ):
        from portal_app.mfa.throttle import attempt

        _, key = normalize_email(email)
        with attempt(self.accounts, "login", peer, key, email_key=key):
            return self._login(
                email, password, challenge_raw, proof, profile_raw, current_raw, peer, factor
            )

    def _login(self, email, password, challenge_raw, proof, profile_raw, current_raw, peer, factor):
        check_csrf(challenge_raw, proof)
        _, key = normalize_email(email)
        self.accounts.limit("login", peer, key)
        with self.accounts.factory() as session:
            challenge = session.scalar(
                select(LoginChallenge).where(LoginChallenge.digest == token_digest(challenge_raw))
            )
            if (
                challenge is None
                or challenge.consumed_at
                or self.accounts.clock() >= challenge.expires_at
            ):
                raise PublicError("login_challenge_expired", 401)
            data = session.execute(
                select(User.id, User.security_epoch, PasswordCredential.password_hash)
                .join(PasswordCredential, PasswordCredential.user_id == User.id)
                .where(User.email_key == key)
            ).first()
        matched = self.accounts.passwords.verify(password, data.password_hash if data else None)
        if not matched:
            raise PublicError("invalid_credentials", 401)
        with self.accounts.factory.begin() as session:
            # All account session changes serialize on User; no other User lock acquired.
            user = session.get(User, data.id, with_for_update=True)
            credential = session.get(PasswordCredential, user.id)
            if (
                user.status != "active"
                or credential.password_hash != data.password_hash
                or user.email_key != key
                or user.security_epoch != data.security_epoch
            ):
                raise PublicError("invalid_credentials", 401)
            from portal_app.account_security.service import binding
            from portal_app.mfa.crypto import verify_factor

            verify_factor(
                session, user, self.accounts, factor, binding(challenge_raw, "login", None)
            )
            challenge = session.scalar(
                select(LoginChallenge)
                .where(LoginChallenge.digest == token_digest(challenge_raw))
                .with_for_update()
            )
            now = self.accounts.clock()
            if challenge.consumed_at or now >= challenge.expires_at:
                raise PublicError("login_challenge_expired", 401)
            current = session.scalar(
                select(PortalSession).where(PortalSession.digest == token_digest(current_raw or ""))
            )
            if alive(current, now) and current.user_id != user.id:
                raise PublicError("account_switch_requires_logout", 409)
            profile = None
            if valid_secret(profile_raw):
                profile = session.scalar(
                    select(BrowserProfile)
                    .where(BrowserProfile.digest == token_digest(profile_raw))
                    .with_for_update()
                )
            if profile is None:
                profile_raw = secrets.token_urlsafe(32)
                profile = BrowserProfile(digest=token_digest(profile_raw), created_at=now)
                session.add(profile)
                session.flush()
            device = session.scalar(
                select(AccountDevice).where(
                    AccountDevice.user_id == user.id, AccountDevice.profile_id == profile.id
                )
            )
            # Expired sessions never count towards the active-device cap or revive on rotation.
            session.execute(
                update(PortalSession)
                .where(
                    PortalSession.user_id == user.id,
                    PortalSession.revoked_at.is_(None),
                    (PortalSession.expires_at <= now)
                    | (PortalSession.last_activity_at <= now - timedelta(hours=72)),
                )
                .values(revoked_at=now)
            )
            existing = (
                session.scalar(
                    select(PortalSession).where(
                        PortalSession.device_id == device.id, PortalSession.revoked_at.is_(None)
                    )
                )
                if device
                else None
            )
            count = session.scalar(
                select(func.count())
                .select_from(PortalSession)
                .where(PortalSession.user_id == user.id, PortalSession.revoked_at.is_(None))
            )
            if existing is None and count >= self.accounts.settings.connected_device_limit:
                raise PublicError("device_limit_reached", 409)
            if device is None:
                device = AccountDevice(user_id=user.id, profile_id=profile.id, created_at=now)
                session.add(device)
                session.flush()
            raw = secrets.token_urlsafe(32)
            if existing is None:
                existing = PortalSession(
                    user_id=user.id,
                    device_id=device.id,
                    digest=token_digest(raw),
                    created_at=now,
                    expires_at=now + timedelta(days=7),
                    last_activity_at=now,
                )
                session.add(existing)
            else:
                # A new proof rotates the cookie, preserving this active session's absolute limit.
                existing.digest, existing.last_activity_at = token_digest(raw), now
            challenge.consumed_at = now
            session.add(SecurityEvent(user_id=user.id, kind="portal_login", created_at=now))
            session.flush()
            return raw, profile_raw, self.payload(existing, user, raw)

    def payload(self, row, user, raw):
        return {
            "status": "authenticated",
            "server_time": self.accounts.clock().isoformat(),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "email_verified": user.email_verified_at is not None,
            },
            "session_id": str(row.id),
            "csrf_token": csrf(raw),
            "created_at": row.created_at.isoformat(),
            "expires_at": row.expires_at.isoformat(),
            "idle_expires_at": (row.last_activity_at + timedelta(hours=72)).isoformat(),
        }

    def locked(self, session, raw):
        if not valid_secret(raw):
            raise PublicError("authentication_required", 401)
        identifier = session.scalar(
            select(PortalSession.user_id).where(PortalSession.digest == token_digest(raw))
        )
        if identifier is None:
            raise PublicError("authentication_required", 401)
        user = session.get(User, identifier, with_for_update=True)
        # Re-read after acquiring User: a concurrent login may have rotated the digest.
        row = session.scalar(select(PortalSession).where(PortalSession.digest == token_digest(raw)))
        if user.status != "active" or not alive(row, self.accounts.clock()):
            raise PublicError("authentication_required", 401)
        return row, user

    def read(self, raw, *, interaction=False, proof=None, devices=False):
        if interaction:
            check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            row, user = self.locked(session, raw)
            now = self.accounts.clock()
            if interaction:
                row.last_activity_at = now
            result = self.payload(row, user, raw)
            if devices:
                rows = session.scalars(
                    select(PortalSession)
                    .where(
                        PortalSession.user_id == user.id,
                        PortalSession.revoked_at.is_(None),
                        PortalSession.expires_at > now,
                        PortalSession.last_activity_at > now - timedelta(hours=72),
                    )
                    .order_by(PortalSession.created_at, PortalSession.id)
                )
                result["sessions"] = [
                    {
                        "id": str(item.id),
                        "current": item.id == row.id,
                        "created_at": item.created_at.isoformat(),
                        "expires_at": item.expires_at.isoformat(),
                        "idle_expires_at": (
                            item.last_activity_at + timedelta(hours=72)
                        ).isoformat(),
                    }
                    for item in rows
                ]
                result["device_limit"] = self.accounts.settings.connected_device_limit
            return result

    def logout(self, raw, proof, target_id=None):
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            current, user = self.locked(session, raw)
            target = session.get(PortalSession, target_id) if target_id else current
            if target is None or target.user_id != user.id:
                raise PublicError("session_not_found", 404)
            now = self.accounts.clock()
            if current.id != target.id:
                current.last_activity_at = now
            if target.revoked_at is None:
                target.revoked_at = now
            intention = session.scalar(
                select(LogoutRequest).where(LogoutRequest.portal_session_id == target.id)
            )
            if intention is None:
                device = session.get(AccountDevice, target.device_id)
                device.revocation_epoch += 1
                intention = LogoutRequest(
                    user_id=user.id,
                    device_id=target.device_id,
                    portal_session_id=target.id,
                    created_at=now,
                    state="pending",
                    device_epoch=device.revocation_epoch,
                )
                session.add(intention)
                session.add(SecurityEvent(user_id=user.id, kind="portal_logout", created_at=now))
            session.flush()
            return {
                "revocation_id": str(intention.id),
                "status": "portal_logged_out",
                "game_revocation": "pending",
                "current_session_closed": current.id == target.id,
            }
