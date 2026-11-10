"""Test game tools (sandbox): GameSession → Empire binding → test game only, then the service.

Every route answers `sandbox_unavailable` (404) outside a universe created as a test game, so a
normal game never exposes these commands. Commands count as explicit activity."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.access.http import cookie_name
from app.access.service import AccessError
from app.colony.api import Colonies, bootstrap, call, command
from app.control.models import EmpireBinding
from app.fleet.api import project as fleet_projection
from app.sandbox import service

router = APIRouter(prefix="/game/{universe_id}/sandbox")

UUID_PATTERN = r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$"
Amount = Field(default=None, ge=0, le=100_000_000)


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Resources(Body):
    colony_id: str = Field(pattern=UUID_PATTERN)
    alloys: int | None = Amount
    flux: int | None = Amount
    data: int | None = Amount


class Ships(Body):
    colony_id: str = Field(pattern=UUID_PATTERN)
    ships: dict[str, int] = Field(min_length=1, max_length=16)


class Finish(Body):
    scope: Literal["all"] = "all"


class Sandbox(Colonies):
    def authorize_empire(self, session, raw, universe_id, empire_id, needed=()):
        row, access = self.sessions.locked(session, raw, universe_id)
        binding = session.get(EmpireBinding, (access.membership_id, empire_id))
        if (
            binding is None
            or binding.universe_id != universe_id
            or "colony.read" not in binding.permissions
        ):
            raise AccessError("empire_not_found", 404)
        if not set(needed) <= set(binding.permissions):
            raise AccessError("permission_denied", 403)
        service.require(session, universe_id)
        if needed:
            row.last_activity_at = self.clock.now()
        return list(binding.permissions)

    def read(self, raw, universe_id, empire_id):
        with self.factory.begin() as session:
            self.authorize_empire(session, raw, universe_id, empire_id)
            return service.status(session, universe_id, empire_id, self.clock.now())

    def act(self, raw, universe_id, empire_id, operation):
        with self.factory.begin() as session:
            permissions = self.authorize_empire(
                session, raw, universe_id, empire_id, ("colony.construct",)
            )
            at = self.clock.now()
            result = operation(session, at)
            body = {"result": result, **service.status(session, universe_id, empire_id, at)}
            if "fleet.read" in permissions:
                body["fleets"] = fleet_projection(session, universe_id, empire_id, permissions, at)
            return body

    def resources(self, raw, universe_id, empire_id, body: Resources):
        wanted = {
            r: getattr(body, r) for r in ("alloys", "flux", "data") if getattr(body, r) is not None
        }

        def run(session, at):
            service.grant_resources(
                session, self.engine, universe_id, empire_id, UUID(body.colony_id), wanted, at
            )
            return {"colony_id": body.colony_id}

        return self.act(raw, universe_id, empire_id, run)

    def ships(self, raw, universe_id, empire_id, body: Ships):
        def run(session, at):
            service.grant_ships(
                session, self.engine, universe_id, empire_id, UUID(body.colony_id), body.ships, at
            )
            return {"colony_id": body.colony_id}

        return self.act(raw, universe_id, empire_id, run)

    def finish(self, raw, universe_id, empire_id, body: Finish):
        def run(session, at):
            return service.finish(session, self.engine, universe_id, empire_id, at)

        return self.act(raw, universe_id, empire_id, run)


@router.get("/{empire_id}")
async def read(universe_id: UUID, empire_id: UUID, request: Request):
    bootstrap(request)
    raw = request.cookies.get(cookie_name(universe_id))
    return await call(Sandbox(request.app.state).read, raw, universe_id, empire_id)


@router.post("/{empire_id}/resources")
async def resources(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Resources)
    return await call(Sandbox(request.app.state).resources, raw, universe_id, empire_id, body)


@router.post("/{empire_id}/ships")
async def ships(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Ships)
    return await call(Sandbox(request.app.state).ships, raw, universe_id, empire_id, body)


@router.post("/{empire_id}/finish")
async def finish(universe_id: UUID, empire_id: UUID, request: Request):
    raw, body = await command(request, universe_id, Finish)
    return await call(Sandbox(request.app.state).finish, raw, universe_id, empire_id, body)
