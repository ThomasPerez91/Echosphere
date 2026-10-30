from alembic import context

from portal_app.account_security import models as security_models  # noqa: F401
from portal_app.accounts import models as account_models  # noqa: F401
from portal_app.control import models as control_models  # noqa: F401
from portal_app.core.config import Settings
from portal_app.mfa import models as mfa_models  # noqa: F401
from portal_app.persistence.database import create_database_engine
from portal_app.persistence.models import Base
from portal_app.sessions import models as session_models  # noqa: F401

options = {
    "target_metadata": Base.metadata,
    "compare_type": True,
    "version_table": "portal_alembic_version",
}

if context.is_offline_mode():
    context.configure(dialect_name="postgresql", literal_binds=True, **options)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, **options)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
