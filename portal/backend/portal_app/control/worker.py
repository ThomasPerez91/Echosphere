"""At-least-once delivery; acknowledgements never stand for merely sending a request."""

import argparse
import json
import time
from datetime import timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import SQLAlchemyError

from portal_app.account_security.models import AccountRevocation
from portal_app.accounts.service import Accounts
from portal_app.control.models import ControlOutbox, UniverseMembership, UniverseReference
from portal_app.control.service import digest, enqueue
from portal_app.control.transport import DeliveryError, Transport
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine, create_session_factory
from portal_app.sessions.models import LogoutRequest


def stage_revocations(accounts, limit=50):
    # Existing C03/C04 source rows already commit atomically with local revocation.
    # Fan-out is itself durable/transactional and is never tied to a browser response.
    count = 0
    for model, source in (
        (AccountRevocation, "account_revocation_id"),
        (LogoutRequest, "logout_request_id"),
    ):
        with accounts.factory.begin() as session:
            rows = session.scalars(
                select(model)
                .where(
                    model.state == "pending",
                    or_(
                        *[
                            ~exists().where(
                                getattr(ControlOutbox, source) == model.id,
                                ControlOutbox.backend_id == target,
                            )
                            for target in accounts.settings.control_targets
                        ]
                    ),
                )
                .order_by(model.created_at, model.id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            for row in rows:
                for backend in accounts.settings.control_targets:
                    present = session.scalar(
                        select(ControlOutbox.id).where(
                            getattr(ControlOutbox, source) == row.id,
                            ControlOutbox.backend_id == backend,
                        )
                    )
                    if present is not None:
                        continue
                    message = {
                        "kind": "revoke_sessions",
                        "global_user_id": str(row.user_id),
                        "scope": "account" if model is AccountRevocation else "device",
                        "epoch": row.account_epoch
                        if model is AccountRevocation
                        else row.device_epoch,
                        "device_id": str(row.device_id) if model is LogoutRequest else None,
                    }
                    enqueue(session, backend, message, accounts.clock(), **{source: row.id})
                    count += 1
    return count


def acknowledge_source(session, accounts, row):
    for model, field in (
        (LogoutRequest, "logout_request_id"),
        (AccountRevocation, "account_revocation_id"),
    ):
        identifier = getattr(row, field)
        if identifier is None:
            continue
        # Lock source to serialize two backend acknowledgements without losing completion.
        source = session.get(model, identifier, with_for_update=True)
        session.flush()
        deliveries = session.execute(
            select(ControlOutbox.backend_id, ControlOutbox.state).where(
                getattr(ControlOutbox, field) == identifier
            )
        ).all()
        targets = {backend for backend, _ in deliveries}
        # Removing a configured target must never silently abandon a persisted revocation.
        if set(accounts.settings.control_targets) <= targets and all(
            state == "acknowledged" for _, state in deliveries
        ):
            source.state = "acknowledged"


def accept_receipt(session, accounts, row, receipt):
    if (
        not isinstance(receipt, dict)
        or receipt.get("operation_id") != str(row.id)
        or receipt.get("request_digest") != row.request_digest
    ):
        raise DeliveryError("invalid_receipt")
    result, message = receipt.get("result"), row.envelope["message"]
    if not isinstance(result, dict) or result.get("status") not in ("applied", "superseded"):
        raise DeliveryError("invalid_receipt")
    now = accounts.clock()
    if message["kind"] == "provision_universe":
        if (
            result.get("universe_id") != message["universe_id"]
            or result.get("name") != message["name"]
            or result["status"] != "applied"
        ):
            raise DeliveryError("invalid_receipt")
        session.get(UniverseReference, row.universe_id).provisioned = True
    elif message["kind"] == "set_universe_access":
        reported = result.get("snapshot")
        if (
            not isinstance(reported, dict)
            or any(
                reported.get(k) != message[k]
                for k in ("membership_id", "global_user_id", "universe_id")
            )
            or not isinstance(reported.get("revision"), int)
        ):
            raise DeliveryError("invalid_receipt")
        if reported["revision"] < message["revision"] or (
            reported["revision"] == message["revision"] and reported != message
        ):
            raise DeliveryError("invalid_receipt")
        membership = session.get(UniverseMembership, row.membership_id, with_for_update=True)
        prior = membership.applied_snapshot
        if prior is None or reported["revision"] >= prior["revision"]:
            membership.applied_snapshot = reported
            membership.last_checked_at = now
            membership.reconciliation_pending = reported != membership.desired_snapshot
            membership.next_check_at = now + timedelta(
                seconds=accounts.settings.control_reconcile_seconds
            )
    else:
        if (
            any(result.get(k) != message[k] for k in ("scope", "global_user_id", "device_id"))
            or not isinstance(result.get("epoch"), int)
            or result["epoch"] < message["epoch"]
        ):
            raise DeliveryError("invalid_receipt")
    row.state, row.acknowledged_at, row.last_error = "acknowledged", now, None
    acknowledge_source(session, accounts, row)


def deliver_one(accounts, transport):
    with accounts.factory.begin() as session:
        row = session.scalar(
            select(ControlOutbox)
            .where(
                ControlOutbox.state == "pending", ControlOutbox.next_attempt_at <= accounts.clock()
            )
            .order_by(ControlOutbox.next_attempt_at, ControlOutbox.created_at, ControlOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return False
        row.attempts += 1
        try:
            # A savepoint preserves retry metadata while rolling back any invalid acknowledgement.
            with session.begin_nested():
                if digest(row.envelope) != row.request_digest:
                    raise DeliveryError("outbox_content_conflict")
                receipt = None
                if row.attempts > 1:
                    receipt = transport.request(
                        row.backend_id, "GET", f"/internal/v1/operations/{row.id}"
                    )
                if receipt is None:
                    receipt = transport.request(
                        row.backend_id, "POST", "/internal/v1/operations", row.envelope
                    )
                accept_receipt(session, accounts, row, receipt)
        except DeliveryError as error:
            row.last_error = error.code
            row.next_attempt_at = accounts.clock() + timedelta(
                seconds=min(60, 2 ** min(row.attempts, 6))
            )
        return True


def reconcile_one(accounts, transport):
    with accounts.factory.begin() as session:
        row = session.scalar(
            select(UniverseMembership)
            .where(
                UniverseMembership.next_check_at <= accounts.clock(),
                ~exists().where(
                    ControlOutbox.membership_id == UniverseMembership.id,
                    ControlOutbox.state == "pending",
                ),
            )
            .order_by(UniverseMembership.next_check_at, UniverseMembership.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return False
        universe = session.get(UniverseReference, row.universe_id)
        now = accounts.clock()
        row.next_check_at = now + timedelta(seconds=accounts.settings.control_reconcile_seconds)
        try:
            response = transport.request(
                universe.backend_id, "GET", f"/internal/v1/access/{row.id}"
            )
            current = response.get("snapshot") if isinstance(response, dict) else None
            if current is not None and (
                not isinstance(current, dict)
                or any(
                    current.get(k) != row.desired_snapshot[k]
                    for k in ("membership_id", "global_user_id", "universe_id")
                )
                or not isinstance(current.get("revision"), int)
            ):
                raise DeliveryError("invalid_revision")
            row.last_checked_at = now
            row.reconciliation_pending = current != row.desired_snapshot
            if current is not None and (
                row.applied_snapshot is None
                or current["revision"] >= row.applied_snapshot["revision"]
            ):
                row.applied_snapshot = current
            if current is None or current["revision"] < row.revision:
                # Same desired state, dates and revision; new delivery ID, never a renewal.
                enqueue(
                    session,
                    universe.backend_id,
                    row.desired_snapshot,
                    now,
                    membership_id=row.id,
                    universe_id=universe.id,
                )
        except DeliveryError:
            row.reconciliation_pending = True
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be between 1 and 1000")
    settings = Settings()
    engine = create_database_engine(settings)
    accounts = Accounts(create_session_factory(engine), settings)
    try:
        while True:
            try:
                stage_revocations(accounts, args.limit)
                processed = 0
                while processed < args.limit and deliver_one(accounts, Transport(settings)):
                    processed += 1
                reconcile_one(accounts, Transport(settings))
                print(json.dumps({"processed": processed}), flush=True)
            except SQLAlchemyError:
                print('{"status":"accounts_unavailable"}', flush=True)
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                break
            time.sleep(settings.control_poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
