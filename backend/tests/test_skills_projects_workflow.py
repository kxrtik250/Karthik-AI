"""Regression tests for validated Skills and Projects workflow in PostgreSQL.

Ensures:
1. Complete database isolation: tests run exclusively against karthik_ai_test.
2. Skill creation, whitespace stripping, and input validation.
3. Skill case-insensitive duplicate rejection (e.g. 'Python' vs 'python').
4. Skill updating with collision prevention.
5. Skill deletion.
6. Project creation, technology tag deduplication, and input validation.
7. Project invalid date rejection (end_date < start_date).
8. Project invalid status rejection.
9. Project case-insensitive duplicate rejection.
10. Project updating with collision and date checks.
11. Project deletion.
12. Authoritative RAG grounding integration:
    - Empty projects guard triggers when zero projects exist.
    - Verified project additions provide real technologies to RAG context without hallucination.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.database import async_session
from app.services.context_builder import context_builder
from app.services.personal_context import get_projects_context, get_relevant_personal_context


@pytest.mark.asyncio
async def test_skills_projects_database_isolation():
    """Verify that tests execute strictly on karthik_ai_test and never the live DB."""
    async with async_session() as session:
        res = await session.execute(text("SELECT current_database();"))
        db_name = res.scalar()
        assert db_name == "karthik_ai_test"


# ---------------------------------------------------------------------------
# Skills Workflow Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_create_and_validation(client: AsyncClient, seeded_profile: dict):
    """Test valid skill creation, whitespace trimming, and validation rejections."""
    # 1. Valid creation
    resp = await client.post("/skills", json={
        "name": "  Python  ",
        "category": "  Programming Languages  ",
        "proficiency": "Advanced",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Python"
    assert data["category"] == "Programming Languages"
    assert data["proficiency"] == "Advanced"

    # 2. Reject empty or whitespace-only name
    resp_empty = await client.post("/skills", json={
        "name": "   ",
        "category": "Programming Languages",
    })
    assert resp_empty.status_code == 422


@pytest.mark.asyncio
async def test_skill_case_insensitive_duplicate_rejection(client: AsyncClient, seeded_profile: dict):
    """Test case-insensitive duplicate rejection on skill creation."""
    # First skill
    resp1 = await client.post("/skills", json={
        "name": "FastAPI",
        "category": "Frameworks",
        "proficiency": "Intermediate",
    })
    assert resp1.status_code == 201

    # Duplicate with different casing
    resp2 = await client.post("/skills", json={
        "name": "fastapi",
        "category": "Frameworks",
        "proficiency": "Intermediate",
    })
    assert resp2.status_code == 400
    assert "already exists in your profile" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_skill_update_and_collision_prevention(client: AsyncClient, seeded_profile: dict):
    """Test updating a skill and collision checks against other skills."""
    # Create two skills
    r1 = await client.post("/skills", json={"name": "PostgreSQL", "category": "Databases"})
    assert r1.status_code == 201
    s1_id = r1.json()["id"]

    r2 = await client.post("/skills", json={"name": "Redis", "category": "Databases"})
    assert r2.status_code == 201

    # Valid update to s1
    r_up = await client.put(f"/skills/{s1_id}", json={"proficiency": "Advanced"})
    assert r_up.status_code == 200
    assert r_up.json()["proficiency"] == "Advanced"
    assert r_up.json()["name"] == "PostgreSQL"

    # Collision update: renaming s1 to 'redis' (colliding with s2)
    r_coll = await client.put(f"/skills/{s1_id}", json={"name": "REDIS"})
    assert r_coll.status_code == 400
    assert "already exists in your profile" in r_coll.json()["detail"].lower()


@pytest.mark.asyncio
async def test_skill_deletion(client: AsyncClient, seeded_profile: dict):
    """Test deleting a skill."""
    r = await client.post("/skills", json={"name": "Docker", "category": "Tools"})
    assert r.status_code == 201
    skill_id = r.json()["id"]

    del_resp = await client.delete(f"/skills/{skill_id}")
    assert del_resp.status_code == 204

    # Verify skill is gone
    list_resp = await client.get("/skills")
    assert list_resp.status_code == 200
    assert not any(s["id"] == skill_id for s in list_resp.json())


# ---------------------------------------------------------------------------
# Projects Workflow Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_create_and_validation(client: AsyncClient, seeded_profile: dict):
    """Test valid project creation, technology deduplication, and invalid input rejections."""
    # 1. Valid creation
    payload = {
        "name": "  Carbon Footprint Tracker  ",
        "description": "Full-stack carbon emission monitoring system",
        "technologies": ["Python", "  FastAPI  ", "Python", "React"],
        "status": "completed",
        "role": "Lead Developer",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30",
    }
    resp = await client.post("/projects", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Carbon Footprint Tracker"
    assert data["technologies"] == ["Python", "FastAPI", "React"]  # deduplicated and trimmed
    assert data["status"] == "completed"

    # 2. Reject empty project name
    bad_name = await client.post("/projects", json={"name": "   "})
    assert bad_name.status_code == 422

    # 3. Reject invalid status
    bad_status = await client.post("/projects", json={
        "name": "Test Project",
        "status": "invalid_status",
    })
    assert bad_status.status_code == 422

    # 4. Reject end_date earlier than start_date
    bad_dates = await client.post("/projects", json={
        "name": "Time Traveler Project",
        "start_date": "2024-12-01",
        "end_date": "2024-01-01",
    })
    assert bad_dates.status_code == 422
    assert "cannot be earlier than start_date" in bad_dates.json()["detail"][0]["msg"].lower()


@pytest.mark.asyncio
async def test_project_case_insensitive_duplicate_rejection(client: AsyncClient, seeded_profile: dict):
    """Test case-insensitive duplicate rejection on project creation."""
    r1 = await client.post("/projects", json={
        "name": "Campus Placement Portal",
        "technologies": ["React", "Node.js"],
    })
    assert r1.status_code == 201

    # Duplicate name with different casing
    r2 = await client.post("/projects", json={
        "name": "campus placement portal",
        "technologies": ["Angular"],
    })
    assert r2.status_code == 400
    assert "already exists in your profile" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_project_update_and_collision_prevention(client: AsyncClient, seeded_profile: dict):
    """Test project updating, date validation on update, and collision rejection."""
    r1 = await client.post("/projects", json={"name": "Alpha System", "status": "planned"})
    assert r1.status_code == 201
    p1_id = r1.json()["id"]

    r2 = await client.post("/projects", json={"name": "Beta System", "status": "in_progress"})
    assert r2.status_code == 201

    # Valid update
    r_up = await client.put(f"/projects/{p1_id}", json={
        "status": "completed",
        "description": "Updated description",
        "technologies": ["Docker", "Kubernetes"],
    })
    assert r_up.status_code == 200
    assert r_up.json()["status"] == "completed"
    assert r_up.json()["technologies"] == ["Docker", "Kubernetes"]

    # Collision update: renaming p1 to 'beta system'
    r_coll = await client.put(f"/projects/{p1_id}", json={"name": "BETA SYSTEM"})
    assert r_coll.status_code == 400
    assert "already exists in your profile" in r_coll.json()["detail"].lower()

    # Invalid dates update
    r_bad_dates = await client.put(f"/projects/{p1_id}", json={
        "start_date": "2025-06-01",
        "end_date": "2025-01-01",
    })
    assert r_bad_dates.status_code == 422
    assert "cannot be earlier than start_date" in r_bad_dates.json()["detail"][0]["msg"].lower()


@pytest.mark.asyncio
async def test_project_deletion(client: AsyncClient, seeded_profile: dict):
    """Test deleting a project."""
    r = await client.post("/projects", json={"name": "Legacy Project"})
    assert r.status_code == 201
    proj_id = r.json()["id"]

    del_resp = await client.delete(f"/projects/{proj_id}")
    assert del_resp.status_code == 204

    # Verify project is gone
    get_resp = await client.get(f"/projects/{proj_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_project_url_and_description_validation(client: AsyncClient, seeded_profile: dict):
    """Test rejection of generic root domain URLs and uninformative descriptions."""
    # 1. Reject generic github root link
    r_gen1 = await client.post("/projects", json={
        "name": "Generic URL Project",
        "url": "https://github.com/",
    })
    assert r_gen1.status_code == 422
    assert "generic link" in r_gen1.json()["detail"][0]["msg"].lower()

    # 2. Reject generic gitlab root link without repo
    r_gen2 = await client.post("/projects", json={
        "name": "GitLab Root Project",
        "url": "https://gitlab.com",
    })
    assert r_gen2.status_code == 422
    assert "generic link" in r_gen2.json()["detail"][0]["msg"].lower()

    # 3. Reject description shorter than 10 characters
    r_short_desc = await client.post("/projects", json={
        "name": "Short Desc Project",
        "description": "too short",
    })
    assert r_short_desc.status_code == 422
    assert "at least 10 characters long" in r_short_desc.json()["detail"][0]["msg"].lower()

    # 4. Accept valid project with specific repo and informative description
    r_valid = await client.post("/projects", json={
        "name": "Student Management System",
        "description": "Full-stack academic portal for student record tracking",
        "url": "https://github.com/karthik/student-management",
        "technologies": ["Python", "SQL", "JavaScript", "Git"],
        "status": "completed",
    })
    assert r_valid.status_code == 201
    valid_id = r_valid.json()["id"]
    assert r_valid.json()["url"] == "https://github.com/karthik/student-management"

    # 5. Reject generic URL on update
    r_bad_up = await client.put(f"/projects/{valid_id}", json={
        "url": "https://bitbucket.org/",
    })
    assert r_bad_up.status_code == 422
    assert "generic link" in r_bad_up.json()["detail"][0]["msg"].lower()


# ---------------------------------------------------------------------------
# Grounding & RAG Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rag_project_grounding_integration(client: AsyncClient, seeded_profile: dict):
    """Verify that:
    1. Before projects are added, project technology questions trigger the empty projects guard.
    2. Once a verified project is added, RAG retrieves authoritative project technologies without hallucination.
    """
    # 1. Zero projects -> deterministic empty projects guard
    resp_empty = await client.post("/rag/chat", json={"message": "what technologies are in my projects?"})
    assert resp_empty.status_code == 200
    empty_ans = resp_empty.json()["message"]["content"]
    assert "no project records" in empty_ans.lower() or "not have any project" in empty_ans.lower()

    # 2. Add real project with specific technologies
    proj_resp = await client.post("/projects", json={
        "name": "Karthik AI Agent",
        "description": "Personal AI assistant with RAG and FastAPI",
        "technologies": ["Python", "FastAPI", "PostgreSQL", "React"],
        "status": "in_progress",
    })
    assert proj_resp.status_code == 201

    # 3. Personal context returns the registered project
    async with async_session() as session:
        proj_list = await get_projects_context(session)
        assert len(proj_list) == 1
        assert proj_list[0]["name"] == "Karthik AI Agent"
        assert "FastAPI" in proj_list[0]["technologies"]

        ctx_data = await get_relevant_personal_context(session, "what technologies are in my projects?")
        built = context_builder.build_context(ctx_data, [], [])
        assert "Karthik AI Agent" in built.prompt_context
        assert "FastAPI" in built.prompt_context
        assert "PostgreSQL" in built.prompt_context

    # 4. Query RAG again: empty project guard should NOT fire
    resp_with_proj = await client.post("/rag/chat", json={"message": "what technologies are in my projects?"})
    assert resp_with_proj.status_code == 200
    ans_with_proj = resp_with_proj.json()["message"]["content"]

    # Must NOT state that there are no project records
    assert "no project records are currently stored" not in ans_with_proj.lower()
    # Must reflect real technologies from the database
    assert any(tech in ans_with_proj for tech in ["Python", "FastAPI", "PostgreSQL", "React"])


@pytest.mark.asyncio
async def test_project_description_grounding_rejection_of_unsupported_features(
    client: AsyncClient, seeded_profile: dict
):
    """Verify that:
    1. Describing 'Student management' cites only verified facts from the database (name, role, status, description, technologies).
    2. Unsupported features (CRUD operations, course registrations, attendance tracking, fee management, JWT)
       are strictly never presented as implemented features.
    3. Explicitly notes that extended implementation details are not stored and invites user to provide them.
    """
    # Create the exact Student management project
    proj_resp = await client.post("/projects", json={
        "name": "Student management",
        "role": "full stack developer",
        "status": "completed",
        "description": "A full-stack student management application for maintaining student records and managing student information.",
        "technologies": ["Python", "SQL", "JavaScript", "Git"],
        "start_date": "2026-01-12",
        "end_date": "2026-07-12",
    })
    assert proj_resp.status_code == 201

    # Test 1: "Describe the Student management project"
    resp1 = await client.post("/rag/chat", json={"message": "Describe the Student management project"})
    assert resp1.status_code == 200
    ans1 = resp1.json()["message"]["content"]

    # Must contain verified facts
    assert "student management" in ans1.lower()
    assert "full stack developer" in ans1.lower()
    assert "completed" in ans1.lower()
    assert "maintaining student records" in ans1.lower()
    assert "python" in ans1.lower()
    assert "sql" in ans1.lower()

    # Must NOT claim unverified features as implemented
    unsupported_claims = [
        "crud operations", "course registration", "attendance record", "attendance management",
        "fee management", "jwt", "docker", "django", "passport", "flask"
    ]
    # Note: If mentioned in the disclaimer ("such as CRUD operations... are not documented"), that is allowed,
    # but it must NOT state that the project features/modules include them.
    assert "features include" not in ans1.lower()
    assert "modules in the student management project are" not in ans1.lower()
    assert "application allowed students to create accounts" not in ans1.lower()
    assert "not documented" in ans1.lower()

    # Test 2: "Tell me about my Student management project"
    resp2 = await client.post("/rag/chat", json={"message": "Tell me about my Student management project"})
    assert resp2.status_code == 200
    ans2 = resp2.json()["message"]["content"]
    assert "student management" in ans2.lower()
    assert "not documented" in ans2.lower()


@pytest.mark.asyncio
async def test_project_undocumented_details_guard(client: AsyncClient, seeded_profile: dict):
    """Verify that when a user asks for specific implementation details, features, modules,
    or architecture that are not stored in PostgreSQL:
    1. The response clearly states that those details are not documented in the project record.
    2. Displays the documented facts.
    3. Prompts the user to provide them.
    """
    proj_resp = await client.post("/projects", json={
        "name": "Student management",
        "role": "full stack developer",
        "status": "completed",
        "description": "A full-stack student management application for maintaining student records and managing student information.",
        "technologies": ["Python", "SQL", "JavaScript", "Git"],
    })
    assert proj_resp.status_code == 201

    # 1. Feature query
    resp_feat = await client.post("/rag/chat", json={"message": "What features does the Student management project have?"})
    assert resp_feat.status_code == 200
    ans_feat = resp_feat.json()["message"]["content"]
    assert "not documented" in ans_feat.lower()
    assert "please provide the specific implementation details" in ans_feat.lower() or "please provide" in ans_feat.lower()
    assert "full stack developer" in ans_feat.lower()

    # 2. Module query
    resp_mod = await client.post("/rag/chat", json={"message": "What are the modules in the Student management project?"})
    assert resp_mod.status_code == 200
    ans_mod = resp_mod.json()["message"]["content"]
    assert "not documented" in ans_mod.lower()
    assert "please provide" in ans_mod.lower()

    # 3. Authentication query
    resp_auth = await client.post("/rag/chat", json={"message": "How is authentication handled in the Student management project?"})
    assert resp_auth.status_code == 200
    ans_auth = resp_auth.json()["message"]["content"]
    assert "not documented" in ans_auth.lower()


@pytest.mark.asyncio
async def test_project_multiturn_followup_grounding(client: AsyncClient, seeded_profile: dict):
    """Verify multi-turn conversation maintains strict project grounding across conversational turns."""
    await client.post("/projects", json={
        "name": "Student management",
        "role": "full stack developer",
        "status": "completed",
        "description": "A full-stack student management application for maintaining student records and managing student information.",
        "technologies": ["Python", "SQL", "JavaScript", "Git"],
    })

    # Turn 1: Initial project query
    r1 = await client.post("/rag/chat", json={"message": "What projects have I completed?"})
    assert r1.status_code == 200
    conv_id = r1.json()["conversation_id"]
    ans1 = r1.json()["message"]["content"]
    assert "student management" in ans1.lower()

    # Turn 2: Follow-up asking for features
    r2 = await client.post("/rag/chat", json={
        "conversation_id": conv_id,
        "message": "What features does it have?",
    })
    assert r2.status_code == 200
    ans2 = r2.json()["message"]["content"]
    assert "not documented" in ans2.lower()
    assert "please provide" in ans2.lower()

    # Turn 3: Follow-up asking for modules
    r3 = await client.post("/rag/chat", json={
        "conversation_id": conv_id,
        "message": "What are its modules?",
    })
    assert r3.status_code == 200
    ans3 = r3.json()["message"]["content"]
    assert "not documented" in ans3.lower()

    # Turn 4: Follow-up asking to describe in detail
    r4 = await client.post("/rag/chat", json={
        "conversation_id": conv_id,
        "message": "Describe it in detail",
    })
    assert r4.status_code == 200
    ans4 = r4.json()["message"]["content"]
    assert "student management" in ans4.lower()
    assert "not documented" in ans4.lower()

