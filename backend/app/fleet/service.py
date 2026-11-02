"""Fleets on the Empire Operations timeline (physically the Exploration stream, ruleset v0.4+).

Lock order: Game principal → Empire Operations → Research → Colonies (sorted). Commands catch the
Operations stream up before any decision; projections never do (worker or command only). Handlers
write Fleet/Knowledge rows of their Empire only: never a Colony, so unloading is a command.
"""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, literal, select, tuple_

from app.colonization.service import found_colony
from app.colony.service import ColonyError, catch_up_owned, owned_colony, recoverable_refunds
from app.colony.service import rules_for as ruleset_for
from app.fleet.models import (
    Fleet,
    FleetCargo,
    FleetMission,
    FleetMissionLeg,
    FleetOperation,
    FleetReport,
    FleetStack,
    ShipOrder,
)
from app.frontier import service as frontier
from app.frontier.encounter import add as frontier_add
from app.galaxy import service as galaxy
from app.galaxy.models import GalaxyRoute, PlanetKnowledge
from app.persistence.models import Colony, Planet
from app.simulation.clock import utc
from app.simulation.models import ColonyTimeline, ResourceBalance, ScheduledEvent
from app.simulation.production import RESOURCES, ProductionState, amount, produce
from app.simulation.scheduler import IdempotencyConflict, TimelineError, lock_stream, schedule

OPEN = ("queued", "active")


class FleetError(ColonyError):
    pass


def rules_for(session, universe_id):
    rules = ruleset_for(session, universe_id)
    if rules.fleets is None:
        raise FleetError("Fleets absent from pinned ruleset", "fleet_unavailable")
    return rules


def operations(session, engine, universe_id, empire_id, at):
    """Command path: lock and fully catch up the Empire Operations stream before deciding."""
    state = galaxy.state_for(session, universe_id, empire_id)
    lock_stream(session, state.stream_id, universe_id)
    progress = engine.catch_up_stream(session, state.stream_id, universe_id, utc(at))
    if progress.fenced:
        # A due Combat is not resolved yet: never let military state move past the battle.
        raise FleetError("A combat must be resolved first", "combat_pending")
    if not progress.complete:
        raise FleetError("Operations need retry/operator", "fleet_busy")
    return state


def check_key(key):
    if not key or len(key) > 160:
        raise FleetError("Invalid intent", "invalid_request")


def micro(value):
    """Request quantities are whole units; storage is in micro-units."""
    if type(value) is not int or value < 0:
        raise FleetError("Invalid amount", "invalid_request")
    try:
        return amount(value * 1_000_000)
    except ValueError:
        raise FleetError("Invalid amount", "invalid_request") from None


def debit(session, colony_id, cost):
    balances = {r: session.get(ResourceBalance, (colony_id, r)) for r in RESOURCES}
    if any(balances[r].stock < cost.get(r, 0) for r in RESOURCES):
        raise FleetError("Insufficient source resources", "insufficient_resources")
    for r in RESOURCES:
        balances[r].stock -= cost.get(r, 0)


def credit_capped(session, colony_id, amounts_by_resource):
    """Credit up to free storage; returns (credited, kept) per resource, nothing silently lost."""
    credited, kept = {}, {}
    for r, value in amounts_by_resource.items():
        balance = session.get(ResourceBalance, (colony_id, r))
        if balance is None or balance.capacity is None:
            raise FleetError("Missing finite colony storage capacity", "colony_not_found")
        room = max(0, balance.capacity - balance.stock)
        credited[r] = min(value, room)
        kept[r] = value - credited[r]
        balance.stock = amount(balance.stock + credited[r])
        if balance.stock == balance.capacity:
            balance.remainder = 0
    return credited, kept


def estimated_balances(session, colony_id, at):
    """Read-only stock estimate for previews: settled state + production, no write, no lock."""
    timeline = session.get(ColonyTimeline, colony_id)
    result = {}
    for r in sorted(RESOURCES):
        balance = session.get(ResourceBalance, (colony_id, r))
        state = ProductionState(
            balance.stock,
            balance.rate_per_hour,
            timeline.settled_at,
            balance.remainder,
            balance.capacity,
        )
        result[r] = produce(state, max(utc(at), timeline.settled_at))
    return result


# --- Production --------------------------------------------------------------------------------


def is_colonizer(rules, ship_class):
    return rules.colonization is not None and ship_class == rules.colonization.colonizer_class


def colonizer_rank(session, rules, empire_id):
    """N = colonies + existing colonizers + colonizer units in open orders (founding keeps N)."""
    ship_class = rules.colonization.colonizer_class
    colonies = session.scalar(
        select(func.count()).select_from(Colony).where(Colony.empire_id == empire_id)
    )
    units = session.scalar(
        select(func.coalesce(func.sum(FleetStack.count), 0))
        .join(Fleet, Fleet.id == FleetStack.fleet_id)
        .where(Fleet.empire_id == empire_id, FleetStack.ship_class == ship_class)
    )
    ordered = session.scalar(
        select(func.coalesce(func.sum(ShipOrder.quantity), 0)).where(
            ShipOrder.empire_id == empire_id,
            ShipOrder.ship_class == ship_class,
            ShipOrder.status.in_(OPEN),
        )
    )
    return colonies + units + ordered


