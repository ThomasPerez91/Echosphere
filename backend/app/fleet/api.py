"""Public Fleet API: GameSession → binding permissions → Empire scope, then the Fleet services.

Projections read persisted state only: they never catch up the Empire Operations stream, so a GET
can never finish a production or move a Fleet (worker or command only). Commands namespace
their intention keys per membership and count as explicit activity. No Portal call.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select

from app.access.http import cookie_name
from app.access.service import AccessError
from app.colony.api import Colonies, bootstrap, call, command
from app.colony.projection import amounts
from app.colony.service import rules_for
from app.combat import service as combat
from app.control.models import EmpireBinding
from app.fleet import service
from app.fleet.models import Fleet, FleetMission, FleetReport, ShipOrder
from app.frontier import service as frontier
from app.galaxy import service as galaxy
from app.galaxy.models import PlanetKnowledge, SystemKnowledge
from app.persistence.models import Colony, Empire, Planet
from app.simulation.scheduler import lock_stream

router = APIRouter(prefix="/game/{universe_id}/fleets")

UUID_PATTERN = r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$"
Key = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
Units = dict[str, int]
Cargo = dict[Literal["alloys", "flux", "data"], int]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Order(Body):
    idempotency_key: str = Key
    colony_id: str = Field(pattern=UUID_PATTERN)
    ship_class: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    quantity: int = Field(ge=1, le=1000)


class Plan(Body):
    fleet_id: str = Field(pattern=UUID_PATTERN)
    kind: Literal[
        "DEPLOY", "SURVEY", "RETURN", "COLONIZE", "ATTACK", "PROSPECT", "STUDY", "EXTRACT"
    ]
    destination_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    target_planet_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    # EXP-02 (v0.10): the curiosity a STUDY analyses, the deposit an EXTRACT works.
    target_opportunity_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    # EXP-02b: extraction length in whole hours (bounded by the pinned ruleset).
    duration_hours: int | None = Field(default=None, ge=1, le=1000)
    # EXP-02b: after the extraction, stay in the deposit's system (default) or come back.
    after: Literal["STAY", "RETURN"] | None = None
    units: Units = Field(min_length=1, max_length=16)


class Launch(Plan):
    idempotency_key: str = Key
    cargo: Cargo | None = None


class Keyed(Body):
    idempotency_key: str = Key


class Split(Keyed):
    units: Units = Field(min_length=1, max_length=16)
    cargo: Cargo | None = None


class Merge(Keyed):
    target_id: str = Field(pattern=UUID_PATTERN)


class Load(Keyed):
    colony_id: str = Field(pattern=UUID_PATTERN)
    cargo: Cargo = Field(min_length=1)


class ProtocolChoice(Keyed):
    protocol: Literal["SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"] | None


class Unload(Keyed):
    colony_id: str = Field(pattern=UUID_PATTERN)


def system_ref(session, empire_id, system_id, *, detected=True):
    known = session.get(SystemKnowledge, (empire_id, system_id)) if system_id else None
    if known is None or (known.state == "DETECTED" and not detected):
        return None
    ref = {"id": str(system_id), "state": known.state}
    if known.state != "DETECTED":
        ref["name"] = known.known_name
    return ref


def scrub(result, permissions):
    """Reports carry Knowledge projections: Colony ids stay behind colony.read."""
    if "colony.read" in permissions:
        return result
    system = (result.get("discoveries") or {}).get("system")
    if system and system.get("observation"):
        system = {**system, "observation": None}
        result = {**result, "discoveries": {**result["discoveries"], "system": system}}
    if result.get("colony_id"):
        result = {**result, "colony_id": None}  # the founding is reported, the Colony is not
    return result


def known_planets(session, empire_id, system_id, owned):
    """Structure from Knowledge only; an own Colony is named only with colony.read (`owned`)."""
    return [
        {
            "id": str(p.planet_id),
            "name": p.known_name,
            "sector_capacity": p.sector_capacity,
            "orbital_capacity": p.orbital_capacity,
            "colony_id": owned.get(p.planet_id),
        }
        for p in session.scalars(
            select(PlanetKnowledge)
            .where(PlanetKnowledge.empire_id == empire_id, PlanetKnowledge.system_id == system_id)
            .order_by(PlanetKnowledge.planet_id)
        )
    ]


def mission_view(session, mission, permissions, known):
    report = session.get(FleetReport, mission.id)
    snap = mission.snapshot
    # UX-API-01: the route as launched (persisted legs), only through systems the Empire knows.
    path = service.mission_path(session, mission, known)
    return ({"path": path} if path is not None else {}) | {
        "id": str(mission.id),
        "fleet_id": str(mission.fleet_id),
        "kind": mission.kind,
        "status": mission.status,
        "origin": system_ref(session, mission.empire_id, mission.origin_id),
        "destination": system_ref(session, mission.empire_id, mission.destination_id),
        "hops": len(snap["path"]),
        "stacks": snap["stacks"],
        "cargo": amounts(snap["cargo"]),
        "cost": amounts(snap["cost"]),
        "started_at": mission.started_at.isoformat(),
        "travel_arrival_at": mission.travel_arrival_at.isoformat(),
        "due_at": mission.due_at.isoformat(),
        "recalled_at": mission.recalled_at.isoformat() if mission.recalled_at else None,
        "return_at": mission.return_at.isoformat() if mission.return_at else None,
        "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
        # Like Research/Exploration: the paying colony is shown only with colony.read.
        "payer_colony_id": str(mission.payer_colony_id) if "colony.read" in permissions else None,
        "target_planet": {
            "id": str(mission.target_planet_id),
            "name": session.get(
                PlanetKnowledge, (mission.empire_id, mission.target_planet_id)
            ).known_name,
        }
        if mission.target_planet_id
        else None,
        # Own engagement state and battle instant only; the defender is never projected.
        "attack": combat.attack_of(session, mission) if mission.kind == "ATTACK" else None,
        "report": {
            "observed_at": report.observed_at.isoformat(),
            "processed_at": report.processed_at.isoformat(),
            "result": scrub(report.result, permissions),
        }
        if report
        else None,
    }


def project(session, universe_id, empire_id, permissions, at):
    rules = rules_for(session, universe_id)
    base = {
        "server_time": at.isoformat(),
        "empire": {"id": str(empire_id), "name": session.get(Empire, empire_id).name},
        "permissions": permissions,
        "available": rules.fleets is not None,
    }
    if rules.fleets is None:
        return base
    f = rules.fleets
    colony_read = "colony.read" in permissions
    colonies = list(
        session.scalars(
            select(Colony)
            .where(Colony.universe_id == universe_id, Colony.empire_id == empire_id)
            .order_by(Colony.created_at, Colony.id)
        )
    )
    systems = {c.id: service.colony_system(session, c) for c in colonies}
    colony_views = []
    for colony in colonies if colony_read else []:
        orders = session.scalars(
            select(ShipOrder)
            .where(ShipOrder.colony_id == colony.id, ShipOrder.status.in_(service.OPEN))
            .order_by(ShipOrder.sequence)
        )
        colony_views.append(
            {
                "id": str(colony.id),
                "name": session.get(Planet, colony.planet_id).name,
                "system_id": str(systems[colony.id]),
                "orders": [
                    {
                        "id": str(o.id),
                        "ship_class": o.ship_class,
                        "quantity": o.quantity,
                        "status": o.status,
                        "accepted_at": o.accepted_at.isoformat(),
                        "started_at": o.started_at.isoformat() if o.started_at else None,
                        "due_at": o.due_at.isoformat() if o.due_at else None,
                        "cost": amounts(o.snapshot["cost"]),
                        "cancel": {
                            k: amounts(v) for k, v in service.cancel_preview(session, o, at).items()
                        }
                        if "fleet.build" in permissions
                        else None,
                    }
                    for o in orders
                ],
            }
        )
    fleet_views = []
    for fleet in session.scalars(
        select(Fleet)
        .where(
            Fleet.empire_id == empire_id,
            Fleet.status.notin_(("MERGED", "SETTLED", "DESTROYED")),
        )
        .order_by(Fleet.kind, Fleet.created_at, Fleet.id)
    ):
        stacks = service.stacks_of(session, fleet.id)
        # Every own Colony of this system, chosen explicitly to load/unload: never "the first".
        here = [c for c in colonies if fleet.system_id and systems[c.id] == fleet.system_id]
        carried = service.cargo_of(session, fleet.id)
        mission = (
            session.get(FleetMission, fleet.active_mission_id) if fleet.active_mission_id else None
        )
        fleet_views.append(
            {
                "id": str(fleet.id),
                "name": fleet.name,
                "kind": fleet.kind,
                "status": fleet.status,
                "home_colony_id": str(fleet.home_colony_id) if colony_read else None,
                "system": system_ref(session, empire_id, fleet.system_id),
                "stacks": stacks,
                "cargo": amounts(carried),
                "capacity": str(f.cargo_capacity(stacks)),
                "mission_id": str(mission.id) if mission else None,
                # 13B (v0.9): first-contact protocol of a stationed task Fleet, else null.
                "protocol": fleet.protocol,
                "colonies_here": [
                    {
                        "id": str(c.id),
                        "name": session.get(Planet, c.planet_id).name,
                        "unload": {
                            k: amounts(v)
                            for k, v in service.unload_preview(session, fleet, c.id, at).items()
                        }
                        if carried
                        else None,
                    }
                    for c in (here if colony_read else [])
                ],
            }
        )
    # Every open mission (in-flight list, recall, deadlines) plus the 30 latest completed ones:
    # the history limit never hides a fleet still travelling.
    recent = (
        select(FleetMission.id)
        .where(FleetMission.empire_id == empire_id, FleetMission.status == "completed")
        .order_by(FleetMission.started_at.desc(), FleetMission.id)
        .limit(30)
    )
    missions = session.scalars(
        select(FleetMission)
        .where(
            FleetMission.empire_id == empire_id,
            or_(FleetMission.status.in_(("active", "returning")), FleetMission.id.in_(recent)),
        )
        .order_by(FleetMission.started_at.desc(), FleetMission.id)
    )
    known = session.scalars(
        select(SystemKnowledge)
        .where(SystemKnowledge.universe_id == universe_id, SystemKnowledge.empire_id == empire_id)
        .order_by(SystemKnowledge.system_id)
    )
    galaxy_read = "galaxy.read" in permissions
    known_ids = service.known_systems(session, universe_id, empire_id)
    owned = {c.planet_id: str(c.id) for c in colonies} if colony_read else {}
    x = rules.colonization
    colonization = None
    if x is not None:
        quote = service.colonizer_quote(session, rules, empire_id)
        colonization = {
            "colonizer_class": x.colonizer_class,
            "package_minimum": amounts(x.package_minimum()),
            "max_colonies": x.max_colonies,
            "max_active_missions": x.max_active_missions,
            # The progressive price depends on the colony count: production rights only.
            "colonizer_quote": {
                "rank": quote["rank"],
                "multiplier_bps": quote["multiplier_bps"],
                "cost": amounts(quote["cost"]),
            }
            if colony_read and "fleet.build" in permissions
            else None,
        }
    systems_view = []
    for k in known:
        ref = system_ref(session, empire_id, k.system_id, detected=galaxy_read)
        if ref is None:
            continue
        if x is not None and ref["state"] != "DETECTED":
            ref["planets"] = known_planets(session, empire_id, k.system_id, owned)
        systems_view.append(ref)
    return base | {
        "catalogue": {
            key: {
                "name": ship.name,
                "cost": amounts(f.order_quote(key, 1)[0]),
                "build_us": str(f.order_quote(key, 1)[1]),
                "hop_seconds": ship.hop_seconds,
                "flux_per_hop": ship.flux_per_hop,
                "cargo": str(f.cargo_capacity({key: 1})),
                "survey": ship.survey,
            }
            for key, ship in f.classes.items()
        },
        "queue_limit": f.queue_limit,
        "max_quantity": f.max_quantity,
        "colonies": colony_views,
        "fleets": fleet_views,
        "missions": [mission_view(session, m, permissions, known_ids) for m in missions],
        "colonization": colonization,
        "frontier": frontier_view(session, rules, universe_id, empire_id),
        "combat": combat_view(session, rules, universe_id, empire_id, permissions),
        # Destinations come from Knowledge only; DETECTED signals need galaxy.read (SURVEY).
        "systems": systems_view,
    }


def frontier_view(session, rules, universe_id, empire_id):
    """13B: enabled protocols and this Empire's own detections (anonymous unless identified)."""
    if rules.frontier is None:
        return None

    def name(empire):
        row = session.get(Empire, empire)
        return row.name if row else None

    return {
        "protocols": list(rules.frontier.protocols),
        "detections": frontier.detections_for(
            session,
            universe_id,
            empire_id,
            name,
            lambda system: system_ref(session, empire_id, system),
        ),
        "encounters": frontier.encounters_for(
            session,
            universe_id,
            empire_id,
            name,
            lambda system: system_ref(session, empire_id, system),
        ),
    }


