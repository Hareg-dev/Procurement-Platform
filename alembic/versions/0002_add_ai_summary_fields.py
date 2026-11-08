"""Add AI summary fields to RFQ and Bid models

Revision ID: 0002
Revises: 0001
Create Date: 2025-10-30 21:38:00.000000

Guarded so it can run after the baseline created the tables from the current
models (where these columns already exist).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(bind).get_columns(table_name)
    }


def upgrade() -> None:
    bind = op.get_bind()

    if "ai_summary" not in _column_names(bind, "rfqs"):
        op.add_column("rfqs", sa.Column("ai_summary", sa.Text(), nullable=True))

    if "ai_summary" not in _column_names(bind, "bids"):
        op.add_column("bids", sa.Column("ai_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    if "ai_summary" in _column_names(bind, "bids"):
        op.drop_column("bids", "ai_summary")
    if "ai_summary" in _column_names(bind, "rfqs"):
        op.drop_column("rfqs", "ai_summary")
