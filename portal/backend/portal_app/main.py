"""Portal composition root: Accounts services only, no Game connection or session issuance."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

from portal_app.accounts.security import PublicError
from portal_app.accounts.service import Accounts
from portal_app.api.accounts import AccountBodyLimit
from portal_app.api.accounts import router as accounts_router
from portal_app.api.probes import router
from portal_app.core.config import Settings
from portal_app.persistence.database import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()
    engine = create_database_engine(configuration)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Echosphere Portal", version="0.0.1", lifespan=lifespan)
    application.state.database_engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.state.accounts = Accounts(application.state.session_factory, configuration)
    application.add_middleware(AccountBodyLimit)

    @application.exception_handler(PublicError)
    async def public_error(request: Request, exc: PublicError):
        return JSONResponse(
            {"error": {"code": exc.code}},
            status_code=exc.status,
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Default FastAPI validation includes raw input values, including passwords/tokens.
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

    application.include_router(router)
    application.include_router(accounts_router)
    return application


app = create_app()
