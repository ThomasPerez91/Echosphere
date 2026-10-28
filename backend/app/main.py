"""Application composition root: HTTP and persistence are separate adapters."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    application.state.database_engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.include_router(router)
    return application


app = create_app()
