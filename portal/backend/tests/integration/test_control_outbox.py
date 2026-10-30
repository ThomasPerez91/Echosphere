import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from portal_app.account_security.models import AccountRevocation
from portal_app.account_security.service import AccountSecurity
from portal_app.accounts.models import User
from portal_app.control.models import ControlOutbox, UniverseMembership, UniverseReference
from portal_app.control.service import Lobby
from portal_app.control.transport import DeliveryError
from portal_app.control.worker import deliver_one, reconcile_one, stage_revocations
from portal_app.main import create_app
from portal_app.sessions.models import LogoutRequest
from portal_app.sessions.service import SESSION_COOKIE, Sessions, csrf

pytestmark = pytest.mark.integration
PASSWORD = "Control plane test password 2026 !"
EMAIL = "lobby@example.org"


class Remote:
    """Scripted HTTP boundary only; actual Game transactions/crypto tested separately."""

    def __init__(self):
        self.receipts, self.states, self.requests = {}, {}, []
        self.lose_reply = False
        self.unavailable = False

    def request(self, backend, method, path, body=None):
        self.requests.append((backend, method, path, copy.deepcopy(body)))
        if self.unavailable:
            raise DeliveryError("control_unavailable")
        if method == "GET":
            identifier = path.rsplit("/", 1)[1]
            return (
                self.states.get(identifier)
                if "/access/" in path
                else self.receipts.get((backend, identifier))
            )
        message = body["message"]
        if message["kind"] == "provision_universe":
            result = {
                "status": "applied",
                "universe_id": message["universe_id"],
                "name": message["name"],
            }
        elif message["kind"] == "set_universe_access":
            result = {"status": "applied", "snapshot": copy.deepcopy(message)}
            self.states[message["membership_id"]] = {"snapshot": copy.deepcopy(message)}
        else:
            result = {
                "status": "applied",
                **{key: message[key] for key in ("scope", "global_user_id", "device_id", "epoch")},
            }
        from portal_app.control.service import digest

        receipt = {
            "operation_id": body["operation_id"],
            "request_digest": digest(body),
            "result": result,
        }
        self.receipts[backend, body["operation_id"]] = receipt
        if self.lose_reply:
            self.lose_reply = False
            raise DeliveryError("control_unavailable")
        return receipt


@pytest.fixture
def setup(accounts):
    accounts.register(EMAIL, PASSWORD, "peer")
    sessions = Sessions(accounts)
    challenge = sessions.challenge("peer")
    raw = sessions.login(EMAIL, PASSWORD, challenge, csrf(challenge), None, None, "peer")[0]
    with accounts.factory() as session:
        user = session.scalar(select(User.id))
    universe = uuid4()
    lobby = Lobby(accounts)
    lobby.provision(universe, "Universe réel", "seed", "primary")
    return lobby, user, universe, raw, Remote()


def drain(accounts, remote):
    for _ in range(20):
        if not deliver_one(accounts, remote):
            return
    raise AssertionError("Unexpected unbounded delivery")


def test_owned_empty_lobby_no_implicit_participation_and_reads_do_not_touch_idle(setup):
    lobby, user, universe, raw, remote = setup
    before = Sessions(lobby.accounts).read(raw)
    assert lobby.read(raw)["memberships"] == []
    lobby.accounts.test_clock[0] += timedelta(hours=1)
    assert Sessions(lobby.accounts).read(raw)["idle_expires_at"] == before["idle_expires_at"]
    with lobby.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(UniverseMembership)) == 0
    app = create_app(lobby.accounts.settings)
    app.state.accounts = lobby.accounts
    with TestClient(app, base_url=lobby.accounts.settings.public_origin) as client:
        assert (
            client.get("/lobby/memberships", headers={"X-Portal-Request": "bootstrap"}).status_code
            == 401
        )
        client.cookies.set(SESSION_COOKIE, raw)
        assert client.get("/lobby/memberships").status_code == 403
        assert (
            client.get("/lobby/memberships", headers={"X-Portal-Request": "bootstrap"}).json()[
                "memberships"
            ]
            == []
        )
        assert client.post("/lobby/join", json={"universe_id": str(universe)}).status_code == 404


