"""agent runtime: runs, provenance steps and human-gated proposals

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07

Idempotent like the rest of the chain.
"""

from alembic import op
import sqlalchemy as sa

from app.core.db import Base
from app.models import agents  # noqa: F401  (registers the agent tables)


# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


NEW_TABLES = ("agent_runs", "agent_steps", "agent_proposals")


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    missing = [
        Base.metadata.tables[name]
        for name in NEW_TABLES
        if name in Base.metadata.tables and name not in existing
    ]
    if missing:
        Base.metadata.create_all(
            bind=bind, tables=missing, checkfirst=True
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    for name in reversed(NEW_TABLES):
        table = Base.metadata.tables.get(name)
        if table is not None and name in existing:
            table.drop(bind=bind, checkfirst=True)
