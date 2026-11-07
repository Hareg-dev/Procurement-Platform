"""Add AI summary fields to RFQ and Bid models

Revision ID: 0002
Revises: 0001
Create Date: 2025-10-30 21:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add AI summary field to rfqs table
    op.add_column('rfqs', sa.Column('ai_summary', sa.Text(), nullable=True))
    
    # Add AI summary field to bids table
    op.add_column('bids', sa.Column('ai_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove AI summary fields
    op.drop_column('bids', 'ai_summary')
    op.drop_column('rfqs', 'ai_summary')
