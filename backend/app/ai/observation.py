"""Trusted bounded perception and candidate preconditions, exclusively from owned/known data.

The policy sees JSON only. Service quotes remain authoritative; candidate generation never
loads the world, another Empire's holdings, or a Fleet×Planet product.
"""

from copy import deepcopy
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, or_, select

from app.ai.policy import circular_page
from app.ai.rules import BOOTSTRAP_ORDER, fingerprint
from app.colony import service as colony
from app.fleet import service as fleet
from app.fleet.models import Fleet, FleetMission, FleetReport, FleetStack, ShipOrder
from app.galaxy import service as galaxy
from app.galaxy.models import PlanetKnowledge, RouteKnowledge, SystemKnowledge
from app.persistence.models import Colony
from app.relations import service as relations
from app.relations.models import RelationContact, RelationPair
from app.relations.rules import cooled_down, pair, proposal_open, recent
from app.research import service as research
from app.simulation.production import MICRO_UNITS as M
from app.simulation.production import RESOURCES


class ObservationLimit(ValueError):
    pass


def sql_page(session, query, column, cursor, size):
    """Disjoint keyset halves, each LIMITed before materialization; covers M in ceil(M/P) visits."""
    query = query.order_by(column)
    if cursor:
        marker = UUID(cursor)
        rows = list(session.scalars(query.where(column > marker).limit(size)))
        if len(rows) < size:
            rows += list(session.scalars(query.where(column <= marker).limit(size - len(rows))))
    else:
        rows = list(session.scalars(query.limit(size)))
    return rows


LOGISTICS_FLEET_LIMIT = 64


def protocol_fleets(session, rules, u, e, colonies):
    """B08: own operational (TASK) Fleets stationed in a system holding an own colony, except
    pure logistics (a lone colonizer, or a Fleet carrying cargo). Own data only, bounded."""
    systems = sorted({UUID(c["system_id"]) for c in colonies.values()}, key=str)
    if not systems:
        return []
    found = []
    for f in session.scalars(
        select(Fleet)
        .where(
            Fleet.universe_id == u,
            Fleet.empire_id == e,
            Fleet.kind == "TASK",
            Fleet.status == "STATIONED",
            Fleet.system_id.in_(systems),
        )
        .order_by(Fleet.id)
        .limit(LOGISTICS_FLEET_LIMIT)
    ):
        units = fleet.stacks_of(session, f.id)
        if fleet.cargo_of(session, f.id) or set(units) == {rules.colonization.colonizer_class}:
            continue
        found.append(str(f.id))
    return found


