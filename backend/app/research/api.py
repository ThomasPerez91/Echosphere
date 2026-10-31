"""GameSession → scoped EmpireBinding → Research → financing Colony read access."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field
from sqlalchemy import select

from app.access.http import cookie_name
from app.access.service import AccessError
from app.colony.api import Colonies, Empty, bootstrap, call, command
from app.colony.projection import amounts, iso
from app.colony.service import catch_up_owned
from app.control.models import EmpireBinding
from app.persistence.models import Colony, Empire, Planet
from app.research import service as research
from app.research.models import ResearchOrder
from app.simulation.models import ResourceBalance
from app.simulation.production import RESOURCES

router = APIRouter(prefix="/game/{universe_id}/research")


class Start(Empty):
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
    technology_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    colony_id: str = Field(pattern=r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$")


class Research(Colonies):
    def authorize_empire(self, session, raw, universe_id, empire_id, permission, interaction=False):
        row, access = self.sessions.locked(session, raw, universe_id)
        binding = session.get(EmpireBinding, (access.membership_id, empire_id))
        if (
            binding is None
            or binding.universe_id != universe_id
            or "research.read" not in binding.permissions
        ):
            raise AccessError("empire_not_found", 404)
        if permission not in binding.permissions:
            raise AccessError("permission_denied", 403)
        if interaction:
            row.last_activity_at = self.clock.now()
        return list(binding.permissions), access

    def sources(self, session, universe_id, empire_id, permissions):
        if "colony.read" not in permissions:
            return []
        return list(
            session.scalars(
                select(Colony)
                .where(
                    Colony.universe_id == universe_id,
                    Colony.empire_id == empire_id,
                )
                .order_by(Colony.id)
            )
        )

    def listing(self, raw, universe_id):
        with self.factory.begin() as session:
            _, access = self.sessions.locked(session, raw, universe_id)
            rows = session.execute(
                select(Empire, EmpireBinding)
                .join(EmpireBinding, EmpireBinding.empire_id == Empire.id)
                .where(
                    Empire.universe_id == universe_id,
                    EmpireBinding.membership_id == access.membership_id,
                )
            ).all()
            return {
                "empires": [
                    {"id": str(e.id), "name": e.name}
                    for e, b in rows
                    if "research.read" in b.permissions
                ]
            }

    def prepare(self, session, universe_id, empire_id, permissions, now):
        research.catch_up(session, self.engine, universe_id, empire_id, now)
        sources = self.sources(session, universe_id, empire_id, permissions)
        # Sorted total order, including sources of a two-colony cancellation preview.
        for colony in sources:
            catch_up_owned(session, self.engine, universe_id, empire_id, colony.id, now)
        return sources

    def projection(self, session, universe_id, empire_id, permissions, now, sources):
        cat = research.catalogue(session, universe_id)
        known = research.acquired(session, empire_id)
        queue = research.pending(session, empire_id)
        source_ids = {c.id for c in sources}
        options = []
        for key, tech in cat.technologies.items():
            snap = research.quote(session, universe_id, empire_id, key, "")
            try:
                research.validate_start(session, empire_id, key, snap)
                reason = None if "research.start" in permissions else "permission_denied"
                if not sources:
                    reason = "funding_unavailable"
            except research.ResearchError as exc:
                reason = exc.code
            options.append(
                {
                    "id": key,
                    **tech.model_dump(),
                    "cost": amounts(snap.cost),
                    "base_duration_us": str(snap.base_duration_us),
                    "duration_us": str(snap.duration_us),
                    "bonuses": snap.bonuses,
                    "available": reason is None,
                    "reason": reason,
                }
            )
        orders = []
        for row in queue:
            affected = research.cancellation_plan(session, empire_id, row)
            can_refund = all(r.colony_id in source_ids for r in affected)
            refunds = []
            if can_refund:
                for colony_id, theoretical, _, recovered, lost in research.refund_plan(
                    session, affected
                ):
                    refunds.append(
                        {
                            "colony_id": str(colony_id),
                            "colony_name": session.get(
                                Planet, session.get(Colony, colony_id).planet_id
                            ).name,
                            "theoretical": amounts(
                                {r: sum(v[r] for v in theoretical.values()) for r in RESOURCES}
                            ),
                            "recoverable": amounts(recovered),
                            "lost": amounts(lost),
                        }
                    )
            snap = research.read_snapshot(session, row)
            orders.append(
                {
                    "id": str(row.id),
                    "technology_id": row.technology_id,
                    "name": snap.technology.name,
                    "status": row.status,
                    "colony_id": str(row.colony_id) if row.colony_id in source_ids else None,
                    "cost": amounts(snap.cost),
                    "duration_us": str(snap.duration_us),
                    "started_at": iso(row.started_at),
                    "due_at": iso(row.due_at),
                    "blocked_reason": row.blocked_reason,
                    "cancel": {
                        "available": can_refund and "research.cancel" in permissions,
                        "refunds": refunds,
                        "also_cancels": [str(r.id) for r in affected if r.id != row.id],
                    },
                }
            )
        return {
            "server_time": iso(now),
            "ruleset_version": cat.version,
            "empire": {"id": str(empire_id), "name": session.get(Empire, empire_id).name},
            "permissions": permissions,
            "queue_limit": cat.queue_limit,
            "acquired": [
                {
                    "technology_id": r.technology_id,
                    "acquired_at": iso(r.acquired_at),
                    "effect": r.effect,
                    "reduction_bps": r.reduction_bps,
                }
                for r in known
            ],
            "bonuses": research.bonuses(session, empire_id),
            "queue": orders,
            "technologies": options,
            "sources": [
                {
                    "id": str(c.id),
                    "name": session.get(Planet, c.planet_id).name,
                    "stocks": amounts(
                        {r: session.get(ResourceBalance, (c.id, r)).stock for r in RESOURCES}
                    ),
                }
                for c in sources
            ],
        }

    def read(self, raw, universe_id, empire_id):
        with self.factory.begin() as session:
            permissions, _ = self.authorize_empire(
                session, raw, universe_id, empire_id, "research.read"
            )
            now = self.clock.now()
            sources = self.prepare(session, universe_id, empire_id, permissions, now)
            return self.projection(session, universe_id, empire_id, permissions, now, sources)

    def start(self, raw, universe_id, empire_id, body):
        with self.factory.begin() as session:
            permissions, access = self.authorize_empire(
                session, raw, universe_id, empire_id, "research.start", True
            )
            now = self.clock.now()
            sources = self.prepare(session, universe_id, empire_id, permissions, now)
            colony_id = UUID(body.colony_id)
            if colony_id not in {c.id for c in sources}:
                raise AccessError("colony_not_found", 404)
            row = research.start(
                session,
                self.engine,
                universe_id,
                empire_id,
                colony_id,
                key=f"http:{access.membership_id}:{body.idempotency_key}",
                technology_id=body.technology_id,
                at=now,
            )
            return {
                "order": {"id": str(row.id), "status": row.status},
                "research": self.projection(
                    session, universe_id, empire_id, permissions, now, sources
                ),
            }

    def cancel(self, raw, universe_id, empire_id, order_id):
        with self.factory.begin() as session:
            permissions, _ = self.authorize_empire(
                session, raw, universe_id, empire_id, "research.cancel", True
            )
            now = self.clock.now()
            sources = self.prepare(session, universe_id, empire_id, permissions, now)
            row = session.scalar(
                select(ResearchOrder).where(
                    ResearchOrder.id == order_id,
                    ResearchOrder.empire_id == empire_id,
                    ResearchOrder.universe_id == universe_id,
                )
            )
            if row is None:
                raise AccessError("order_not_found", 404)
            affected = research.cancellation_plan(session, empire_id, row)
            if row.colony_id not in {c.id for c in sources} or any(
                r.colony_id not in {c.id for c in sources} for r in affected
            ):
                raise AccessError("permission_denied", 403)
            row = research.cancel(session, self.engine, universe_id, empire_id, order_id, at=now)
            return {
                "order": {
                    "id": str(row.id),
                    "status": row.status,
                    "refunded": amounts(row.refunded or {}),
                },
                "research": self.projection(
                    session, universe_id, empire_id, permissions, now, sources
                ),
            }


@router.get("")
async def listing(universe_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Research(request.app.state).listing,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
    )


@router.get("/{empire_id}")
async def read(universe_id: UUID, empire_id: UUID, request: Request):
    bootstrap(request)
    return await call(
        Research(request.app.state).read,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
        empire_id,
    )


@router.post("/{empire_id}/orders")
async def start(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Start)
    return await call(Research(request.app.state).start, raw, universe_id, empire_id, body)


@router.post("/{empire_id}/orders/{order_id}/cancel")
async def cancel(universe_id: UUID, empire_id: UUID, order_id: UUID, request: Request):
    raw, _ = await command(request, universe_id, Empty)
    return await call(Research(request.app.state).cancel, raw, universe_id, empire_id, order_id)
