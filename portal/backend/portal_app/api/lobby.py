"""Owned lobby projection. Reads neither renew Game rights nor refresh Portal inactivity."""

from uuid import UUID

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from portal_app.api.accounts import check_origin, peer_address
from portal_app.api.sessions import bootstrap, response
from portal_app.control.service import Lobby
from portal_app.handoff.service import Handoff
from portal_app.sessions.service import SESSION_COOKIE

router = APIRouter(prefix="/lobby")


@router.get("/memberships")
async def memberships(request: Request):
    bootstrap(request)
    return response(
        await run_in_threadpool(
            Lobby(request.app.state.accounts).read, request.cookies.get(SESSION_COOKIE)
        )
    )


@router.post("/universes/{universe_id}/renew")
async def renew(universe_id: UUID, request: Request):
    check_origin(request)
    return response(
        await run_in_threadpool(
            Handoff(request.app.state.accounts).renew,
            request.cookies.get(SESSION_COOKIE),
            request.headers.get("x-csrf-token"),
            universe_id,
            peer_address(request),
        )
    )