def test_pending_is_not_applied_and_lobby_is_account_scoped(setup):
    lobby, user, universe, raw, remote = setup
    member = lobby.set_access(user, universe, "active", [])
    assert lobby.read(raw)["memberships"][0]["delivery_state"] == "pending"
    drain(lobby.accounts, remote)
    projection = lobby.read(raw)["memberships"][0]
    assert projection["delivery_state"] == "applied" and not projection["entry_available"]
    lobby.accounts.register("other@example.org", PASSWORD, "other")
    sessions = Sessions(lobby.accounts)
    challenge = sessions.challenge("other")
    other = sessions.login(
        "other@example.org", PASSWORD, challenge, csrf(challenge), None, None, "other"
    )[0]
    assert lobby.read(other)["memberships"] == []
    assert member["revision"] == 1


def test_timeout_after_remote_commit_recovers_receipt_without_new_identity_or_expiry(setup):
    lobby, user, universe, raw, remote = setup
    drain(lobby.accounts, remote)
    member = lobby.set_access(user, universe, "active", [])
    remote.lose_reply = True
    assert deliver_one(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        row = session.get(ControlOutbox, UUID(member["operation_id"]))
        assert row.state == "pending" and row.attempts == 1
        original = copy.deepcopy(row.envelope)
    assert lobby.read(raw)["memberships"][0]["delivery_state"] == "pending"
    lobby.accounts.test_clock[0] += timedelta(hours=2)
    drain(lobby.accounts, remote)
    assert remote.requests[-1][1] == "GET"
    with lobby.accounts.factory() as session:
        row = session.get(ControlOutbox, UUID(member["operation_id"]))
        assert row.state == "acknowledged" and row.envelope == original
    assert (
        sum(
            method == "POST" and body["operation_id"] == member["operation_id"]
            for _, method, _, body in remote.requests
            if body
        )
        == 1
    )


def test_revision_and_epoch_allocation_is_serialized_and_renewal_is_not_global_logout(setup):
    lobby, user, universe, raw, remote = setup
    lobby.set_access(user, universe, "active", [])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: lobby.set_access(user, universe, "active", []), range(2)))
    assert {r["revision"] for r in results} == {2, 3}
    with lobby.accounts.factory() as session:
        row = session.scalar(select(UniverseMembership))
        assert row.access_epoch == 1 and session.get(User, user).security_epoch == 0
    lobby.set_access(user, universe, "suspended", [])
    lobby.set_access(user, universe, "active", [])
    with lobby.accounts.factory() as session:
        row = session.scalar(select(UniverseMembership))
        assert row.revision == 5 and row.access_epoch == 3
    Sessions(lobby.accounts).read(raw)


def test_fanout_revocations_complete_only_after_every_target_acknowledges(setup):
    lobby, user, universe, raw, remote = setup
    accounts = lobby.accounts
    drain(accounts, remote)
    accounts.settings.control_targets["second"] = "https://second-game:9443"
    Sessions(accounts).logout(raw, csrf(raw))
    with accounts.factory.begin() as session:
        AccountSecurity(accounts).revoke_all(
            session, session.get(User, user, with_for_update=True), "logout_all", accounts.clock()
        )
    assert stage_revocations(accounts) == 4
    assert stage_revocations(accounts) == 0
    assert deliver_one(accounts, remote)
    with accounts.factory() as session:
        assert all(row.state == "pending" for row in session.scalars(select(LogoutRequest)))
        assert all(row.state == "pending" for row in session.scalars(select(AccountRevocation)))
    drain(accounts, remote)
    with accounts.factory() as session:
        assert session.scalar(select(LogoutRequest.state)) == "acknowledged"
        assert session.scalar(select(AccountRevocation.state)) == "acknowledged"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ControlOutbox)
                .where(ControlOutbox.state == "acknowledged")
            )
            == 5
        )


