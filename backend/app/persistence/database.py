from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
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
    # Services will own explicit `with factory.begin()` transactions, shared by humans and AI.
    return sessionmaker(bind=engine, expire_on_commit=False)


def check_database(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