def combat_view(session, rules, universe_id, empire_id, permissions):
    """Ruleset terms; incoming alerts and dated reports only with combat.read."""
    k = rules.combat
    if k is None:
        return None
    readable = "combat.read" in permissions
    return {
        "classes": list(k.classes),
        "min_warning_seconds": k.min_warning_seconds,
        "alerts": combat.alerts_for(session, universe_id, empire_id) if readable else None,
        "reports": combat.reports_for(session, universe_id, empire_id) if readable else None,
    }


class Fleets(Colonies):
    def authorize_empire(self, session, raw, universe_id, empire_id, needed=(), *, act=False):
        row, access = self.sessions.locked(session, raw, universe_id)
        binding = session.get(EmpireBinding, (access.membership_id, empire_id))
        if (
            binding is None
            or binding.universe_id != universe_id
            or "fleet.read" not in binding.permissions
        ):
            raise AccessError("empire_not_found", 404)
        if not set(needed) <= set(binding.permissions):
            raise AccessError("permission_denied", 403)
        if act:
            row.last_activity_at = self.clock.now()
        return list(binding.permissions), access

    def listing(self, raw, universe_id):
        with self.factory.begin() as session:
            _, access = self.sessions.locked(session, raw, universe_id)
            rows = session.execute(
                select(Empire, EmpireBinding)
                .join(EmpireBinding, EmpireBinding.empire_id == Empire.id)
                .where(
                    Empire.universe_id == universe_id,
                    EmpireBinding.universe_id == universe_id,
                    EmpireBinding.membership_id == access.membership_id,
                )
                .order_by(Empire.name, Empire.id)
            ).all()
            return {
                "empires": [
                    {"id": str(e.id), "name": e.name}
                    for e, b in rows
                    if "fleet.read" in b.permissions
                ]
            }

    def read(self, raw, universe_id, empire_id):
        with self.factory.begin() as session:
            permissions, _ = self.authorize_empire(session, raw, universe_id, empire_id)
            if rules_for(session, universe_id).fleets is not None:
                # Like Galaxy: lock the Empire Operations stream, never catch it up. The worker
                # holds it while applying an event, so fleets, missions and reports are read
                # from one consistent state (never MOVING with an already completed mission).
                state = galaxy.state_for(session, universe_id, empire_id)
                lock_stream(session, state.stream_id, universe_id)
            return project(session, universe_id, empire_id, permissions, self.clock.now())

    def act(self, raw, universe_id, empire_id, needed, operation, *, with_rights=False):
        with self.factory.begin() as session:
            permissions, access = self.authorize_empire(
                session, raw, universe_id, empire_id, needed, act=True
            )
            at = self.clock.now()
            ns = f"http:{access.membership_id}:"
            if with_rights:
                result = operation(session, at, ns, permissions)
            else:
                result = operation(session, at, ns)
            return {
                "result": result,
                "fleets": project(session, universe_id, empire_id, permissions, at),
            }

    def order(self, raw, universe_id, empire_id, body: Order):
        def run(session, at, ns):
            row = service.order_ships(
                session,
                self.engine,
                universe_id,
                empire_id,
                UUID(body.colony_id),
                body.ship_class,
                body.quantity,
                key=ns + body.idempotency_key,
                at=at,
            )
            return {"order_id": str(row.id), "status": row.status}

        needed = ("fleet.build", "colony.read")
        return self.act(raw, universe_id, empire_id, needed, run)

    def cancel(self, raw, universe_id, empire_id, order_id):
        def run(session, at, _):
            row = service.cancel_order(
                session, self.engine, universe_id, empire_id, order_id, at=at
            )
            return {"order_id": str(row.id), "refunded": amounts(row.refunded or {})}

        needed = ("fleet.build", "colony.read")
        return self.act(raw, universe_id, empire_id, needed, run)

    @staticmethod
    def mission_rights(kind):
        if kind == "ATTACK":
            # A dedicated right, never implied by fleet.command; colony.read stays optional.
            return ("fleet.command", "galaxy.read", "combat.read", "combat.attack")
        if kind == "COLONIZE":
            # Founding is irreversible in v0.5: a dedicated right, never colony.construct.
            return ("fleet.command", "galaxy.read", "colony.expand")
        if kind in ("SURVEY", "PROSPECT", "STUDY", "EXTRACT"):
            return ("fleet.command", "galaxy.read")
        return ("fleet.command",)

    def preview(self, raw, universe_id, empire_id, body: Plan):
        with self.factory.begin() as session:
            permissions, _ = self.authorize_empire(
                session, raw, universe_id, empire_id, self.mission_rights(body.kind)
            )
            quote = service.preview(
                session,
                universe_id,
                empire_id,
                UUID(body.fleet_id),
                body.kind,
                UUID(body.destination_id) if body.destination_id else None,
                body.units,
                self.clock.now(),
                UUID(body.target_planet_id) if body.target_planet_id else None,
                "colony.read" in permissions,
                UUID(body.target_opportunity_id) if body.target_opportunity_id else None,
                body.duration_hours,
                body.after,
            )
            if "colony.read" not in permissions:
                # Commanding stays allowed without colony.read; the paying colony is not shown.
                quote["payer_colony_id"] = None
            return {**quote, "cost": amounts(quote["cost"])} | {
                k: str(quote[k]) for k in ("travel_us", "survey_us")
            }

    def launch(self, raw, universe_id, empire_id, body: Launch):
        def run(session, at, ns, permissions):
            mission = service.launch(
                session,
                self.engine,
                universe_id,
                empire_id,
                UUID(body.fleet_id),
                body.kind,
                UUID(body.destination_id) if body.destination_id else None,
                body.units,
                body.cargo,
                key=ns + body.idempotency_key,
                at=at,
                target_planet_id=UUID(body.target_planet_id) if body.target_planet_id else None,
                colony_read="colony.read" in permissions,
                target_opportunity_id=UUID(body.target_opportunity_id)
                if body.target_opportunity_id
                else None,
                duration_hours=body.duration_hours,
                after=body.after,
            )
            return {"mission_id": str(mission.id), "fleet_id": str(mission.fleet_id)}

        return self.act(
            raw, universe_id, empire_id, self.mission_rights(body.kind), run, with_rights=True
        )

    def recall(self, raw, universe_id, empire_id, mission_id, body: Keyed):
        def run(session, at, ns):
            mission = service.recall(
                session,
                self.engine,
                universe_id,
                empire_id,
                mission_id,
                key=ns + body.idempotency_key,
                at=at,
            )
            return {"mission_id": str(mission.id), "return_at": mission.return_at.isoformat()}

        return self.act(raw, universe_id, empire_id, ("fleet.command",), run)

    def split(self, raw, universe_id, empire_id, fleet_id, body: Split):
        def run(session, at, ns):
            return service.split(
                session,
                self.engine,
                universe_id,
                empire_id,
                fleet_id,
                body.units,
                body.cargo,
                key=ns + body.idempotency_key,
                at=at,
            )

        return self.act(raw, universe_id, empire_id, ("fleet.command",), run)

    def merge(self, raw, universe_id, empire_id, fleet_id, body: Merge):
        def run(session, at, ns):
            return service.merge(
                session,
                self.engine,
                universe_id,
                empire_id,
                fleet_id,
                UUID(body.target_id),
                key=ns + body.idempotency_key,
                at=at,
            )

        return self.act(raw, universe_id, empire_id, ("fleet.command",), run)

    def protocol(self, raw, universe_id, empire_id, fleet_id, body: ProtocolChoice):
        def run(session, at, ns):
            return service.set_protocol(
                session,
                self.engine,
                universe_id,
                empire_id,
                fleet_id,
                body.protocol,
                key=ns + body.idempotency_key,
                at=at,
            )

        return self.act(raw, universe_id, empire_id, ("fleet.command",), run)

    def load(self, raw, universe_id, empire_id, fleet_id, body: Load):
        def run(session, at, ns):
            result = service.load(
                session,
                self.engine,
                universe_id,
                empire_id,
                fleet_id,
                UUID(body.colony_id),
                body.cargo,
                key=ns + body.idempotency_key,
                at=at,
            )
            return {k: amounts(v) for k, v in result.items()}

        needed = ("fleet.command", "colony.read")
        return self.act(raw, universe_id, empire_id, needed, run)

    def unload(self, raw, universe_id, empire_id, fleet_id, body: Unload):
        def run(session, at, ns):
            result = service.unload(
                session,
                self.engine,
                universe_id,
                empire_id,
                fleet_id,
                UUID(body.colony_id),
                key=ns + body.idempotency_key,
                at=at,
            )
            return {k: amounts(v) for k, v in result.items()}

        needed = ("fleet.command", "colony.read")
        return self.act(raw, universe_id, empire_id, needed, run)