def snapshot_order(rules, ship_class, quantity, rank=None):
    """Accepted batch price; a colonizer's progressive price is fixed here, never recomputed."""
    cost, duration = rules.fleets.order_quote(ship_class, quantity)
    snapshot = {
        "version": rules.version,
        "engagement": rules.fleets.engagement_version,
        "ship_class": ship_class,
        "quantity": quantity,
        "cost": cost,
        "duration_us": duration,
        "refund_queued_bps": rules.fleets.refund_queued_bps,
        "refund_active_bps": rules.fleets.refund_active_bps,
    }
    if is_colonizer(rules, ship_class):
        if quantity > rules.colonization.colonizer_max_quantity or rank is None:
            raise ValueError("Colonizer orders hold one unit at a known rank")
        bps = rules.colonization.multiplier_bps(rank)
        snapshot["cost"] = {r: amount(v * bps // 10000) for r, v in cost.items()}
        snapshot["colonizer_rank"], snapshot["multiplier_bps"] = rank, bps
    elif rank is not None:
        raise ValueError("Only colonizers have a progressive price")
    return snapshot


def colonizer_quote(session, rules, empire_id):
    """Current server price of the next colonizer; the command recomputes it under lock."""
    if rules.colonization is None:
        return None
    rank = colonizer_rank(session, rules, empire_id)
    snapshot = snapshot_order(rules, rules.colonization.colonizer_class, 1, rank)
    return {"rank": rank, "multiplier_bps": snapshot["multiplier_bps"], "cost": snapshot["cost"]}


def activate_next(session, state, colony_id, at):
    if session.scalar(
        select(ShipOrder.id).where(ShipOrder.colony_id == colony_id, ShipOrder.status == "active")
    ):
        return
    following = session.scalar(
        select(ShipOrder)
        .where(ShipOrder.colony_id == colony_id, ShipOrder.status == "queued")
        .order_by(ShipOrder.sequence)
    )
    if following is None:
        return
    following.status, following.started_at = "active", utc(at)
    following.due_at = utc(at) + timedelta(microseconds=following.snapshot["duration_us"])
    session.flush()
    schedule(
        session,
        state.stream_id,
        following.universe_id,
        key=f"ship-order:{following.id}",
        kind="SHIP_ORDER_COMPLETE",
        due_at=following.due_at,
        payload={"order_id": str(following.id)},
    )


def order_ships(
    session, engine, universe_id, empire_id, colony_id, ship_class, quantity, *, key, at
):
    with session.begin_nested():
        owned_colony(session, universe_id, empire_id, colony_id)
        rules = rules_for(session, universe_id)
        state = operations(session, engine, universe_id, empire_id, at)
        existing = session.scalar(
            select(ShipOrder).where(
                ShipOrder.empire_id == empire_id, ShipOrder.idempotency_key == key
            )
        )
        if existing is not None:
            if (existing.colony_id, existing.ship_class, existing.quantity) != (
                colony_id,
                ship_class,
                quantity,
            ):
                raise IdempotencyConflict("Production intention reused")
            return existing
        check_key(key)
        try:
            # Serialized by the Operations stream lock: two concurrent orders get N then N + 1.
            rank = (
                colonizer_rank(session, rules, empire_id)
                if is_colonizer(rules, ship_class)
                else None
            )
            snapshot = snapshot_order(rules, ship_class, quantity, rank)
        except ValueError:
            raise FleetError("Unknown class or invalid quantity", "invalid_request") from None
        queued = session.scalar(
            select(func.count())
            .select_from(ShipOrder)
            .where(ShipOrder.colony_id == colony_id, ShipOrder.status.in_(OPEN))
        )
        if queued >= rules.fleets.queue_limit:
            raise FleetError("Production queue full", "queue_full")
        catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        debit(session, colony_id, snapshot["cost"])
        sequence = (
            session.scalar(
                select(func.max(ShipOrder.sequence)).where(ShipOrder.colony_id == colony_id)
            )
            or 0
        ) + 1
        order = ShipOrder(
            empire_id=empire_id,
            universe_id=universe_id,
            colony_id=colony_id,
            ship_class=ship_class,
            quantity=quantity,
            sequence=sequence,
            status="queued",
            idempotency_key=key,
            snapshot=snapshot,
            accepted_at=utc(at),
        )
        session.add(order)
        session.flush()
        activate_next(session, state, colony_id, at)
        return order


def refund_plan(order):
    snap = order.snapshot
    bps = snap["refund_active_bps"] if order.status == "active" else snap["refund_queued_bps"]
    return {r: value * bps // 10000 for r, value in snap["cost"].items()}


def cancel_preview(session, order, at):
    """Q39 preview: theoretical, recoverable at current estimated stocks, and definitive loss."""
    theoretical = refund_plan(order)
    estimate = estimated_balances(session, order.colony_id, at)
    recovered = {
        r: min(v, max(0, (estimate[r].capacity or 0) - estimate[r].stock))
        for r, v in theoretical.items()
    }
    lost = {r: theoretical[r] - recovered[r] for r in theoretical}
    return {"theoretical": theoretical, "recoverable": recovered, "lost": lost}


def cancel_order(session, engine, universe_id, empire_id, order_id, *, at):
    with session.begin_nested():
        rules_for(session, universe_id)
        state = operations(session, engine, universe_id, empire_id, at)
        order = session.get(ShipOrder, order_id, populate_existing=True)
        if order is None or order.empire_id != empire_id or order.universe_id != universe_id:
            raise FleetError("Order unavailable", "order_not_found")
        if order.status == "cancelled":
            return order
        if order.status == "completed":
            raise FleetError("Completed production cannot be cancelled", "order_completed")
        catch_up_owned(session, engine, universe_id, empire_id, order.colony_id, at)
        balances = {r: session.get(ResourceBalance, (order.colony_id, r)) for r in RESOURCES}
        # Explicit application of Q39: capped per resource, overflow definitively lost.
        actual, refunds, _ = recoverable_refunds(balances, {str(order.id): refund_plan(order)})
        for r, value in refunds.items():
            balances[r].stock = amount(balances[r].stock + value)
            if balances[r].stock == balances[r].capacity:
                balances[r].remainder = 0
        if order.status == "active":
            event = session.scalar(
                select(ScheduledEvent).where(
                    ScheduledEvent.stream_id == state.stream_id,
                    ScheduledEvent.idempotency_key == f"ship-order:{order.id}",
                )
            )
            if event is None or event.status != "pending":
                raise TimelineError("Active production event missing or blocked")
            # Acknowledge the cancelled deadline: no partial ship, no blocking obsolete event.
            event.status, event.completed_at, event.error_code = "completed", utc(at), "cancelled"
        order.status, order.cancelled_at = "cancelled", utc(at)
        order.refunded = actual[str(order.id)]
        session.flush()
        activate_next(session, state, order.colony_id, at)
        return order


def colony_system(session, colony):
    return session.get(Planet, colony.planet_id).system_id


def garrison_for(session, colony):
    row = session.scalar(
        select(Fleet).where(Fleet.home_colony_id == colony.id, Fleet.kind == "GARRISON")
    )
    if row is None:
        name = session.get(Planet, colony.planet_id).name
        row = Fleet(
            empire_id=colony.empire_id,
            universe_id=colony.universe_id,
            home_colony_id=colony.id,
            kind="GARRISON",
            status="STATIONED",
            system_id=colony_system(session, colony),
            name=f"Garnison {name}"[:80],
        )
        session.add(row)
        session.flush()
    return row


def complete_order(session, event):
    if set(event.payload) != {"order_id"}:
        raise TimelineError("Invalid production payload")
    order = session.get(ShipOrder, UUID(event.payload["order_id"]))
    if order is None or order.universe_id != event.universe_id:
        raise TimelineError("Order outside event universe")
    state = galaxy.state_for(session, order.universe_id, order.empire_id)
    if state.stream_id != event.stream_id or event.idempotency_key != f"ship-order:{order.id}":
        raise TimelineError("Order outside event stream")
    if order.status == "completed":
        return
    rules = rules_for(session, order.universe_id)
    if (
        order.status != "active"
        or order.due_at != event.due_at
        or order.snapshot
        != snapshot_order(
            rules, order.ship_class, order.quantity, order.snapshot.get("colonizer_rank")
        )
        or order.due_at - order.started_at != timedelta(microseconds=order.snapshot["duration_us"])
    ):
        raise TimelineError("Inconsistent production snapshot/deadline")
    garrison = garrison_for(session, session.get(Colony, order.colony_id))
    # Atomic batch: the whole quantity appears at once, never a partial delivery.
    add_units(session, garrison.id, {order.ship_class: order.quantity})
    order.status, order.completed_at = "completed", event.due_at
    session.flush()
    activate_next(session, state, order.colony_id, event.due_at)


# --- Fleet composition and cargo ---------------------------------------------------------------


def stacks_of(session, fleet_id):
    return {
        s.ship_class: s.count
        for s in session.scalars(select(FleetStack).where(FleetStack.fleet_id == fleet_id))
    }


def cargo_of(session, fleet_id):
    return {
        c.resource: c.amount
        for c in session.scalars(select(FleetCargo).where(FleetCargo.fleet_id == fleet_id))
    }


def write_map(session, model, fleet_id, key_name, value_name, values):
    for row in session.scalars(select(model).where(model.fleet_id == fleet_id)):
        session.delete(row)
    session.flush()
    for key, value in sorted(values.items()):
        if value:
            session.add(model(fleet_id=fleet_id, **{key_name: key, value_name: value}))
    session.flush()


def set_stacks(session, fleet_id, values):
    write_map(session, FleetStack, fleet_id, "ship_class", "count", values)


def set_cargo(session, fleet_id, values):
    write_map(session, FleetCargo, fleet_id, "resource", "amount", values)


def add_units(session, fleet_id, units):
    current = stacks_of(session, fleet_id)
    for c, n in units.items():
        current[c] = current.get(c, 0) + n
    set_stacks(session, fleet_id, current)


def owned_fleet(session, universe_id, empire_id, fleet_id):
    row = session.get(Fleet, fleet_id, populate_existing=True)
    if row is None or row.universe_id != universe_id or row.empire_id != empire_id:
        raise FleetError("Fleet unavailable", "fleet_not_found")
    return row


def stationed(row):
    if row.status != "STATIONED":
        raise FleetError("Fleet is not stationed", "fleet_moving")
    return row


def parse_units(rules, units):
    if not isinstance(units, dict) or not units:
        raise FleetError("Units required", "invalid_request")
    result = {}
    for c, n in units.items():
        if c not in rules.fleets.classes or type(n) is not int or n < 1:
            raise FleetError("Invalid units", "invalid_request")
        result[c] = n
    return result


def parse_cargo(cargo):
    if cargo is None:
        return {}
    if not isinstance(cargo, dict) or not set(cargo) <= RESOURCES:
        raise FleetError("Invalid cargo", "invalid_request")
    return {r: micro(v) for r, v in cargo.items() if v}


def detach(session, rules, source, units, cargo):
    """Split a stationed Fleet: chosen units and cargo leave, each side within its capacity."""
    have, carried = stacks_of(session, source.id), cargo_of(session, source.id)
    if any(have.get(c, 0) < n for c, n in units.items()):
        raise FleetError("Units unavailable in fleet", "units_unavailable")
    if any(carried.get(r, 0) < v for r, v in cargo.items()):
        raise FleetError("Cargo unavailable in fleet", "cargo_unavailable")
    remaining = {c: have.get(c, 0) - units.get(c, 0) for c in have}
    remaining = {c: n for c, n in remaining.items() if n}
    kept = {r: carried.get(r, 0) - cargo.get(r, 0) for r in carried}
    if source.kind == "TASK" and not remaining:
        raise FleetError("A task fleet keeps at least one unit", "invalid_request")
    if sum(cargo.values()) > rules.fleets.cargo_capacity(units) or sum(
        kept.values()
    ) > rules.fleets.cargo_capacity(remaining):
        raise FleetError("Cargo exceeds a resulting fleet capacity", "cargo_capacity")
    count = session.scalar(
        select(func.count()).select_from(Fleet).where(Fleet.empire_id == source.empire_id)
    )
    new = Fleet(
        empire_id=source.empire_id,
        universe_id=source.universe_id,
        home_colony_id=source.home_colony_id,
        kind="TASK",
        status="STATIONED",
        system_id=source.system_id,
        name=f"Flotte {count}",
    )
    session.add(new)
    session.flush()
    set_stacks(session, source.id, remaining)
    set_cargo(session, source.id, kept)
    set_stacks(session, new.id, units)
    set_cargo(session, new.id, cargo)
    return new


def ledger(session, empire_id, key, kind, request):
    check_key(key)
    row = session.get(FleetOperation, (empire_id, key))
    if row is not None and (row.kind, row.request) != (kind, request):
        raise IdempotencyConflict("Fleet intention reused")
    return row


def record(session, universe_id, empire_id, key, kind, request, result, at):
    session.add(
        FleetOperation(
            empire_id=empire_id,
            idempotency_key=key,
            universe_id=universe_id,
            kind=kind,
            request=request,
            result=result,
            accepted_at=utc(at),
        )
    )
    session.flush()
    return result


def split(session, engine, universe_id, empire_id, fleet_id, units, cargo, *, key, at):
    with session.begin_nested():
        rules = rules_for(session, universe_id)
        operations(session, engine, universe_id, empire_id, at)
        request = {"fleet_id": str(fleet_id), "units": units, "cargo": cargo or {}}
        done = ledger(session, empire_id, key, "split", request)
        if done is not None:
            return done.result
        source = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
        new = detach(session, rules, source, parse_units(rules, units), parse_cargo(cargo))
        return record(
            session, universe_id, empire_id, key, "split", request, {"fleet_id": str(new.id)}, at
        )


def merge(session, engine, universe_id, empire_id, fleet_id, target_id, *, key, at):
    with session.begin_nested():
        rules_for(session, universe_id)
        operations(session, engine, universe_id, empire_id, at)
        request = {"fleet_id": str(fleet_id), "target_id": str(target_id)}
        done = ledger(session, empire_id, key, "merge", request)
        if done is not None:
            return done.result
        source = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
        target = stationed(owned_fleet(session, universe_id, empire_id, target_id))
        if source.id == target.id or source.kind != "TASK":
            raise FleetError("Only a task fleet merges into another", "invalid_request")
        if source.system_id != target.system_id:
            raise FleetError("Fleets are not in the same system", "fleet_elsewhere")
        # Stacks and cargo add up; combined capacity always covers combined cargo.
        add_units(session, target.id, stacks_of(session, source.id))
        total = cargo_of(session, target.id)
        for r, v in cargo_of(session, source.id).items():
            total[r] = amount(total.get(r, 0) + v)
        set_cargo(session, target.id, total)
        set_stacks(session, source.id, {})
        set_cargo(session, source.id, {})
        frontier.end_protocol(session, source, at)
        source.status, source.system_id = "MERGED", None
        session.flush()
        return record(
            session, universe_id, empire_id, key, "merge", request, {"fleet_id": str(target.id)}, at
        )


def set_protocol(session, engine, universe_id, empire_id, fleet_id, protocol, *, key, at):
    """13B FC1: set (or clear with None) the first-contact protocol of a stationed task Fleet.
    It holds until the Fleet leaves, merges or is destroyed, or the protocol is changed."""
    with session.begin_nested():
        rules = rules_for(session, universe_id)
        frontier.check_protocol(rules, protocol)
        operations(session, engine, universe_id, empire_id, at)
        request = {"fleet_id": str(fleet_id), "protocol": protocol}
        done = ledger(session, empire_id, key, "protocol", request)
        if done is not None:
            return done.result
        fleet = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
        if fleet.kind != "TASK":
            raise FleetError("Only an operational (task) fleet holds a protocol", "protocol_task")
        frontier.start_protocol(session, fleet, protocol, at)
        result = {"fleet_id": str(fleet.id), "protocol": protocol}
        return record(session, universe_id, empire_id, key, "protocol", request, result, at)


def colony_here(session, universe_id, empire_id, fleet, colony_id):
    colony = owned_colony(session, universe_id, empire_id, colony_id)
    if colony_system(session, colony) != fleet.system_id:
        raise FleetError("Fleet is not in this colony's system", "fleet_elsewhere")
    return colony


def load(session, engine, universe_id, empire_id, fleet_id, colony_id, cargo, *, key, at):
    with session.begin_nested():
        rules = rules_for(session, universe_id)
        operations(session, engine, universe_id, empire_id, at)
        request = {"fleet_id": str(fleet_id), "colony_id": str(colony_id), "cargo": cargo}
        done = ledger(session, empire_id, key, "load", request)
        if done is not None:
            return done.result
        fleet = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
        colony_here(session, universe_id, empire_id, fleet, colony_id)
        wanted = parse_cargo(cargo)
        if not wanted:
            raise FleetError("Nothing to load", "invalid_request")
        carried = cargo_of(session, fleet.id)
        capacity = rules.fleets.cargo_capacity(stacks_of(session, fleet.id))
        if sum(carried.values()) + sum(wanted.values()) > capacity:
            raise FleetError("Cargo exceeds fleet capacity", "cargo_capacity")
        catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        debit(session, colony_id, wanted)
        for r, v in wanted.items():
            carried[r] = amount(carried.get(r, 0) + v)
        set_cargo(session, fleet.id, carried)
        return record(session, universe_id, empire_id, key, "load", request, {"loaded": wanted}, at)


def unload_preview(session, fleet, colony_id, at):
    carried, estimate = cargo_of(session, fleet.id), estimated_balances(session, colony_id, at)
    credited = {
        r: min(v, max(0, (estimate[r].capacity or 0) - estimate[r].stock))
        for r, v in carried.items()
    }
    return {"credited": credited, "kept": {r: carried[r] - credited[r] for r in carried}}


def unload(session, engine, universe_id, empire_id, fleet_id, colony_id, *, key, at):
    with session.begin_nested():
        rules_for(session, universe_id)
        operations(session, engine, universe_id, empire_id, at)
        request = {"fleet_id": str(fleet_id), "colony_id": str(colony_id)}
        done = ledger(session, empire_id, key, "unload", request)
        if done is not None:
            return done.result
        fleet = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
        colony_here(session, universe_id, empire_id, fleet, colony_id)
        carried = cargo_of(session, fleet.id)
        if not carried:
            raise FleetError("Nothing to unload", "invalid_request")
        catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        # Up to free storage; the surplus stays aboard, never lost.
        credited, kept = credit_capped(session, colony_id, carried)
        set_cargo(session, fleet.id, kept)
        return record(
            session,
            universe_id,
            empire_id,
            key,
            "unload",
            request,
            {"credited": credited, "kept": {r: v for r, v in kept.items() if v}},
            at,
        )


# --- Missions ------------------------------------------------------------------------------------


NO_COST = dict.fromkeys(sorted(RESOURCES), 0)


def plan_colonize(session, rules, fleet, destination_id, stacks, target_planet_id):
    x = rules.colonization
    if x is None:
        raise FleetError("Colonization absent from pinned ruleset", "colonization_unavailable")
    if target_planet_id is None:
        raise FleetError("Target planet required", "invalid_request")
    known = session.get(PlanetKnowledge, (fleet.empire_id, target_planet_id))
    if known is None or known.universe_id != fleet.universe_id:
        raise FleetError("Planet not found", "planet_not_found")
    if destination_id not in (None, known.system_id):
        raise FleetError("Destination is the target planet's system", "invalid_request")
    if stacks != {x.colonizer_class: 1}:
        raise FleetError("COLONIZE engages exactly one colonizer", "colonize_units")
    if known.system_id == fleet.system_id:
        # Same system: 0 hop, no travel, no fuel, still resolved by the worker.
        return known.system_id, [], dict(NO_COST), 0, 0
    path = galaxy.known_path(
        session, fleet.universe_id, fleet.empire_id, fleet.system_id, known.system_id, mapped=True
    )
    cost, travel, _ = rules.fleets.mission_quote(
        stacks, len(path), rules.colony.speeds["fleet"], False
    )
    return known.system_id, path, cost, travel, 0


def round_trip(cost):
    """ATTACK pays its way back at launch: twice the one-way fuel, never debited again."""
    return {r: amount(2 * v) for r, v in cost.items()}


def plan_attack(session, rules, fleet, destination_id, stacks, target_planet_id):
    k = rules.combat
    if k is None:
        raise FleetError("Combat absent from pinned ruleset", "combat_unavailable")
    if target_planet_id is None:
        raise FleetError("Target planet required", "invalid_request")
    # A known planet only (PlanetKnowledge exists once its system is MAPPED or better).
    known = session.get(PlanetKnowledge, (fleet.empire_id, target_planet_id))
    if known is None or known.universe_id != fleet.universe_id:
        raise FleetError("Planet not found", "planet_not_found")
    if destination_id not in (None, known.system_id):
        raise FleetError("Destination is the target planet's system", "invalid_request")
    if not stacks or any(c not in k.classes for c in stacks):
        raise FleetError("ATTACK engages military units only", "attack_units")
    if known.system_id == fleet.system_id:
        # Same system: 0 hop, no travel, no fuel; the battle still waits the warning window.
        return known.system_id, [], dict(NO_COST), 0, 0
    path = galaxy.known_path(
        session, fleet.universe_id, fleet.empire_id, fleet.system_id, known.system_id, mapped=True
    )
    cost, travel, _ = rules.fleets.mission_quote(
        stacks, len(path), rules.colony.speeds["fleet"], False
    )
    return known.system_id, path, round_trip(cost), travel, 0


def battle_time(rules, started_at, travel_arrival_at):
    """Q02: never less than the minimum warning after launch, never before the arrival."""
    return max(
        utc(travel_arrival_at),
        utc(started_at) + timedelta(seconds=rules.combat.min_warning_seconds),
    )


def attack_terms(rules, target_planet_id, battle_at):
    """ATTACK-only snapshot part: target, accepted Combat rules and the battle instant."""
    return {
        "target_planet_id": str(target_planet_id),
        "combat": rules.combat.model_dump(),
        "battle_at": utc(battle_at).isoformat(),
    }


def check_attack(session, empire_id, target_planet_id, colony_read):
    """Own-knowledge refusal only. Under the planet row lock shared with COLONIZE, the
    occupant at launch is bound internally as the defender; nothing about it is returned."""
    session.scalar(select(Planet.id).where(Planet.id == target_planet_id).with_for_update())
    owner = session.scalar(select(Colony.empire_id).where(Colony.planet_id == target_planet_id))
    if owner == empire_id:
        code = "target_owned" if colony_read else "target_unavailable"
        raise FleetError("Target unavailable", code)
    return owner


def plan_mission(session, rules, fleet, kind, destination_id, stacks, target_planet_id=None):
    """Server path and quote; the client never chooses routes, durations or costs."""
    if kind == "COLONIZE":
        return plan_colonize(session, rules, fleet, destination_id, stacks, target_planet_id)
    if kind == "ATTACK":
        return plan_attack(session, rules, fleet, destination_id, stacks, target_planet_id)
    if kind not in ("DEPLOY", "SURVEY", "RETURN") or target_planet_id is not None:
        raise FleetError("Unknown mission", "invalid_request")
    home = colony_system(session, session.get(Colony, fleet.home_colony_id))
    if kind == "RETURN":
        if destination_id not in (None, home):
            raise FleetError("RETURN targets the home colony system", "invalid_request")
        destination_id = home
    if destination_id is None:
        raise FleetError("Destination required", "invalid_request")
    if kind == "SURVEY" and not all(rules.fleets.classes[c].survey for c in stacks):
        raise FleetError("SURVEY requires survey-capable units only", "survey_units")
    path = galaxy.known_path(
        session,
        fleet.universe_id,
        fleet.empire_id,
        fleet.system_id,
        destination_id,
        mapped=kind != "SURVEY",
    )
    cost, travel, survey = rules.fleets.mission_quote(
        stacks, len(path), rules.colony.speeds["fleet"], kind == "SURVEY"
    )
    return destination_id, path, cost, travel, survey


def colonize_terms(rules, target_planet_id, due_at, started_at, mission_id):
    """COLONIZE-only snapshot part: target, accepted expansion rules and the immutable rank."""
    return {
        "target_planet_id": str(target_planet_id),
        "colonization": rules.colonization.model_dump(),
        "rank": {
            "due_at": due_at.isoformat(),
            "started_at": started_at.isoformat(),
            "mission_id": str(mission_id),
        },
    }


def mission_snapshot(rules, kind, fleet_id, origin, destination, path, stacks, cargo, quote):
    cost, travel, survey = quote
    return {
        "version": rules.version,
        "engagement": rules.fleets.engagement_version,
        "kind": kind,
        "fleet_id": str(fleet_id),
        "origin_id": str(origin),
        "destination_id": str(destination),
        "path": [str(r) for r in path],
        "stacks": stacks,
        "cargo": cargo,
        "cost": cost,
        "travel_us": travel,
        "survey_us": survey,
        "speed": rules.colony.speeds["fleet"].model_dump(),
        "classes": {c: rules.fleets.classes[c].model_dump() for c in sorted(stacks)},
    }


def launch(
    session,
    engine,
    universe_id,
    empire_id,
    fleet_id,
    kind,
    destination_id,
    units,
    cargo,
    *,
    key,
    at,
    target_planet_id=None,
    colony_read=False,
):
    with session.begin_nested():
        rules = rules_for(session, universe_id)
        state = operations(session, engine, universe_id, empire_id, at)
        request = {
            "fleet_id": str(fleet_id),
            "kind": kind,
            "destination_id": str(destination_id) if destination_id else None,
            "units": units,
            "cargo": cargo or {},
        }
        if target_planet_id is not None:
            request["target_planet_id"] = str(target_planet_id)
        existing = session.scalar(
            select(FleetMission).where(
                FleetMission.empire_id == empire_id, FleetMission.idempotency_key == key
            )
        )
        if existing is not None:
            if existing.snapshot.get("request") != request:
                raise IdempotencyConflict("Mission intention reused")
            return existing
        check_key(key)
        source = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
        wanted, moved_cargo = parse_units(rules, units), parse_cargo(cargo)
        have = stacks_of(session, source.id)
        # A whole task fleet moves itself with its cargo; otherwise a detachment leaves.
        whole = source.kind == "TASK" and wanted == have and not moved_cargo
        stacks = have if whole else wanted
        if any(have.get(c, 0) < n for c, n in wanted.items()):
            raise FleetError("Units unavailable in fleet", "units_unavailable")
        destination, path, *quote = plan_mission(
            session, rules, source, kind, destination_id, stacks, target_planet_id
        )
        if kind == "COLONIZE":
            check_colonize(
                session,
                rules,
                empire_id,
                target_planet_id,
                cargo_of(session, source.id) if whole else moved_cargo,
                colony_read,
            )
        defender = None
        if kind == "ATTACK":
            if moved_cargo or (whole and cargo_of(session, source.id)):
                raise FleetError("ATTACK carries no cargo", "attack_cargo")
            defender = check_attack(session, empire_id, target_planet_id, colony_read)
        origin = source.system_id
        fleet = source if whole else detach(session, rules, source, wanted, moved_cargo)
        catch_up_owned(session, engine, universe_id, empire_id, fleet.home_colony_id, at)
        debit(session, fleet.home_colony_id, quote[0])
        travel_arrival = utc(at) + timedelta(microseconds=quote[1])
        due = travel_arrival + timedelta(microseconds=quote[2])
        if kind == "ATTACK":
            due = battle_time(rules, at, travel_arrival)
        mission_id = uuid4()
        snapshot = mission_snapshot(
            rules,
            kind,
            fleet.id,
            origin,
            destination,
            path,
            stacks,
            cargo_of(session, fleet.id),
            quote,
        )
        if kind == "COLONIZE":
            snapshot |= colonize_terms(rules, target_planet_id, due, utc(at), mission_id)
        if kind == "ATTACK":
            snapshot |= attack_terms(rules, target_planet_id, due)
        snapshot["request"] = request
        mission = FleetMission(
            id=mission_id,
            empire_id=empire_id,
            universe_id=universe_id,
            fleet_id=fleet.id,
            kind=kind,
            status="active",
            origin_id=origin,
            destination_id=destination,
            payer_colony_id=fleet.home_colony_id,
            target_planet_id=target_planet_id,
            idempotency_key=key,
            snapshot=snapshot,
            started_at=utc(at),
            travel_arrival_at=travel_arrival,
            due_at=due,
        )
        session.add(mission)
        session.flush()
        for ordinal, route_id in enumerate(path):
            session.add(
                FleetMissionLeg(
                    mission_id=mission.id,
                    ordinal=ordinal,
                    empire_id=empire_id,
                    universe_id=universe_id,
                    route_id=route_id,
                )
            )
        # A departing Fleet ends its stationing, hence any frontier protocol (13B).
        frontier.end_protocol(session, fleet, at)
        fleet.status, fleet.system_id, fleet.active_mission_id = "MOVING", None, mission.id
        session.flush()
        frontier.record_outbound(session, rules, mission, state.stream_id, path, quote[1])
        if kind == "ATTACK":
            # No arrival event: the Combat orchestrator resolves the engagement at battle_at.
            from app.combat.service import open_engagement

            open_engagement(session, mission, state.stream_id, defender)
            # After the engagement exists: a friendly watcher may react to this hostile entry.
            frontier.plan_for_mission(session, rules, mission)
            return mission
        schedule(
            session,
            state.stream_id,
            universe_id,
            key=f"fleet-arrival:{mission.id}",
            kind="FLEET_ARRIVAL",
            due_at=due,
            payload={"mission_id": str(mission.id)},
        )
        frontier.plan_for_mission(session, rules, mission)
        return mission


def check_colonize(session, rules, empire_id, target_planet_id, package, colony_read):
    """Own-knowledge checks only: foreign occupation is never checked (nor revealed) at launch."""
    x = rules.colonization
    owner = session.scalar(select(Colony.empire_id).where(Colony.planet_id == target_planet_id))
    if owner == empire_id:
        # Without colony.read, the exact own colony is not revealed by a specific code.
        code = "target_owned" if colony_read else "target_unavailable"
        raise FleetError("Target unavailable", code)
    active = session.scalar(
        select(func.count())
        .select_from(FleetMission)
        .where(
            FleetMission.empire_id == empire_id,
            FleetMission.kind == "COLONIZE",
            FleetMission.status == "active",
        )
    )
    if active >= x.max_active_missions:
        raise FleetError("A colonization is already under way", "colonization_active")
    colonies = session.scalar(
        select(func.count()).select_from(Colony).where(Colony.empire_id == empire_id)
    )
    if colonies + active >= x.max_colonies:
        raise FleetError("Colony limit reached for this ruleset", "colony_limit")
    if package is not None and any(package.get(r, 0) < v for r, v in x.package_minimum().items()):
        raise FleetError("Founding package below the minimum", "package_insufficient")


def preview(
    session,
    universe_id,
    empire_id,
    fleet_id,
    kind,
    destination_id,
    units,
    at,
    target_planet_id=None,
    colony_read=False,
):
    """Read-only quote of a launch; the command recomputes everything under lock."""
    rules = rules_for(session, universe_id)
    source = stationed(owned_fleet(session, universe_id, empire_id, fleet_id))
    wanted, have = parse_units(rules, units), stacks_of(session, source.id)
    if any(have.get(c, 0) < n for c, n in wanted.items()):
        raise FleetError("Units unavailable in fleet", "units_unavailable")
    destination, path, cost, travel, survey = plan_mission(
        session, rules, source, kind, destination_id, wanted, target_planet_id
    )
    if kind == "COLONIZE":
        # The package aboard is chosen at launch; the launch checks it against the minimum.
        check_colonize(session, rules, empire_id, target_planet_id, None, colony_read)
    if kind == "ATTACK":
        # Read-only: own target only; a foreign occupant or defence is never consulted.
        owner = session.scalar(select(Colony.empire_id).where(Colony.planet_id == target_planet_id))
        if owner == empire_id:
            raise FleetError(
                "Target unavailable", "target_owned" if colony_read else "target_unavailable"
            )
    estimate = estimated_balances(session, source.home_colony_id, at)
    travel_arrival = utc(at) + timedelta(microseconds=travel)
    quote = {
        "kind": kind,
        "destination_id": str(destination),
        "hops": len(path),
        "cost": cost,
        "travel_us": travel,
        "survey_us": survey,
        "travel_arrival_at": travel_arrival.isoformat(),
        "due_at": (travel_arrival + timedelta(microseconds=survey)).isoformat(),
        "payer_colony_id": str(source.home_colony_id),
        "affordable": all(estimate[r].stock >= cost[r] for r in cost),
        "target_planet_id": str(target_planet_id) if kind in ("COLONIZE", "ATTACK") else None,
        "package_minimum": rules.colonization.package_minimum() if kind == "COLONIZE" else None,
    }
    if kind == "ATTACK":
        quote["due_at"] = battle_time(rules, at, travel_arrival).isoformat()
        quote["battle_at"] = quote["due_at"]
        quote["units"] = wanted
    return quote


def check_mission_event(session, event, prefix):
    if set(event.payload) != {"mission_id"}:
        raise TimelineError("Invalid mission payload")
    mission = session.get(FleetMission, UUID(event.payload["mission_id"]))
    if mission is None or mission.universe_id != event.universe_id:
        raise TimelineError("Mission outside event universe")
    state = galaxy.state_for(session, mission.universe_id, mission.empire_id)
    if state.stream_id != event.stream_id or event.idempotency_key != f"{prefix}:{mission.id}":
        raise TimelineError("Mission outside event stream")
    return mission


def verified_path(session, mission, *, local=False):
    """Persisted legs must chain origin → destination; only a local COLONIZE has none."""
    legs = list(
        session.scalars(
            select(FleetMissionLeg)
            .where(FleetMissionLeg.mission_id == mission.id)
            .order_by(FleetMissionLeg.ordinal)
        )
    )
    node = mission.origin_id
    for leg in legs:
        route = session.get(GalaxyRoute, leg.route_id)
        if (
            route is None
            or route.universe_id != mission.universe_id
            or node
            not in (
                route.a_id,
                route.b_id,
            )
        ):
            raise TimelineError("Inconsistent mission path")
        node = route.b_id if route.a_id == node else route.a_id
    if local and not legs and mission.origin_id == mission.destination_id:
        return []
    if not legs or node != mission.destination_id:
        raise TimelineError("Inconsistent mission path")
    return [leg.route_id for leg in legs]


SNAPSHOT_KEYS = {
    "version",
    "engagement",
    "kind",
    "fleet_id",
    "origin_id",
    "destination_id",
    "path",
    "stacks",
    "cargo",
    "cost",
    "travel_us",
    "survey_us",
    "speed",
    "classes",
    "request",
}
COLONIZE_KEYS = SNAPSHOT_KEYS | {"target_planet_id", "colonization", "rank"}
ATTACK_KEYS = SNAPSHOT_KEYS | {"target_planet_id", "combat", "battle_at"}


def verify_mission_snapshot(session, mission, engaged=None):
    """Worker check of the accepted intention: the snapshot is rebuilt from the pinned ruleset,
    the persisted legs and the engaged composition, then compared exactly. Any drift is a
    TimelineError (rollback, retry then blocked), never a silent repositioning.

    `engaged`: after a battle, an ATTACK is checked against the composition it launched with
    (recorded in the resolved engagement), not against its survivors."""
    snapshot, fleet = mission.snapshot, session.get(Fleet, mission.fleet_id)
    rules = ruleset_for(session, mission.universe_id)
    colonize, attack = mission.kind == "COLONIZE", mission.kind == "ATTACK"
    keys = COLONIZE_KEYS if colonize else (ATTACK_KEYS if attack else SNAPSHOT_KEYS)
    if (
        rules.fleets is None
        or (colonize and rules.colonization is None)
        or (attack and rules.combat is None)
        or not isinstance(snapshot, dict)
        or set(snapshot) != keys
        or fleet is None
        or (fleet.universe_id, fleet.empire_id) != (mission.universe_id, mission.empire_id)
        or fleet.home_colony_id != mission.payer_colony_id
    ):
        raise TimelineError("Inconsistent mission snapshot")
    path = verified_path(session, mission, local=colonize or attack)
    stacks = stacks_of(session, fleet.id) if engaged is None else engaged
    # 13B: units destroyed by frontier engagements on the way were part of the launch.
    stacks = frontier_add(stacks, frontier.intercepted_losses(session, mission.id))
    survey = mission.kind == "SURVEY"
    try:
        if survey and not all(rules.fleets.classes[c].survey for c in stacks):
            raise ValueError("SURVEY with a non-survey class")
        if colonize and stacks != {rules.colonization.colonizer_class: 1}:
            raise ValueError("COLONIZE engages exactly one colonizer")
        if attack and (not stacks or any(c not in rules.combat.classes for c in stacks)):
            raise ValueError("ATTACK engages military units only")
        if attack and cargo_of(session, fleet.id):
            raise ValueError("ATTACK carries no cargo")
        if (colonize or attack) and not path:
            quote = (dict(NO_COST), 0, 0)
        else:
            quote = rules.fleets.mission_quote(
                stacks, len(path), rules.colony.speeds["fleet"], survey
            )
            if attack:
                quote = (round_trip(quote[0]), quote[1], quote[2])
    except (KeyError, ValueError):
        raise TimelineError("Inconsistent mission snapshot") from None
    expected = mission_snapshot(
        rules,
        mission.kind,
        fleet.id,
        mission.origin_id,
        mission.destination_id,
        path,
        stacks,
        cargo_of(session, fleet.id),
        quote,
    )
    if colonize:
        expected |= colonize_terms(
            rules, mission.target_planet_id, mission.due_at, mission.started_at, mission.id
        )
        minimum = rules.colonization.package_minimum()
        if any(cargo_of(session, fleet.id).get(r, 0) < v for r, v in minimum.items()):
            raise TimelineError("Inconsistent mission snapshot")
    if attack:
        expected |= attack_terms(rules, mission.target_planet_id, mission.due_at)
    if any(snapshot[k] != v for k, v in expected.items()):
        raise TimelineError("Inconsistent mission snapshot")
    if mission.kind == "RETURN" and mission.destination_id != colony_system(
        session, session.get(Colony, fleet.home_colony_id)
    ):
        raise TimelineError("Inconsistent mission snapshot")
    _, travel, survey_us = quote
    if mission.travel_arrival_at - mission.started_at != timedelta(microseconds=travel):
        raise TimelineError("Inconsistent mission deadlines")
    due = (
        battle_time(rules, mission.started_at, mission.travel_arrival_at)
        if attack
        else mission.travel_arrival_at + timedelta(microseconds=survey_us)
    )
    if mission.due_at != due:
        raise TimelineError("Inconsistent mission deadlines")


def settle_fleet(session, mission, system_id, at):
    fleet = session.get(Fleet, mission.fleet_id)
    if fleet.active_mission_id != mission.id or fleet.status != "MOVING":
        raise TimelineError("Fleet engagement inconsistent")
    fleet.status, fleet.system_id, fleet.active_mission_id = "STATIONED", system_id, None
    mission.status, mission.completed_at = "completed", at
    session.flush()


def complete_arrival(session, event, processed_at):
    mission = check_mission_event(session, event, "fleet-arrival")
    if mission.status == "completed" and session.get(FleetReport, mission.id) is not None:
        return
    if (
        mission.status != "active"
        or mission.due_at != event.due_at
        or (mission.recalled_at, mission.return_at) != (None, None)
    ):
        raise TimelineError("Inconsistent mission deadline")
    verify_mission_snapshot(session, mission)
    if mission.kind == "COLONIZE":
        return resolve_colonize(session, mission, event, processed_at)
    result = {"kind": mission.kind, "destination_id": str(mission.destination_id)}
    if mission.kind == "SURVEY":
        # Mapping happens at due_at only, after the analysis; same monotone Knowledge merge.
        result["discoveries"] = galaxy.map_system(
            session, mission.universe_id, mission.empire_id, mission.destination_id, event.due_at
        )
    session.add(
        FleetReport(
            mission_id=mission.id,
            empire_id=mission.empire_id,
            universe_id=mission.universe_id,
            observed_at=event.due_at,
            processed_at=utc(processed_at),
            result=result,
        )
    )
    settle_fleet(session, mission, mission.destination_id, event.due_at)


def lock_target(session, mission):
    """Row lock on the target planet (not a stream): serializes competing claims and recalls."""
    session.scalar(select(Planet.id).where(Planet.id == mission.target_planet_id).with_for_update())


def better_claim(session, mission):
    """A competing COLONIZE still awaiting resolution with a better immutable rank blocks."""
    rank = tuple_(literal(mission.due_at), literal(mission.started_at), literal(mission.id))
    return session.scalar(
        select(FleetMission.id)
        .where(
            FleetMission.universe_id == mission.universe_id,
            FleetMission.kind == "COLONIZE",
            FleetMission.target_planet_id == mission.target_planet_id,
            FleetMission.status == "active",
            FleetMission.recalled_at.is_(None),
            FleetMission.id != mission.id,
            tuple_(FleetMission.due_at, FleetMission.started_at, FleetMission.id) < rank,
        )
        .limit(1)
    )


def resolve_colonize(session, mission, event, processed_at):
    """Order-independent outcome: P free and no better active claim → found; else unavailable.

    Every better-ranked claim has due_at <= this one, so its recall window is already closed:
    the decision depends only on persisted missions and ranks, never on worker scheduling.
    """
    lock_target(session, mission)
    occupied = session.scalar(select(Colony.id).where(Colony.planet_id == mission.target_planet_id))
    base = {
        "kind": "COLONIZE",
        "destination_id": str(mission.destination_id),
        "planet_id": str(mission.target_planet_id),
    }
    if occupied is not None or better_claim(session, mission) is not None:
        # Same public result whatever the cause; no Empire, fleet, stock or activity revealed.
        result = base | {"outcome": "failed", "reason": "target_unavailable"}
        session.add(report_for(mission, event, processed_at, result))
        settle_fleet(session, mission, mission.destination_id, event.due_at)
        return
    fleet = session.get(Fleet, mission.fleet_id)
    if fleet.active_mission_id != mission.id or fleet.status != "MOVING":
        raise TimelineError("Fleet engagement inconsistent")
    colony = found_colony(
        session,
        mission.universe_id,
        mission.empire_id,
        mission.target_planet_id,
        mission.id,
        cargo_of(session, fleet.id),
        event.due_at,
    )
    # The colonizer becomes the Command Core; the whole committed cargo became its stock.
    set_stacks(session, fleet.id, {})
    set_cargo(session, fleet.id, {})
    fleet.status, fleet.system_id, fleet.active_mission_id = "SETTLED", None, None
    mission.status, mission.completed_at = "completed", event.due_at
    session.flush()
    result = base | {"outcome": "founded", "colony_id": str(colony.id)}
    session.add(report_for(mission, event, processed_at, result))
    # Handlers may run inside a Combat catch-up that locks a relation pair afterwards: no
    # presence contact here (pair → contact order); the next own refresh records it.
    galaxy.refresh_monitoring(
        session, mission.universe_id, mission.empire_id, event.due_at, contacts=False
    )
    session.flush()


def report_for(mission, event, processed_at, result):
    return FleetReport(
        mission_id=mission.id,
        empire_id=mission.empire_id,
        universe_id=mission.universe_id,
        observed_at=event.due_at,
        processed_at=utc(processed_at),
        result=result,
    )


def recall(session, engine, universe_id, empire_id, mission_id, *, key, at):
    with session.begin_nested():
        rules = rules_for(session, universe_id)
        state = operations(session, engine, universe_id, empire_id, at)
        request = {"mission_id": str(mission_id)}
        done = ledger(session, empire_id, key, "recall", request)
        mission = session.get(FleetMission, mission_id, populate_existing=True)
        if mission is None or mission.empire_id != empire_id or mission.universe_id != universe_id:
            raise FleetError("Mission unavailable", "mission_not_found")
        if done is None and mission.kind == "ATTACK" and mission.status == "returning":
            if mission.recalled_at is None:
                raise FleetError("The battle already took place", "recall_too_late")
        if done is not None or mission.status == "returning":
            return mission
        if mission.status == "completed":
            raise FleetError("Fleet already arrived", "recall_too_late")
        if mission.kind == "RETURN":
            raise FleetError("A return cannot be recalled", "recall_refused")
        if mission.kind == "ATTACK":
            return recall_attack(session, state, mission, key, request, at)
        if mission.kind == "COLONIZE":
            lock_target(session, mission)  # visible to a competing claim only once committed
        # DEPLOY until arrival; SURVEY only while travelling, never during the analysis.
        if utc(at) >= mission.travel_arrival_at:
            raise FleetError("Fleet already arrived", "recall_too_late")
        event = session.scalar(
            select(ScheduledEvent).where(
                ScheduledEvent.stream_id == state.stream_id,
                ScheduledEvent.idempotency_key == f"fleet-arrival:{mission.id}",
            )
        )
        if event is None or event.status != "pending":
            raise TimelineError("Arrival event missing or blocked")
        # Never schedule a return from a drifted mission: its origin comes from the snapshot.
        verify_mission_snapshot(session, mission)
        event.status, event.completed_at, event.error_code = "completed", utc(at), "cancelled"
        mission.status, mission.recalled_at = "returning", utc(at)
        mission.return_at = utc(at) + (utc(at) - mission.started_at)
        session.flush()
        frontier.record_way_back(session, rules, mission, state.stream_id, utc(at), utc(at))
        schedule(
            session,
            state.stream_id,
            universe_id,
            key=f"fleet-return:{mission.id}",
            kind="FLEET_RETURN",
            due_at=mission.return_at,
            payload={"mission_id": str(mission.id)},
        )
        frontier.plan_for_mission(session, rules, mission)
        record(session, universe_id, empire_id, key, "recall", request, request, at)
        return mission


def recall_attack(session, state, mission, key, request, at):
    """Until battle_at: symmetric way back while travelling, one full travel once arrived;
    a local (0 hop) attack is stationed at once. The engagement is cancelled, fences lifted."""
    from app.combat.service import cancel_engagement

    now = utc(at)
    if now >= mission.due_at:
        raise FleetError("The battle is due", "recall_too_late")
    verify_mission_snapshot(session, mission)
    cancel_engagement(session, mission, now)
    origin = mission.origin_id
    if origin == mission.destination_id:
        mission.recalled_at = mission.return_at = now
        session.add(
            FleetReport(
                mission_id=mission.id,
                empire_id=mission.empire_id,
                universe_id=mission.universe_id,
                observed_at=now,
                processed_at=now,
                result={"kind": "RECALLED", "destination_id": str(origin)},
            )
        )
        settle_fleet(session, mission, origin, now)
    else:
        travelled = (
            now - mission.started_at
            if now < mission.travel_arrival_at
            else mission.travel_arrival_at - mission.started_at
        )
        mission.status, mission.recalled_at = "returning", now
        mission.return_at = now + travelled
        session.flush()
        rules = ruleset_for(session, mission.universe_id)
        frontier.record_way_back(
            session, rules, mission, state.stream_id, now, min(now, mission.travel_arrival_at)
        )
        schedule(
            session,
            state.stream_id,
            mission.universe_id,
            key=f"fleet-return:{mission.id}",
            kind="FLEET_RETURN",
            due_at=mission.return_at,
            payload={"mission_id": str(mission.id)},
        )
        frontier.plan_for_mission(session, rules, mission)
    record(session, mission.universe_id, mission.empire_id, key, "recall", request, request, at)
    return mission


def complete_attack_return(session, mission, event, processed_at):
    from app.combat.models import CombatEngagement

    engagement = session.scalar(
        select(CombatEngagement).where(CombatEngagement.mission_id == mission.id)
    )
    travel = mission.travel_arrival_at - mission.started_at
    recalled = mission.recalled_at
    if engagement is None or mission.status != "returning" or mission.return_at != event.due_at:
        raise TimelineError("Inconsistent return deadline")
    if recalled is not None:
        back = recalled - mission.started_at if recalled < mission.travel_arrival_at else travel
        valid = engagement.state == "cancelled" and mission.return_at == recalled + back
        engaged, result = None, {"kind": "RECALLED"}
    else:
        valid = engagement.state == "resolved" and mission.return_at == mission.due_at + travel
        engaged = {c: n for c, n in engagement.snapshot["attacker"]["units"].items() if n}
        result = {
            "kind": "ATTACK",
            "engagement_id": str(engagement.id),
            "outcome": engagement.result["outcome"],
        }
    if not valid:
        raise TimelineError("Inconsistent return deadline")
    verify_mission_snapshot(session, mission, engaged)
    origin = UUID(mission.snapshot["origin_id"])
    session.add(
        FleetReport(
            mission_id=mission.id,
            empire_id=mission.empire_id,
            universe_id=mission.universe_id,
            observed_at=event.due_at,
            processed_at=utc(processed_at),
            result=result | {"destination_id": str(origin)},
        )
    )
    settle_fleet(session, mission, origin, event.due_at)


def complete_return(session, event, processed_at):
    mission = check_mission_event(session, event, "fleet-return")
    if mission.status == "completed" and session.get(FleetReport, mission.id) is not None:
        return
    if mission.kind == "ATTACK":
        return complete_attack_return(session, mission, event, processed_at)
    if (
        mission.status != "returning"
        or mission.return_at != event.due_at
        or mission.recalled_at is None
        or not mission.started_at <= mission.recalled_at < mission.travel_arrival_at
        or mission.return_at != mission.recalled_at + (mission.recalled_at - mission.started_at)
    ):
        raise TimelineError("Inconsistent return deadline")
    verify_mission_snapshot(session, mission)
    origin = UUID(mission.snapshot["origin_id"])
    session.add(
        FleetReport(
            mission_id=mission.id,
            empire_id=mission.empire_id,
            universe_id=mission.universe_id,
            observed_at=event.due_at,
            processed_at=utc(processed_at),
            result={"kind": "RECALLED", "destination_id": str(origin)},
        )
    )
    settle_fleet(session, mission, origin, event.due_at)
