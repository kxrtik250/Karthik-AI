"""Tests for Interactive Mock Interview and Technical Assessment Simulator."""

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
from app.schemas.interview import (
    AnswerEvaluation,
    EvaluateAnswerRequest,
    InterviewQuestion,
)


@pytest.mark.asyncio
async def test_interview_database_isolation(db_session: AsyncSession):
    """Confirm tests strictly execute against karthik_ai_test and never karthik_ai_db."""
    result = await db_session.execute(text("SELECT current_database();"))
    current_db = result.scalar()
    assert current_db == "karthik_ai_test", f"Safety violation: running on {current_db} instead of test db!"


@pytest.mark.asyncio
async def test_start_interview_project_deep_dive_grounded(
    db_session: AsyncSession,
):
    """Verify that project deep-dive questions are grounded in candidate's real project records."""
    # Seed profile
    prof = Profile(
        name="Karthik Sriram",
        email="karthiksriram2005@gmail.com",
        university="Anna University",
        degree="B.E",
        branch="Computer Science and Engineering",
        graduation_year=2026,
        cgpa=8.5,
        career_goals="Software Engineer / AI Developer",
    )
    db_session.add(prof)
    await db_session.flush()

    # Seed project: Student management
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
            "/api/interview/start",
            json={
                "round_type": "project_deep_dive",
                "difficulty": "intermediate",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["round_type"] == "project_deep_dive"
        assert data["total_questions"] >= 3
        questions = data["questions"]

        # Verify questions strictly reference Student management and candidate's tech stack
        q_texts = " ".join(q["question_text"] for q in questions)
        assert "Student management" in q_texts
        assert "full stack developer" in q_texts
        assert "python" in q_texts.lower()
        assert "sql" in q_texts.lower()


@pytest.mark.asyncio
async def test_start_interview_tailored_to_placement_drive(
    db_session: AsyncSession,
):
    """Verify mock interview adapts to target placement drive company and role requirements."""
    # Seed profile
    prof = Profile(
        name="Karthik Sriram",
        email="karthiksriram2005@gmail.com",
        graduation_year=2026,
    )
    db_session.add(prof)
    await db_session.flush()

    # Seed company & drive
    company = Company(name="Zoho Corporation")
    db_session.add(company)
    await db_session.flush()

    drive = PlacementDrive(
        profile_id=prof.id,
        company_id=company.id,
        role="Backend Systems Engineer",
        required_skills=["Python", "PostgreSQL", "REST APIs"],
        tier="Tier-1",
    )
    db_session.add(drive)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/interview/start",
            json={
                "drive_id": str(drive.id),
                "round_type": "technical",
                "difficulty": "intermediate",
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["company_name"] == "Zoho Corporation"
        assert data["role"] == "Backend Systems Engineer"
        assert data["round_type"] == "technical"
        assert len(data["questions"]) >= 3


@pytest.mark.asyncio
async def test_evaluate_answer_rubric_scoring_and_strengths(
    db_session: AsyncSession,
):
    """Verify answer evaluation produces accurate rubric score, strengths, and model answer."""
    question = {
        "question_id": "q_1",
        "question_index": 1,
        "round_type": "technical",
        "topic": "SQL & Relational Query Optimization",
        "question_text": "How do you prevent N+1 query problems and optimize index usage in PostgreSQL?",
        "context_hint": "Discuss eager loading and composite indexing.",
        "expected_key_points": [
            "eager loading to prevent N+1 overhead",
            "B-tree index fundamentals and composite index",
            "execution plan inspection using EXPLAIN ANALYZE",
        ],
    }

    answer_text = (
        "In relational databases like PostgreSQL, the N+1 problem occurs when fetching child entities in a loop. "
        "I prevent this by utilizing eager loading strategies such as JOINs or selectinload in SQLAlchemy. "
        "For index optimization, I analyze execution plans with EXPLAIN ANALYZE to identify sequential scans and "
        "create composite B-tree indexes ordered by column cardinality, ensuring high selectivity."
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/interview/evaluate-answer",
            json={
                "session_id": str(uuid.uuid4()),
                "question_id": "q_1",
                "answer_text": answer_text,
                "question": question,
                "total_questions": 3,
            },
        )

        assert resp.status_code == 200, resp.text
        eval_data = resp.json()
        assert eval_data["score"] >= 8
        assert len(eval_data["feedback_strengths"]) > 0
        assert eval_data["model_answer"] is not None
        assert not eval_data["is_final_question"]


@pytest.mark.asyncio
async def test_evaluate_answer_grounding_warning_for_unsupported_claims(
    db_session: AsyncSession,
):
    """Verify that hallucinating unsupported features in project answers triggers a grounding warning."""
    question = {
        "question_id": "q_1",
        "question_index": 1,
        "round_type": "project_deep_dive",
        "topic": "Architecture & Tech Stack",
        "question_text": "Walk me through the architecture of your Student management project.",
        "context_hint": "Focus on your documented role and technologies.",
        "expected_key_points": [
            "Separation of concerns",
            "Rationale for chosen technologies",
            "Data flow between client and server",
        ],
    }

    # Candidate claims automated attendance tracking which was not in the project record
    answer_text = (
        "In my Student management project, I designed an automated attendance tracking system with real-time biometric "
        "logging using a distributed microservices architecture and Python."
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/interview/evaluate-answer",
            json={
                "session_id": str(uuid.uuid4()),
                "question_id": "q_1",
                "answer_text": answer_text,
                "question": question,
                "total_questions": 3,
            },
        )

        assert resp.status_code == 200, resp.text
        eval_data = resp.json()
        assert eval_data["grounding_warning"] is not None
        assert "attendance tracking" in eval_data["grounding_warning"]
        assert "not documented" in eval_data["grounding_warning"]


@pytest.mark.asyncio
async def test_complete_interview_readiness_summary(
    db_session: AsyncSession,
):
    """Verify end-to-end completion computes aggregate readiness rating and suggested action items."""
    evaluations = [
        {
            "session_id": "session-123",
            "question_id": "q_1",
            "question_index": 1,
            "score": 9,
            "feedback_strengths": ["Clear explanation of relational indexing."],
            "feedback_improvements": ["Mention connection pooling."],
            "model_answer": "Model answer 1",
            "is_final_question": False,
        },
        {
            "session_id": "session-123",
            "question_id": "q_2",
            "question_index": 2,
            "score": 8,
            "feedback_strengths": ["Solid STAR structure."],
            "feedback_improvements": ["Add quantitative impact."],
            "model_answer": "Model answer 2",
            "is_final_question": True,
        },
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/interview/complete",
            json={
                "session_id": "session-123",
                "company_name": "Zoho",
                "role": "Backend Engineer",
                "round_type": "technical",
                "evaluations": evaluations,
            },
        )

        assert resp.status_code == 200, resp.text
        summary = resp.json()
        assert summary["overall_score"] == 8.5
        assert summary["readiness_level"] == "Ready for Interview"
        assert len(summary["strengths_summary"]) > 0
        assert len(summary["suggested_action_items"]) > 0
