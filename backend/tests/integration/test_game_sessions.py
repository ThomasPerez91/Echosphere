from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from alembic import command
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text

from app.access.http import cookie_name
from app.access.models import ConsumedTicket, GameSession, PreAuth
from app.access.service import AccessError, GameSessions, csrf
from app.access.tickets import TYPE
from app.control.contracts import Operation
from app.control.service import SERVICE, Control
from app.core.config import Settings
from app.main import create_app
from app.persistence.database import create_session_factory

pytestmark = pytest.mark.integration


@pytest.fixture
def game(database_engine, tmp_path):
    key = Ed25519PrivateKey.generate()
    public = tmp_path / "public.pem"
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    settings = Settings(handoff_public_keys={"test-key": public}, game_universe_session_limit=2)
    now = [datetime(2026, 10, 30, 12, tzinfo=UTC)]
    factory = create_session_factory(database_engine)
    service = GameSessions(factory, settings, lambda: now[0])
    service.test_clock, service.test_key = now, key
    service.control = Control(factory, service.clock)
    try:
        yield service
    finally:
        with database_engine.begin() as connection:
            connection.execute(
                text("TRUNCATE universes, game_principals, control_operations CASCADE")
            )


def apply(game, message):
    return game.control.apply(
        SERVICE,
        Operation.model_validate({"version": 1, "operation_id": str(uuid4()), "message": message}),
    )


def grant(game, user=None, universe=None, membership=None, revision=1, epoch=1, status="active"):
    user, universe, membership = user or uuid4(), universe or uuid4(), membership or uuid4()
    apply(
        game,
        {
            "kind": "provision_universe",
            "universe_id": str(universe),
            "name": "C07 test only",
            "seed": "test",
        },
    )
    apply(
        game,
        {
            "kind": "set_universe_access",
            "global_user_id": str(user),
            "universe_id": str(universe),
            "membership_id": str(membership),
            "revision": revision,
            "access_epoch": epoch,
            "account_epoch": 0,
            "status": status,
            "bindings": [],
            "portal_confirmed_at": game.clock().isoformat(),
            "valid_until": (game.clock() + timedelta(hours=8)).isoformat(),
        },
    )
    return user, universe, membership


def ticket(game, context, device=None, **changes):
    user, universe, membership = context
    identifier, raw = game.start(universe)
    wire = {
        "iss": game.settings.portal_public_origin,
        "aud": game.settings.game_public_origin,
        "sub": str(user),
        "universe_id": str(universe),
        "membership_id": str(membership),
        "device_id": str(device or uuid4()),
        "pre_auth_id": str(identifier),
        "jti": str(uuid4()),
        "iat": int(game.clock().timestamp()),
        "exp": int(game.clock().timestamp()) + 60,
        "revision": 1,
        "access_epoch": 1,
        "account_epoch": 0,
        "device_epoch": 0,
        **changes,
    }
    encoded = jwt.encode(
        wire, game.test_key, algorithm="EdDSA", headers={"typ": TYPE, "kid": "test-key"}
    )
    return encoded, raw, wire


def enter(game, context, device=None):
    encoded, pre, wire = ticket(game, context, device)
    raw, payload = game.exchange(encoded, pre, None, context[1])
    return raw, payload, wire


def test_consumption_concurrent_unique_and_lost_response_cannot_replay(game):
    context = grant(game)
    encoded, pre, _ = ticket(game, context)

    def exchange(_):
        try:
            return game.exchange(encoded, pre, None, context[1])
        except AccessError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(exchange, range(2)))
    assert sum(value is not None for value in results) == 1
    with pytest.raises(AccessError):
        game.exchange(encoded, pre, None, context[1])
    with game.factory() as session:
        assert session.scalar(select(func.count()).select_from(ConsumedTicket)) == 1
        assert session.scalar(select(func.count()).select_from(GameSession)) == 1
        assert session.scalar(select(PreAuth.consumed_at)) == game.clock()


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "https://attacker.example"},
        {"iss": "other"},
        {"exp": 0},
        {"exp": 1793361661},
        {"iat": 9999999999, "exp": 10000000000},
        {"account_epoch": 1},
        {"device_epoch": 1},
        {"access_epoch": 2},
        {"revision": 2},
        {"universe_id": str(uuid4())},
        {"membership_id": str(uuid4())},
        {"sub": str(uuid4())},
        {"iat": True},
        {"extra": "forbidden"},
    ],
)
def test_invalid_claims_never_consume_or_create_session(game, changes):
    context = grant(game)
    encoded, pre, _ = ticket(game, context, **changes)
    with pytest.raises(AccessError):
        game.exchange(encoded, pre, None, context[1])
    with game.factory() as session:
        assert session.scalar(select(func.count()).select_from(GameSession)) == 0
        assert session.scalar(select(PreAuth.consumed_at)) is None


