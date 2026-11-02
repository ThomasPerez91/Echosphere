"""Public Relations API: GameSession → binding permissions → Empire scope, then the services.

Reads never write gameplay state and never catch up a stream. Commands lock only the pair row,
namespace their intention keys per membership and count as explicit activity. No Portal call.
Without `relations.read` the Empire is indistinguishable from an unknown identifier.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.access.http import cookie_name
from app.access.service import AccessError
from app.colony.api import Colonies, bootstrap, call, command
from app.colony.service import rules_for
from app.control.models import EmpireBinding
from app.persistence.models import Empire
from app.relations import service

router = APIRouter(prefix="/game/{universe_id}/relations")


class Keyed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")


Action = Literal["propose", "withdraw", "accept", "refuse", "terminate"]


class Relations(Colonies):
    def authorize_empire(self, session, raw, universe_id, empire_id, needed=(), *, act=False):
        row, access = self.sessions.locked(session, raw, universe_id)
        binding = session.get(EmpireBinding, (access.membership_id, empire_id))
        if (
            binding is None
            or binding.universe_id != universe_id
            or "relations.read" not in binding.permissions
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
            available = rules_for(session, universe_id).relations is not None
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
                "available": available,
                "empires": [
                    {"id": str(e.id), "name": e.name}
                    for e, b in rows
                    if "relations.read" in b.permissions
                ],
            }

    def read(self, raw, universe_id, empire_id):
        with self.factory.begin() as session:
            permissions, _ = self.authorize_empire(session, raw, universe_id, empire_id)
            view = service.project(session, universe_id, empire_id, self.clock.now())
            if "relations.negotiate" not in permissions:
                for relation in view["relations"]:
                    relation["actions"] = []
            return view | {"can_negotiate": "relations.negotiate" in permissions}

    def act(self, raw, universe_id, empire_id, action: Action, counterpart_id, body: Keyed):
        with self.factory.begin() as session:
            permissions, access = self.authorize_empire(
                session,
                raw,
                universe_id,
                empire_id,
                ("relations.read", "relations.negotiate"),
                act=True,
            )
            at = self.clock.now()
            result = service.OPERATIONS[action](
                session,
                universe_id,
                empire_id,
                counterpart_id,
                key=f"http:{access.membership_id}:{body.idempotency_key}",
                at=at,
            )
            view = service.project(session, universe_id, empire_id, at)
            return {"result": result, "relations": view | {"can_negotiate": True}}


@router.get("")
async def empires(universe_id: UUID, request: Request):
    bootstrap(request)
    raw = request.cookies.get(cookie_name(universe_id))
    return await call(Relations(request.app.state).listing, raw, universe_id)


@router.get("/{empire_id}")
async def relations(universe_id: UUID, empire_id: UUID, request: Request):
    bootstrap(request)
    raw = request.cookies.get(cookie_name(universe_id))
    return await call(Relations(request.app.state).read, raw, universe_id, empire_id)


@router.post("/{empire_id}/{counterpart_id}/{action}")
async def negotiate(
    universe_id: UUID, empire_id: UUID, counterpart_id: UUID, action: Action, request: Request
):
    raw, body = await command(request, universe_id, Keyed)
    return await call(
        Relations(request.app.state).act, raw, universe_id, empire_id, action, counterpart_id, body
    )
