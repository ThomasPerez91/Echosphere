"""Navigation forms only: no cross-origin credentialed API and no ticket in a URL."""

import secrets
from html import escape
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse

from portal_app.accounts.security import PublicError
from portal_app.api.accounts import peer_address
from portal_app.handoff.service import Handoff
from portal_app.sessions.service import SESSION_COOKIE, csrf

router = APIRouter(prefix="/handoff")


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


def page(title, action, fields, origin):
    nonce = secrets.token_urlsafe(24)
    hidden = "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(str(v), quote=True)}">'
        for k, v in fields.items()
    )
    return HTMLResponse(
        '<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Echosphere — {escape(title)}</title>'
        f'<style nonce="{nonce}">{TRANSFER_STYLE}</style>'
        f"<body><main><h1>{escape(title)}</h1>"
        f'<form method="post" action="{escape(action, quote=True)}">{hidden}'
        '<button type="submit">Continuer</button></form>'
        "<p>Le transfert expire rapidement. En cas d’échec, recommencez depuis le lobby.</p>"
        "</main></body></html>",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "strict-origin",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": f"default-src 'none'; style-src 'nonce-{nonce}'; "
            f"form-action {origin}; "
            "frame-ancestors 'none'; base-uri 'none'",
        },
    )


async def form(request, required):
    if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
        raise PublicError("invalid_request", 415)
    raw = await request.body()
    if len(raw) > 8192 or request.url.query:
        raise PublicError("invalid_request", 422)
    try:
        values = parse_qs(raw.decode("ascii"), strict_parsing=True, max_num_fields=8)
        if set(values) != set(required) or any(len(v) != 1 for v in values.values()):
            raise ValueError()
        return {k: v[0] for k, v in values.items()}
    except (UnicodeError, ValueError):
        raise PublicError("invalid_request", 422) from None


@router.post("/prepare")
async def prepare(request: Request):
    fields = await form(request, ("universe_id", "pre_auth_id"))
    try:
        universe, pre_auth = UUID(fields["universe_id"]), UUID(fields["pre_auth_id"])
    except ValueError:
        raise PublicError("invalid_request", 422) from None
    raw = request.cookies.get(SESSION_COOKIE)
    await run_in_threadpool(
        Handoff(request.app.state.accounts).prepare, raw, universe, request.headers.get("origin")
    )
    origin = request.app.state.accounts.settings.public_origin
    return page(
        "Confirmer l’entrée dans l’univers",
        origin + "/api/handoff/issue",
        {"universe_id": universe, "pre_auth_id": pre_auth, "csrf": csrf(raw)},
        origin,
    )


@router.post("/issue")
async def issue(request: Request):
    origin = request.app.state.accounts.settings.public_origin
    if request.headers.get("origin") != origin:
        raise PublicError("origin_denied", 403)
    fields = await form(request, ("universe_id", "pre_auth_id", "csrf"))
    try:
        universe, pre_auth = UUID(fields["universe_id"]), UUID(fields["pre_auth_id"])
    except ValueError:
        raise PublicError("invalid_request", 422) from None
    ticket, target = await run_in_threadpool(
        Handoff(request.app.state.accounts).issue,
        request.cookies.get(SESSION_COOKIE),
        fields["csrf"],
        universe,
        pre_auth,
        peer_address(request),
    )
    return page(
        "Entrer dans l’univers",
        f"{target}/api/game/{universe}/exchange",
        {"ticket": ticket},
        target,
    )
