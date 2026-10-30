"""Trusted technical orchestration. No public create/join policy is introduced."""

import hashlib
import json
from datetime import UTC, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError
from portal_app.control.models import ControlOutbox, UniverseMembership, UniverseReference
from portal_app.sessions.service import Sessions

PERMISSIONS = frozenset(("colony.read", "colony.construct", "colony.cancel"))


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

    def set_access(self, user_id, universe_id, status, bindings):
        if status not in ("active", "suspended", "revoked"):
            raise PublicError("invalid_access")
        bindings = normalized_bindings(bindings)
        with self.accounts.factory.begin() as session:
            user = session.get(User, UUID(str(user_id)), with_for_update=True)
            universe = session.get(UniverseReference, UUID(str(universe_id)))
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
                .where(UniverseMembership.user_id == user.id)
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
                        "entry_available": False,
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
            return {
                "memberships": memberships,
                "revocations": revocations,
                "handoff_available": False,
            }
