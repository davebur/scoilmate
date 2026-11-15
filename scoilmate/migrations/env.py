"""Alembic environment: uses the app's engine (FK checks on) unless a connection is supplied."""

from alembic import context

from scoilmate import db
from scoilmate.models import Base

config = context.config
target_metadata = Base.metadata


def run():
    connection = config.attributes.get("connection")
    if connection is None:
        with db.engine().connect() as conn:
            context.configure(
                connection=conn, target_metadata=target_metadata, render_as_batch=True
            )
            with context.begin_transaction():
                context.run_migrations()
            conn.commit()
    else:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


run()
