"""v2 sourcing core: events, lots, invitations, Q&A, addenda, sealed bids

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07

Idempotent like the rest of the chain: tables are created only when missing,
so it is safe on databases already bootstrapped by earlier revisions.
"""

from alembic import op
import sqlalchemy as sa

from app.core.db import Base
from app.models import sourcing  # noqa: F401  (registers the sourcing tables)


# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


NEW_TABLES = (
    "sourcing_events",
    "sourcing_lots",
    "sourcing_lines",
    "sourcing_invitations",
    "sourcing_questions",
    "sourcing_addenda",
    "sourcing_bids",
    "sourcing_bid_lines",
)


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
