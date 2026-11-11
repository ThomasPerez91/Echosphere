"""Authenticated operations commit their effect and immutable result together."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from app.ai.models import AIController
from app.control.contracts import Access, HandOver, NameEmpire, Provision, Revoke, Start, digest
from app.control.models import (
    ControlOperation,
    EmpireBinding,
    GameAccess,
    GameDevice,
    GamePrincipal,
)
from app.persistence.models import Empire, Universe

SERVICE = "portal-control"
ALLOWED = frozenset(
    (
        "provision_universe",
        "start_universe",
        "name_empire",
        "hand_over_empire",
        "set_universe_access",
        "revoke_sessions",
        "get_operation",
        "get_access_revision",
    )
)


class ControlError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


def authorize(service, operation):
    if service != SERVICE or operation not in ALLOWED:
        raise ControlError("service_denied", 403)


def account_lock(session, identifier):
    session.execute(
        insert(GamePrincipal)
        .values(global_user_id=identifier, account_epoch=0)
        .on_conflict_do_nothing()
    )
    return session.get(GamePrincipal, identifier, with_for_update=True)


def snapshot(row):
    return row.snapshot if row else None


class _Clock:
    """Adapter: the scheduler expects an object with now(); Control keeps a plain callable."""

    def __init__(self, now):
        self.now = now


class Control:
    def __init__(self, factory, clock=None):
        self.factory = factory
        self.clock = clock or (lambda: datetime.now(UTC))

    def apply(self, service, operation):
        authorize(service, operation.message.kind)
        # The receipt digest is the one of the operation as sent (fields left to their defaults
        # are not part of it): Portal computes it on its own envelope, without Game's defaults.
        # Rows stored before this rule carry the digest of the full dump: still recognised.
        checksum = digest(operation.model_dump(mode="json", exclude_unset=True))
        legacy = digest(operation.model_dump(mode="json"))
        with self.factory.begin() as session:
            lock = int.from_bytes(
                hashlib.sha256(f"{service}:{operation.operation_id}".encode()).digest()[:8],
                signed=True,
            )
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
            previous = session.get(ControlOperation, (service, operation.operation_id))
            if previous:
                if previous.request_digest not in (checksum, legacy):
                    raise ControlError("operation_content_conflict")
                if previous.request_digest != checksum:
                    previous.request_digest = checksum  # same content, the caller's digest
                    session.flush()
                return self.receipt(previous)
            message = operation.message
            if isinstance(message, Provision):
                result = self.provision(session, message)
            elif isinstance(message, Start):
                result = self.start(session, message)
            elif isinstance(message, NameEmpire):
                result = self.name_empire(session, message)
            elif isinstance(message, HandOver):
                result = self.hand_over(session, message)
            elif isinstance(message, Access):
                result = self.access(session, message)
            elif isinstance(message, Revoke):
                result = self.revoke(session, message)
            row = ControlOperation(
                service_id=service,
                operation_id=operation.operation_id,
                request_digest=checksum,
                result=result,
                created_at=self.clock(),
                version=1,
            )
            session.add(row)
            session.flush()
            return self.receipt(row)

    @staticmethod
    def receipt(row):
        return {
            "operation_id": str(row.operation_id),
            "request_digest": row.request_digest,
            "result": row.result,
        }

    def operation(self, service, identifier):
        authorize(service, "get_operation")
        with self.factory() as session:
            row = session.get(ControlOperation, (service, identifier))
            if row is None:
                raise ControlError("operation_not_found", 404)
            return self.receipt(row)

    def revision(self, service, identifier):
        authorize(service, "get_access_revision")
        with self.factory() as session:
            row = session.get(GameAccess, identifier)
            if row is None:
                raise ControlError("access_not_found", 404)
            return {"snapshot": snapshot(row)}

    def provision(self, session, message):
        # Serialize the shared Universe UUID without acquiring another account/stream lock.
        session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": int.from_bytes(message.universe_id.bytes[:8], signed=True)},
        )
        row = session.get(Universe, message.universe_id)
        if row is None:
            session.add(Universe(id=message.universe_id, name=message.name, seed=message.seed))
        elif row.name != message.name or row.seed != message.seed:
            raise ControlError("universe_content_conflict")
        return {"status": "applied", "universe_id": str(message.universe_id), "name": message.name}

    def start(self, session, message):
        """Same atomic bootstrap as the operator CLI, in the operation transaction: the immutable
        receipt and the started world commit together, a retried delivery replays the receipt."""
        from app.ai.bootstrap import bootstrap
        from app.ai.controller import AIDenied
        from app.colony.rules import load_ruleset
        from app.simulation.scheduler import IdempotencyConflict
        from app.simulation.service import TimeEngine

        clock = _Clock(self.clock)
        try:
            started = bootstrap(
                session,
                TimeEngine(self.factory, clock),
                message.universe_id,
                message.name,
                message.seed,
                list(message.profiles),
                clock.now(),
                rules=load_ruleset(message.ruleset),
                humans=message.humans,
                size=message.size,
                sandbox=message.sandbox,
                shape=message.shape,
            )
        except IdempotencyConflict:
            raise ControlError("universe_content_conflict") from None
        except AIDenied as error:
            raise ControlError(str(error.args[0]) if error.args else "start_denied", 409) from None
        seats = [actor["empire_id"] for actor in started["actors"] if actor["profile"] is None]
        result = {
            "status": "applied",
            "universe_id": str(message.universe_id),
            "name": message.name,
            "human_empire_id": seats[0],
            "started_at": started["started_at"],
        }
        if message.family != "solo":
            result["human_empire_ids"] = seats  # seat order = starting-site order
        return result

    @staticmethod
    def _empire(session, message):
        # Same parent row lock as the access grant and AI activation paths.
        empire = session.scalar(
            select(Empire).where(Empire.id == message.empire_id).with_for_update()
        )
        if empire is None or empire.universe_id != message.universe_id:
            raise ControlError("empire_scope_denied", 403)
        return empire

    def name_empire(self, session, message):
        """Q60: renames a human Empire; an AI-controlled Empire keeps its name."""
        empire = self._empire(session, message)
        if session.scalar(select(AIController.id).where(AIController.empire_id == empire.id)):
            raise ControlError("empire_ai_controlled", 409)
        empire.name = message.name
        return {
            "status": "applied",
            "universe_id": str(message.universe_id),
            "empire_id": str(empire.id),
            "name": message.name,
        }

    def hand_over(self, session, message):
        """Q60: the Empire of a player who left goes on under a server AI with the same rules
        (no resource, unit or knowledge granted). Idempotent: an existing controller replays."""
        from app.ai.controller import AIDenied, activate

        empire = self._empire(session, message)
        current = session.scalar(select(AIController).where(AIController.empire_id == empire.id))
        if current is None:
            bound = select(EmpireBinding.empire_id).where(EmpireBinding.empire_id == empire.id)
            if session.scalar(bound.limit(1)):
                # The seat is still bound: Portal's revocation has not been applied yet.
                raise ControlError("empire_still_bound", 409)
            empire.controller_type = "ai"
            try:
                current = activate(
                    session, message.universe_id, empire.id, message.profile, self.clock()
                )
            except AIDenied as error:
                code = str(error.args[0]) if error.args else "hand_over_denied"
                raise ControlError(code) from None
        elif current.profile != message.profile:
            raise ControlError("hand_over_conflict")
        return {
            "status": "applied",
            "universe_id": str(message.universe_id),
            "empire_id": str(empire.id),
            "profile": current.profile,
        }

    def access(self, session, message):
        principal = account_lock(session, message.global_user_id)
        if message.portal_confirmed_at > self.clock():
            raise ControlError("confirmation_in_future", 422)
        if session.get(Universe, message.universe_id) is None:
            raise ControlError("universe_not_found", 404)
        row = session.get(GameAccess, message.membership_id)
        wire = message.model_dump(mode="json")
        if row and (
            row.global_user_id != message.global_user_id or row.universe_id != message.universe_id
        ):
            raise ControlError("membership_scope_conflict")
        if row and message.revision < row.revision:
            return {"status": "superseded", "snapshot": snapshot(row)}
        if row and message.revision == row.revision:
            if row.snapshot_digest != digest(wire):
                raise ControlError("access_revision_conflict")
            return {"status": "applied", "snapshot": snapshot(row)}
        existing = session.scalar(
            select(GameAccess.membership_id).where(
                GameAccess.global_user_id == message.global_user_id,
                GameAccess.universe_id == message.universe_id,
            )
        )
        if existing is not None and existing != message.membership_id:
            raise ControlError("membership_scope_conflict")
        if row:
            changed = row.status != message.status or row.snapshot["bindings"] != wire["bindings"]
            if message.access_epoch < row.access_epoch or (
                changed and message.access_epoch <= row.access_epoch
            ):
                raise ControlError("access_epoch_conflict")
        for binding in message.bindings:
            empire = session.scalar(
                select(Empire).where(Empire.id == binding.empire_id).with_for_update()
            )
            if empire is None or empire.universe_id != message.universe_id:
                raise ControlError("empire_scope_denied", 403)
            if (
                session.scalar(
                    select(AIController.id).where(AIController.empire_id == empire.id).limit(1)
                )
                is not None
            ):
                raise ControlError("empire_ai_controlled", 409)
        principal.account_epoch = max(principal.account_epoch, message.account_epoch)
        if row is None:
            row = GameAccess(
                membership_id=message.membership_id,
                global_user_id=message.global_user_id,
                universe_id=message.universe_id,
            )
            session.add(row)
        row.revision, row.access_epoch, row.status = (
            message.revision,
            message.access_epoch,
            message.status,
        )
        row.portal_confirmed_at, row.valid_until = message.portal_confirmed_at, message.valid_until
        row.snapshot, row.snapshot_digest = wire, digest(wire)
        session.flush()
        session.execute(
            delete(EmpireBinding).where(EmpireBinding.membership_id == row.membership_id)
        )
        for binding in message.bindings:
            session.add(
                EmpireBinding(
                    membership_id=row.membership_id,
                    universe_id=row.universe_id,
                    empire_id=binding.empire_id,
                    permissions=binding.permissions,
                )
            )
        return {"status": "applied", "snapshot": wire}

    def revoke(self, session, message):
        principal = account_lock(session, message.global_user_id)
        if message.scope == "account":
            principal.account_epoch = max(principal.account_epoch, message.epoch)
            epoch = principal.account_epoch
        else:
            device = session.get(GameDevice, (message.global_user_id, message.device_id))
            if device is None:
                device = GameDevice(
                    global_user_id=message.global_user_id,
                    device_id=message.device_id,
                    device_epoch=message.epoch,
                )
                session.add(device)
            else:
                device.device_epoch = max(device.device_epoch, message.epoch)
            epoch = device.device_epoch
        return {
            "status": "applied",
            "scope": message.scope,
            "global_user_id": str(message.global_user_id),
            "device_id": str(message.device_id) if message.device_id else None,
            "epoch": epoch,
        }