def protocol_posture(session, rules, profile, u, e, fleet_id, alerts, at):
    """B08 deterministic posture of one own Fleet, from facts this Empire really knows: its own
    contacts and relation pairs (dated hostile acts against it, pacts), its own anonymous
    detections in that system, its own Combat alerts. Never another Empire's holdings."""
    from app.frontier.encounter import known_enemy
    from app.frontier.models import FrontierDetection

    policy, f = rules.ai.frontier, session.get(Fleet, fleet_id)
    allowed = policy.protocols[profile]
    units = fleet.stacks_of(session, f.id)
    armed = any(c in rules.combat.classes and n for c, n in units.items())
    window = rules.frontier.ambush_window
    enemy = None
    if "AMBUSH" in allowed and armed:
        for contact in session.scalars(
            select(RelationContact)
            .where(RelationContact.universe_id == u, RelationContact.observer_empire_id == e)
            .order_by(RelationContact.observed_empire_id)
            .limit(LOGISTICS_FLEET_LIMIT)
        ):
            other = contact.observed_empire_id
            low, high = pair(e, other)
            row = session.get(RelationPair, (low, high))
            if row is None or relations.covering_pact(session, low, high, at) is not None:
                continue
            act = row.last_hostile_by_low_at if other == low else row.last_hostile_by_high_at
            if known_enemy(contact.first_seen_at, [act] if act else [], at, window):
                enemy = other
                break
    # Acceptable risk: no announced attack and no recent hostile act suffered from anyone.
    grievance_window = timedelta(seconds=rules.ai.diplomacy.grievance_seconds)
    grievance = bool(alerts) or any(
        recent(
            row.last_hostile_by_low_at if row.high_empire_id == e else row.last_hostile_by_high_at,
            at,
            grievance_window,
        )
        for row in session.scalars(
            select(RelationPair)
            .where(
                RelationPair.universe_id == u,
                or_(RelationPair.low_empire_id == e, RelationPair.high_empire_id == e),
            )
            .order_by(RelationPair.low_empire_id, RelationPair.high_empire_id)
            .limit(LOGISTICS_FLEET_LIMIT)
        )
    )
    sighted = session.scalar(
        select(FrontierDetection.id)
        .where(
            FrontierDetection.universe_id == u,
            FrontierDetection.observer_empire_id == e,
            FrontierDetection.system_id == f.system_id,
            FrontierDetection.identified.is_(False),
            FrontierDetection.detected_at > at - timedelta(seconds=policy.sighting_seconds),
            FrontierDetection.detected_at <= at,
        )
        .limit(1)
    )
    if enemy is not None:
        desired, basis, utility = "AMBUSH", "known_enemy", policy.ambush_utility
    elif "FRIENDLY_CONTACT" in allowed and sighted is not None and not grievance:
        desired, basis, utility = "FRIENDLY_CONTACT", "anonymous_sighting", policy.friendly_utility
    else:
        desired, basis, utility = "SURVEILLANCE", "presence", policy.surveillance_utility
    return {
        "fleet_id": str(f.id),
        "system_id": str(f.system_id),
        "current": f.protocol,
        "desired": desired,
        "basis": basis,
        "utility": utility,
    }


