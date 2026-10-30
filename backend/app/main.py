"""Application composition root: HTTP and persistence are separate adapters."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from app.access.http import GameBodyLimit
from app.access.http import router as access_router
from app.access.service import AccessError
from app.api.probes import router
from app.core.config import Settings
from app.persistence.database import create_database_engine, create_session_factory


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
    application.add_middleware(GameBodyLimit)

    @application.exception_handler(AccessError)
    async def denied(request: Request, exc: AccessError):
        return JSONResponse(
            {"error": {"code": exc.code}},
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
        return JSONResponse(
            {"error": {"code": "temporarily_unavailable"}},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    application.include_router(access_router)
    application.state.database_engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.include_router(router)
    return application


app = create_app()
