"""Owned lobby projection. Reads neither renew Game rights nor refresh Portal inactivity."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from portal_app.api.sessions import bootstrap, response
from portal_app.control.service import Lobby
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