@pytest.mark.parametrize(
    "variant", ["signature", "unknown_key", "type", "algorithm", "header_url", "cookie"]
)
def test_signature_header_and_browser_binding_refusals(game, variant):
    context = grant(game)
    encoded, pre, wire = ticket(game, context)
    if variant == "signature":
        encoded = jwt.encode(
            wire,
            Ed25519PrivateKey.generate(),
            algorithm="EdDSA",
            headers={"typ": TYPE, "kid": "test-key"},
        )
    elif variant in ("unknown_key", "type", "header_url"):
        header = {"typ": TYPE, "kid": "test-key"}
        header.update(
            {
                "unknown_key": {"kid": "unknown"},
                "type": {"typ": "JWT"},
                "header_url": {"jku": "https://attacker.example"},
            }[variant]
        )
        encoded = jwt.encode(wire, game.test_key, algorithm="EdDSA", headers=header)
    elif variant == "algorithm":
        encoded = jwt.encode(
            wire,
            "synthetic-test-key-32-bytes-long!!!",
            algorithm="HS256",
            headers={"typ": TYPE, "kid": "test-key"},
        )
    else:
        pre = "x" * 43
    with pytest.raises(AccessError):
        game.exchange(encoded, pre, None, context[1])


def test_exact_deadlines_and_automatic_reads_never_keep_session_alive(game):
    context = grant(game)
    raw, initial, _ = enter(game, context)
    game.test_clock[0] += timedelta(hours=1, minutes=59)
    assert game.read(raw, context[1])["idle_expires_at"] == initial["idle_expires_at"]
    game.test_clock[0] += timedelta(minutes=1)
    with pytest.raises(AccessError):
        game.read(raw, context[1], interaction=True, proof=csrf(raw))
    raw, initial, _ = enter(game, context)
    for _ in range(5):
        game.test_clock[0] += timedelta(hours=1)
        game.read(raw, context[1], interaction=True, proof=csrf(raw))
    game.test_clock[0] += timedelta(hours=1)
    with pytest.raises(AccessError):
        game.read(raw, context[1], interaction=True, proof=csrf(raw))


def test_access_renewal_does_not_extend_existing_session_and_reentry_rotates(game):
    context = grant(game)
    device = uuid4()
    raw, initial, _ = enter(game, context, device)
    game.test_clock[0] += timedelta(hours=1)
    grant(game, *context, revision=2)
    encoded, pre, _ = ticket(game, context, device, revision=2)
    rotated, payload = game.exchange(encoded, pre, raw, context[1])
    assert raw != rotated and payload["session_id"] == initial["session_id"]
    assert payload["expires_at"] == initial["expires_at"]
    assert payload["access_valid_until"] == initial["access_valid_until"]
    with pytest.raises(AccessError):
        game.read(raw, context[1])


def test_targeted_logout_only_its_universe_device_and_old_ceremony_denied(game):
    one = grant(game)
    two = grant(game, user=one[0])
    device = uuid4()
    raw_one, _, _ = enter(game, one, device)
    raw_two, _, _ = enter(game, two, device)
    other, _, _ = enter(game, one, uuid4())
    encoded, pre, _ = ticket(game, one, device)
    game.logout(raw_one, one[1], csrf(raw_one))
    for call in (
        lambda: game.read(raw_one, one[1]),
        lambda: game.exchange(encoded, pre, None, one[1]),
    ):
        with pytest.raises(AccessError):
            call()
    assert game.read(raw_two, two[1])["status"] == "authenticated"
    assert game.read(other, one[1])["status"] == "authenticated"


