#!/usr/bin/env python3
"""
Create initial migration for the procurement platform.
Run this locally before deploying to Railway.
"""
from alembic import command
from alembic.config import Config
from app.core.config import settings

def create_initial_migration():
    """Create initial migration with all models."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    try:
        # Create initial migration
        command.revision(
            alembic_cfg, 
            message="Initial migration", 
            autogenerate=True
        )
        print("Initial migration created successfully!")
        print("Review the migration file in alembic/versions/")
        print("Ready for Railway deployment!")
    except Exception as e:
        print(f"Migration creation failed: {e}")

if __name__ == "__main__":
    create_initial_migration()