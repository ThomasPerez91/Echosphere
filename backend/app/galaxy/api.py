"""GameSession-authorized projections start from Empire knowledge, never the global map."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field
from sqlalchemy import select

from app.access.http import cookie_name
from app.access.service import AccessError
from app.colony.api import Colonies, Empty, bootstrap, call, command
from app.colony.projection import amounts
from app.colony.service import catch_up_owned, rules_for
from app.control.models import EmpireBinding
from app.galaxy import service
from app.galaxy.models import ExplorationMission, ExplorationReport, RouteKnowledge, SystemKnowledge
from app.persistence.models import Colony, Empire, Planet
from app.research import service as research
from app.simulation.models import ResourceBalance

router = APIRouter(prefix="/game/{universe_id}")


class Start(Empty):
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
    colony_id: str = Field(pattern=r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$")
    destination_id: str = Field(pattern=r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$")


class Galaxy(Colonies):
    def authorize_empire(self, session, raw, universe_id, empire_id, read, start=False):
        row, access = self.sessions.locked(session, raw, universe_id)
        binding = session.get(EmpireBinding, (access.membership_id, empire_id))
        if binding is None or binding.universe_id != universe_id or read not in binding.permissions:
            raise AccessError("empire_not_found", 404)
        if start and not {
            "galaxy.read",
            "exploration.read",
            "exploration.start",
            "colony.read",
        } <= (set(binding.permissions)):
            raise AccessError("permission_denied", 403)
        if start:
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
            ).all()
            return {
                "empires": [
                    {"id": str(e.id), "name": e.name}
                    for e, b in rows
                    if "galaxy.read" in b.permissions
                ]
            }

    def projection(self, session, universe_id, empire_id, permissions, at):
        service.refresh_monitoring(session, universe_id, empire_id, at)
        knowledge = list(
            session.scalars(
                select(SystemKnowledge)
                .where(
                    SystemKnowledge.universe_id == universe_id,
                    SystemKnowledge.empire_id == empire_id,
                )
                .order_by(SystemKnowledge.system_id)
            )
        )
        routes = list(
            session.scalars(
                select(RouteKnowledge)
                .where(
                    RouteKnowledge.universe_id == universe_id, RouteKnowledge.empire_id == empire_id
                )
                .order_by(RouteKnowledge.route_id)
            )
        )
        sources, options = [], []
        if "colony.read" in permissions:
            research.catch_up(session, self.engine, universe_id, empire_id, at)
            colonies = list(
                session.scalars(
                    select(Colony)
                    .where(Colony.universe_id == universe_id, Colony.empire_id == empire_id)
                    .order_by(Colony.id)
                )
            )
            rules = rules_for(session, universe_id)
            active = session.scalar(
                select(ExplorationMission.id).where(
                    ExplorationMission.empire_id == empire_id, ExplorationMission.status == "active"
                )
            )
            for colony in colonies:
                catch_up_owned(session, self.engine, universe_id, empire_id, colony.id, at)
                planet = session.get(Planet, colony.planet_id)
                stocks = {
                    r: session.get(ResourceBalance, (colony.id, r)).stock
                    for r in ("alloys", "flux", "data")
                }
                sources.append(
                    {"id": str(colony.id), "name": planet.name, "stocks": amounts(stocks)}
                )
                for target in knowledge:
                    if target.state != "DETECTED":
                        continue
                    try:
                        path = service.known_path(
                            session, universe_id, empire_id, planet.system_id, target.system_id
                        )
                    except service.GalaxyError:
                        continue
                    cost, duration = rules.exploration.quote(len(path))
                    reason = (
                        "permission_denied"
                        if not {"exploration.read", "exploration.start"} <= set(permissions)
                        else "exploration_active"
                        if active
                        else "insufficient_resources"
                        if any(stocks[r] < v for r, v in cost.items())
                        else None
                    )
                    options.append(
                        {
                            "colony_id": str(colony.id),
                            "destination_id": str(target.system_id),
                            "hops": len(path),
                            "cost": amounts(cost),
                            "duration_us": str(duration),
                            "reason": reason,
                        }
                    )
        return {
            "server_time": at.isoformat(),
            "empire": {"id": str(empire_id), "name": session.get(Empire, empire_id).name},
            "permissions": permissions,
            "systems": [service.project_system(session, k) for k in knowledge],
            "routes": [
                {"id": str(r.route_id), "a_id": str(r.a_id), "b_id": str(r.b_id)} for r in routes
            ],
            "sources": sources,
            "options": options,
            "missions": self.missions_projection(session, universe_id, empire_id, permissions)
            if "exploration.read" in permissions
            else [],
        }

    def missions_projection(self, session, universe_id, empire_id, permissions):
        result = []
        for row in session.scalars(
            select(ExplorationMission)
            .where(
                ExplorationMission.universe_id == universe_id,
                ExplorationMission.empire_id == empire_id,
            )
            .order_by(ExplorationMission.started_at.desc(), ExplorationMission.id)
        ):
            report = session.get(ExplorationReport, row.id)
            result.append(
                {
                    "id": str(row.id),
                    "destination_id": str(row.destination_id),
                    # Like Research: the funding source is shown only with colony.read.
                    "colony_id": str(row.colony_id) if "colony.read" in permissions else None,
                    "status": row.status,
                    "started_at": row.started_at.isoformat(),
                    "due_at": row.due_at.isoformat(),
                    "cost": amounts(row.snapshot["cost"]),
                    "report": {
                        "observed_at": report.observed_at.isoformat(),
                        "processed_at": report.processed_at.isoformat(),
                        "discoveries": report.discoveries,
                    }
                    if report
                    else None,
                }
            )
        return result

    def read(self, raw, universe_id, empire_id, system_id=None, missions=False):
        with self.factory.begin() as session:
            permissions, _ = self.authorize_empire(
                session,
                raw,
                universe_id,
                empire_id,
                "exploration.read" if missions else "galaxy.read",
            )
            at = self.clock.now()
            service.catch_up(session, self.engine, universe_id, empire_id, at)
            if missions:
                return {
                    "missions": self.missions_projection(
                        session, universe_id, empire_id, permissions
                    )
                }
            if system_id is not None:
                known = session.get(SystemKnowledge, (empire_id, system_id))
                if known is None or known.universe_id != universe_id:
                    raise AccessError("system_not_found", 404)
                service.refresh_monitoring(session, universe_id, empire_id, at)
                return service.project_system(session, known)
            return self.projection(session, universe_id, empire_id, permissions, at)

    def start(self, raw, universe_id, empire_id, body):
        with self.factory.begin() as session:
            permissions, access = self.authorize_empire(
                session, raw, universe_id, empire_id, "galaxy.read", start=True
            )
            at = self.clock.now()
            mission = service.start(
                session,
                self.engine,
                universe_id,
                empire_id,
                UUID(body.colony_id),
                UUID(body.destination_id),
                key=f"http:{access.membership_id}:{body.idempotency_key}",
                at=at,
            )
            return {
                "mission_id": str(mission.id),
                "galaxy": self.projection(session, universe_id, empire_id, permissions, at),
            }


@router.get("/galaxy")
async def listing(universe_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Galaxy(request.app.state).listing,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
    )


@router.get("/galaxy/{empire_id}")
async def read(universe_id: UUID, empire_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Galaxy(request.app.state).read,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
        empire_id,
    )


@router.get("/galaxy/{empire_id}/systems/{system_id}")
async def detail(universe_id: UUID, empire_id: UUID, system_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Galaxy(request.app.state).read,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
        empire_id,
        system_id,
    )


@router.get("/exploration/{empire_id}/missions")
async def missions(universe_id: UUID, empire_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Galaxy(request.app.state).read,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
        empire_id,
        None,
        True,
    )


@router.post("/exploration/{empire_id}/missions")
async def start(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Start)
    return await call(Galaxy(request.app.state).start, raw, universe_id, empire_id, body)
