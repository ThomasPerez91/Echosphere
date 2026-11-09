"""Owned lobby projection. Reads neither renew Game rights nor refresh Portal inactivity."""

from uuid import UUID

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from portal_app.api.accounts import check_origin, peer_address
from portal_app.api.sessions import bootstrap, response
from portal_app.control.invitations import Invitations
from portal_app.control.life import GameLife
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


@router.post("/universes")
async def create(request: Request):
    """UX-API-02 self-service SOLO universe: CSRF, session, rate limit, idempotent request_id."""
    check_origin(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    return response(
        await run_in_threadpool(
            Lobby(request.app.state.accounts).create,
            request.cookies.get(SESSION_COOKIE),
            request.headers.get("x-csrf-token"),
            body,
            peer_address(request),
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


async def _json(request):
    check_origin(request)
    try:
        body = await request.json()
    except ValueError:
        body = None
    return body if isinstance(body, dict) else {}


def _proofs(request):
    return request.cookies.get(SESSION_COOKIE), request.headers.get("x-csrf-token")


@router.post("/universes/{universe_id}/invite-link")
async def invite_link(universe_id: UUID, request: Request):
    """UX-API-03: new shareable link (the previous one stops working); creator only."""
    await _json(request)
    return response(await run_in_threadpool(
        Invitations(request.app.state.accounts).link, *_proofs(request), universe_id))


@router.post("/universes/{universe_id}/invitations")
async def invite_email(universe_id: UUID, request: Request):
    body = await _json(request)
    return response(await run_in_threadpool(
        Invitations(request.app.state.accounts).send, *_proofs(request), universe_id,
        body.get("email"), peer_address(request)))


@router.post("/invitations/{invitation_id}/revoke")
async def invite_revoke(invitation_id: UUID, request: Request):
    await _json(request)
    return response(await run_in_threadpool(
        Invitations(request.app.state.accounts).revoke, *_proofs(request), invitation_id))


@router.post("/invitations/accept")
async def invite_accept(request: Request):
    """Join with {"token"} (link or email link) or {"invitation_id"} (email, from the lobby)."""
    body = await _json(request)
    return response(await run_in_threadpool(
        Invitations(request.app.state.accounts).accept, *_proofs(request),
        body.get("token"), body.get("invitation_id"), body.get("empire_name")))


@router.post("/invitations/{invitation_id}/decline")
async def invite_decline(invitation_id: UUID, request: Request):
    await _json(request)
    return response(await run_in_threadpool(
        Invitations(request.app.state.accounts).decline, *_proofs(request), invitation_id))


@router.post("/universes/{universe_id}/empire-name")
async def empire_name(universe_id: UUID, request: Request):
    """Q60: rename the Empire of my seat ({"name"}); applied by Game through the outbox."""
    body = await _json(request)
    return response(await run_in_threadpool(
        GameLife(request.app.state.accounts).rename, *_proofs(request), universe_id,
        body.get("name")))


@router.post("/universes/{universe_id}/leave")
async def leave(universe_id: UUID, request: Request):
    """Q60: archive my solo game, or leave a multi game (my Empire goes on under an AI)."""
    await _json(request)
    return response(await run_in_threadpool(
        GameLife(request.app.state.accounts).leave, *_proofs(request), universe_id))
