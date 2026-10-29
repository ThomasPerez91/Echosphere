"""Portal composition root: no Game imports, connections or authentication yet."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    application.include_router(router)
    return application


app = create_app()
