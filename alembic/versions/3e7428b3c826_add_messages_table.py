"""Add messages table

Revision ID: 3e7428b3c826
Revises: 5d2e17da5aea
Create Date: 2026-01-30 21:11:06.802018

The original revision was an empty autogenerate stub, so the messages table
never existed in any migrated database. Create it from the model metadata when
missing.
"""

from alembic import op
import sqlalchemy as sa

from app.core.db import Base
from app.models import message  # noqa: F401  (registers the messages table)


# revision identifiers, used by Alembic.
revision = "3e7428b3c826"
down_revision = "5d2e17da5aea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "messages" in sa.inspect(bind).get_table_names():
        return

    Base.metadata.tables["messages"].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "messages" not in sa.inspect(bind).get_table_names():
        return

    Base.metadata.tables["messages"].drop(bind=bind, checkfirst=True)
