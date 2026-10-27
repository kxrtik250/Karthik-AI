"""Automated Test Suite for Phase 7: Placement Intelligence.

Verifies:
1. Deterministic eligibility evaluation (ELIGIBLE, NOT_ELIGIBLE, UNKNOWN / insufficient data).
2. Deterministic skill matching (required & preferred skills, matching & missing, percentages).
3. Opportunity prioritization ranking (composite scoring, sorting, explainability).
4. Profile vs Drive comparison endpoint.
5. Preparation strategy generation with LLM and document context.
6. Chat intent routing for placement queries.
7. Database isolation safety (all tests execute on karthik_ai_test).
"""

from datetime import date, timedelta
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.placement import PlacementDrive
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill
from app.services.placement_intelligence import placement_intelligence_service


@pytest.mark.asyncio
async def test_placement_eligibility_engine_deterministic_rules(db_session: AsyncSession):
    """
    Verifies that eligibility evaluation strictly follows deterministic logic:
    - Passes when all criteria meet or exceed requirements.
    - Fails when any criterion is not met.
    - Yields UNKNOWN when profile data is missing or backlog criteria requires candidate verification.
    """
    # 1. Candidate profile
    candidate = Profile(
        name="Test Candidate",
        cgpa=8.20,
        branch="Computer Science and Engineering",
        graduation_year=2026,
    )
    db_session.add(candidate)

    company = Company(name="TechCorp", industry="Technology")
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(candidate)
    await db_session.refresh(company)

    # Drive 1: Fully Eligible
    drive_eligible = PlacementDrive(
        id=uuid.uuid4(),
        profile_id=candidate.id,
        company_id=company.id,
        role="Software Engineer",
        status="open",
        min_cgpa=7.50,
        eligible_branches=["CSE", "IT"],
        graduation_year=2026,
        backlog_allowed=True,
    )

    # Drive 2: Ineligible due to CGPA
    drive_cgpa_fail = PlacementDrive(
        id=uuid.uuid4(),
        profile_id=candidate.id,
        company_id=company.id,
        role="Research Engineer",
        status="open",
        min_cgpa=8.80,  # candidate has 8.20
        eligible_branches=["CSE"],
        graduation_year=2026,
        backlog_allowed=True,
    )

    # Drive 3: Ineligible due to Branch
    drive_branch_fail = PlacementDrive(
        id=uuid.uuid4(),
        profile_id=candidate.id,
        company_id=company.id,
        role="Mechanical Specialist",
        status="open",
        min_cgpa=7.00,
        eligible_branches=["Mechanical", "Civil"],
        graduation_year=2026,
        backlog_allowed=True,
    )

    # Drive 4: Ineligible due to Batch Year
    drive_year_fail = PlacementDrive(
        id=uuid.uuid4(),
        profile_id=candidate.id,
        company_id=company.id,
        role="Associate Consultant",
        status="open",
        min_cgpa=7.00,
        eligible_branches=["CSE"],
        graduation_year=2025,  # candidate is 2026
        backlog_allowed=True,
    )

    # Drive 5: Unknown due to backlog verification requirement
    drive_backlog_unknown = PlacementDrive(
        id=uuid.uuid4(),
        profile_id=candidate.id,
        company_id=company.id,
        role="Systems Engineer",
        status="open",
        min_cgpa=8.00,
        eligible_branches=["CSE"],
        graduation_year=2026,
        backlog_allowed=False,  # candidate must verify zero backlogs
    )

    # Test evaluations
    res1 = placement_intelligence_service.evaluate_eligibility(candidate, drive_eligible)
    assert res1.status == "ELIGIBLE"
    assert res1.is_eligible is True

    res2 = placement_intelligence_service.evaluate_eligibility(candidate, drive_cgpa_fail)
    assert res2.status == "NOT_ELIGIBLE"
    assert res2.is_eligible is False
    assert any("CGPA" in r for r in res2.reasons)

    res3 = placement_intelligence_service.evaluate_eligibility(candidate, drive_branch_fail)
    assert res3.status == "NOT_ELIGIBLE"
    assert res3.is_eligible is False
    assert any("Branch" in r for r in res3.reasons)

    res4 = placement_intelligence_service.evaluate_eligibility(candidate, drive_year_fail)
    assert res4.status == "NOT_ELIGIBLE"
    assert res4.is_eligible is False
    assert any("Graduation year" in r for r in res4.reasons)

    res5 = placement_intelligence_service.evaluate_eligibility(candidate, drive_backlog_unknown)
    assert res5.status == "UNKNOWN"
    assert res5.is_eligible is None

    # Test missing profile data -> Never guess, always return UNKNOWN
    res_none_profile = placement_intelligence_service.evaluate_eligibility(None, drive_eligible)
    assert res_none_profile.status == "UNKNOWN"
    assert res_none_profile.is_eligible is None

    # Incomplete profile (missing CGPA)
    candidate_no_gpa = Profile(name="No GPA", branch="CSE", graduation_year=2026)
    res_missing_cgpa = placement_intelligence_service.evaluate_eligibility(candidate_no_gpa, drive_eligible)
    assert res_missing_cgpa.status == "UNKNOWN"
    assert res_missing_cgpa.is_eligible is None