def test_unavailable_service_retries_without_claiming_applied(setup):
    lobby, user, universe, raw, remote = setup
    remote.unavailable = True
    assert deliver_one(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        row = session.scalar(select(ControlOutbox))
        assert row.state == "pending" and row.last_error == "control_unavailable"
    assert not deliver_one(lobby.accounts, remote)
    remote.unavailable = False
    lobby.accounts.test_clock[0] += timedelta(minutes=1)
    drain(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        assert session.get(UniverseReference, universe).provisioned


def test_reconciliation_repairs_missing_state_without_renewing_or_adopting_higher_intent(setup):
    lobby, user, universe, raw, remote = setup
    member = lobby.set_access(user, universe, "active", [])
    drain(lobby.accounts, remote)
    identifier = member["membership_id"]
    remote.states.clear()
    lobby.accounts.test_clock[0] += timedelta(minutes=2)
    assert reconcile_one(lobby.accounts, remote)
    assert lobby.read(raw)["memberships"][0]["delivery_state"] == "pending"
    drain(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        row = session.get(UniverseMembership, UUID(identifier))
        assert row.revision == 1 and row.portal_confirmed_at < lobby.accounts.clock()
        original = copy.deepcopy(row.desired_snapshot)
    remote.states[identifier]["snapshot"]["revision"] = 99
    lobby.accounts.test_clock[0] += timedelta(minutes=2)
    assert reconcile_one(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        row = session.get(UniverseMembership, UUID(identifier))
        assert row.desired_snapshot == original and row.reconciliation_pending


def test_old_receipt_cannot_lower_applied_revision(setup):
    lobby, user, universe, raw, remote = setup
    one = lobby.set_access(user, universe, "active", [])
    two = lobby.set_access(user, universe, "suspended", [])
    with lobby.accounts.factory.begin() as session:
        earlier = session.get(ControlOutbox, UUID(one["operation_id"]))
        earlier.next_attempt_at += timedelta(hours=1)
    drain(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        assert (
            session.scalar(select(UniverseMembership)).applied_snapshot["revision"]
            == two["revision"]
        )
    lobby.accounts.test_clock[0] += timedelta(hours=1)
    drain(lobby.accounts, remote)
    with lobby.accounts.factory() as session:
        assert (
            session.scalar(select(UniverseMembership)).applied_snapshot["revision"]
            == two["revision"]
        )


def test_intention_and_outbox_creation_rollback_together(setup):
    lobby, user, universe, raw, remote = setup

    def interrupt(session, context, instances):
        if any(isinstance(row, ControlOutbox) for row in session.new):
            raise RuntimeError("synthetic delivery interruption")

    event.listen(lobby.accounts.factory.class_, "before_flush", interrupt)
    try:
        with pytest.raises(RuntimeError):
            lobby.set_access(user, universe, "active", [])
    finally:
        event.remove(lobby.accounts.factory.class_, "before_flush", interrupt)
    with lobby.accounts.factory() as session:
        assert session.scalar(select(func.count()).select_from(UniverseMembership)) == 0


def test_pending_sources_already_staged_do_not_starve_later_revocations(setup):
    lobby, user, universe, raw, remote = setup
    accounts = lobby.accounts
    for _ in range(3):
        with accounts.factory.begin() as session:
            AccountSecurity(accounts).revoke_all(
                session,
                session.get(User, user, with_for_update=True),
                "logout_all",
                accounts.clock(),
            )
    assert stage_revocations(accounts, limit=1) == 1
    assert stage_revocations(accounts, limit=1) == 1
    assert stage_revocations(accounts, limit=1) == 1
    assert stage_revocations(accounts, limit=1) == 0


def test_invalid_receipt_rolls_back_acknowledgement(setup):
    lobby, user, universe, raw, remote = setup
    drain(lobby.accounts, remote)
    member = lobby.set_access(user, universe, "active", [])

    class Contradiction:
        def request(self, backend, method, path, body=None):
            receipt = remote.request(backend, method, path, body)
            receipt["result"]["snapshot"]["valid_until"] = "2099-01-01T00:00:00Z"
            return receipt

    assert deliver_one(lobby.accounts, Contradiction())
    with lobby.accounts.factory() as session:
        assert session.get(ControlOutbox, UUID(member["operation_id"])).state == "pending"
        assert session.scalar(select(UniverseMembership)).applied_snapshot is None
    assert lobby.read(raw)["memberships"][0]["delivery_state"] == "pending"


def test_removing_a_target_does_not_abandon_its_persisted_revocation(setup):
    lobby, user, universe, raw, remote = setup
    accounts = lobby.accounts
    drain(accounts, remote)
    accounts.settings.control_targets["second"] = "https://second-game:9443"
    Sessions(accounts).logout(raw, csrf(raw))
    stage_revocations(accounts)
    with accounts.factory.begin() as session:
        source = session.scalar(select(LogoutRequest))
        for row in session.scalars(
            select(ControlOutbox).where(
                ControlOutbox.logout_request_id == source.id,
                ControlOutbox.backend_id == "second",
            )
        ):
            row.next_attempt_at += timedelta(hours=1)
    del accounts.settings.control_targets["second"]
    drain(accounts, remote)
    with accounts.factory() as session:
        assert session.scalar(select(LogoutRequest.state)) == "pending"
