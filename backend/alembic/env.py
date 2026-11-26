from alembic import context
from app.database import Base, engine
from app import member_d_models

if context.is_offline_mode():
    raise RuntimeError('Use online migration for existing-schema validation')
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