def cookie(request, universe_id):
    return request.cookies.get(cookie_name(universe_id))


@router.get("")
async def listing(universe_id: UUID, request: Request):
    bootstrap(request)
    return await call(Fleets(request.app.state).listing, cookie(request, universe_id), universe_id)


@router.get("/{empire_id}")
async def read(universe_id: UUID, empire_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Fleets(request.app.state).read, cookie(request, universe_id), universe_id, empire_id
    )


@router.post("/{empire_id}/orders")
async def order(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Order)
    return await call(Fleets(request.app.state).order, raw, universe_id, empire_id, body)


@router.post("/{empire_id}/orders/{order_id}/cancel")
async def cancel(universe_id: UUID, empire_id: UUID, order_id: UUID, request: Request):
    # Same intention contract as every Fleet command; cancelling is idempotent by order itself.
    raw, _ = await command(request, universe_id, Keyed)
    return await call(Fleets(request.app.state).cancel, raw, universe_id, empire_id, order_id)


@router.post("/{empire_id}/missions/preview")
async def preview(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Plan)
    return await call(Fleets(request.app.state).preview, raw, universe_id, empire_id, body)


@router.post("/{empire_id}/missions")
async def launch(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Launch)
    return await call(Fleets(request.app.state).launch, raw, universe_id, empire_id, body)


