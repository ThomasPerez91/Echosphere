"""Same-origin Portal session API. Automatic reads never count as activity."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from portal_app.accounts.security import PublicError
from portal_app.api.accounts import Credentials, check_origin, peer_address
from portal_app.sessions.service import (
    CHALLENGE_COOKIE,
    PROFILE_COOKIE,
    SESSION_COOKIE,
    Sessions,
    csrf,
)

router = APIRouter(prefix="/auth")


class LoginCredentials(Credentials):
    factor: dict | None = None


def service(request):
    return Sessions(request.app.state.accounts)


def response(payload):
    return JSONResponse(
        payload, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    )


def cookie(result, name, value, maximum):
    result.set_cookie(
        name, value, max_age=maximum, secure=True, httponly=True, samesite="strict", path="/"
    )


def bootstrap(request):
    origin = request.headers.get("origin")
    if request.headers.get("x-portal-request") != "bootstrap" or (
        origin is not None and origin != request.app.state.accounts.settings.public_origin
    ):
        raise PublicError("origin_denied", 403)


@router.get("/challenge")
async def challenge(request: Request):
    bootstrap(request)
    raw = await run_in_threadpool(service(request).challenge, peer_address(request))
    result = response({"csrf_token": csrf(raw)})
    cookie(result, CHALLENGE_COOKIE, raw, 300)
    return result


@router.post("/login")
async def login(data: LoginCredentials, request: Request):
    check_origin(request)
    raw, profile, payload = await run_in_threadpool(
        service(request).login,
        data.email,
        data.password.get_secret_value(),
        request.cookies.get(CHALLENGE_COOKIE),
        request.headers.get("x-csrf-token"),
        request.cookies.get(PROFILE_COOKIE),
        request.cookies.get(SESSION_COOKIE),
        peer_address(request),
        data.factor,
    )
    result = response(payload)
    now = request.app.state.accounts.clock()
    maximum = max(0, int((datetime.fromisoformat(payload["expires_at"]) - now).total_seconds()))
    cookie(result, SESSION_COOKIE, raw, maximum)
    cookie(result, PROFILE_COOKIE, profile, 365 * 86400)
    result.delete_cookie(CHALLENGE_COOKIE, secure=True, httponly=True, samesite="strict", path="/")
    return result


@router.get("/session")
async def session_state(request: Request):
    bootstrap(request)
    return response(
        await run_in_threadpool(service(request).read, request.cookies.get(SESSION_COOKIE))
    )


@router.get("/sessions")
async def sessions(request: Request):
    bootstrap(request)
    return response(
        await run_in_threadpool(
            service(request).read, request.cookies.get(SESSION_COOKIE), devices=True
        )
    )


@router.post("/navigation")
async def navigation(request: Request):
    check_origin(request)
    # Only this explicit server-defined navigation/refresh action counts, never GET/polling.
    return response(
        await run_in_threadpool(
            service(request).read,
            request.cookies.get(SESSION_COOKIE),
            interaction=True,
            proof=request.headers.get("x-csrf-token"),
        )
    )


async def close(request, target=None):
    check_origin(request)
    payload = await run_in_threadpool(
        service(request).logout,
        request.cookies.get(SESSION_COOKIE),
        request.headers.get("x-csrf-token"),
        target,
    )
    result = response(payload)
    if payload["current_session_closed"]:
        result.delete_cookie(
            SESSION_COOKIE, secure=True, httponly=True, samesite="strict", path="/"
        )
    return result


@router.post("/logout")
async def logout(request: Request):
    return await close(request)


@router.post("/sessions/{identifier}/logout")
async def logout_session(identifier: UUID, request: Request):
    return await close(request, identifier)
