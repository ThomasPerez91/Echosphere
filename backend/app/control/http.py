"""Dedicated mTLS listener. Peer identity comes from the verified TLS connection only."""

import hashlib
import ssl
from pathlib import Path
from uuid import UUID

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse
from uvicorn.protocols.http.h11_impl import H11Protocol

from app.control.contracts import Operation
from app.control.service import SERVICE, Control, ControlError
from app.core.config import Settings
from app.persistence.database import create_database_engine, create_session_factory


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > 65536:
                await JSONResponse({"error": {"code": "invalid_contract"}}, status_code=413)(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def buffered():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, buffered, send)


class PeerProtocol(H11Protocol):
    def connection_made(self, transport):
        super().connection_made(transport)
        tls = transport.get_extra_info("ssl_object")
        peer = tls.getpeercert(binary_form=True) if tls else None
        fingerprint = hashlib.sha256(peer).hexdigest() if peer else None
        upstream = self.app

        async def authenticated_connection(scope, receive, send):
            # An HTTP header, forwarded scheme or request body cannot write this ASGI state.
            scope = {**scope, "control_peer": fingerprint}
            await upstream(scope, receive, send)

        self.app = authenticated_connection


def fingerprint(path):
    der = ssl.PEM_cert_to_DER_cert(Path(path).read_text())
    return hashlib.sha256(der).hexdigest()


def create_internal_app(settings=None):
    settings = settings or Settings()
    trusted = {fingerprint(settings.control_peer_cert)}
    if settings.control_next_peer_cert is not None:
        trusted.add(fingerprint(settings.control_next_peer_cert))
    engine = create_database_engine(settings)
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    application.add_middleware(BodyLimit)
    application.state.control = Control(create_session_factory(engine))

    @application.middleware("http")
    async def authenticated(request, call_next):
        if (
            request.scope.get("scheme") != "https"
            or request.scope.get("control_peer") not in trusted
        ):
            return JSONResponse({"error": {"code": "service_denied"}}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(ControlError)
    async def denied(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=error.status)

    @application.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse({"error": {"code": "invalid_contract"}}, status_code=422)

    @application.exception_handler(SQLAlchemyError)
    async def unavailable(request, error):
        return JSONResponse({"error": {"code": "game_unavailable"}}, status_code=503)

    @application.get("/internal/v1/health")
    def health():
        return {"status": "ok"}

    @application.post("/internal/v1/operations")
    def operate(data: Operation, request: Request):
        return request.app.state.control.apply(SERVICE, data)

    @application.get("/internal/v1/operations/{identifier}")
    def result(identifier: UUID, request: Request):
        return request.app.state.control.operation(SERVICE, identifier)

    @application.get("/internal/v1/access/{identifier}")
    def revision(identifier: UUID, request: Request):
        return request.app.state.control.revision(SERVICE, identifier)

    return application


def main():
    settings = Settings()
    # No plaintext endpoint or forwarded-header identity; this process serves only this listener.
    uvicorn.run(
        create_internal_app(settings),
        host="0.0.0.0",
        port=9443,
        http=PeerProtocol,
        proxy_headers=False,
        access_log=False,
        ssl_certfile=str(settings.control_cert),
        ssl_keyfile=str(settings.control_key),
        ssl_ca_certs=str(settings.control_client_ca),
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        limit_concurrency=32,
        timeout_keep_alive=5,
    )


if __name__ == "__main__":
    main()