def test_account_device_membership_revocation_invalidates_tickets_and_sessions(game):
    one = grant(game)
    two = grant(game, user=one[0])
    device, another = uuid4(), uuid4()
    raw, _, _ = enter(game, one, device)
    other, _, _ = enter(game, two, another)
    encoded, pre, _ = ticket(game, one, device)
    apply(
        game,
        {
            "kind": "revoke_sessions",
            "scope": "device",
            "global_user_id": str(one[0]),
            "device_id": str(device),
            "epoch": 1,
        },
    )
    with pytest.raises(AccessError):
        game.read(raw, one[1])
    with pytest.raises(AccessError):
        game.exchange(encoded, pre, None, one[1])
    assert game.read(other, two[1])["status"] == "authenticated"
    grant(game, *two, revision=2, epoch=2, status="suspended")
    with pytest.raises(AccessError):
        game.read(other, two[1])
    grant(game, *two, revision=3, epoch=3)
    with pytest.raises(AccessError):
        game.read(other, two[1])
    apply(
        game,
        {"kind": "revoke_sessions", "scope": "account", "global_user_id": str(one[0]), "epoch": 1},
    )
    encoded, pre, _ = ticket(game, two, another, revision=3, access_epoch=3)
    with pytest.raises(AccessError):
        game.exchange(encoded, pre, None, two[1])


def test_cap_serialized_without_silent_eviction_or_membership_limit(game):
    one = grant(game)
    contexts = [one, grant(game, user=one[0]), grant(game, user=one[0])]
    device = uuid4()

    def exchange(context):
        try:
            return enter(game, context, device)[0], context
        except AccessError as exc:
            assert exc.code == "game_session_limit_reached"
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(exchange, contexts))
    valid = [r for r in results if r]
    assert len(valid) == 2
    for raw, context in valid:
        assert game.read(raw, context[1])["status"] == "authenticated"


def test_no_silent_account_switch_or_cross_universe_use(game):
    one = grant(game)
    raw, _, _ = enter(game, one)
    other = grant(game, universe=one[1])
    encoded, pre, _ = ticket(game, other)
    with pytest.raises(AccessError, match="account_switch"):
        game.exchange(encoded, pre, raw, other[1])
    with pytest.raises(AccessError):
        game.read(raw, uuid4())


def test_expired_preauth_key_removal_and_transaction_rollback(game, migration_config):
    context = grant(game)
    encoded, pre, wire = ticket(game, context)
    game.test_clock[0] += timedelta(minutes=5)
    fresh = jwt.encode(
        {**wire, "iat": int(game.clock().timestamp()), "exp": int(game.clock().timestamp()) + 60},
        game.test_key,
        algorithm="EdDSA",
        headers={"typ": TYPE, "kid": "test-key"},
    )
    with pytest.raises(AccessError):
        game.exchange(fresh, pre, None, context[1])
    encoded, pre, _ = ticket(game, context)

    def fail(session, *args):
        if any(isinstance(row, ConsumedTicket) for row in session.new):
            raise RuntimeError("synthetic rollback")

    event.listen(game.factory.class_, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError):
            game.exchange(encoded, pre, None, context[1])
    finally:
        event.remove(game.factory.class_, "before_flush", fail)
    raw, _ = game.exchange(encoded, pre, None, context[1])
    with pytest.raises(RuntimeError, match="populated Game session"):
        command.downgrade(migration_config, "0005_game_access")
    command.check(migration_config)
    game.settings.handoff_public_keys = {}
    with pytest.raises(AccessError):
        game.read(raw, context[1])


