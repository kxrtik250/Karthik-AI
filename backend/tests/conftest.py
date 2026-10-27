"""Pytest configuration and isolated fixtures for karthik_ai test suite.

Ensures all tests connect ONLY to karthik_ai_test and never the live development DB.
"""

import os
import sys
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Activate test environment before importing app modules
os.environ["TESTING"] = "true"

from app.config import settings
settings.testing = True

from app.database import set_database_url, async_session, get_db
from app.models.base import Base
import app.models  # load all models
from app.main import app

# Point database to isolated test DB
test_engine = set_database_url(settings.test_database_url)


@pytest.fixture(scope="session", autouse=True)
def verify_test_database_isolation():
    """Session-level safety barrier: verifies we are connected exclusively to karthik_ai_test."""
    import asyncio

    async def _check():
        async with test_engine.begin() as conn:
            res = await conn.execute(text("SELECT current_database();"))
            current_db = res.scalar()
            if current_db != "karthik_ai_test":
                raise RuntimeError(
                    f"CRITICAL SAFETY ABORT: Tests connected to '{current_db}' instead of 'karthik_ai_test'!"
                )
            # Recreate all tables on test database to ensure fresh schema matching Base
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_check())


@pytest_asyncio.fixture
async def db_session():
    """Yields an isolated async database session on karthik_ai_test."""
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def clean_test_database():
    """Cleans all test tables on karthik_ai_test before each test run using transactional DELETE."""
    from app.models.conversation import Conversation, Message
    from app.models.document import Document, DocumentChunk
    from app.models.placement import PlacementDrive
    from app.models.company import Company
    from app.models.certification import Certification
    from app.models.project import Project
    from app.models.skill import Skill
    from app.models.profile import Profile
    from sqlalchemy import delete

    async with async_session() as session:
        await session.execute(delete(Message))
        await session.execute(delete(Conversation))
        await session.execute(delete(DocumentChunk))
        await session.execute(delete(Document))
        await session.execute(delete(PlacementDrive))
        await session.execute(delete(Company))
        await session.execute(delete(Certification))
        await session.execute(delete(Project))
        await session.execute(delete(Skill))
        await session.execute(delete(Profile))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client bound in-memory to the FastAPI app using karthik_ai_test."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver/api",
    ) as ac:
        yield ac


# -------------------------------------------------------------
# Test Fixtures / Factories (TEST DATA ONLY - NEVER PRODUCTION)
# -------------------------------------------------------------

@pytest.fixture
def fake_phase6_profile():
    return {
        "name": "Karthik",
        "email": "test-fixture@example.edu",
        "university": "Amrita Vishwa Vidyapeetham",
        "degree": "B.Tech",
        "branch": "Computer Science and Engineering",
        "graduation_year": 2026,
        "cgpa": 8.50,
        "career_goals": "Aspiring AI Engineer and Systems Architect",
        "summary": "Computer Science student and Media Co-Lead at ACM Student Chapter.",
    }


@pytest_asyncio.fixture
async def seeded_profile(client: AsyncClient, fake_phase6_profile: dict):
    resp = await client.post("/profile", json=fake_phase6_profile)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def fake_phase6_skills():
    return [
        {"name": "Python", "category": "Programming Languages", "proficiency": "Advanced"},
        {"name": "FastAPI", "category": "Frameworks", "proficiency": "Intermediate"},
        {"name": "PostgreSQL", "category": "Databases", "proficiency": "Intermediate"},
    ]


@pytest.fixture
def fake_phase6_project():
    return {
        "name": "Carbon Footprint Tracker",
        "description": "Full-stack carbon emission monitoring and telemetry calculation system",
        "technologies": ["Python", "FastAPI", "React", "PostgreSQL"],
        "status": "completed",
        "role": "Lead Developer",
    }


@pytest.fixture
def fake_phase6_certification():
    return {
        "name": "AWS Certified Cloud Practitioner",
        "issuer": "Amazon Web Services",
        "issue_date": "2024-05-15",
    }


@pytest.fixture
def fake_phase6_company_and_placement():
    return {
        "company": {
            "name": "Google",
            "industry": "Technology",
            "location": "Mountain View, CA",
        },
        "placement": {
            "role": "Software Engineer Intern",
            "status": "applied",
            "compensation": "30 LPA",
            "deadline": "2026-11-30",
        },
    }
