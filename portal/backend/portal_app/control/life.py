"""Q60 life of a game: the player's Empire name, leaving a multi game, archiving a solo game.

Every write runs under the account lock, then the universe row lock (same order as creation,
invitations and the control worker). Game effects go through the control outbox only.
"""

from uuid import UUID

from sqlalchemy import select

from portal_app.accounts.security import PublicError
from portal_app.control.models import UniverseMembership, UniverseReference
from portal_app.control.service import PERMISSIONS, Lobby, enqueue
from portal_app.sessions.service import Sessions, check_csrf

# An archived solo game stays readable (reports, map) but no longer playable.
READ_ONLY = sorted(p for p in PERMISSIONS if p.endswith(".read"))
# The AI that takes over a seat left in a multi game: the cautious, non-offensive profile.
HAND_OVER_PROFILE = "economic_cautious"


def empire_name(value):
    """2 to 40 visible characters after trimming; the same rule as Game's `name_empire`."""
    if not isinstance(value, str):
        raise PublicError("invalid_empire_name", 422)
    value = " ".join(value.split())
    if not 2 <= len(value) <= 40 or any(ord(c) < 32 or 127 <= ord(c) < 160 for c in value):
        raise PublicError("invalid_empire_name", 422)
    return value


def name_message(universe, empire_id, name):
    return {
        "kind": "name_empire",
        "universe_id": str(universe.id),
        "empire_id": str(empire_id),
        "name": name,
    }


def set_name(session, accounts, universe, member, name):
    """Records the name for `Mes parties` and asks Game to rename the bound Empire."""
    member.empire_name = name
    enqueue(
        session,
        universe.backend_id,
        name_message(universe, member.bindings[0]["empire_id"], name),
        accounts.clock(),
        universe_id=universe.id,
    )


class GameLife:
    def __init__(self, accounts):
        self.accounts = accounts

    def _member(self, session, raw):
        _, user = Sessions(self.accounts).locked(session, raw)
        return user

    def _target(self, session, user, universe_id):
        try:
            identifier = UUID(str(universe_id))
        except ValueError:
            raise PublicError("universe_not_found", 404) from None
        universe = session.get(UniverseReference, identifier, with_for_update=True)
        member = session.scalar(
            select(UniverseMembership)
            .where(
                UniverseMembership.user_id == user.id,
                UniverseMembership.universe_id == identifier,
            )
            .with_for_update()
        )
        if universe is None or member is None:
            raise PublicError("universe_not_found", 404)
        return universe, member

    def rename(self, raw, proof, universe_id, name):
        check_csrf(raw, proof)
        name = empire_name(name)
        with self.accounts.factory.begin() as session:
            user = self._member(session, raw)
            universe, member = self._target(session, user, universe_id)
            if (
                member.desired_status != "active"
                or member.left_at is not None
                or universe.archived_at is not None
                or len(member.bindings) != 1
            ):
                raise PublicError("rename_unavailable", 409)
            if member.empire_name != name:
                set_name(session, self.accounts, universe, member, name)
            return {"empire_name": name}

    def leave(self, raw, proof, universe_id):
        """Solo: archived, rights reduced to reading. Multi: seat revoked, then the Empire goes
        on under a server AI (Game refuses the hand-over while the seat is still bound)."""
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            user = self._member(session, raw)
            universe, member = self._target(session, user, universe_id)
            family = (universe.start_request or {}).get("family")
            if member.left_at is not None:
                return {"status": "left"}
            if family == "solo" and universe.created_by == user.id:
                if universe.archived_at is None:
                    if len(member.bindings) != 1:
                        raise PublicError("leave_unavailable", 409)
                    universe.archived_at = self.accounts.clock()
                    seat = member.bindings[0]["empire_id"]
                    Lobby(self.accounts).grant(
                        session, user, universe, "active",
                        [{"empire_id": seat, "permissions": READ_ONLY}],
                    )
                return {"status": "archived"}
            if family != "private" or len(member.bindings) != 1:
                raise PublicError("leave_unavailable", 409)
            now = self.accounts.clock()
            seat = member.bindings[0]["empire_id"]
            member.left_at = now
            # The seat is never offered again: taken_seats counts it.
            universe.left_seats = [*(universe.left_seats or []), seat]
            Lobby(self.accounts).grant(session, user, universe, "revoked", [])
            enqueue(
                session,
                universe.backend_id,
                {
                    "kind": "hand_over_empire",
                    "universe_id": str(universe.id),
                    "empire_id": seat,
                    "profile": HAND_OVER_PROFILE,
                },
                now,
                universe_id=universe.id,
            )
            return {"status": "left"}

    def delete(self, raw, proof, universe_id):
        """Recette 09/11/2026: the creator removes a solo game, or a creation that never started,
        from the lists. Access to Game is revoked; nothing is shown again. A multi game is left
        (its other players go on), never deleted."""
        check_csrf(raw, proof)
        with self.accounts.factory.begin() as session:
            user = self._member(session, raw)
            try:
                identifier = UUID(str(universe_id))
            except ValueError:
                raise PublicError("universe_not_found", 404) from None
            universe = session.get(UniverseReference, identifier, with_for_update=True)
            if universe is None or universe.created_by != user.id:
                raise PublicError("universe_not_found", 404)
            if universe.deleted_at is not None:
                return {"status": "deleted"}
            family = (universe.start_request or {}).get("family")
            if family == "private" and universe.human_empire_id is not None:
                raise PublicError("delete_unavailable", 409)
            member = session.scalar(
                select(UniverseMembership)
                .where(
                    UniverseMembership.user_id == user.id,
                    UniverseMembership.universe_id == identifier,
                )
                .with_for_update()
            )
            if member is not None and member.desired_status != "revoked":
                Lobby(self.accounts).grant(session, user, universe, "revoked", [])
            universe.deleted_at = self.accounts.clock()
            return {"status": "deleted"}