@pytest.mark.asyncio
async def test_placement_skill_matching_engine(db_session: AsyncSession):
    """
    Verifies deterministic skill matching and normalization (e.g. FastAPI, PostgreSQL, React).
    """
    candidate = Profile(name="Karthik Skill Test")
    db_session.add(candidate)
    await db_session.commit()
    await db_session.refresh(candidate)

    s1 = Skill(profile_id=candidate.id, name="Python", proficiency="Advanced")
    s2 = Skill(profile_id=candidate.id, name="FastAPI", proficiency="Intermediate")
    s3 = Skill(profile_id=candidate.id, name="PostgreSQL", proficiency="Intermediate")
    db_session.add_all([s1, s2, s3])
    await db_session.commit()

    drive = PlacementDrive(
        id=uuid.uuid4(),
        profile_id=candidate.id,
        company_id=uuid.uuid4(),
        role="Backend Developer",
        status="open",
        required_skills=["python", "fast-api", "docker"],
        preferred_skills=["postgres", "kubernetes"],
    )

    user_skills = [s1, s2, s3]
    match_result = placement_intelligence_service.calculate_skill_match(user_skills, drive)

    # 2 out of 3 required matched (python, fast-api; docker missing)
    assert "python" in match_result.matching_required
    assert "fast-api" in match_result.matching_required
    assert "docker" in match_result.missing_required
    assert round(match_result.required_match_percentage) == 67

    # 1 out of 2 preferred matched (postgres; kubernetes missing)
    assert "postgres" in match_result.matching_preferred
    assert "kubernetes" in match_result.missing_preferred
    assert round(match_result.preferred_match_percentage) == 50

    # Overall match = 0.75 * 66.7 + 0.25 * 50 = 62.5%
    assert 60 <= match_result.overall_match_percentage <= 65


