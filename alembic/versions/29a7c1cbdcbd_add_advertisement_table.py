"""add_advertisement_table

Revision ID: 29a7c1cbdcbd
Revises: 0002
Create Date: 2025-11-27 11:33:59.110350

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "29a7c1cbdcbd"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advertisements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("target_industries", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_advertisements_id"), "advertisements", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_advertisements_id"), table_name="advertisements")
    op.drop_table("advertisements")
