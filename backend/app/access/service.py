"""Access admission serializes with C06 revocation on the principal before any stream lock."""

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text

from app.access.models import ConsumedTicket, GameSession, PreAuth
from app.access.tickets import TicketDenied, verify
from app.control.models import GameAccess, GameDevice, GamePrincipal
from app.persistence.models import Universe


class AccessError(Exception):
    def __init__(self, code="handoff_denied", status=403):
        self.code, self.status = code, status
        super().__init__(code)


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def secret(raw):
    return isinstance(raw, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", raw) is not None


def csrf(raw):
    if not secret(raw):
        raise AccessError("authentication_required", 401)
    return hmac.new(raw.encode(), b"echosphere:game:csrf:v1", hashlib.sha256).hexdigest()


def check_csrf(raw, proof):
    if (
        not isinstance(proof, str)
        or re.fullmatch(r"[a-f0-9]{64}", proof) is None
        or not hmac.compare_digest(csrf(raw), proof)
    ):
        raise AccessError("csrf_denied")


def alive(row, now):
    return (
        row is not None
        and row.revoked_at is None
        and now
        < min(row.expires_at, row.access_valid_until, row.last_activity_at + timedelta(hours=2))
    )


class GameSessions:
    def __init__(self, factory, settings, clock=None):
        self.factory, self.settings = factory, settings
        self.clock = clock or (lambda: datetime.now(UTC))

    def start(self, universe_id, peer="unknown"):
        with self.factory.begin() as session:
            if session.get(Universe, universe_id) is None:
                raise AccessError("universe_not_found", 404)
            now = self.clock()
            peer_digest = digest(peer)
            session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {
                    "key": int.from_bytes(
                        hashlib.sha256(("preauth:" + peer_digest).encode()).digest()[:8],
                        signed=True,
                    )
                },
            )
            count = session.scalar(
                select(func.count())
                .select_from(PreAuth)
                .where(
                    PreAuth.peer_digest == peer_digest,
                    PreAuth.created_at > now - timedelta(hours=1),
                )
            )
            if count >= self.settings.pre_auth_ip_limit:
                raise AccessError("rate_limited", 429)
            raw = secrets.token_urlsafe(32)
            row = PreAuth(
                peer_digest=peer_digest,
                universe_id=universe_id,
                digest=digest(raw),
                created_at=now,
                expires_at=now + timedelta(minutes=5),
            )
            session.add(row)
            session.flush()
            return row.id, raw

    def exchange(self, ticket, pre_auth_raw, current_raw, universe_id):
        try:
            claims, key_id = verify(ticket, self.settings, self.clock())
        except TicketDenied:
            raise AccessError() from None
        if claims.universe_id != universe_id or not secret(pre_auth_raw):
            raise AccessError()
        with self.factory.begin() as session:
            # Do not create a principal/access on an untrusted admission path.
            principal = session.get(GamePrincipal, claims.sub, with_for_update=True)
            now = self.clock()
            if principal is None or now.timestamp() >= claims.exp:
                raise AccessError()
            access = session.get(GameAccess, claims.membership_id)
            device = session.get(GameDevice, (claims.sub, claims.device_id))
            if (
                access is None
                or access.global_user_id != claims.sub
                or access.universe_id != universe_id
                or access.status != "active"
                or now >= access.valid_until
                or access.portal_confirmed_at > now
                or access.revision < claims.revision
                or access.access_epoch != claims.access_epoch
                or principal.account_epoch != claims.account_epoch
                or (device.device_epoch if device else 0) != claims.device_epoch
            ):
                raise AccessError()
            pre_auth = session.get(PreAuth, claims.pre_auth_id, with_for_update=True)
            if (
                pre_auth is None
                or pre_auth.universe_id != universe_id
                or not hmac.compare_digest(pre_auth.digest, digest(pre_auth_raw))
                or pre_auth.consumed_at
                or now >= pre_auth.expires_at
                or session.get(ConsumedTicket, claims.jti)
            ):
                raise AccessError()
            now = self.clock()
            if (
                now.timestamp() >= claims.exp
                or now >= pre_auth.expires_at
                or now >= access.valid_until
            ):
                raise AccessError()
            # A targeted logout invalidates in-flight browser ceremonies as well as its cookie.
            last_logout = session.scalar(
                select(GameSession.logout_at)
                .where(
                    GameSession.global_user_id == claims.sub,
                    GameSession.device_id == claims.device_id,
                    GameSession.universe_id == universe_id,
                    GameSession.logout_at.is_not(None),
                )
                .order_by(GameSession.logout_at.desc())
                .limit(1)
            )
            if last_logout and pre_auth.created_at <= last_logout:
                raise AccessError()
            current = session.scalar(
                select(GameSession).where(GameSession.digest == digest(current_raw or ""))
            )
            if alive(current, now) and current.global_user_id != claims.sub:
                # C06 may already have invalidated the old account's cookie through epochs.
                # Read-only checks need no second principal lock; a concurrent new revocation
                # can only make this conservative refusal obsolete, never authorize an old cookie.
                previous_principal = session.get(GamePrincipal, current.global_user_id)
                previous_device = session.get(
                    GameDevice, (current.global_user_id, current.device_id)
                )
                previous_access = session.get(GameAccess, current.membership_id)
                if self.effective(
                    current, previous_principal, previous_device, previous_access, now
                ):
                    raise AccessError("account_switch_requires_logout", 409)
            if device is None:
                device = GameDevice(
                    global_user_id=claims.sub, device_id=claims.device_id, device_epoch=0
                )
                session.add(device)
                session.flush()
            rows = list(
                session.scalars(
                    select(GameSession).where(
                        GameSession.global_user_id == claims.sub,
                        GameSession.device_id == claims.device_id,
                        GameSession.revoked_at.is_(None),
                    )
                )
            )
            active, existing = 0, None
            for row in rows:
                other_access = session.get(GameAccess, row.membership_id)
                if not self.effective(row, principal, device, other_access, now):
                    row.revoked_at = now
                else:
                    active += 1
                    if row.universe_id == universe_id:
                        existing = row
            if existing is None and active >= self.settings.game_universe_session_limit:
                raise AccessError("game_session_limit_reached", 409)
            session.flush()
            raw = secrets.token_urlsafe(32)
            if existing:
                # Re-entry rotates the proof, without extending this session's absolute/access cap.
                existing.digest, existing.last_activity_at, existing.key_id = (
                    digest(raw),
                    now,
                    key_id,
                )
                row = existing
            else:
                row = GameSession(
                    global_user_id=claims.sub,
                    device_id=claims.device_id,
                    membership_id=claims.membership_id,
                    universe_id=universe_id,
                    digest=digest(raw),
                    key_id=key_id,
                    account_epoch=claims.account_epoch,
                    device_epoch=claims.device_epoch,
                    access_epoch=claims.access_epoch,
                    created_at=now,
                    last_activity_at=now,
                    access_valid_until=access.valid_until,
                    expires_at=min(now + timedelta(hours=8), access.valid_until),
                )
                session.add(row)
            pre_auth.consumed_at = now
            session.add(
                ConsumedTicket(
                    id=claims.jti,
                    pre_auth_id=pre_auth.id,
                    consumed_at=now,
                    expires_at=datetime.fromtimestamp(claims.exp, UTC),
                )
            )
            session.flush()
            return raw, self.payload(row, access, raw, session.get(Universe, row.universe_id).name)

    def effective(self, row, principal, device, access, now):
        return (
            alive(row, now)
            and principal is not None
            and device is not None
            and access is not None
            and access.global_user_id == row.global_user_id
            and access.universe_id == row.universe_id
            and access.status == "active"
            and now < access.valid_until
            and principal.account_epoch == row.account_epoch
            and device.device_epoch == row.device_epoch
            and access.access_epoch == row.access_epoch
            and row.key_id in self.settings.handoff_public_keys
        )

    def locked(self, session, raw, universe_id):
        if not secret(raw):
            raise AccessError("authentication_required", 401)
        identifier = session.scalar(
            select(GameSession.global_user_id).where(GameSession.digest == digest(raw))
        )
        if identifier is None:
            raise AccessError("authentication_required", 401)
        principal = session.get(GamePrincipal, identifier, with_for_update=True)
        row = session.scalar(select(GameSession).where(GameSession.digest == digest(raw)))
        if row is None or row.universe_id != universe_id:
            raise AccessError("authentication_required", 401)
        access = session.get(GameAccess, row.membership_id)
        device = session.get(GameDevice, (row.global_user_id, row.device_id))
        if not self.effective(row, principal, device, access, self.clock()):
            raise AccessError("authentication_required", 401)
        return row, access

    @staticmethod
    def payload(row, access, raw, universe_name):
        return {
            "status": "authenticated",
            "universe_name": universe_name,
            "session_id": str(row.id),
            "global_user_id": str(row.global_user_id),
            "universe_id": str(row.universe_id),
            "membership_id": str(row.membership_id),
            "csrf_token": csrf(raw),
            "created_at": row.created_at.isoformat(),
            "expires_at": row.expires_at.isoformat(),
            "idle_expires_at": (row.last_activity_at + timedelta(hours=2)).isoformat(),
            "access_valid_until": row.access_valid_until.isoformat(),
            "bindings": access.snapshot["bindings"],
        }

    def read(self, raw, universe_id, *, interaction=False, proof=None):
        if interaction:
            check_csrf(raw, proof)
        with self.factory.begin() as session:
            row, access = self.locked(session, raw, universe_id)
            if interaction:
                row.last_activity_at = self.clock()
            return self.payload(row, access, raw, session.get(Universe, row.universe_id).name)

    def logout(self, raw, universe_id, proof):
        check_csrf(raw, proof)
        with self.factory.begin() as session:
            row, _ = self.locked(session, raw, universe_id)
            row.revoked_at = row.logout_at = self.clock()
            return {"status": "game_logged_out"}
