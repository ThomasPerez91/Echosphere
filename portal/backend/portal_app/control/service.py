"""Trusted technical orchestration and the self-service SOLO creation (UX-API-02, Q59)."""

import hashlib
import json
import secrets
from datetime import UTC, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError
from portal_app.control.models import ControlOutbox, UniverseMembership, UniverseReference
from portal_app.sessions.service import Sessions, check_csrf

PERMISSIONS = frozenset(("colony.read", "colony.construct", "colony.cancel",
    "research.read", "research.start", "research.cancel",
    "galaxy.read", "exploration.read", "exploration.start",
    "fleet.read", "fleet.build", "fleet.command", "colony.expand",
    "combat.read", "combat.attack", "relations.read", "relations.negotiate"))


# AI profiles the Game ruleset knows (app.ai.rules.PROFILES); Game validates them again.
AI_PROFILES = frozenset(("economic_cautious", "expansionist"))
# A5 (09/11/2026), COL-11 (10/11/2026): every new game is v0.11 (galaxy-v2, opportunities,
# unique key buildings, fast early pace); existing games keep their pinned ruleset.
CREATION_RULESET = "v0.12"


# Q61 caps per map size (galaxy-v2): a pre-check for a clear message; Game's pinned ruleset
# remains the authority and refuses any start beyond it.
EMPIRE_CAPS = {100: 4, 300: 12, 500: 20, 1000: 40, 2000: 40}
DEFAULT_SIZE = 100
MAX_HUMANS, MAX_AI = 10, 30
INVITE_MODES = frozenset(("link", "email"))
# Galaxy shapes (ruleset v0.12, recette 11/11/2026); `random` lets Game draw one from the seed.
GALAXY_SHAPES = frozenset(("random", "elliptical", "spiral2", "spiral4", "irregular", "clusters"))


# Delivery errors after which the Game answered but refused the start: retries go on (at-least-once
# outbox), yet the creator must know it will probably not succeed on its own.
REFUSED_ERRORS = frozenset({"remote_conflict", "remote_refused", "invalid_receipt"})
DELAYED_AFTER_ATTEMPTS = 3


def creation_state(pending):
    """What the creator sees while a started universe is not playable yet.

    `pending` is the newest undelivered control message of the universe (or None). The error codes
    are the transport's own short codes, never a remote body or a stack trace.
    """
    if pending is None or not pending.last_error:
        return "starting"
    if pending.last_error in REFUSED_ERRORS:
        return "refused"
    return "delayed" if pending.attempts >= DELAYED_AFTER_ATTEMPTS else "starting"


def creation_request(body):
    """Validated SOLO or PRIVATE (multi) creation intention, or PublicError. Pure function."""
    base = {"request_id", "name", "family", "profiles"}
    if not isinstance(body, dict) or not base <= set(body):
        raise PublicError("invalid_creation")
    family = body["family"]
    if family not in ("solo", "private"):
        raise PublicError("family_unavailable", 422)
    # Q60: the creator may name their Empire; optional so earlier clients keep working.
    # Q61: the map size is optional (100 systems by default).
    # Test game (recette 10/11/2026): optional, solo only, refused in production by `create`.
    # Galaxy shape (recette 11/11/2026): optional, any family.
    optional = {"empire_name", "size", "sandbox", "shape"}
    if set(body) - optional != (base if family == "solo" else base | {"humans", "invite"}):
        raise PublicError("invalid_creation")
    humans = 1 if family == "solo" else body["humans"]
    if family == "private" and (
        type(humans) is not int or not 2 <= humans <= MAX_HUMANS
        or body["invite"] not in INVITE_MODES
    ):
        raise PublicError("invalid_creation")
    name, profiles = body["name"], body["profiles"]
    if not isinstance(name, str) or not 3 <= len(name.strip()) <= 60 or name != name.strip():
        raise PublicError("invalid_creation")
    if (
        not isinstance(profiles, list)
        or len(profiles) > MAX_AI
        or any(not isinstance(p, str) or p not in AI_PROFILES for p in profiles)
    ):
        raise PublicError("invalid_creation")
    size = body.get("size", DEFAULT_SIZE)
    if type(size) is not int or size not in EMPIRE_CAPS:
        raise PublicError("invalid_creation")
    if humans + len(profiles) > EMPIRE_CAPS[size]:
        raise PublicError("too_many_empires")
    try:
        request_id = UUID(str(body["request_id"]))
    except ValueError:
        raise PublicError("invalid_creation") from None
    wanted = {
        "request_id": request_id, "name": name, "family": family, "profiles": list(profiles),
        "size": size,
    }
    if family == "private":
        wanted.update(humans=humans, invite=body["invite"])
    if "sandbox" in body:
        if type(body["sandbox"]) is not bool or (body["sandbox"] and family != "solo"):
            raise PublicError("invalid_creation")
        if body["sandbox"]:
            wanted["sandbox"] = True
    if "shape" in body:
        if body["shape"] not in GALAXY_SHAPES:
            raise PublicError("invalid_creation")
        wanted["shape"] = body["shape"]
    if "empire_name" in body:
        from portal_app.control.life import empire_name

        wanted["empire_name"] = empire_name(body["empire_name"])
    return wanted