@pytest.mark.asyncio
async def test_placement_opportunity_prioritization(db_session: AsyncSession):
    """
    Verifies transparent opportunity ranking by composite score:
    Eligibility (40) + Skill Match (30) + Urgency (15) + Tier (15).
    """
    candidate = Profile(
        name="Candidate Prioritized",
        cgpa=8.5,
        branch="CSE",
        graduation_year=2026,
    )
    db_session.add(candidate)
    await db_session.commit()
    await db_session.refresh(candidate)

    s1 = Skill(profile_id=candidate.id, name="Python")
    s2 = Skill(profile_id=candidate.id, name="FastAPI")
    db_session.add_all([s1, s2])

    c1 = Company(name="HighTierCorp")
    c2 = Company(name="LowTierCorp")
    db_session.add_all([c1, c2])
    await db_session.commit()

    today = date.today()

    # Drive A: High priority (Eligible, 100% skill match, approaching deadline, Super Dream)
    drive_a = PlacementDrive(
        profile_id=candidate.id,
        company_id=c1.id,
        role="Senior Backend Engineer",
        status="open",
        min_cgpa=8.0,
        eligible_branches=["CSE"],
        graduation_year=2026,
        backlog_allowed=True,
        required_skills=["Python", "FastAPI"],
        tier="Super Dream",
        compensation="24 LPA",
        deadline=today + timedelta(days=5),
    )

    # Drive B: Lower priority (Not eligible, lower match, no deadline)
    drive_b = PlacementDrive(
        profile_id=candidate.id,
        company_id=c2.id,
        role="Frontend Associate",
        status="open",
        min_cgpa=9.5,  # candidate not eligible
        eligible_branches=["CSE"],
        graduation_year=2026,
        backlog_allowed=True,
        required_skills=["Angular", "Vue", "Swift"],
        tier="Standard",
        compensation="5 LPA",
    )
    db_session.add_all([drive_a, drive_b])
    await db_session.commit()

    rankings = await placement_intelligence_service.rank_opportunities(
        db_session, candidate, [s1, s2]
    )

    assert len(rankings) == 2
    top = rankings[0]
    bottom = rankings[1]

    # Drive A should rank top with HIGH priority
    assert top.company_name == "HighTierCorp"
    assert top.priority_level == "HIGH"
    assert top.composite_score >= 80
    assert len(top.score_breakdown) >= 4

    # Drive B should rank lower
    assert bottom.company_name == "LowTierCorp"
    assert bottom.priority_level in ["MEDIUM", "LOW"]
    assert bottom.composite_score < top.composite_score


