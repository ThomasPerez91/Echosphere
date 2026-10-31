"""Public Colony API: authenticate and authorize, then delegate to the 5A services.

Every request: GameSession (principal lock, same lock as C06 revocation) → effective GameAccess →
EmpireBinding permission → colony scope. Commands re-check rights inside the transaction that
accepts them and count as explicit activity. No Portal call, no rule computed here.
"""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.access.http import HEADERS, cookie_name, origin
from app.access.service import AccessError, GameSessions, check_csrf
from app.colony.projection import amounts, project
from app.colony.service import ColonyError, cancel, catch_up_owned, enqueue
from app.control.models import EmpireBinding
from app.persistence.models import Colony, Empire, Planet
from app.simulation.scheduler import IdempotencyConflict, TimelineError
from app.simulation.service import TimeEngine

router = APIRouter(prefix="/game/{universe_id}/colonies")

STATUS = {
    "colony_not_found": 404,
    "empire_not_found": 404,
    "technology_not_found": 404,
    "research_busy": 503,
    "order_not_found": 404,
    "invalid_request": 422,
    "colony_busy": 503,
}


class Construction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")
    infrastructure_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    sector_index: int = Field(ge=1, le=10_000)
    target_level: int = Field(ge=1, le=1_000_000)


class Empty(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Colonies:
    def __init__(self, state):
        self.factory, self.clock = state.session_factory, state.clock
        self.sessions = GameSessions(self.factory, state.settings, state.clock.now)
        self.engine = TimeEngine(self.factory, state.clock)

    def authorize(self, session, raw, universe_id, colony_id, permission, *, interaction=False):
        row, access = self.sessions.locked(session, raw, universe_id)
        colony = session.scalar(
            select(Colony).where(Colony.id == colony_id, Colony.universe_id == universe_id)
        )
        binding = (
            session.get(EmpireBinding, (access.membership_id, colony.empire_id))
            if colony is not None
            else None
        )
        # Without read access the colony is indistinguishable from an unknown identifier.
        if (
            binding is None
            or binding.universe_id != universe_id
            or "colony.read" not in binding.permissions
        ):
            raise AccessError("colony_not_found", 404)
        if permission not in binding.permissions:
            raise AccessError("permission_denied", 403)
        if interaction:
            # Explicit command: checked alive by locked() before; never moves absolute deadlines.
            row.last_activity_at = self.sessions.clock()
        return colony, list(binding.permissions), access

    def listing(self, raw, universe_id):
        with self.factory.begin() as session:
            _, access = self.sessions.locked(session, raw, universe_id)
            bindings = session.scalars(
                select(EmpireBinding).where(EmpireBinding.membership_id == access.membership_id)
            ).all()
            readable = [b.empire_id for b in bindings if "colony.read" in b.permissions]
            colonies = session.scalars(
                select(Colony)
                .where(Colony.universe_id == universe_id, Colony.empire_id.in_(readable))
                .order_by(Colony.created_at, Colony.id)
            ).all()
            return {
                "server_time": self.sessions.clock().isoformat(),
                "colonies": [
                    {
                        "id": str(colony.id),
                        "name": session.get(Planet, colony.planet_id).name,
                        "empire": {
                            "id": str(colony.empire_id),
                            "name": session.get(Empire, colony.empire_id).name,
                        },
                    }
                    for colony in colonies
                ],
            }

    def read(self, raw, universe_id, colony_id):
        with self.factory.begin() as session:
            colony, permissions, _ = self.authorize(
                session, raw, universe_id, colony_id, "colony.read"
            )
            now = self.clock.now()
            # Lazy, deterministic catch-up: the same path as commands and the worker.
            rules = catch_up_owned(
                session, self.engine, universe_id, colony.empire_id, colony.id, now
            )
            return project(session, rules, colony, permissions, now)

    def construct(self, raw, universe_id, colony_id, command: Construction):
        with self.factory.begin() as session:
            colony, permissions, access = self.authorize(
                session, raw, universe_id, colony_id, "colony.construct", interaction=True
            )
            now = self.clock.now()
            order = enqueue(
                session,
                self.engine,
                universe_id,
                colony.empire_id,
                colony.id,
                # Namespaced per membership: another participant can never replay this key.
                key=f"http:{access.membership_id}:{command.idempotency_key}",
                kind=command.infrastructure_type,
                sector=command.sector_index,
                target_level=command.target_level,
                at=now,
            )
            rules = catch_up_owned(
                session, self.engine, universe_id, colony.empire_id, colony.id, now
            )
            return {
                "order": {"id": str(order.id), "status": order.status},
                "colony": project(session, rules, colony, permissions, now),
            }

    def cancel(self, raw, universe_id, colony_id, order_id):
        with self.factory.begin() as session:
            colony, permissions, _ = self.authorize(
                session, raw, universe_id, colony_id, "colony.cancel", interaction=True
            )
            now = self.clock.now()
            order = cancel(
                session, self.engine, universe_id, colony.empire_id, colony.id, order_id, at=now
            )
            rules = catch_up_owned(
                session, self.engine, universe_id, colony.empire_id, colony.id, now
            )
            return {
                "order": {
                    "id": str(order.id),
                    "status": order.status,
                    "refunded": amounts(order.refunded or {}),
                },
                "colony": project(session, rules, colony, permissions, now),
            }


def failure(code, status):
    return AccessError(code, status)


async def call(function, *args):
    try:
        return JSONResponse(await run_in_threadpool(function, *args), headers=HEADERS)
    except ColonyError as error:
        raise failure(error.code, STATUS.get(error.code, 409)) from None
    except IdempotencyConflict:
        raise failure("idempotency_conflict", 409) from None
    except TimelineError:
        raise failure("colony_busy", 503) from None


def bootstrap(request):
    if request.headers.get("x-game-request") != "bootstrap" or (
        request.headers.get("origin") not in (None, request.app.state.settings.game_public_origin)
    ):
        raise AccessError("origin_denied")
    if request.url.query:
        raise AccessError("invalid_request", 422)


async def command(request, universe_id, model):
    origin(request, request.app.state.settings.game_public_origin)
    raw = request.cookies.get(cookie_name(universe_id))
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise AccessError("invalid_request", 415)
    # Proof is checked before any database work, as for C07 actions.
    check_csrf(raw, request.headers.get("x-csrf-token"))
    try:
        return raw, model.model_validate_json(await request.body())
    except (ValidationError, ValueError):
        raise AccessError("invalid_request", 422) from None


@router.get("")
async def colonies(universe_id: UUID, request: Request):
    bootstrap(request)
    raw = request.cookies.get(cookie_name(universe_id))
    return await call(Colonies(request.app.state).listing, raw, universe_id)


@router.get("/{colony_id}")
async def colony(universe_id: UUID, colony_id: UUID, request: Request):
    bootstrap(request)
    raw = request.cookies.get(cookie_name(universe_id))
    return await call(Colonies(request.app.state).read, raw, universe_id, colony_id)


@router.post("/{colony_id}/construction-orders")
async def construct(universe_id: UUID, colony_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Construction)
    return await call(Colonies(request.app.state).construct, raw, universe_id, colony_id, body)


@router.post("/{colony_id}/construction-orders/{order_id}/cancel")
async def cancel_order(universe_id: UUID, colony_id: UUID, order_id: UUID, request: Request):
    raw, _ = await command(request, universe_id, Empty)
    return await call(Colonies(request.app.state).cancel, raw, universe_id, colony_id, order_id)
