"""Application composition root: HTTP and persistence are separate adapters."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.access.http import GameBodyLimit, navigation_error
from app.access.http import router as access_router
from app.access.service import AccessError
from app.api.probes import router
from app.colony.api import router as colony_router
from app.core.config import Settings
from app.persistence.database import create_database_engine, create_session_factory
from app.research.api import router as research_router
from app.simulation.clock import SystemClock


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    engine = create_database_engine(configuration)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Echosphere", version="0.0.1", lifespan=lifespan)
    application.state.settings = configuration
    # Injectable time source shared by sessions and Colony commands; system UTC by default.
    application.state.clock = SystemClock()
    application.add_middleware(GameBodyLimit)

    @application.exception_handler(AccessError)
    async def denied(request: Request, exc: AccessError):
        if "text/html" in request.headers.get("accept", "") and request.url.path.startswith(
            "/game/"
        ):
            return navigation_error(request, exc.code, exc.status)
        return JSONResponse(
            {"error": {"code": exc.code}, "portal_url": configuration.portal_public_origin},
            status_code=exc.status,
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"error": {"code": "invalid_request"}},
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(SQLAlchemyError)
    async def unavailable(request: Request, exc: SQLAlchemyError):
        if "text/html" in request.headers.get("accept", "") and request.url.path.startswith(
            "/game/"
        ):
            return navigation_error(request, "temporarily_unavailable", 503)
        return JSONResponse(
            {
                "error": {"code": "temporarily_unavailable"},
                "portal_url": configuration.portal_public_origin,
            },
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    application.include_router(access_router)
    application.include_router(colony_router)
    application.include_router(research_router)
    application.state.database_engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.include_router(router)
    return application


app = create_app()
