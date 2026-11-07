"""Add public profile fields to Company and User models

Revision ID: 0001
Revises: 
Create Date: 2025-10-30 21:32:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add public profile fields to companies table
    op.add_column('companies', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('companies', sa.Column('public_description', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('logo_url', sa.String(length=500), nullable=True))
    op.add_column('companies', sa.Column('location', sa.String(length=255), nullable=True))
    
    # Create index on is_public for efficient filtering
    op.create_index(op.f('ix_companies_is_public'), 'companies', ['is_public'], unique=False)
    
    # Add public profile fields to users table
    op.add_column('users', sa.Column('title', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove public profile fields from users table
    op.drop_column('users', 'bio')
    op.drop_column('users', 'title')
    
    # Remove public profile fields from companies table
    op.drop_index(op.f('ix_companies_is_public'), table_name='companies')
    op.drop_column('companies', 'location')
    op.drop_column('companies', 'logo_url')
    op.drop_column('companies', 'public_description')
    op.drop_column('companies', 'is_public')