def test_http_cookie_origin_csrf_body_and_public_errors(game):
    context = grant(game)
    app = create_app(game.settings)
    app.state.session_factory = game.factory
    # HTTP uses a real clock; use current dates for this test instead of injecting client time.
    game.test_clock[0] = datetime.now(UTC)
    grant(game, *context, revision=2)
    encoded, pre, _ = ticket(game, context, revision=2)
    client = TestClient(app, base_url=game.settings.game_public_origin)
    client.cookies.set(cookie_name(context[1], True), pre)
    endpoint = f"/game/{context[1]}"
    assert client.post(endpoint + "/exchange", data={"ticket": encoded}).status_code == 403
    result = client.post(
        endpoint + "/exchange",
        data={"ticket": encoded},
        headers={"Origin": game.settings.portal_public_origin},
        follow_redirects=False,
    )
    assert result.status_code == 303 and "ticket" not in result.headers["location"]
    assert "Secure" in result.headers["set-cookie"] and "HttpOnly" in result.headers["set-cookie"]
    assert "Domain=" not in result.headers["set-cookie"]
    read = client.get(endpoint + "/session", headers={"X-Game-Request": "bootstrap"})
    assert read.status_code == 200 and read.headers["cache-control"] == "no-store"
    assert (
        client.get(
            endpoint + "/session",
            headers={"X-Game-Request": "bootstrap", "Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            endpoint + "/logout",
            data={"csrf": "bad"},
            headers={"Origin": game.settings.game_public_origin},
        ).status_code
        == 403
    )
    assert client.post(endpoint + "/exchange", content="x" * 9000).status_code == 413
    result = client.post(
        endpoint + "/logout",
        data={"csrf": read.json()["csrf_token"]},
        headers={"Origin": game.settings.game_public_origin},
    )
    assert result.status_code == 200


def test_exchange_racing_revocation_cannot_restore_access(game):
    context = grant(game)
    encoded, pre, _ = ticket(game, context)

    def exchange():
        try:
            return game.exchange(encoded, pre, None, context[1])[0]
        except AccessError:
            return None

    def revoke():
        return apply(
            game,
            {
                "kind": "revoke_sessions",
                "scope": "account",
                "global_user_id": str(context[0]),
                "epoch": 1,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(exchange), pool.submit(revoke)
        raw, _ = first.result(), second.result()
    if raw:
        with pytest.raises(AccessError):
            game.read(raw, context[1])
    with pytest.raises(AccessError):
        game.exchange(encoded, pre, None, context[1])


def test_pre_auth_rate_limit_is_configurable_and_does_not_trust_client_clock(game):
    context = grant(game)
    game.settings.pre_auth_ip_limit = 2
    game.start(context[1], "one-peer")
    game.start(context[1], "one-peer")
    with pytest.raises(AccessError, match="rate_limited"):
        game.start(context[1], "one-peer")
    game.start(context[1], "another-peer")


def test_sql_session_membership_cannot_belong_to_another_account(game):
    from sqlalchemy.exc import IntegrityError

    one = grant(game)
    raw, payload, _ = enter(game, one)
    other = grant(game, universe=one[1])
    other_raw, _, wire = enter(game, other)
    game.logout(other_raw, other[1], csrf(other_raw))
    with pytest.raises(IntegrityError) as failure, game.factory.begin() as session:
        row = session.get(GameSession, UUID(payload["session_id"]))
        row.global_user_id, row.device_id = other[0], UUID(wire["device_id"])
        session.flush()
    assert failure.value.orig.diag.constraint_name == "fk_game_sessions_membership_id_game_accesses"
    assert game.read(raw, one[1])["status"] == "authenticated"


def test_cookie_already_revoked_by_portal_does_not_trap_next_account(game):
    one = grant(game)
    raw, _, _ = enter(game, one)
    apply(
        game,
        {"kind": "revoke_sessions", "scope": "account", "global_user_id": str(one[0]), "epoch": 1},
    )
    other = grant(game, universe=one[1])
    encoded, pre, _ = ticket(game, other)
    replacement, _ = game.exchange(encoded, pre, raw, other[1])
    assert game.read(replacement, other[1])["global_user_id"] == str(other[0])
    with pytest.raises(AccessError):
        game.read(raw, one[1])