def start_receipt(message, result):
    """Seats (human Empires, creator's first) when Game's receipt matches this start, else None."""
    if (
        result.get("status") != "applied"
        or result.get("universe_id") != message["universe_id"]
        or result.get("name") != message["name"]
        or not isinstance(result.get("human_empire_id"), str)
        or not isinstance(result.get("started_at"), str)
    ):
        return None
    humans = message.get("humans", 1)
    seats = result.get("human_empire_ids", [result["human_empire_id"]])
    if (
        not isinstance(seats, list)
        or len(seats) != humans
        or seats[0] != result["human_empire_id"]
        or (humans == 1 and "human_empire_ids" in result)
    ):
        return None
    try:
        seats = [str(UUID(seat)) for seat in seats]
    except (TypeError, ValueError):
        return None
    return seats if len(set(seats)) == len(seats) else None


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def wire_time(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def normalized_bindings(bindings):
    result = []
    for binding in bindings:
        if set(binding) != {"empire_id", "permissions"}:
            raise PublicError("invalid_binding")
        permissions = binding["permissions"]
        if (
            not isinstance(permissions, list)
            or not permissions
            or len(set(permissions)) != len(permissions)
            or not set(permissions) <= PERMISSIONS
        ):
            raise PublicError("invalid_binding")
        result.append(
            {"empire_id": str(UUID(str(binding["empire_id"]))), "permissions": sorted(permissions)}
        )
    if len(result) > 100 or len({b["empire_id"] for b in result}) != len(result):
        raise PublicError("invalid_binding")
    return sorted(result, key=lambda b: b["empire_id"])


def enqueue(session, backend, message, now, **references):
    identifier = uuid4()
    envelope = {"version": 1, "operation_id": str(identifier), "message": message}
    row = ControlOutbox(
        id=identifier,
        backend_id=backend,
        envelope=envelope,
        request_digest=digest(envelope),
        created_at=now,
        next_attempt_at=now,
        **references,
    )
    session.add(row)
    return row


class Lobby:
    def __init__(self, accounts):
        self.accounts = accounts

    def provision(self, identifier, name, seed, backend):
        if (
            backend not in self.accounts.settings.control_targets
            or not name.strip()
            or len(name) > 120
            or not 1 <= len(seed) <= 200
        ):
            raise PublicError("invalid_provision")
        identifier = UUID(str(identifier))
        with self.accounts.factory.begin() as session:
            if session.get(UniverseReference, identifier):
                raise PublicError("universe_already_referenced", 409)
            now = self.accounts.clock()
            session.add(
                UniverseReference(id=identifier, backend_id=backend, name=name, created_at=now)
            )
            session.flush()
            row = enqueue(
                session,
                backend,
                {
                    "kind": "provision_universe",
                    "universe_id": str(identifier),
                    "name": name,
                    "seed": seed,
                },
                now,
                universe_id=identifier,
            )
            return str(row.id)

    def create(self, raw, proof, body, peer="unknown"):
        """Self-service SOLO universe: one Portal transaction stores the intention and the
        start_universe delivery. Replaying the same request_id returns the same universe."""
        check_csrf(raw, proof)
        wanted = creation_request(body)
        target = self.accounts.settings.creation_target
        if target not in self.accounts.settings.control_targets:
            raise PublicError("creation_unavailable", 503)
        if wanted.get("sandbox") and self.accounts.settings.production:
            raise PublicError("sandbox_unavailable", 403)
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            existing = session.scalar(
                select(UniverseReference).where(
                    UniverseReference.created_by == user.id,
                    UniverseReference.creation_request_id == wanted["request_id"],
                )
            )
            options = {"family": wanted["family"], "profiles": wanted["profiles"],
                       "ruleset": CREATION_RULESET, "size": wanted["size"]}
            if wanted["family"] == "private":
                options.update(humans=wanted["humans"], invite=wanted["invite"])
            if "empire_name" in wanted:
                options["empire_name"] = wanted["empire_name"]
            if wanted.get("sandbox"):
                options["sandbox"] = True
            if "shape" in wanted:
                options["shape"] = wanted["shape"]
            if existing is not None:
                if existing.name != wanted["name"] or existing.start_request != options:
                    raise PublicError("creation_request_conflict", 409)
                return {"universe_id": str(existing.id), "status": "starting"}
            self.accounts.limit("universe_create", peer, str(user.id))
            now, identifier = self.accounts.clock(), uuid4()
            session.add(
                UniverseReference(
                    id=identifier, backend_id=target, name=wanted["name"], created_at=now,
                    created_by=user.id, creation_request_id=wanted["request_id"],
                    start_request=options,
                )
            )
            session.flush()
            message = {
                "kind": "start_universe",
                "universe_id": str(identifier),
                "name": wanted["name"],
                # Server-side randomness; never chosen by the browser.
                "seed": secrets.token_urlsafe(24),
                "family": wanted["family"],
                "ruleset": CREATION_RULESET,
                "size": wanted["size"],
                "profiles": wanted["profiles"],
            }
            if wanted["family"] == "private":
                message["humans"] = wanted["humans"]
            if wanted.get("sandbox"):
                message["sandbox"] = True
            if "shape" in wanted:
                message["shape"] = wanted["shape"]
            enqueue(session, target, message, now, universe_id=identifier)
            return {"universe_id": str(identifier), "status": "starting"}

    def set_access(self, user_id, universe_id, status, bindings):
        if status not in ("active", "suspended", "revoked"):
            raise PublicError("invalid_access")
        bindings = normalized_bindings(bindings)
        with self.accounts.factory.begin() as session:
            user = session.get(User, UUID(str(user_id)), with_for_update=True)
            universe = session.get(UniverseReference, UUID(str(universe_id)))
            return self.grant(session, user, universe, status, bindings)

    def grant(self, session, user, universe, status, bindings):
        """Membership intention + access delivery in the caller's transaction (user locked)."""
        if user is None or universe is None or (status == "active" and user.status != "active"):
            raise PublicError("access_scope_denied", 403)
        row = session.scalar(
            select(UniverseMembership).where(
                UniverseMembership.user_id == user.id,
                UniverseMembership.universe_id == universe.id,
            )
        )
        now = self.accounts.clock()
        if row is None:
            row = UniverseMembership(
                id=uuid4(), user_id=user.id, universe_id=universe.id, revision=1, access_epoch=1
            )
            session.add(row)
        else:
            row.revision += 1
            if row.desired_status != status or row.bindings != bindings:
                row.access_epoch += 1
        row.desired_status, row.bindings = status, bindings
        row.portal_confirmed_at, row.valid_until = now, now + timedelta(hours=8)
        row.next_check_at, row.reconciliation_pending = now, True
        message = {
            "kind": "set_universe_access",
            "membership_id": str(row.id),
            "global_user_id": str(user.id),
            "universe_id": str(universe.id),
            "revision": row.revision,
            "access_epoch": row.access_epoch,
            "account_epoch": user.security_epoch,
            "status": status,
            "portal_confirmed_at": wire_time(now),
            "valid_until": wire_time(row.valid_until),
            "bindings": bindings,
        }
        row.desired_snapshot = message
        session.flush()
        delivery = enqueue(
            session,
            universe.backend_id,
            message,
            now,
            membership_id=row.id,
            universe_id=universe.id,
        )
        return {
            "membership_id": str(row.id),
            "operation_id": str(delivery.id),
            "revision": row.revision,
        }

    def read(self, raw):
        with self.accounts.factory.begin() as session:
            _, user = Sessions(self.accounts).locked(session, raw)
            rows = session.execute(
                select(UniverseMembership, UniverseReference)
                .join(UniverseReference, UniverseReference.id == UniverseMembership.universe_id)
                .where(
                    UniverseMembership.user_id == user.id,
                    UniverseReference.deleted_at.is_(None),
                )
                .order_by(UniverseReference.created_at, UniverseReference.id)
            ).all()
            memberships = []
            now = self.accounts.clock()
            for row, universe in rows:
                applied = row.applied_snapshot
                confirmed = bool(
                    universe.provisioned
                    and applied == row.desired_snapshot
                    and not row.reconciliation_pending
                )
                memberships.append(
                    {
                        "membership_id": str(row.id),
                        "universe_id": str(universe.id),
                        "name": universe.name,
                        "desired_status": row.desired_status,
                        "applied_status": applied["status"] if applied else None,
                        "delivery_state": "applied" if confirmed else "pending",
                        "revision": row.revision,
                        "valid_until": wire_time(row.valid_until),
                        "expired": now >= row.valid_until,
                        "last_checked_at": wire_time(row.last_checked_at)
                        if row.last_checked_at
                        else None,
                        "entry_available": bool(
                            confirmed
                            and user.email_verified_at is not None
                            and row.desired_status == "active"
                            and now < row.valid_until
                            and universe.backend_id in self.accounts.settings.game_public_targets
                        ),
                        "entry_url": (
                            self.accounts.settings.game_public_targets.get(universe.backend_id, "")
                            + f"/api/game/{universe.id}/start"
                        )
                        if universe.backend_id in self.accounts.settings.game_public_targets
                        else None,
                    }
                )
            from portal_app.account_security.models import AccountRevocation
            from portal_app.sessions.models import LogoutRequest

            revocations = []
            for model, scope in ((AccountRevocation, "account"), (LogoutRequest, "device")):
                for item in session.scalars(
                    select(model)
                    .where(model.user_id == user.id)
                    .order_by(model.created_at.desc())
                    .limit(20)
                ):
                    revocations.append(
                        {
                            "scope": scope,
                            "state": item.state,
                            "created_at": wire_time(item.created_at),
                        }
                    )
            from portal_app.control.invitations import taken_seats
            from portal_app.control.models import UniverseInvitation

            references = {universe.id: universe for _, universe in rows}
            members = {member.id: member for member, _ in rows}
            for item in memberships:
                universe = references[UUID(item["universe_id"])]
                options = universe.start_request or {}
                item["family"] = options.get("family", "operator")
                item["sandbox"] = bool(options.get("sandbox"))
                item["creator"] = universe.created_by == user.id
                if universe.started_at is not None:
                    item["started_at"] = wire_time(universe.started_at)
                member = members[UUID(item["membership_id"])]
                # Q60: chosen Empire name, archived solo game, multi game left by this player.
                item["empire_name"] = member.empire_name
                item["archived"] = universe.archived_at is not None
                item["left"] = member.left_at is not None
                if options.get("family") == "private":
                    item["seats_total"] = options.get("humans", 1)
                    item["seats_taken"] = len(taken_seats(session, universe))
                    if item["creator"]:
                        item["invite_mode"] = options.get("invite")
                        item["sent_invitations"] = [
                            {"id": str(sent.id), "email": sent.email, "state": sent.state,
                             "expires_at": wire_time(sent.expires_at)}
                            for sent in session.scalars(
                                select(UniverseInvitation)
                                .where(UniverseInvitation.universe_id == universe.id,
                                       UniverseInvitation.mode == "email")
                                .order_by(UniverseInvitation.created_at.desc())
                                .limit(20)
                            )
                        ]
            joined = {UUID(item["universe_id"]) for item in memberships}
            invitations = [
                {"id": str(row.id), "universe_id": str(row.universe_id), "name": name,
                 "expires_at": wire_time(row.expires_at)}
                for row, name in session.execute(
                    select(UniverseInvitation, UniverseReference.name)
                    .join(UniverseReference, UniverseReference.id == UniverseInvitation.universe_id)
                    .where(UniverseInvitation.mode == "email",
                           UniverseInvitation.state == "open",
                           UniverseInvitation.email == user.email_key,
                           UniverseInvitation.expires_at > now)
                    .order_by(UniverseInvitation.created_at)
                    .limit(20)
                )
                if row.universe_id not in joined
            ]
            creations = [
                {
                    "universe_id": str(universe.id),
                    "name": universe.name,
                    "created_at": wire_time(universe.created_at),
                    "state": creation_state(
                        session.scalar(
                            select(ControlOutbox)
                            .where(
                                ControlOutbox.universe_id == universe.id,
                                ControlOutbox.state == "pending",
                            )
                            .order_by(ControlOutbox.created_at.desc())
                            .limit(1)
                        )
                    ),
                }
                for universe in session.scalars(
                    select(UniverseReference)
                    .where(
                        UniverseReference.created_by == user.id,
                        UniverseReference.deleted_at.is_(None),
                    )
                    .order_by(UniverseReference.created_at, UniverseReference.id)
                )
                # Started universes appear as memberships once access is granted.
                if universe.id not in joined
            ]
            return {
                "memberships": memberships,
                "creations": creations,
                "invitations": invitations,
                "revocations": revocations,
                "handoff_available": True,
            }
