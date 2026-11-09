from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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


def start(control, profiles=("economic_cautious",), identifier=None, operation=None, name="Orion"):
    universe = identifier or uuid4()
    request = op(
        {
            "kind": "start_universe",
            "universe_id": str(universe),
            "name": name,
            "seed": "server-random-seed",
            "family": "solo",
            "ruleset": "v0.10",
            "profiles": list(profiles),
        },
        operation,
    )
    return universe, request, control.apply(SERVICE, request)


def test_start_universe_bootstraps_one_human_and_ai_opponents_with_an_immutable_receipt(control):
    from app.ai.models import AIController

    universe, request, receipt = start(control, ("economic_cautious", "expansionist"))
    result = receipt["result"]
    assert result["status"] == "applied" and result["universe_id"] == str(universe)
    with control.factory() as session:
        empires = session.scalars(select(Empire).where(Empire.universe_id == universe)).all()
        assert len(empires) == 3
        human = session.get(Empire, UUID(result["human_empire_id"]))
        assert human.controller_type == "human" and human.universe_id == universe
        controlled = set(session.scalars(select(AIController.empire_id)))
        assert human.id not in controlled and len(controlled & {e.id for e in empires}) == 2
    # A retried delivery replays the receipt; the world is not started twice.
    assert control.apply(SERVICE, request) == receipt
    with control.factory() as session:
        assert session.scalar(select(func.count()).select_from(Empire)) == 3
    # The receipt's human Empire is the one Portal may grant; an AI Empire is refused.
    granted = control.apply(
        SERVICE,
        access(
            control,
            universe=universe,
            bindings=[{"empire_id": result["human_empire_id"], "permissions": ["colony.read"]}],
        ),
    )
    assert granted["result"]["status"] == "applied"


def test_start_universe_refuses_a_different_intention_for_the_same_universe(control):
    universe, _, _ = start(control, ())
    with pytest.raises(ControlError) as refused:
        start(control, ("expansionist",), identifier=universe)
    assert refused.value.code == "universe_content_conflict"
    # An operator-provisioned universe (other seed) is never started over by this operation.
    provisioned = provision(control)
    with pytest.raises(ControlError) as occupied:
        start(control, (), identifier=provisioned, name="Test")
    assert occupied.value.code == "bootstrap_requires_empty_universe"


def test_private_start_creates_one_seat_per_human_and_keeps_solo_receipts_unchanged(control):
    from app.ai.models import AIBootstrap

    universe = uuid4()
    request = op(
        {
            "kind": "start_universe",
            "universe_id": str(universe),
            "name": "Multi",
            "seed": "server-random-seed",
            "family": "private",
            "humans": 3,
            "ruleset": "v0.10",
            "profiles": ["expansionist"],
        }
    )
    result = control.apply(SERVICE, request)["result"]
    seats = result["human_empire_ids"]
    assert len(seats) == 3 and result["human_empire_id"] == seats[0]
    with control.factory() as session:
        types = {e.id: e.controller_type for e in session.scalars(
            select(Empire).where(Empire.universe_id == universe))}
        assert len(types) == 4 and {types[UUID(s)] for s in seats} == {"human"}
        assert session.get(AIBootstrap, universe).request["humans"] == 3
    solo, _, receipt = start(control, ())
    assert "human_empire_ids" not in receipt["result"]
    with control.factory() as session:
        assert "humans" not in session.get(AIBootstrap, solo).request


def test_a_player_names_their_empire_and_a_left_seat_goes_on_under_an_ai(control):
    from app.ai.models import AIController

    universe = uuid4()
    started = control.apply(SERVICE, op({
        "kind": "start_universe", "universe_id": str(universe), "name": "Multi",
        "seed": "server-random-seed", "family": "private", "humans": 2, "ruleset": "v0.10",
        "profiles": [],
    }))["result"]
    first, second = started["human_empire_ids"]
    target = {"universe_id": str(universe), "empire_id": second}
    named = control.apply(SERVICE, op({"kind": "name_empire", **target, "name": "Concorde"}))
    assert named["result"] == {"status": "applied", **target, "name": "Concorde"}
    with control.factory() as session:
        assert session.get(Empire, UUID(second)).name == "Concorde"
    # A seat still bound to a player is never handed over.
    membership, user = uuid4(), uuid4()
    rights = [{"empire_id": second, "permissions": ["colony.read"]}]
    control.apply(SERVICE, access(control, universe, user, membership, bindings=rights))
    hand_over = {"kind": "hand_over_empire", **target, "profile": "economic_cautious"}
    with pytest.raises(ControlError) as bound:
        control.apply(SERVICE, op(hand_over))
    assert bound.value.code == "empire_still_bound"
    control.apply(SERVICE, access(control, universe, user, membership, revision=2, epoch=2,
                                  state="revoked"))
    request = op(hand_over)
    receipt = control.apply(SERVICE, request)
    assert receipt["result"] == {"status": "applied", **target, "profile": "economic_cautious"}
    assert control.apply(SERVICE, request) == receipt
    # A second delivery (new operation id) replays the same controller; another profile conflicts.
    assert control.apply(SERVICE, op(hand_over))["result"] == receipt["result"]
    with pytest.raises(ControlError) as other:
        control.apply(SERVICE, op({**hand_over, "profile": "expansionist"}))
    assert other.value.code == "hand_over_conflict"
    with control.factory() as session:
        empire = session.get(Empire, UUID(second))
        assert empire.controller_type == "ai" and empire.name == "Concorde"
        assert session.scalar(select(func.count()).select_from(AIController)) == 1
    # The AI Empire can be neither renamed nor granted to a human again.
    with pytest.raises(ControlError) as renamed:
        control.apply(SERVICE, op({"kind": "name_empire", **target, "name": "Autre"}))
    assert renamed.value.code == "empire_ai_controlled"
    with pytest.raises(ControlError) as granted:
        control.apply(SERVICE, access(control, universe, bindings=rights))
    assert granted.value.code == "empire_ai_controlled"
    # An Empire of another universe is out of scope.
    with pytest.raises(ControlError) as scope:
        control.apply(SERVICE, op({"kind": "name_empire", "universe_id": str(uuid4()),
                                   "empire_id": first, "name": "Intrus"}))
    assert scope.value.code == "empire_scope_denied"


def test_v010_start_generates_the_requested_map_size_and_enforces_its_empire_cap(control):
    from app.galaxy.models import GalaxySystem, StartingSite

    def message(size, humans, profiles):
        return op({
            "kind": "start_universe", "universe_id": str(uuid4()), "name": "Carte",
            "seed": "server-random-seed", "family": "private", "humans": humans,
            "ruleset": "v0.10", "size": size, "profiles": profiles,
        })

    # 100 systems hold 4 Empires at most (Q61): a fifth is refused before any write.
    with pytest.raises(ControlError) as capped:
        control.apply(SERVICE, message(100, 3, ["expansionist", "economic_cautious"]))
    assert capped.value.code == "invalid_bootstrap_configuration"
    request = message(300, 5, ["expansionist"] * 3)
    universe = UUID(request["message"]["universe_id"])
    result = control.apply(SERVICE, request)["result"]
    assert len(result["human_empire_ids"]) == 5
    with control.factory() as session:
        def count(model):
            return session.scalar(
                select(func.count()).select_from(model).where(model.universe_id == universe)
            )

        systems, sites = count(GalaxySystem), count(StartingSite)
        assert (systems, sites) == (300, 8)  # one starting site per Empire of the game
        assert session.scalar(
            select(func.count()).select_from(Empire).where(Empire.universe_id == universe)
        ) == 8
