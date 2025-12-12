#!/usr/bin/env python3
"""
Database migration script for Railway deployment.
Run this after deployment to create/update database schema.
"""
import asyncio
import sys
from alembic import command
from alembic.config import Config
from app.core.config import settings

def run_migrations():
    """Run Alembic migrations."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    
    try:
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        print("Database migrations completed successfully!")
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()