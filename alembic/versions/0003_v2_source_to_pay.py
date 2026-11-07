"""v2 source-to-pay foundation

Revision ID: 0003
Revises: 3e7428b3c826
Create Date: 2026-11-07

Adds organization memberships, budgets, requisitions, approval matrix,
approval steps, audit trail and transactional outbox, then backfills an
org-admin membership for existing buyer/admin users.

The revision is idempotent: the application still bootstraps schema with
``create_all()`` in this phase, so it must work whether or not those tables
already exist.
"""

from alembic import op
import sqlalchemy as sa

from app.core.db import Base
from app.models import procurement  # noqa: F401  (registers the v2 tables)


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "3e7428b3c826"
branch_labels = None
depends_on = None


NEW_TABLES = (
    "organization_members",
    "budgets",
    "requisitions",
    "requisition_lines",
    "approval_policies",
    "approval_steps",
    "audit_events",
    "outbox_events",
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
        Base.metadata.create_all(bind=bind, tables=missing, checkfirst=True)

    # SQLAlchemy's Enum persists member *names*, hence 'BUYER'/'ADMIN'.
    op.execute(
        sa.text(
            """
            INSERT INTO organization_members
                (organization_id, user_id, org_role, is_active,
                 created_at, updated_at)
            SELECT u.company_id, u.id, 'ORG_ADMIN', TRUE,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM users u
            WHERE u.role IN ('BUYER', 'ADMIN')
              AND NOT EXISTS (
                  SELECT 1 FROM organization_members m
                  WHERE m.user_id = u.id
                    AND m.organization_id = u.company_id
              )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    for name in reversed(NEW_TABLES):
        table = Base.metadata.tables.get(name)
        if table is not None and name in existing:
            table.drop(bind=bind, checkfirst=True)