@pytest.mark.asyncio
async def test_placement_api_endpoints_and_comparison(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies Placement Intelligence REST endpoints:
    - GET /api/placements/open
    - GET /api/placements/upcoming
    - GET /api/placements/eligible
    - GET /api/placements/priorities
    - GET /api/placements/{id}/eligibility
    - GET /api/placements/{id}/match
    - GET /api/placements/{id}/comparison
    """
    # Create Profile
    profile = Profile(
        name="Karthik",
        university="Sathyabama Institute of Science and Technology",
        degree="B.E.",
        branch="Computer Science and Engineering",
        graduation_year=2027,
        cgpa=7.52,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    # Create Skills
    s1 = Skill(profile_id=profile.id, name="Python", proficiency="Advanced")
    s2 = Skill(profile_id=profile.id, name="FastAPI", proficiency="Intermediate")
    db_session.add_all([s1, s2])

    # Create Project
    p1 = Project(
        profile_id=profile.id,
        name="AI Retrieval System",
        technologies=["Python", "FastAPI", "PostgreSQL"],
        status="completed",
    )
    db_session.add(p1)

    # Create Company & Placement Drive
    comp = Company(name="HCLTech", industry="IT Services")
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    drive = PlacementDrive(
        profile_id=profile.id,
        company_id=comp.id,
        role="Associate Software Engineer",
        status="open",
        min_cgpa=7.0,
        eligible_branches=["Computer Science and Engineering"],
        graduation_year=2027,
        backlog_allowed=True,
        required_skills=["Python", "FastAPI"],
        compensation="8 LPA",
        deadline=date.today() + timedelta(days=10),
    )
    db_session.add(drive)
    await db_session.commit()
    await db_session.refresh(drive)

    # 1. GET /api/placements/open
    r_open = await client.get("/placements/open")
    assert r_open.status_code == 200
    assert len(r_open.json()) >= 1
    assert r_open.json()[0]["role"] == "Associate Software Engineer"

    # 2. GET /api/placements/upcoming
    r_up = await client.get("/placements/upcoming?days=30")
    assert r_up.status_code == 200
    assert len(r_up.json()) >= 1

    # 3. GET /api/placements/eligible
    r_elig = await client.get("/placements/eligible")
    assert r_elig.status_code == 200
    assert len(r_elig.json()) >= 1
    assert r_elig.json()[0]["status"] == "ELIGIBLE"

    # 4. GET /api/placements/priorities
    r_prio = await client.get("/placements/priorities")
    assert r_prio.status_code == 200
    assert len(r_prio.json()) >= 1
    assert r_prio.json()[0]["eligibility_status"] == "ELIGIBLE"

    # 5. GET /api/placements/{id}/eligibility
    r_d_elig = await client.get(f"/placements/{drive.id}/eligibility")
    assert r_d_elig.status_code == 200
    assert r_d_elig.json()["status"] == "ELIGIBLE"

    # 6. GET /api/placements/{id}/match
    r_d_match = await client.get(f"/placements/{drive.id}/match")
    assert r_d_match.status_code == 200
    assert r_d_match.json()["required_match_percentage"] == 100.0

    # 7. GET /api/placements/{id}/comparison
    r_comp = await client.get(f"/placements/{drive.id}/comparison")
    assert r_comp.status_code == 200
    comp_json = r_comp.json()
    assert comp_json["drive"]["id"] == str(drive.id)
    assert comp_json["eligibility"]["status"] == "ELIGIBLE"
    assert len(comp_json["matching_projects"]) >= 1
    assert comp_json["matching_projects"][0]["name"] == "AI Retrieval System"


@pytest.mark.asyncio
async def test_placement_preparation_plan_endpoint(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies POST /api/placements/{id}/prepare returns structured preparation strategy.
    """
    profile = Profile(name="Prep Candidate", cgpa=8.0, branch="CSE", graduation_year=2026)
    comp = Company(name="Amazon", industry="Cloud/Tech")
    db_session.add_all([profile, comp])
    await db_session.commit()
    await db_session.refresh(profile)
    await db_session.refresh(comp)

    drive = PlacementDrive(
        profile_id=profile.id,
        company_id=comp.id,
        role="SDE 1",
        status="open",
        min_cgpa=7.5,
        eligible_branches=["CSE"],
        graduation_year=2026,
        required_skills=["Data Structures", "Algorithms", "Java"],
        selection_process=["Online Assessment", "Technical Interview 1", "Bar Raiser Interview"],
    )
    db_session.add(drive)
    await db_session.commit()
    await db_session.refresh(drive)

    prep_res = await client.post(f"/placements/{drive.id}/prepare")
    assert prep_res.status_code == 200
    prep_data = prep_res.json()
    assert prep_data["company_name"] == "Amazon"
    assert prep_data["role"] == "SDE 1"
    assert len(prep_data["selection_process"]) == 3
    assert len(prep_data["preparation_advice"]) > 50


@pytest.mark.asyncio
async def test_placement_chat_eligibility_query(client: AsyncClient, db_session: AsyncSession):
    """
    Verifies that asking placement eligibility questions via /rag/query routes to placement context
    and answers factually without hallucinating.
    """
    profile = Profile(
        name="Karthik",
        university="Sathyabama Institute of Science and Technology",
        cgpa=7.52,
        branch="Computer Science and Engineering",
        graduation_year=2027,
    )
    comp = Company(name="HCLTech", industry="Technology")
    db_session.add_all([profile, comp])
    await db_session.commit()
    await db_session.refresh(profile)
    await db_session.refresh(comp)

    drive = PlacementDrive(
        profile_id=profile.id,
        company_id=comp.id,
        role="Software Engineer",
        status="open",
        min_cgpa=7.0,
        eligible_branches=["Computer Science and Engineering"],
        graduation_year=2027,
        backlog_allowed=True,
    )
    db_session.add(drive)
    await db_session.commit()

    res = await client.post(
        "/rag/query",
        json={"question": "Which placement drives am I eligible for?"},
    )
    assert res.status_code == 200
    answer = res.json()["answer"]
    assert "HCLTech" in answer or "eligible" in answer.lower()
    assert "placements" in res.json().get("structured_sources", [])