def collect(session, controller, rules, at):
    u, e, cfg = controller.universe_id, controller.empire_id, rules.ai
    memory = deepcopy(controller.memory)
    cursors = memory.setdefault("cursors", {})
    failed = memory.setdefault("failed_targets", {})
    owned = list(
        session.scalars(
            select(Colony)
            .where(Colony.universe_id == u, Colony.empire_id == e)
            .order_by(Colony.id)
            .limit(13)
        )
    )
    if len(owned) > rules.colonization.max_colonies:
        raise ObservationLimit("own_colony_budget")
    states, colonies = {}, {}
    for c in owned:
        state = colony.colony_state(session, c)
        states[str(c.id)] = state
        colonies[str(c.id)] = {
            "id": str(c.id),
            "planet_id": str(c.planet_id),
            "system_id": str(state.planet.system_id),
            "resources": {
                r: {
                    "stock": state.balances[r].stock,
                    "rate": state.balances[r].rate_per_hour,
                    "capacity": state.balances[r].capacity,
                }
                for r in sorted(RESOURCES)
            },
            "infrastructures": [
                {"sector": b.sector_index, "kind": b.infrastructure_type, "level": b.level}
                for b in sorted(state.infrastructures, key=lambda b: b.sector_index)
            ],
            "queue": [
                {
                    "sector": q.sector_index,
                    "kind": q.infrastructure_type,
                    "level": q.target_level,
                    "due_at": q.due_at.isoformat() if q.due_at else None,
                }
                for q in state.queue
            ],
        }
    systems = list(
        session.scalars(
            select(SystemKnowledge)
            .where(SystemKnowledge.universe_id == u, SystemKnowledge.empire_id == e)
            .order_by(SystemKnowledge.system_id)
            .limit(51)
        )
    )
    planets = list(
        session.scalars(
            select(PlanetKnowledge)
            .where(PlanetKnowledge.universe_id == u, PlanetKnowledge.empire_id == e)
            .order_by(PlanetKnowledge.planet_id)
            .limit(251)
        )
    )
    if len(systems) > 50 or len(planets) > 250:
        raise ObservationLimit("known_world_budget")
    known = {str(p.planet_id): p for p in planets}
    fleets = sql_page(
        session,
        select(Fleet).where(
            Fleet.universe_id == u, Fleet.empire_id == e, Fleet.status.in_(["STATIONED", "MOVING"])
        ),
        Fleet.id,
        cursors.get("fleets"),
        cfg.fleet_page_size,
    )
    if fleets:
        cursors["fleets"] = str(fleets[-1].id)
    fs = {
        str(f.id): {
            "id": str(f.id),
            "kind": f.kind,
            "status": f.status,
            "system_id": str(f.system_id) if f.system_id else None,
            "home_colony_id": str(f.home_colony_id),
            "units": fleet.stacks_of(session, f.id),
            "cargo": fleet.cargo_of(session, f.id),
        }
        for f in fleets
    }
    # Private failure memory comes solely from this Empire's own public reports.
    reports = sql_page(
        session,
        select(FleetReport).where(FleetReport.universe_id == u, FleetReport.empire_id == e),
        FleetReport.mission_id,
        cursors.get("reports"),
        64,
    )
    if reports:
        cursors["reports"] = str(reports[-1].mission_id)
    for report in reports:
        if report.result.get("reason") == "target_unavailable":
            target = report.result.get("planet_id")
            if target in known:
                failed[target] = {
                    "planet_id": target,
                    "observed_at": report.observed_at.isoformat(),
                    "reason": "target_unavailable",
                }
    if len(failed) > 250:
        raise ObservationLimit("failure_memory_budget")
    own_planets = {str(c.planet_id) for c in owned}
    project = memory.get("project")
    if project and (
        controller.sequence - project["since"] >= cfg.project_turn_limit
        or project.get("planet_id") in failed
        or project.get("planet_id") in own_planets
        or project.get("colony_id") not in {None, *colonies}
    ):
        memory.pop("project", None)
        project = None
    queued = list(
        session.scalars(
            select(ShipOrder)
            .where(
                ShipOrder.universe_id == u,
                ShipOrder.empire_id == e,
                ShipOrder.status.in_(["active", "queued"]),
            )
            .order_by(ShipOrder.colony_id, ShipOrder.sequence)
            .limit(37)
        )
    )
    if len(queued) > 36:
        raise ObservationLimit("ship_order_budget")
    acquired = {r.technology_id for r in research.acquired(session, e)}
    research_queue = research.pending(session, e)
    surveyed = bool(
        session.scalar(
            select(FleetMission.id)
            .where(
                FleetMission.universe_id == u,
                FleetMission.empire_id == e,
                FleetMission.kind == "SURVEY",
                FleetMission.status == "completed",
            )
            .limit(1)
        )
    )
    active_colonize = bool(
        session.scalar(
            select(FleetMission.id)
            .where(
                FleetMission.universe_id == u,
                FleetMission.empire_id == e,
                FleetMission.kind == "COLONIZE",
                FleetMission.status == "active",
            )
            .limit(1)
        )
    )
    counts = {}
    for ship in rules.fleets.classes:
        counts[ship] = session.scalar(
            select(func.coalesce(func.sum(FleetStack.count), 0))
            .join(Fleet, Fleet.id == FleetStack.fleet_id)
            .where(
                Fleet.universe_id == u,
                Fleet.empire_id == e,
                FleetStack.ship_class == ship,
                Fleet.status.in_(["STATIONED", "MOVING"]),
            )
        ) + sum(o.quantity for o in queued if o.ship_class == ship)
    candidates = []
    reserve = {
        cid: {
            r: sum(
                colony.construction_quote(rules, states[cid], kind, 1).cost[r]
                for kind in cfg.producers.values()
            )
            for r in RESOURCES
        }
        for cid in colonies
    }

    def add(
        goal,
        operation,
        body,
        utility,
        *,
        bootstrap=False,
        project_after=None,
        reason=None,
        priority=False,
    ):
        if len(candidates) >= cfg.candidate_limit:
            raise ObservationLimit("candidate_budget")
        cost, duration = dict.fromkeys(sorted(RESOURCES), 0), 0
        payer = body.get("colony_id")
        try:
            if operation == "build":
                q = colony.plan_order(
                    rules, states[payer], body["kind"], body["sector"], body["level"]
                )
                cost = dict(q.cost)
                duration = colony.effective_duration_us(
                    q.base_duration_us,
                    rules.colony.speeds["construction"],
                    colony.construction_bonus(rules, states[payer].infrastructures),
                )
            elif operation == "research":
                q = research.quote(session, u, e, body["technology"], UUID(payer))
                research.validate_start(session, e, body["technology"], q)
                cost, duration = dict(q.cost), q.duration_us
            elif operation == "order":
                fleet.check_unlocked(session, rules, UUID(payer), body["ship"])
                q = fleet.snapshot_order(
                    rules,
                    body["ship"],
                    1,
                    fleet.colonizer_rank(session, rules, e)
                    if body["ship"] == rules.colonization.colonizer_class
                    else None,
                    fleet.ship_bonus(session, e),
                )
                cost, duration = dict(q["cost"]), q["duration_us"]
                if sum(o.colony_id == UUID(payer) for o in queued) >= rules.fleets.queue_limit:
                    reason = reason or "queue_full"
            elif operation == "launch":
                q = fleet.preview(
                    session,
                    u,
                    e,
                    UUID(body["fleet_id"]),
                    body["kind"],
                    UUID(body["destination_id"]) if body.get("destination_id") else None,
                    body["units"],
                    at,
                    UUID(body["planet_id"]) if body.get("planet_id") else None,
                    True,
                )
                cost, duration, payer = (
                    q["cost"],
                    q["travel_us"] + q["survey_us"],
                    q["payer_colony_id"],
                )
            elif operation == "load":
                cost = fleet.parse_cargo(body["cargo"])
                f = fs[body["fleet_id"]]
                if sum(f["cargo"].values()) + sum(cost.values()) > rules.fleets.cargo_capacity(
                    f["units"]
                ):
                    reason = reason or "cargo_capacity"
            elif operation == "unload":
                f = next(f for f in fleets if str(f.id) == body["fleet_id"])
                if not any(fleet.unload_preview(session, f, UUID(payer), at)["credited"].values()):
                    reason = reason or "storage_full"
            if payer in colonies:
                for r in RESOURCES:
                    stock = colonies[payer]["resources"][r]["stock"]
                    if stock < cost.get(r, 0):
                        reason = reason or "insufficient_resources"
                    elif (
                        not bootstrap
                        and cost.get(r, 0)
                        and stock - cost.get(r, 0) < reserve[payer][r]
                    ):
                        reason = reason or "policy_reserve"
        except colony.ColonyError as error:
            reason = reason or error.code
        action = {"operation": operation, "body": body}
        candidates.append(
            {
                **action,
                "key": fingerprint(action | {"project": project_after}),
                "goal": goal,
                "utility": utility,
                "bootstrap": bootstrap,
                "reason": reason,
                "cost": {r: cost.get(r, 0) for r in sorted(RESOURCES)},
                "duration_us": duration,
                "project_after": project_after,
                "manages_project": project_after is not None or operation == "unload",
                **({"priority": True} if priority else {}),
            }
        )

    def page(family, references):
        # References are bounded owned/known identifiers, not quoted candidates or SQL world rows.
        chosen, cursor = circular_page(references, cursors.get(family, 0), cfg.family_pages[family])
        cursors[family] = cursor
        return chosen

    needed = {}
    economy_refs = []
    for cid, state in states.items():
        projected = {
            b.sector_index: (b.infrastructure_type, b.level) for b in state.infrastructures
        }
        projected.update(
            {q.sector_index: (q.infrastructure_type, q.target_level) for q in state.queue}
        )
        for kind in (cfg.producers[r] for r in BOOTSTRAP_ORDER):
            if not any(k == kind for k, _ in projected.values()):
                needed[cid] = kind
                break
        free = next(
            (i for i in range(1, state.planet.sector_capacity + 1) if i not in projected), 0
        )
        economy_refs.extend(
            (cid, free, kind, 1) for kind in sorted(rules.catalogue.infrastructures)
        )
        economy_refs.extend(
            (cid, i, kind, level + 1) for i, (kind, level) in sorted(projected.items())
        )
    for cid, sector, kind, level in page("economy", economy_refs):
        bootstrap = needed.get(cid) == kind and level == 1
        utility = 0
        for resource, producer in cfg.producers.items():
            if kind == producer:
                target = cfg.economy_target_per_hour[resource] * M
                rate = colonies[cid]["resources"][resource]["rate"]
                utility = max(0, min(1000, (target - rate) * 1000 // target))
        if kind == cfg.industry_kind:
            utility = cfg.industry_utility // level
        if kind in getattr(cfg, "unlocks", {}):
            utility = cfg.unlocks[kind] // level
        if kind == cfg.storage_kind:
            utility = (
                1000
                if any(
                    v["stock"] * 10000 >= v["capacity"] * cfg.storage_threshold_bps
                    for v in colonies[cid]["resources"].values()
                )
                else 0
            )
        add(
            "economy",
            "build",
            {"colony_id": cid, "kind": kind, "sector": sector, "level": level},
            1000 if bootstrap else utility,
            bootstrap=bootstrap,
            reason="bootstrap_order" if cid in needed and not bootstrap else None,
        )
    tech_refs = [(cid, tech) for cid in colonies for tech in sorted(rules.research.technologies)]
    for cid, tech in page("research", tech_refs):
        add(
            "research",
            "research",
            {"colony_id": cid, "technology": tech},
            1000 if not research_queue else cfg.research_queued_utility,
            reason="already_acquired" if tech in acquired else None,
        )

    def ship_fleet(ship):
        options = [f for f in fs.values() if f["status"] == "STATIONED" and f["units"].get(ship)]
        if not options:
            return None
        idx = cursors.get(f"source_{ship}", 0) % len(options)
        cursors[f"source_{ship}"] = idx + 1
        return options[idx]

    funding = list(colonies)
    funding_index = cursors.get("funding", 0)
    source_colony = funding[funding_index % len(funding)] if funding else None
    cursors["funding"] = (funding_index + 1) % max(1, len(funding))
    probe = ship_fleet("probe")
    detected = [str(s.system_id) for s in systems if s.state == "DETECTED"]
    for destination in page("exploration", detected):
        if probe:
            add(
                "exploration",
                "launch",
                {
                    "fleet_id": probe["id"],
                    "kind": "SURVEY",
                    "destination_id": destination,
                    "units": {"probe": 1},
                },
                1000,
            )
        elif source_colony:
            add(
                "exploration",
                "order",
                {"colony_id": source_colony, "ship": "probe"},
                1000,
                reason="probe_engaged" if counts["probe"] else None,
            )

    def prepare(ship, goal, dest_system, project_after, *, planet=None, supply=None):
        f = ship_fleet(ship)
        if not f:
            if source_colony:
                add(
                    goal,
                    "order",
                    {"colony_id": source_colony, "ship": ship},
                    1000,
                    project_after=project_after,
                    reason="unit_engaged" if counts[ship] else None,
                    bootstrap=supply is not None,
                )
            return
        if f["kind"] != "TASK" or f["units"] != {ship: 1}:
            add(
                goal,
                "split",
                {"fleet_id": f["id"], "units": {ship: 1}},
                1000,
                project_after=project_after,
                bootstrap=supply is not None,
            )
            return
        package = rules.colonization.package_minimum() if planet else supply["package"]
        gap = {r: max(0, package.get(r, 0) - f["cargo"].get(r, 0)) for r in RESOURCES}
        if any(gap.values()):
            local = [cid for cid, c in colonies.items() if c["system_id"] == f["system_id"]]
            here = local[funding_index % len(local)] if local else None
            if here:
                add(
                    goal,
                    "load",
                    {
                        "fleet_id": f["id"],
                        "colony_id": here,
                        "cargo": {r: (v + M - 1) // M for r, v in gap.items()},
                    },
                    1000,
                    project_after=project_after,
                    bootstrap=supply is not None,
                )
            else:
                add(
                    goal,
                    "launch",
                    {"fleet_id": f["id"], "kind": "RETURN", "units": {ship: 1}},
                    1000,
                    project_after=project_after,
                    bootstrap=supply is not None,
                )
        elif supply and f["system_id"] == dest_system:
            add(
                goal,
                "unload",
                {"fleet_id": f["id"], "colony_id": supply["colony_id"]},
                1000,
                project_after=None,
                bootstrap=True,
            )
        else:
            body = {
                "fleet_id": f["id"],
                "kind": "COLONIZE" if planet else "DEPLOY",
                "destination_id": dest_system,
                "units": {ship: 1},
            }
            if planet:
                body["planet_id"] = planet
            add(
                goal,
                "launch",
                body,
                1000,
                project_after=project_after,
                bootstrap=supply is not None,
            )

    for target in page("expansion", list(known)):
        if target in own_planets or target in failed or active_colonize or project:
            # The reference was visited, without discovering any foreign occupant.
            continue
        if not surveyed and cfg.expansion_before_survey_utility == 0:
            continue
        prepare(
            rules.colonization.colonizer_class,
            "expansion",
            str(known[target].system_id),
            {"kind": "colonize", "planet_id": target, "since": controller.sequence},
            planet=target,
        )
    # A live project gets a reserved logistics slot; it does not displace the circular planet page.
    logistics_refs = ([project] if project else []) + [
        {"kind": "supply", "colony_id": cid, "since": controller.sequence}
        for cid in needed
        if any(
            colonies[cid]["resources"][r]["stock"]
            < colony.construction_quote(rules, states[cid], needed[cid], 1).cost[r]
            and colonies[cid]["resources"][r]["rate"] == 0
            for r in RESOURCES
        )
    ]
    for task in page("logistics", logistics_refs):
        if task["kind"] == "colonize":
            target = task["planet_id"]
            if target in known and not active_colonize:
                prepare(
                    rules.colonization.colonizer_class,
                    "expansion",
                    str(known[target].system_id),
                    task,
                    planet=target,
                )
        elif task["colony_id"] in needed:
            cid = task["colony_id"]
            package = dict(colony.construction_quote(rules, states[cid], needed[cid], 1).cost)
            prepare(
                "freighter",
                "logistics",
                colonies[cid]["system_id"],
                task,
                supply={"colony_id": cid, "package": package},
            )
    # v0.7 defensive goal: keep a few military units at each own colony; an own incoming alert
    # (planet, battle_at, state: the defender's legitimate knowledge) raises its utility.
    # Never an offensive candidate: the dispatcher has no combat capability at all.
    alerts = []
    military = getattr(cfg, "military", None)
    watch = getattr(cfg, "frontier", None)
    postures = []
    if military is not None:
        from app.combat.service import alerts_for

        alerts = alerts_for(session, u, e, limit=24, history=False)
        threatened = {a["planet_id"] for a in alerts}
        ship = military.ship_class
        references = list(colonies)
        if watch is not None:
            # v0.9 (B08): protocol choices share the military page and budget, after colonies.
            watched = protocol_fleets(session, rules, u, e, colonies)
            references += [f"fleet:{fid}" for fid in watched]
        for ref in page("military", references):
            if ref.startswith("fleet:"):
                posture = protocol_posture(
                    session, rules, controller.profile, u, e, UUID(ref[6:]), alerts, at
                )
                postures.append(posture)
                if posture["desired"] != posture["current"]:
                    add(
                        "military",
                        "protocol",
                        {"fleet_id": posture["fleet_id"], "protocol": posture["desired"]},
                        posture["utility"],
                    )
                continue
            cid = ref
            here = session.scalar(
                select(func.coalesce(func.sum(FleetStack.count), 0))
                .join(Fleet, Fleet.id == FleetStack.fleet_id)
                .where(
                    Fleet.universe_id == u,
                    Fleet.empire_id == e,
                    Fleet.status == "STATIONED",
                    Fleet.system_id == UUID(colonies[cid]["system_id"]),
                    FleetStack.ship_class == ship,
                )
            ) + sum(o.quantity for o in queued if o.ship_class == ship and str(o.colony_id) == cid)
            if here >= military.target_per_colony:
                continue
            urgent = colonies[cid]["planet_id"] in threatened
            add(
                "military",
                "order",
                {"colony_id": cid, "ship": ship},
                military.alert_utility if urgent else military.baseline_utility,
                priority=urgent,
            )
    # v0.8 diplomacy (Q18 B8): only this Empire's own contacts and pairs. One slot answers the
    # oldest open incoming proposal (priority, consumes the turn); the rest of the page visits own
    # contacts circularly for a spontaneous proposal. Never a withdrawal, a rupture or an attack.
    diplomacy = getattr(cfg, "diplomacy", None)
    seen = []
    if diplomacy is not None:
        window = timedelta(seconds=diplomacy.grievance_seconds)

        def theirs(row, other):
            if row is None:
                return None
            if other == row.low_empire_id:
                return row.last_hostile_by_low_at
            return row.last_hostile_by_high_at

        received = session.scalar(
            select(RelationPair)
            .where(
                RelationPair.universe_id == u,
                or_(RelationPair.low_empire_id == e, RelationPair.high_empire_id == e),
                RelationPair.proposal_by_empire_id.is_not(None),
                RelationPair.proposal_by_empire_id != e,
                RelationPair.proposal_expires_at > at,
            )
            .order_by(
                RelationPair.proposed_at, RelationPair.low_empire_id, RelationPair.high_empire_id
            )
            .limit(1)
        )
        if received is not None:
            other = received.proposal_by_empire_id
            grievance = recent(theirs(received, other), at, window)
            add(
                "diplomacy",
                "relation",
                {"action": "refuse" if grievance else "accept", "counterpart_id": str(other)},
                diplomacy.response_utility,
                priority=True,
            )
            seen.append(
                {
                    "counterpart_id": str(other),
                    "incoming_proposal": True,
                    "hostile_by_counterpart_at": theirs(received, other).isoformat()
                    if theirs(received, other)
                    else None,
                }
            )
        rule = diplomacy.proposal_rules[controller.profile]
        contacts = sql_page(
            session,
            select(RelationContact).where(
                RelationContact.universe_id == u, RelationContact.observer_empire_id == e
            ),
            RelationContact.observed_empire_id,
            cursors.get("contacts"),
            cfg.family_pages["diplomacy"] - 1,
        )
        if contacts:
            cursors["contacts"] = str(contacts[-1].observed_empire_id)
        for contact in contacts:
            other = contact.observed_empire_id
            low, high = pair(e, other)
            row = session.get(RelationPair, (low, high))
            fact = theirs(row, other)
            mine = None
            if row is not None:
                mine = row.low_cooldown_until if e == low else row.high_cooldown_until
            reason = None
            if row is not None and relations.covering_pact(session, low, high, at) is not None:
                reason = "pact_active"
            elif row is not None and proposal_open(row.proposal_expires_at, at):
                reason = "proposal_open"
            elif not cooled_down(mine, at):
                reason = "proposal_cooldown"
            elif recent(fact, at, window):
                reason = "recent_grievance"
            elif rule == "past_grievance_only" and fact is None:
                reason = "no_past_grievance"
            add(
                "diplomacy",
                "relation",
                {"action": "propose", "counterpart_id": str(other)},
                diplomacy.proposal_utility,
                reason=reason,
            )
            seen.append(
                {
                    "counterpart_id": str(other),
                    "incoming_proposal": False,
                    "hostile_by_counterpart_at": fact.isoformat() if fact else None,
                    "reason": reason,
                }
            )
    # Reject rather than silently truncate oversized/unbounded entity state.
    routes = list(
        session.scalars(
            select(RouteKnowledge)
            .where(RouteKnowledge.universe_id == u, RouteKnowledge.empire_id == e)
            .order_by(RouteKnowledge.route_id)
            .limit(101)
        )
    )
    if len(routes) > 100:
        raise ObservationLimit("route_budget")
    observation = {
        "at": at.isoformat(),
        "colonies": list(colonies.values()),
        "systems": [galaxy.project_system(session, s) for s in systems],
        "routes": [{"id": str(r.route_id), "a": str(r.a_id), "b": str(r.b_id)} for r in routes],
        "fleets": list(fs.values()),
        "acquired": sorted(acquired),
        "research_queue": [
            {"id": str(q.id), "technology": q.technology_id} for q in research_queue
        ],
        "unit_counts": counts,
        "candidates": candidates,
        **({"alerts": alerts} if military is not None else {}),
        **({"relations": seen} if diplomacy is not None else {}),
        **({"frontier": postures} if watch is not None else {}),
    }
    return observation, memory
