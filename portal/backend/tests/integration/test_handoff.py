from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_app.accounts.models import User
from portal_app.accounts.security import PublicError
from portal_app.control.models import ControlOutbox, UniverseMembership, UniverseReference
from portal_app.control.service import Lobby
from portal_app.handoff.service import Handoff
from portal_app.main import create_app
from portal_app.sessions.models import PortalSession
from portal_app.sessions.service import SESSION_COOKIE, Sessions, csrf

pytestmark = pytest.mark.integration


@pytest.fixture
def handoff(accounts, tmp_path):
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "handoff.pem"
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    accounts.settings.handoff_private_key = private
    accounts.register("handoff@example.org", "A long test passphrase 2026 !", "peer")
    challenge = Sessions(accounts).challenge("peer")
    raw = Sessions(accounts).login(
        "handoff@example.org",
        "A long test passphrase 2026 !",
        challenge,
        csrf(challenge),
        None,
        None,
        "peer",
    )[0]
    with accounts.factory.begin() as session:
        user = session.scalar(select(User))
        user.email_verified_at = accounts.clock()
        identifier = user.id
    universe = uuid4()
    lobby = Lobby(accounts)
    lobby.provision(universe, "Test only", "seed", "primary")
    lobby.set_access(identifier, universe, "active", [])
    with accounts.factory.begin() as session:
        reference = session.get(UniverseReference, universe)
        reference.provisioned = True
        member = session.scalar(select(UniverseMembership))
        member.applied_snapshot = member.desired_snapshot
        member.reconciliation_pending = False
    return Handoff(accounts), raw, universe, key


def test_verified_acknowledged_scope_and_claims_no_credentials(handoff, accounts):
    service, raw, universe, key = handoff
    pre = uuid4()
    token, target = service.issue(raw, csrf(raw), universe, pre)
    claims = jwt.decode(
        token,
        key.public_key(),
        algorithms=["EdDSA"],
        audience=target,
        issuer=accounts.settings.public_origin,
        options={"verify_exp": False, "verify_iat": False},
    )
    assert claims["pre_auth_id"] == str(pre) and claims["exp"] - claims["iat"] == 60
    assert {"email", "password", "permissions", "bindings"}.isdisjoint(claims)
    assert jwt.get_unverified_header(token) == {
        "alg": "EdDSA",
        "kid": "local-v1",
        "typ": "echosphere-handoff+jwt",
    }
    projection = Lobby(accounts).read(raw)["memberships"][0]
    assert projection["entry_available"] and projection["entry_url"].endswith(f"/{universe}/start")


@pytest.mark.parametrize(
    "variant", ["unverified", "pending", "suspended", "expired", "scope", "csrf", "session"]
)
def test_ineligible_sessions_or_rights_do_not_issue(handoff, accounts, variant):
    service, raw, universe, _ = handoff
    with accounts.factory.begin() as session:
        user, member = session.scalar(select(User)), session.scalar(select(UniverseMembership))
        if variant == "unverified":
            user.email_verified_at = None
        elif variant == "pending":
            member.reconciliation_pending = True
        elif variant == "suspended":
            member.desired_status = "suspended"
        elif variant == "expired":
            accounts.test_clock[0] += timedelta(hours=8)
    if variant == "scope":
        universe = uuid4()
    if variant == "session":
        raw = "x" * 43
    with pytest.raises(PublicError):
        service.issue(raw, "wrong" if variant == "csrf" else csrf(raw), universe, uuid4())


def test_renewal_is_explicit_durable_and_preserves_access_epoch(handoff, accounts):
    service, raw, universe, _ = handoff
    with accounts.factory() as session:
        old = session.scalar(select(UniverseMembership))
        revision, epoch, expiry = old.revision, old.access_epoch, old.valid_until
    accounts.test_clock[0] += timedelta(hours=1)
    Lobby(accounts).read(raw)
    with accounts.factory() as session:
        assert session.scalar(select(UniverseMembership.valid_until)) == expiry
    assert service.renew(raw, csrf(raw), universe) == {"status": "pending"}
    with accounts.factory() as session:
        member = session.scalar(select(UniverseMembership))
        assert member.access_epoch == epoch and member.revision == revision + 1
        assert member.valid_until == accounts.clock() + timedelta(hours=8)
        assert member.reconciliation_pending
        rows = list(
            session.scalars(select(ControlOutbox).where(ControlOutbox.membership_id == member.id))
        )
        assert len(rows) == 2
    with pytest.raises(PublicError):
        service.issue(raw, csrf(raw), universe, uuid4())


def test_normal_logout_generation_changes_not_hidden_by_ticket_or_renew(handoff, accounts):
    service, raw, universe, _ = handoff
    Sessions(accounts).logout(raw, csrf(raw))
    with pytest.raises(PublicError):
        service.issue(raw, csrf(raw), universe, uuid4())
    with pytest.raises(PublicError):
        service.renew(raw, csrf(raw), universe)


def test_forms_exact_origins_no_ticket_url_csrf_and_no_store(handoff, accounts):
    service, raw, universe, _ = handoff
    app = create_app(accounts.settings)
    app.state.accounts = accounts
    client = TestClient(app, base_url=accounts.settings.public_origin)
    client.cookies.set(SESSION_COOKIE, raw)
    fields = {"universe_id": str(universe), "pre_auth_id": str(uuid4())}
    assert client.post("/handoff/prepare", data=fields).status_code == 403
    prepared = client.post(
        "/handoff/prepare",
        data=fields,
        headers={"Origin": accounts.settings.game_public_targets["primary"]},
    )
    assert prepared.status_code == 200 and "csrf" in prepared.text
    assert "no-store" == prepared.headers["cache-control"]
    fields["csrf"] = csrf(raw)
    assert client.post("/handoff/issue", data=fields).status_code == 403
    result = client.post(
        "/handoff/issue", data=fields, headers={"Origin": accounts.settings.public_origin}
    )
    assert result.status_code == 200 and 'name="ticket"' in result.text
    assert (
        "script" not in result.text
        and "frame-ancestors 'none'" in result.headers["content-security-policy"]
    )
    assert (
        client.post(
            "/handoff/issue?ticket=forbidden",
            data=fields,
            headers={"Origin": accounts.settings.public_origin},
        ).status_code
        == 422
    )
    assert client.post("/handoff/issue", content="x" * 9000).status_code == 413
    with accounts.factory() as session:
        row = session.get(PortalSession, UUID(Sessions(accounts).read(raw)["session_id"]))
        assert row.last_activity_at == accounts.clock()


def test_operator_bootstrap_resolves_foreign_keys_in_fresh_process():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from portal_app.control.operator import main; "
            "from portal_app.persistence.models import Base; "
            "assert len(Base.metadata.sorted_tables) > 0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
