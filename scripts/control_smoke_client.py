"""Fixture/client of smoke_control_compose, executed only inside a disposable Accounts *_test."""

import copy
import json
import os
import socket
import ssl
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from portal_app.account_security.models import AccountRevocation
from portal_app.account_security.service import AccountSecurity
from portal_app.accounts.models import PasswordCredential, User
from portal_app.accounts.security import Passwords
from portal_app.accounts.service import Accounts
from portal_app.control.models import ControlOutbox, UniverseMembership
from portal_app.control.service import Lobby
from portal_app.control.transport import DeliveryError, Transport
from portal_app.control.worker import deliver_one, reconcile_one, stage_revocations
from portal_app.core.config import Settings
from portal_app.core.init_control_tls import ca, leaf
from portal_app.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from portal_app.sessions.models import LogoutRequest
from portal_app.sessions.service import Sessions, csrf
from sqlalchemy import func, select


def rejected(context):
    try:
        with httpx.Client(verify=context, trust_env=False, timeout=3) as client:
            response = client.get("https://game-control:9443/internal/v1/health")
    except httpx.HTTPError:
        return
    raise AssertionError(f"TLS unexpectedly reached HTTP: {response.status_code}")


def main():
    settings = Settings()
    if os.getenv("RUN_CONTROL_SMOKE") != "1" or not settings.postgres_db.endswith(
        "_test"
    ):
        raise SystemExit(
            "Control smoke requires an explicitly enabled disposable *_test database"
        )
    engine = create_database_engine(settings)
    accounts = Accounts(create_session_factory(engine), settings)
    transport = Transport(settings)
    try:
        for _ in range(50):
            try:
                if transport.request("primary", "GET", "/internal/v1/health") == {
                    "status": "ok"
                }:
                    break
            except DeliveryError:
                time.sleep(0.2)
        else:
            raise AssertionError("Private listener did not become ready")
        # No client certificate and a client from another issuer must fail at TLS.
        rejected(ssl.create_default_context(cafile=settings.control_ca))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaf(root, "wrong", "wrong-service", ca(root, "wrong-ca"), client=True)
            context = ssl.create_default_context(cafile=settings.control_ca)
            context.load_cert_chain(root / "wrong.pem", root / "wrong.key")
            rejected(context)
        # A valid certificate from the trusted issuer still has no service permission unless pinned.
        context = ssl.create_default_context(cafile=settings.control_ca)
        context.load_cert_chain("/run/rogue/client.pem", "/run/rogue/client.key")
        with httpx.Client(verify=context, trust_env=False, timeout=3) as client:
            result = client.get(
                "https://game-control:9443/internal/v1/health",
                headers={
                    "X-Control-Service": "portal-control",
                    "X-Forwarded-Proto": "https",
                    "X-Client-Cert": "forged-verified-client",
                },
            )
            assert result.status_code == 403
        context = ssl.create_default_context(cafile=settings.control_ca)
        context.load_cert_chain(settings.control_cert, settings.control_key)
        with socket.create_connection(("game-control", 9443), timeout=3) as connection:
            try:
                context.wrap_socket(connection, server_hostname="wrong.invalid")
            except ssl.SSLCertVerificationError:
                pass
            else:
                raise AssertionError("Server name mismatch was accepted")
        with httpx.Client(verify=context, trust_env=False, timeout=3) as client:
            assert (
                client.post(
                    "https://game-control:9443/internal/v1/operations",
                    json={"version": 99},
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "https://game-control:9443/internal/v1/operations",
                    content=b"x" * 65537,
                ).status_code
                == 413
            )

        # This is test fixture data in a guarded disposable Accounts DB, never startup/runtime data.
        password = "Isolated control smoke password 2026 !"
        user_id = uuid4()
        now = accounts.clock()
        with accounts.factory.begin() as session:
            session.add(
                User(
                    id=user_id,
                    email="control-smoke@example.org",
                    email_key="control-smoke@example.org",
                    status="active",
                    email_verified_at=now,
                    created_at=now,
                )
            )
            session.flush()
            session.add(
                PasswordCredential(
                    user_id=user_id,
                    password_hash=Passwords().hasher.hash(password),
                    changed_at=now,
                )
            )
        sessions = Sessions(accounts)
        challenge = sessions.challenge("smoke")
        raw = sessions.login(
            "control-smoke@example.org",
            password,
            challenge,
            csrf(challenge),
            None,
            None,
            "smoke",
        )[0]
        lobby = Lobby(accounts)
        universe_id = uuid4()
        lobby.provision(
            universe_id, "Isolated control test", "test-only-seed", "primary"
        )

        def drain(boundary=transport):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                deliver_one(accounts, boundary)
                with accounts.factory() as session:
                    count = session.scalar(
                        select(func.count())
                        .select_from(ControlOutbox)
                        .where(ControlOutbox.state == "pending")
                    )
                if count == 0:
                    return
                time.sleep(0.2)
            raise AssertionError("Delivery did not converge")

        drain()
        first = lobby.set_access(user_id, universe_id, "active", [])
        assert lobby.read(raw)["memberships"][0]["delivery_state"] == "pending"
        drain()
        assert lobby.read(raw)["memberships"][0]["delivery_state"] == "applied"
        with accounts.factory() as session:
            original = copy.deepcopy(
                session.get(ControlOutbox, UUID(first["operation_id"])).envelope
            )
        second = lobby.set_access(user_id, universe_id, "suspended", [])

        class LostReply:
            lost = False

            def request(self, backend, method, path, body=None):
                result = transport.request(backend, method, path, body)
                if method == "POST" and not self.lost:
                    self.lost = True
                    raise DeliveryError("control_unavailable")
                return result

        boundary = LostReply()
        assert deliver_one(accounts, boundary)
        with accounts.factory() as session:
            assert (
                session.get(ControlOutbox, UUID(second["operation_id"])).state
                == "pending"
            )
        with accounts.factory() as session:
            expected = copy.deepcopy(
                session.get(ControlOutbox, UUID(second["operation_id"])).envelope[
                    "message"
                ]
            )
        drain(boundary)
        # A retry recovers the committed operation; a new stale operation cannot resurrect the grant.
        assert (
            transport.request("primary", "POST", "/internal/v1/operations", original)[
                "operation_id"
            ]
            == first["operation_id"]
        )
        original["operation_id"] = str(uuid4())
        assert (
            transport.request("primary", "POST", "/internal/v1/operations", original)[
                "result"
            ]["status"]
            == "superseded"
        )
        revision = transport.request(
            "primary", "GET", f"/internal/v1/access/{first['membership_id']}"
        )["snapshot"]
        assert revision["status"] == "suspended" and revision["revision"] == 2
        assert revision["valid_until"] == expected["valid_until"]
        assert revision["portal_confirmed_at"] == expected["portal_confirmed_at"]
        lobby.set_access(user_id, universe_id, "active", [])
        drain()
        Sessions(accounts).logout(raw, csrf(raw))
        with accounts.factory.begin() as session:
            AccountSecurity(accounts).revoke_all(
                session,
                session.get(User, user_id, with_for_update=True),
                "logout_all",
                accounts.clock(),
            )
        assert stage_revocations(accounts) == 2
        drain()
        with accounts.factory() as session:
            assert session.scalar(select(LogoutRequest.state)) == "acknowledged"
            assert session.scalar(select(AccountRevocation.state)) == "acknowledged"
            membership = session.scalar(select(UniverseMembership))
            membership.next_check_at = (
                accounts.clock()
            )  # Applied below in a transaction.
        with accounts.factory.begin() as session:
            session.scalar(select(UniverseMembership)).next_check_at = accounts.clock()
        assert reconcile_one(accounts, transport)
        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": "mTLS/pinned-peer/contract/lobby/outbox/lost-ack/replay/revocations/reconciliation",
                }
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    import sys
    import traceback

    try:
        main()
    except Exception as error:  # noqa: BLE001 — redact every test-process failure at this boundary
        print(f"control-smoke: {type(error).__name__}", file=sys.stderr)
        for frame in traceback.extract_tb(error.__traceback__):
            print(
                f"control-smoke: {Path(frame.filename).name}:{frame.lineno} {frame.name}",
                file=sys.stderr,
            )
        raise SystemExit(1) from None
