from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.control.contracts import Operation
from app.control.models import (
    ControlOperation,
    EmpireBinding,
    GameAccess,
    GameDevice,
    GamePrincipal,
)
from app.control.service import SERVICE, Control, ControlError
from app.persistence.database import create_session_factory
from app.persistence.models import Empire, Universe

pytestmark = pytest.mark.integration


@pytest.fixture
def control(database_engine):
    now = [datetime(2026, 10, 30, 12, tzinfo=UTC)]
    service = Control(create_session_factory(database_engine), lambda: now[0])
    service.test_clock = now
    try:
        yield service
    finally:
        with database_engine.begin() as connection:
            connection.execute(
                text("TRUNCATE universes, game_principals, control_operations CASCADE")
            )


def op(message, identifier=None):
    return Operation.model_validate(
        {"version": 1, "operation_id": str(identifier or uuid4()), "message": message}
    )


def provision(control):
    identifier = uuid4()
    request = op(
        {
            "kind": "provision_universe",
            "universe_id": str(identifier),
            "name": "Test",
            "seed": "seed",
        }
    )
    control.apply(SERVICE, request)
    return identifier


def access(
    control,
    universe=None,
    user=None,
    membership=None,
    revision=1,
    epoch=1,
    state="active",
    bindings=None,
):
    now = control.clock()
    return op(
        {
            "kind": "set_universe_access",
            "membership_id": str(membership or uuid4()),
            "global_user_id": str(user or uuid4()),
            "universe_id": str(universe or provision(control)),
            "revision": revision,
            "access_epoch": epoch,
            "account_epoch": 0,
            "status": state,
            "portal_confirmed_at": now.isoformat(),
            "valid_until": (now + timedelta(hours=8)).isoformat(),
            "bindings": bindings or [],
        }
    )


def test_operation_replay_conflict_and_authorization_precedes_receipt(control):
    universe = provision(control)
    request = access(control, universe)
    first = control.apply(SERVICE, request)
    assert control.apply(SERVICE, request) == first
    assert control.operation(SERVICE, request.operation_id) == first
    changed = request.model_copy(deep=True)
    changed.message.status = "suspended"
    with pytest.raises(ControlError, match="operation_content_conflict"):
        control.apply(SERVICE, changed)
    with pytest.raises(ControlError, match="service_denied"):
        control.operation("other-service", request.operation_id)
    with control.factory() as session:
        assert session.scalar(select(func.count()).select_from(GameAccess)) == 1
        assert session.scalar(select(func.count()).select_from(ControlOperation)) == 2


def test_parallel_duplicate_and_out_of_order_never_resurrect_access(control):
    request = access(control)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: control.apply(SERVICE, request), range(2)))
    assert results[0] == results[1]
    m = request.message
    suspend = access(control, m.universe_id, m.global_user_id, m.membership_id, 3, 2, "suspended")
    control.apply(SERVICE, suspend)
    late = access(control, m.universe_id, m.global_user_id, m.membership_id, 2)
    assert control.apply(SERVICE, late)["result"]["status"] == "superseded"
    assert control.revision(SERVICE, m.membership_id)["snapshot"]["status"] == "suspended"
    reactivate = access(control, m.universe_id, m.global_user_id, m.membership_id, 4, 3)
    control.apply(SERVICE, reactivate)
    with control.factory() as session:
        row = session.get(GameAccess, m.membership_id)
        assert row.access_epoch == 3 and row.status == "active"


def test_same_revision_conflict_renewal_does_not_revoke_and_dates_never_slide(control):
    request = access(control)
    control.apply(SERVICE, request)
    m = request.message
    control.test_clock[0] += timedelta(hours=2)
    renewal = access(control, m.universe_id, m.global_user_id, m.membership_id, 2)
    control.apply(SERVICE, renewal)
    assert renewal.message.access_epoch == m.access_epoch
    contradiction = access(
        control, m.universe_id, m.global_user_id, m.membership_id, 2, 2, "suspended"
    )
    with pytest.raises(ControlError, match="access_revision_conflict"):
        control.apply(SERVICE, contradiction)
    control.test_clock[0] += timedelta(hours=10)
    # Delayed first-time delivery applies an already-expired absolute interval; never receipt+8h.
    delayed = access(control, m.universe_id)
    delayed.message.portal_confirmed_at = m.portal_confirmed_at
    delayed.message.valid_until = m.valid_until
    control.apply(SERVICE, delayed)
    with control.factory() as session:
        assert session.get(GameAccess, delayed.message.membership_id).valid_until == m.valid_until


