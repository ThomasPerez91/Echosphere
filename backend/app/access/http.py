"""Public navigation and same-origin Game session API; no Colony projection."""

import ipaddress
import secrets
import socket
from datetime import UTC, datetime
from html import escape
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.access.service import AccessError, GameSessions

router = APIRouter(prefix="/game/{universe_id}")
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def cookie_name(universe, pre_auth=False):
    return f"__Host-game-{'preauth' if pre_auth else 'session'}-{universe.hex}"


def peer(request):
    value = request.client.host if request.client else "unknown"
    proxy = request.app.state.settings.trusted_proxy_host
    if proxy:
        try:
            trusted = {entry[4][0] for entry in socket.getaddrinfo(proxy, None)}
            if value in trusted:
                return str(ipaddress.ip_address(request.headers.get("x-forwarded-for", "")))
        except (OSError, ValueError):
            pass
    return value


def service(request):
    return GameSessions(request.app.state.session_factory, request.app.state.settings)


def origin(request, expected):
    if request.headers.get("origin") != expected or request.url.query:
        raise AccessError("origin_denied")


async def form(request, required):
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        raise AccessError("invalid_request", 415)
    try:
        body = await request.body()
        if len(body) > 8192:
            raise ValueError()
        values = parse_qs(body.decode("ascii"), strict_parsing=True, max_num_fields=4)
        if set(values) != set(required) or any(len(v) != 1 for v in values.values()):
            raise ValueError()
        return {key: value[0] for key, value in values.items()}
    except (UnicodeError, ValueError):
        raise AccessError("invalid_request", 422) from None


TRANSFER_STYLE = """
:root {color-scheme:dark;font-family:system-ui,sans-serif;background:#080e19;color:#e2eaf4}
body {margin:0;padding:clamp(16px,4vw,48px)}
main {max-width:52rem;margin:auto;background:#101a2a;border:1px solid #2c3c51;
      border-radius:12px;padding:clamp(16px,4vw,32px);overflow-wrap:anywhere}
h1 {font-size:clamp(1.5rem,4vw,2rem)} p {line-height:1.6}
a {color:#83e3e8;display:inline-block;padding:12px 0}
button {font:inherit;min-height:44px;padding:10px 18px;border-radius:8px;border:1px solid #83e3e8;
        background:#101a2a;color:#83e3e8;cursor:pointer;max-width:100%}
form {margin:16px 0} :focus-visible {outline:3px solid #f1d18f;outline-offset:3px}
"""


def page(title, body, target, *, transfer=False):
    nonce = secrets.token_urlsafe(24)
    return HTMLResponse(
        '<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Echosphere — {escape(title)}</title>"
        f'<style nonce="{nonce}">{TRANSFER_STYLE}</style><body><main>'
        f"<h1>{escape(title)}</h1>{body}"
        + (
            f'<script nonce="{nonce}">document.getElementById("handoff").requestSubmit();</script>'
            if transfer
            else ""
        )
        + "</main></body></html>",
        headers={
            **HEADERS,
            "Referrer-Policy": "strict-origin",
            "Content-Security-Policy": "default-src 'none'; connect-src 'self'; "
            f"style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; "
            f"form-action {target}; "
            "base-uri 'none'; frame-ancestors 'none'",
        },
    )


def fields(values):
    return "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(str(v), quote=True)}">'
        for k, v in values.items()
    )


