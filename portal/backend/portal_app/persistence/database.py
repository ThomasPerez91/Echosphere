"""Accounts engine and pool, independent from Game persistence."""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from portal_app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=0,
        pool_timeout=3,
        hide_parameters=True,
        connect_args={
            "connect_timeout": settings.database_connect_timeout,
            "options": (
                f"-c timezone=UTC -c statement_timeout={settings.database_statement_timeout_ms}"
            ),
        },
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