def test_changed_rights_require_new_epoch_and_cross_universe_bindings_fail(control):
    universe, foreign = provision(control), provision(control)
    with control.factory.begin() as session:
        empire = Empire(id=uuid4(), universe_id=foreign, name="Foreign", controller_type="human")
        session.add(empire)
    request = access(
        control, universe, bindings=[{"empire_id": str(empire.id), "permissions": ["colony.read"]}]
    )
    with pytest.raises(ControlError, match="empire_scope_denied"):
        control.apply(SERVICE, request)
    request = access(control, universe)
    control.apply(SERVICE, request)
    m = request.message
    with pytest.raises(ControlError, match="access_epoch_conflict"):
        control.apply(
            SERVICE, access(control, universe, m.global_user_id, m.membership_id, 2, 1, "revoked")
        )
    with pytest.raises(ControlError, match="membership_scope_conflict"):
        control.apply(SERVICE, access(control, universe, m.global_user_id))


def test_binding_fk_enforces_universe_and_permissions_are_explicit(control):
    universe = provision(control)
    with control.factory.begin() as session:
        empire = Empire(id=uuid4(), universe_id=universe, name="Human", controller_type="human")
        session.add(empire)
    request = access(
        control, universe, bindings=[{"empire_id": str(empire.id), "permissions": ["colony.read"]}]
    )
    control.apply(SERVICE, request)
    with control.factory() as session:
        assert session.scalar(select(EmpireBinding)).permissions == ["colony.read"]
    foreign = provision(control)
    with pytest.raises(IntegrityError), control.factory.begin() as session:
        session.add(
            EmpireBinding(
                membership_id=request.message.membership_id,
                universe_id=foreign,
                empire_id=empire.id,
                permissions=["colony.read"],
            )
        )


def test_device_and_account_revocations_monotone_and_independent(control):
    user, one, two = uuid4(), uuid4(), uuid4()
    for device, epoch in ((one, 3), (two, 1), (one, 1)):
        control.apply(
            SERVICE,
            op(
                {
                    "kind": "revoke_sessions",
                    "global_user_id": str(user),
                    "scope": "device",
                    "epoch": epoch,
                    "device_id": str(device),
                }
            ),
        )
    for epoch in (4, 2):
        control.apply(
            SERVICE,
            op(
                {
                    "kind": "revoke_sessions",
                    "global_user_id": str(user),
                    "scope": "account",
                    "epoch": epoch,
                }
            ),
        )
    with control.factory() as session:
        assert session.get(GamePrincipal, user).account_epoch == 4
        assert session.get(GameDevice, (user, one)).device_epoch == 3
        assert session.get(GameDevice, (user, two)).device_epoch == 1
        assert session.scalar(select(func.count()).select_from(Universe)) == 0


def test_effect_and_result_rollback_together(control):
    request = access(control)

    def interrupt(session, context, instances):
        if any(isinstance(row, ControlOperation) for row in session.new):
            raise RuntimeError("synthetic result interruption")

    event.listen(control.factory.class_, "before_flush", interrupt)
    try:
        with pytest.raises(RuntimeError):
            control.apply(SERVICE, request)
    finally:
        event.remove(control.factory.class_, "before_flush", interrupt)
    with control.factory() as session:
        assert session.scalar(select(func.count()).select_from(GameAccess)) == 0
    assert control.apply(SERVICE, request)["result"]["status"] == "applied"


def test_invalid_lifetimes_and_future_confirmation_refused(control):
    request = access(control)
    wire = request.model_dump(mode="json")
    wire["message"]["valid_until"] = (control.clock() + timedelta(hours=8, seconds=1)).isoformat()
    with pytest.raises(ValidationError):
        Operation.model_validate(wire)
    control.test_clock[0] -= timedelta(seconds=1)
    with pytest.raises(ControlError, match="confirmation_in_future"):
        control.apply(SERVICE, request)


def test_control_downgrade_populated_is_refused(control, migration_config):
    request = access(control)
    control.apply(SERVICE, request)
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(migration_config, "0004_colony_economy")
    assert control.revision(SERVICE, request.message.membership_id)
    command.check(migration_config)
