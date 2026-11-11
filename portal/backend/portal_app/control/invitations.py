"""UX-API-03 multi (Q59): invitations by link or by email, chosen once by the creator.

A seat is a human Empire created at start. Joining grants the next free seat through the same
membership/access path as the creator's own grant; a link never names an Empire and the token
is stored only as a digest. Every write runs under the account lock, then the universe row lock.
"""

import json
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from portal_app.accounts.security import PublicError, normalize_email, token_digest
from portal_app.control.life import empire_name, set_name
from portal_app.control.models import (
    InvitationEmailOutbox,
    UniverseInvitation,
    UniverseMembership,
    UniverseReference,
)
from portal_app.control.service import PERMISSIONS, Lobby
from portal_app.sessions.service import Sessions, check_csrf

LINK_LIFETIME = timedelta(days=7)
EMAIL_LIFETIME = timedelta(days=7)


def invite_token(value):
    """Shape of a link token; anything else is refused before any lookup."""
    return isinstance(value, str) and 40 <= len(value) <= 64 and value.replace("-", "").replace(
        "_", ""
    ).isalnum()


def taken_seats(session, universe):
    """Seats already bound to a membership of this universe (any status keeps its seat), and
    seats handed over to an AI when their player left (Q60): never offered again."""
    seats = set(universe.seats or [])
    taken = set(universe.left_seats or []) & seats
    for bindings in session.scalars(
        select(UniverseMembership.bindings).where(UniverseMembership.universe_id == universe.id)
    ):
        taken |= {binding["empire_id"] for binding in bindings} & seats
    return taken


def free_seats(session, universe):
    taken = taken_seats(session, universe)
    return [seat for seat in universe.seats or [] if seat not in taken]


