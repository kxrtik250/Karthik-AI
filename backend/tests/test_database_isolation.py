"""Explicit test verifying database isolation between test and development environments."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database import async_session


@pytest.mark.asyncio
async def test_connected_to_test_database_only():
    """Asserts that the test session is connected exclusively to karthik_ai_test."""
    async with async_session() as session:
        res = await session.execute(text("SELECT current_database();"))
        active_db = res.scalar()
        assert active_db == "karthik_ai_test", f"Tests must connect to karthik_ai_test, but got {active_db}!"


@pytest.mark.asyncio
async def test_development_database_remains_isolated_and_unmodified():
    """Directly checks the development database to prove tests do not alter development records."""
    # 1. Connect to dev DB using settings.database_url (read-only verification)
    dev_engine = create_async_engine(settings.database_url)
    async with dev_engine.connect() as dev_conn:
        res = await dev_conn.execute(text("SELECT current_database();"))
        dev_db = res.scalar()
        assert dev_db == "karthik_ai_db"

        # Check that the real development profile is intact
        profile_res = await dev_conn.execute(
            text("SELECT name, university, degree, branch, graduation_year, cgpa FROM profiles LIMIT 1;")
        )
        row = profile_res.fetchone()
        assert row is not None, "Real development profile must exist!"
        assert row.name == "Karthik"
        assert row.university == "Sathyabama Institute of Science and Technology"
        assert row.degree == "B.E."
        assert row.branch == "Computer Science and Engineering"
        assert row.graduation_year == 2027
        assert float(row.cgpa) == 7.52

    await dev_engine.dispose()
