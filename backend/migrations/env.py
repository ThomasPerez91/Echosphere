from alembic import context

from app.access import models as access_models  # noqa: F401
from app.colony import models as colony_models  # noqa: F401
from app.control import models as control_models  # noqa: F401
from app.core.config import Settings
from app.persistence.database import create_database_engine
from app.persistence.models import Base
from app.simulation import models as simulation_models  # noqa: F401

if context.is_offline_mode():
    # Do not render a credential-bearing URL into logs or configparser interpolation.
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
