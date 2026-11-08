"""Verify that Alembic can build and stamp the schema by itself.

The app no longer calls create_all(), so ``alembic upgrade head`` is the only
way to prepare a database. This test runs the real chain against the SQLite
database configured through DATABASE_URL (the same file the suite boots with).
"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    # legacy marketplace
    "companies",
    "users",
    "posts",
    "rfqs",
    "bids",
    "advertisements",
    "messages",
    # v2 source-to-pay
    "organization_members",
    "budgets",
    "requisitions",
    "requisition_lines",
    "approval_policies",
    "approval_steps",
    "audit_events",
    "outbox_events",
    # v2 sourcing
    "sourcing_events",
    "sourcing_lots",
    "sourcing_lines",
    "sourcing_invitations",
    "sourcing_questions",
    "sourcing_addenda",
    "sourcing_bids",
    "sourcing_bid_lines",
}


def test_upgrade_head_builds_and_is_idempotent():
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite":
        pytest.skip("schema bootstrap test runs against SQLite only")

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))

    # env.py overrides sqlalchemy.url from settings, i.e. DATABASE_URL.
    command.upgrade(config, "head")
    # Second pass must be a no-op: every revision is idempotent.
    command.upgrade(config, "head")

    connection = sqlite3.connect(url.database)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table'"
            )
        }
        version = connection.execute(
            "select version_num from alembic_version"
        ).fetchone()
    finally:
        connection.close()

    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables
    assert version == ("0004",)
