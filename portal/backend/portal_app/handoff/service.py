"""Portal issues proofs only for acknowledged rights; no Game DB connection."""

from datetime import timedelta
from uuid import uuid4

import jwt
from sqlalchemy import select

from portal_app.accounts.models import SecurityEvent
from portal_app.accounts.security import PublicError
from portal_app.control.models import UniverseMembership, UniverseReference
from portal_app.control.service import enqueue, wire_time
from portal_app.sessions.models import AccountDevice
from portal_app.sessions.service import Sessions, check_csrf


class Handoff:
    def __init__(self, accounts):
        self.accounts = accounts

    def target(self, session, user, universe_id):
        membership = session.scalar(
            select(UniverseMembership).where(
                UniverseMembership.user_id == user.id, UniverseMembership.universe_id == universe_id
            )
        )
        universe = session.get(UniverseReference, universe_id)
        if membership is None or universe is None:
            raise PublicError("membership_not_found", 404)
        origin = self.accounts.settings.game_public_targets.get(universe.backend_id)
        if origin is None:
            raise PublicError("handoff_unavailable", 503)
        return membership, universe, origin

    def prepare(self, raw, universe_id, origin):
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            _, _, target = self.target(session, user, universe_id)
            if origin != target:
                raise PublicError("origin_denied", 403)
            return target

    def issue(self, raw, proof, universe_id, pre_auth_id, peer="unknown"):
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            portal_session, user = Sessions(self.accounts).locked(session, raw)
            self.accounts.limit("handoff", peer, str(user.id))
            row, universe, origin = self.target(session, user, universe_id)
            now = self.accounts.clock()
            if user.email_verified_at is None:
                raise PublicError("email_verification_required", 403)
            if (
                row.desired_status != "active"
                or not universe.provisioned
                or row.applied_snapshot != row.desired_snapshot
                or row.reconciliation_pending
                or now >= row.valid_until
            ):
                raise PublicError("access_confirmation_required", 409)
            device = session.get(AccountDevice, portal_session.device_id)
            claims = {
                "iss": self.accounts.settings.public_origin,
                "aud": origin,
                "sub": str(user.id),
                "jti": str(uuid4()),
                "universe_id": str(universe_id),
                "membership_id": str(row.id),
                "device_id": str(device.id),
                "pre_auth_id": str(pre_auth_id),
                "iat": int(now.timestamp()),
                "exp": min(int(now.timestamp()) + 60, int(row.valid_until.timestamp())),
                "revision": row.revision,
                "access_epoch": row.access_epoch,
                "account_epoch": user.security_epoch,
                "device_epoch": device.revocation_epoch,
            }
            if claims["exp"] <= claims["iat"]:
                raise PublicError("access_confirmation_required", 409)
            try:
                ticket = jwt.encode(
                    claims,
                    self.accounts.settings.handoff_private_key.read_bytes(),
                    algorithm="EdDSA",
                    headers={
                        "typ": "echosphere-handoff+jwt",
                        "kid": self.accounts.settings.handoff_key_id,
                    },
                )
            except (OSError, ValueError):
                raise PublicError("handoff_unavailable", 503) from None
            portal_session.last_activity_at = now
            session.add(SecurityEvent(user_id=user.id, kind="game_handoff_issued", created_at=now))
            return ticket, origin

    def renew(self, raw, proof, universe_id, peer="unknown"):
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            portal_session, user = Sessions(self.accounts).locked(session, raw)
            self.accounts.limit("handoff", peer, str(user.id))
            row, universe, _ = self.target(session, user, universe_id)
            if user.email_verified_at is None:
                raise PublicError("email_verification_required", 403)
            if (
                row.desired_status != "active"
                or not universe.provisioned
                or row.applied_snapshot != row.desired_snapshot
                or row.reconciliation_pending
            ):
                raise PublicError("access_confirmation_required", 409)
            now = self.accounts.clock()
            row.revision += 1
            row.portal_confirmed_at, row.valid_until = now, now + timedelta(hours=8)
            row.desired_snapshot = {
                **row.desired_snapshot,
                "revision": row.revision,
                "account_epoch": user.security_epoch,
                "portal_confirmed_at": wire_time(now),
                "valid_until": wire_time(row.valid_until),
            }
            row.reconciliation_pending, row.next_check_at = True, now
            portal_session.last_activity_at = now
            enqueue(
                session,
                universe.backend_id,
                row.desired_snapshot,
                now,
                membership_id=row.id,
                universe_id=universe.id,
            )
            return {"status": "pending"}
