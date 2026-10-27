"""Tests for Resume Optimizer and ATS Tailoring Studio."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.company import Company
from app.models.placement import PlacementDrive
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill


@pytest.mark.asyncio
async def test_resume_optimizer_database_isolation(db_session: AsyncSession):
    """Verify that tests strictly execute against karthik_ai_test and never karthik_ai_db."""
    result = await db_session.execute(text("SELECT current_database();"))
    current_db = result.scalar()
    assert current_db == "karthik_ai_test", f"Safety violation: running on {current_db} instead of test db!"


@pytest.mark.asyncio
async def test_resume_optimizer_keyword_match_and_gap_analysis(
    db_session: AsyncSession,
):
    """Verify ATS keyword gap calculation against target placement drive requirements."""
    # Seed profile
    prof = Profile(
        name="Karthik Sriram",
        email="karthiksriram2005@gmail.com",
        university="Anna University",
        degree="B.E",
        branch="Computer Science and Engineering",
        graduation_year=2026,
    )
    db_session.add(prof)
    await db_session.flush()

    # Seed verified skills
    s1 = Skill(profile_id=prof.id, name="Python", category="Programming Languages", proficiency="expert")
    s2 = Skill(profile_id=prof.id, name="SQL", category="Databases", proficiency="advanced")
    s3 = Skill(profile_id=prof.id, name="JavaScript", category="Web", proficiency="intermediate")
    s4 = Skill(profile_id=prof.id, name="Git", category="Tools", proficiency="advanced")
    db_session.add_all([s1, s2, s3, s4])

    # Seed company & drive requiring Python, SQL, Docker, AWS
    company = Company(name="Amazon")
    db_session.add(company)
    await db_session.flush()

    drive = PlacementDrive(
        profile_id=prof.id,
        company_id=company.id,
        role="Cloud Software Engineer",
        required_skills=["Python", "SQL", "Docker", "AWS"],
    )
    db_session.add(drive)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/resume/optimize",
            json={
                "drive_id": str(drive.id),
                "target_role": "Cloud Software Engineer",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["company_name"] == "Amazon"
        assert data["target_role"] == "Cloud Software Engineer"

        ats = data["ats_analysis"]
        matched_lower = [m.lower() for m in ats["matched_skills"]]
        missing_lower = [m.lower() for m in ats["missing_skills"]]

        assert "python" in matched_lower
        assert "sql" in matched_lower
        assert "docker" in missing_lower
        assert "aws" in missing_lower

        # 2 out of 4 matched = 50.0%
        assert ats["ats_match_percentage"] == 50.0
        assert len(ats["strengths"]) > 0
        assert len(ats["recommendations"]) > 0


@pytest.mark.asyncio
async def test_resume_optimizer_strictly_grounded_project_bullets(
    db_session: AsyncSession,
):
    """Verify that tailored project bullets strictly adhere to verified project records."""
    prof = Profile(
        name="Karthik Sriram",
        email="karthiksriram2005@gmail.com",
        graduation_year=2026,
    )
    db_session.add(prof)
    await db_session.flush()

    # Stored Project: Student management
    proj = Project(
        profile_id=prof.id,
        name="Student management",
        role="full stack developer",
        technologies=["python", "sql", "js", "git"],
        status="completed",
        description="A full-stack student management application for maintaining student records and managing student information.",
    )
    db_session.add(proj)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/resume/optimize",
            json={
                "target_role": "Full Stack Developer",
                "custom_jd_text": "Requires experience in Python, SQL, JavaScript, Git, and web application design.",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        tailored = data["tailored_projects"]
        assert len(tailored) == 1

        p_data = tailored[0]
        assert p_data["project_name"] == "Student management"
        assert p_data["role"] == "full stack developer"

        all_bullets_text = " ".join(p_data["bullet_points"]).lower()
        # Verify verified technologies and scope are highlighted
        assert "python" in all_bullets_text
        assert "sql" in all_bullets_text
        assert "student" in all_bullets_text
        assert "record" in all_bullets_text

        # Verify strict grounding: no hallucinated buzzwords
        assert "blockchain" not in all_bullets_text
        assert "biometrics" not in all_bullets_text
        assert "microservices" not in all_bullets_text


@pytest.mark.asyncio
async def test_resume_optimizer_full_markdown_synthesis(
    db_session: AsyncSession,
):
    """Verify that generated Markdown resume includes ATS-compliant single column layout."""
    prof = Profile(
        name="Karthik Sriram",
        email="karthiksriram2005@gmail.com",
        phone="+91 9876543210",
        university="Anna University",
        degree="B.E.",
        branch="Computer Science and Engineering",
        graduation_year=2026,
        cgpa=8.5,
    )
    db_session.add(prof)
    await db_session.flush()

    proj = Project(
        profile_id=prof.id,
        name="Student management",
        role="full stack developer",
        technologies=["python", "sql", "js", "git"],
        description="A full-stack student management application for maintaining student records.",
    )
    db_session.add(proj)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/resume/optimize",
            json={
                "target_role": "Software Engineer",
            },
        )

        assert resp.status_code == 200, resp.text
        md = resp.json()["full_resume_markdown"]

        # Check key resume sections
        assert "# Karthik Sriram" in md
        assert "karthiksriram2005@gmail.com" in md
        assert "## Professional Summary" in md
        assert "## Technical Skills" in md
        assert "## Education" in md
        assert "## Technical Projects" in md
        assert "Student management" in md
        assert "Anna University" in md


@pytest.mark.asyncio
async def test_resume_optimizer_custom_jd_text_parsing(
    db_session: AsyncSession,
):
    """Verify skill extraction from custom job description raw text."""
    prof = Profile(
        name="Karthik Sriram",
        email="karthiksriram2005@gmail.com",
        graduation_year=2026,
    )
    db_session.add(prof)
    await db_session.flush()

    s1 = Skill(profile_id=prof.id, name="Python", category="Languages")
    s2 = Skill(profile_id=prof.id, name="SQL", category="Databases")
    db_session.add_all([s1, s2])
    await db_session.commit()

    custom_jd = (
        "We are hiring a Software Developer. Essential skills include Python, PostgreSQL, Docker, and REST APIs. "
        "Experience with System Design and Linux is a plus."
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/resume/optimize",
            json={
                "target_role": "Software Developer",
                "custom_jd_text": custom_jd,
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        ats = data["ats_analysis"]

        # Python should be matched
        matched_lower = [m.lower() for m in ats["matched_skills"]]
        assert "python" in matched_lower

        # Docker should be detected and marked as missing
        missing_lower = [m.lower() for m in ats["missing_skills"]]
        assert "docker" in missing_lower
