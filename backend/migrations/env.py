from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.models import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)


def include_object(obj, name, type_, reflected, compare_to):
    # Ignore PostGIS system tables and the generated location column and its index.
    if reflected and compare_to is None:
        return False
    return True


engine = create_engine(get_settings().database_url)
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