@router.get("/start")
async def start(universe_id: UUID, request: Request):
    if request.url.query:
        raise AccessError("invalid_request", 422)
    identifier, raw = await run_in_threadpool(service(request).start, universe_id, peer(request))
    target = request.app.state.settings.portal_public_origin
    result = page(
        "Echosphere — entrée sécurisée",
        f'<form id="handoff" method="post" action="{escape(target)}/api/handoff/prepare">'
        + fields({"universe_id": universe_id, "pre_auth_id": identifier})
        + '<button type="submit">Confirmer avec mon compte Portal</button></form>',
        target,
        transfer=True,
    )
    result.set_cookie(
        cookie_name(universe_id, True),
        raw,
        max_age=300,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return result


@router.post("/exchange")
async def exchange(universe_id: UUID, request: Request):
    origin(request, request.app.state.settings.portal_public_origin)
    values = await form(request, ("ticket",))
    raw, payload = await run_in_threadpool(
        service(request).exchange,
        values["ticket"],
        request.cookies.get(cookie_name(universe_id, True)),
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
    )
    result = RedirectResponse(f"/#universe/{universe_id}/empire", status_code=303, headers=HEADERS)
    result.set_cookie(
        cookie_name(universe_id),
        raw,
        max_age=8 * 3600,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    result.delete_cookie(
        cookie_name(universe_id, True), secure=True, httponly=True, samesite="strict", path="/"
    )
    return result


@router.get("/session")
async def read(universe_id: UUID, request: Request):
    if request.headers.get("x-game-request") != "bootstrap" or (
        request.headers.get("origin") not in (None, request.app.state.settings.game_public_origin)
    ):
        raise AccessError("origin_denied")
    payload = await run_in_threadpool(
        service(request).read, request.cookies.get(cookie_name(universe_id)), universe_id
    )
    return session_response(payload, request)


@router.get("/view")
async def view(universe_id: UUID, request: Request):
    await run_in_threadpool(
        service(request).read, request.cookies.get(cookie_name(universe_id)), universe_id
    )
    return RedirectResponse(f"/#universe/{universe_id}/empire", status_code=303, headers=HEADERS)


def session_response(payload, request):
    return JSONResponse(
        {
            **payload,
            "portal_url": request.app.state.settings.portal_public_origin,
            "server_time": datetime.now(UTC).isoformat(),
        },
        headers=HEADERS,
    )


async def action_proof(request):
    if request.headers.get("content-type", "").split(";")[0] == "application/json":
        try:
            if await request.json() != {}:
                raise ValueError()
        except ValueError:
            raise AccessError("invalid_request", 422) from None
        return request.headers.get("x-csrf-token"), True
    return (await form(request, ("csrf",)))["csrf"], False


@router.post("/navigation")
async def navigation(universe_id: UUID, request: Request):
    origin(request, request.app.state.settings.game_public_origin)
    proof, json_mode = await action_proof(request)
    payload = await run_in_threadpool(
        service(request).read,
        request.cookies.get(cookie_name(universe_id)),
        universe_id,
        interaction=True,
        proof=proof,
    )
    if json_mode:
        return session_response(payload, request)
    return RedirectResponse(f"/#universe/{universe_id}/empire", status_code=303, headers=HEADERS)


@router.post("/logout")
async def logout(universe_id: UUID, request: Request):
    origin(request, request.app.state.settings.game_public_origin)
    proof, json_mode = await action_proof(request)
    payload = await run_in_threadpool(
        service(request).logout, request.cookies.get(cookie_name(universe_id)), universe_id, proof
    )
    if json_mode:
        # A late response must not erase a newer handoff's cookie from another tab.
        return JSONResponse(payload, headers=HEADERS)
    return RedirectResponse(
        f"/#universe/{universe_id}/signed-out", status_code=303, headers=HEADERS
    )


def navigation_error(request, code, status):
    messages = {
        "authentication_required": "Votre session a expiré ou a été déconnectée.",
        "game_session_limit_reached": "Fermez une autre partie sur cet appareil.",
        "account_switch_requires_logout": "Déconnectez d’abord la partie de l’autre compte.",
        "temporarily_unavailable": "Le service Game est temporairement indisponible.",
    }
    result = page(
        "Entrée dans la partie interrompue",
        "<p>"
        + messages.get(code, "Le transfert n’est plus valide. Recommencez depuis le lobby.")
        + '</p><a href="'
        + escape(request.app.state.settings.portal_public_origin)
        + '">Retour au lobby</a>',
        request.app.state.settings.game_public_origin,
    )
    result.status_code = status
    return result


class GameBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/game/"):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 8192:
                await JSONResponse(
                    {"error": {"code": "invalid_request"}}, status_code=413, headers=HEADERS
                )(scope, receive, send)
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
