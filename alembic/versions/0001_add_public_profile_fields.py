"""Initial schema and public profile fields

Revision ID: 0001
Revises:
Create Date: 2025-10-30 21:32:00.000000

This revision doubles as the baseline. The original file only added columns and
assumed the core tables already existed, which made the chain unable to build a
fresh database. It now creates the legacy tables when they are missing and
still adds the public-profile columns when they are absent, so it is safe on:

- an empty database (fresh clone / CI),
- a database previously created by the old startup create_all() path.
"""

from alembic import op
import sqlalchemy as sa

from app.core.db import Base
from app.models import orm  # noqa: F401  (registers legacy tables)


# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# Tables as they existed before this revision. Restricting the list keeps the
# baseline stable if unrelated models are added later.
LEGACY_TABLES = ("companies", "users", "posts", "rfqs", "bids")


def _column_names(bind, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(bind).get_columns(table_name)
    }


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    missing_tables = [
        Base.metadata.tables[name]
        for name in LEGACY_TABLES
        if name in Base.metadata.tables and name not in existing_tables
    ]
    if missing_tables:
        # The current models already include the public-profile and AI-summary
        # columns, so the add_column steps below become no-ops on a fresh DB.
        Base.metadata.create_all(
            bind=bind, tables=missing_tables, checkfirst=True
        )

    company_columns = _column_names(bind, "companies")
    if "is_public" not in company_columns:
        op.add_column(
            "companies",
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "public_description" not in company_columns:
        op.add_column(
            "companies", sa.Column("public_description", sa.Text(), nullable=True)
        )
    if "logo_url" not in company_columns:
        op.add_column(
            "companies",
            sa.Column("logo_url", sa.String(length=500), nullable=True),
        )
    if "location" not in company_columns:
        op.add_column(
            "companies",
            sa.Column("location", sa.String(length=255), nullable=True),
        )

    index_names = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("companies")
    }
    if "ix_companies_is_public" not in index_names:
        op.create_index(
            "ix_companies_is_public",
            "companies",
            ["is_public"],
            unique=False,
        )

    user_columns = _column_names(bind, "users")
    if "title" not in user_columns:
        op.add_column(
            "users", sa.Column("title", sa.String(length=100), nullable=True)
        )
    if "bio" not in user_columns:
        op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "users" in existing_tables:
        user_columns = _column_names(bind, "users")
        if "bio" in user_columns:
            op.drop_column("users", "bio")
        if "title" in user_columns:
            op.drop_column("users", "title")

    if "companies" in existing_tables:
        index_names = {
            index["name"]
            for index in sa.inspect(bind).get_indexes("companies")
        }
        if "ix_companies_is_public" in index_names:
            op.drop_index("ix_companies_is_public", table_name="companies")

        company_columns = _column_names(bind, "companies")
        for name in ("location", "logo_url", "public_description", "is_public"):
            if name in company_columns:
                op.drop_column("companies", name)
