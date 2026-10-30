"""Public JSON account endpoints, no session issuance or implicit Game authorization."""

import ipaddress
import socket

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from portal_app.accounts.security import PublicError

router = APIRouter(prefix="/accounts")


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    password: SecretStr = Field(min_length=1, max_length=128)


def peer_address(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    proxy = request.app.state.accounts.settings.trusted_proxy_host
    if proxy:
        try:
            trusted = {entry[4][0] for entry in socket.getaddrinfo(proxy, None)}
            if peer in trusted:
                return str(ipaddress.ip_address(request.headers.get("x-forwarded-for", "")))
        except (OSError, ValueError):
            pass
    # Never trust an arbitrary browser's X-Forwarded-For.
    return peer


def check_origin(request: Request) -> None:
    if request.headers.get("origin") != request.app.state.accounts.settings.public_origin:
        raise PublicError("origin_denied", 403)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise PublicError("invalid_request", 415)


@router.post("/register", status_code=202)
async def register(data: Credentials, request: Request):
    check_origin(request)
    await run_in_threadpool(
        request.app.state.accounts.register,
        data.email,
        data.password.get_secret_value(),
        peer_address(request),
    )
    return JSONResponse(
        {"status": "request_received"}, status_code=202, headers={"Cache-Control": "no-store"}
    )


@router.post("/email/resend", status_code=202)
async def resend(data: Credentials, request: Request):
    check_origin(request)
    await run_in_threadpool(
        request.app.state.accounts.resend,
        data.email,
        data.password.get_secret_value(),
        peer_address(request),
    )
    return JSONResponse(
        {"status": "request_received"}, status_code=202, headers={"Cache-Control": "no-store"}
    )


@router.post("/email/verify")
async def verify(data: Verification, request: Request):
    check_origin(request)
    await run_in_threadpool(
        request.app.state.accounts.verify,
        data.token,
        data.password.get_secret_value(),
        peer_address(request),
    )
    return JSONResponse({"status": "verified"}, headers={"Cache-Control": "no-store"})


class AccountBodyLimit:
    """Bound the raw request before FastAPI/Pydantic parse it; no credential echo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(
            ("/accounts/", "/auth/", "/security/", "/mfa/")
        ):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            maximum = 65536 if scope["path"].startswith("/mfa/") else 8192
            if len(body) > maximum:
                response = JSONResponse(
                    {"error": {"code": "invalid_request"}},
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