@router.post("/{empire_id}/missions/{mission_id}/recall")
async def recall(universe_id: UUID, empire_id: UUID, mission_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Keyed)
    return await call(
        Fleets(request.app.state).recall, raw, universe_id, empire_id, mission_id, body
    )


@router.post("/{empire_id}/{fleet_id}/split")
async def split(universe_id: UUID, empire_id: UUID, fleet_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Split)
    return await call(Fleets(request.app.state).split, raw, universe_id, empire_id, fleet_id, body)


@router.post("/{empire_id}/{fleet_id}/merge")
async def merge(universe_id: UUID, empire_id: UUID, fleet_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Merge)
    return await call(Fleets(request.app.state).merge, raw, universe_id, empire_id, fleet_id, body)


@router.post("/{empire_id}/{fleet_id}/load")
async def load(universe_id: UUID, empire_id: UUID, fleet_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Load)
    return await call(Fleets(request.app.state).load, raw, universe_id, empire_id, fleet_id, body)


@router.post("/{empire_id}/{fleet_id}/unload")
async def unload(universe_id: UUID, empire_id: UUID, fleet_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Unload)
    return await call(Fleets(request.app.state).unload, raw, universe_id, empire_id, fleet_id, body)


@router.post("/{empire_id}/{fleet_id}/protocol")
async def protocol(universe_id: UUID, empire_id: UUID, fleet_id: UUID, request: Request):
    raw, body = await command(request, universe_id, ProtocolChoice)
    return await call(
        Fleets(request.app.state).protocol, raw, universe_id, empire_id, fleet_id, body
    )