class Invitations:
    def __init__(self, accounts):
        self.accounts = accounts

    def owned(self, session, user, universe_id, mode):
        universe = session.get(UniverseReference, UUID(str(universe_id)), with_for_update=True)
        if universe is None or universe.created_by != user.id:
            raise PublicError("universe_not_found", 404)
        options = universe.start_request or {}
        if options.get("family") != "private":
            raise PublicError("invitations_unavailable", 409)
        if options.get("invite") != mode:
            raise PublicError("invitation_mode_mismatch", 409)
        return universe

    def link(self, raw, proof, universe_id):
        """A fresh shareable link; the previous open link stops working."""
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            universe = self.owned(session, user, universe_id, "link")
            now = self.accounts.clock()
            for row in session.scalars(
                select(UniverseInvitation).where(
                    UniverseInvitation.universe_id == universe.id,
                    UniverseInvitation.mode == "link",
                    UniverseInvitation.state == "open",
                )
            ):
                row.state = "revoked"
            session.flush()
            token = secrets.token_urlsafe(32)
            session.add(
                UniverseInvitation(
                    id=uuid4(), universe_id=universe.id, created_by=user.id, mode="link",
                    token_digest=token_digest(token), created_at=now,
                    expires_at=now + LINK_LIFETIME,
                )
            )
            return {
                # Fragment: the token never reaches server logs or the Referer header.
                "url": f"{self.accounts.settings.public_origin}/rejoindre#invite={token}",
                "expires_at": (now + LINK_LIFETIME).isoformat(),
            }

    def send(self, raw, proof, universe_id, address, peer="unknown"):
        """One email invitation for one address, used once, delivered by the email worker."""
        check_csrf(raw, proof)
        recipient, key = normalize_email(address if isinstance(address, str) else "")
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            universe = self.owned(session, user, universe_id, "email")
            if key == user.email_key:
                raise PublicError("invitation_self", 422)
            self.accounts.limit("universe_create", peer, str(user.id))
            existing = session.scalar(
                select(UniverseInvitation).where(
                    UniverseInvitation.universe_id == universe.id,
                    UniverseInvitation.mode == "email",
                    UniverseInvitation.state == "open",
                    UniverseInvitation.email == key,
                )
            )
            if existing is not None:
                raise PublicError("already_invited", 409)
            pending = session.scalars(
                select(UniverseInvitation.id).where(
                    UniverseInvitation.universe_id == universe.id,
                    UniverseInvitation.mode == "email",
                    UniverseInvitation.state == "open",
                )
            ).all()
            capacity = len(free_seats(session, universe)) if universe.seats is not None else (
                (universe.start_request or {}).get("humans", 1) - 1
            )
            if len(pending) >= capacity:
                raise PublicError("game_full", 409)
            now, token = self.accounts.clock(), secrets.token_urlsafe(32)
            invitation = UniverseInvitation(
                id=uuid4(), universe_id=universe.id, created_by=user.id, mode="email",
                token_digest=token_digest(token), email=key, created_at=now,
                expires_at=now + EMAIL_LIFETIME,
            )
            session.add(invitation)
            session.flush()
            outbox = InvitationEmailOutbox(id=uuid4(), invitation_id=invitation.id,
                                           created_at=now, next_attempt_at=now)
            payload = {"outbox_id": str(outbox.id), "invitation_id": str(invitation.id),
                       "recipient": recipient, "token": token, "universe": universe.name}
            outbox.payload_ciphertext = self.accounts.cipher().encrypt(
                json.dumps(payload).encode()
            ).decode()
            session.add(outbox)
            return {"invitation_id": str(invitation.id), "state": "open"}

    def revoke(self, raw, proof, invitation_id):
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            row = session.get(UniverseInvitation, UUID(str(invitation_id)), with_for_update=True)
            if row is None or row.created_by != user.id:
                raise PublicError("invitation_not_found", 404)
            if row.state == "open":
                row.state = "revoked"
            return {"state": row.state}

    def accept(self, raw, proof, token=None, invitation_id=None, name=None):
        """Join with a link token or an email invitation addressed to this account, optionally
        naming the Empire of the seat (Q60)."""
        check_csrf(raw, proof)
        if name is not None:
            name = empire_name(name)
        if (token is None) == (invitation_id is None) or (
            token is not None and not invite_token(token)
        ):
            raise PublicError("invitation_not_found", 404)
        if invitation_id is not None:
            try:
                invitation_id = UUID(str(invitation_id))
            except ValueError:
                raise PublicError("invitation_not_found", 404) from None
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            # Lock order account -> universe -> invitation, as for the creator's own writes.
            where = (
                UniverseInvitation.token_digest == token_digest(token)
                if token is not None
                else UniverseInvitation.id == invitation_id
            )
            target = session.scalar(select(UniverseInvitation.universe_id).where(where))
            if target is None:
                raise PublicError("invitation_not_found", 404)
            universe = session.get(UniverseReference, target, with_for_update=True)
            row = session.scalar(select(UniverseInvitation).where(where).with_for_update())
            now = self.accounts.clock()
            if row is None or row.state != "open" or now >= row.expires_at:
                raise PublicError("invitation_not_found", 404)
            if row.mode == "email" and row.email != user.email_key:
                raise PublicError("invitation_other_account", 403)
            member = session.scalar(
                select(UniverseMembership).where(
                    UniverseMembership.user_id == user.id,
                    UniverseMembership.universe_id == universe.id,
                )
            )
            if member is not None:
                if row.mode == "email":
                    row.state, row.accepted_by, row.accepted_at = "accepted", user.id, now
                return {"universe_id": str(universe.id), "status": "member"}
            if universe.seats is None:
                raise PublicError("game_starting", 409)
            seats = free_seats(session, universe)
            if not seats:
                raise PublicError("game_full", 409)
            granted = Lobby(self.accounts).grant(
                session, user, universe, "active",
                [{"empire_id": seats[0], "permissions": sorted(PERMISSIONS)}],
            )
            if name is not None:
                joined = session.get(UniverseMembership, UUID(granted["membership_id"]))
                set_name(session, self.accounts, universe, joined, name)
            if row.mode == "email":
                row.state, row.accepted_by, row.accepted_at = "accepted", user.id, now
            return {"universe_id": str(universe.id), "status": "joined"}

    def decline(self, raw, proof, invitation_id):
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            row = session.get(UniverseInvitation, UUID(str(invitation_id)), with_for_update=True)
            if row is None or row.mode != "email" or row.email != user.email_key:
                raise PublicError("invitation_not_found", 404)
            if row.state == "open":
                row.state = "declined"
            return {"state": row.state}
