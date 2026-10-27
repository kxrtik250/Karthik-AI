"""Phase 6 Personal Memory & Hybrid Context Intelligence end-to-end tests on isolated test DB."""

import asyncio
import io
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from app.database import async_session


@pytest.mark.asyncio
async def test_phase6_personal_memory_and_hybrid_intelligence(
    client: AsyncClient,
    fake_phase6_profile: dict,
    fake_phase6_skills: list,
    fake_phase6_project: dict,
    fake_phase6_certification: dict,
    fake_phase6_company_and_placement: dict,
):
    """
    Complete end-to-end verification of Phase 6 on isolated test DB:
    1. Database isolation assert (connected strictly to karthik_ai_test)
    2. Seed authoritative personal data into PostgreSQL
    3. Ingest semantic document into pgvector
    4. Verify diagnostic context-summary
    5. Verify 9 core personal context and hybrid questions
    6. Verify multi-turn conversational chat thread
    7. Verify hallucination guard for unknown fact
    """
    # -------------------------------------------------------------
    # STEP 0: Verify Test Database Isolation Barrier
    # -------------------------------------------------------------
    async with async_session() as session:
        res = await session.execute(text("SELECT current_database();"))
        assert res.scalar() == "karthik_ai_test"

    # -------------------------------------------------------------
    # STEP 1: Seed Authoritative Structured Personal Data
    # -------------------------------------------------------------
    # Profile
    p_res = await client.post("/profile", json=fake_phase6_profile)
    assert p_res.status_code == 201

    # Skills
    for s in fake_phase6_skills:
        s_res = await client.post("/skills", json=s)
        assert s_res.status_code == 201

    # Project
    pr_res = await client.post("/projects", json=fake_phase6_project)
    assert pr_res.status_code == 201

    # Certification
    c_res = await client.post("/certifications", json=fake_phase6_certification)
    assert c_res.status_code == 201

    # Company & Placement Drive
    comp_res = await client.post("/companies", json=fake_phase6_company_and_placement["company"])
    assert comp_res.status_code == 201
    cid = comp_res.json()["id"]
    pl_data = {**fake_phase6_company_and_placement["placement"], "company_id": cid}
    pl_res = await client.post("/placements", json=pl_data)
    assert pl_res.status_code == 201

    # -------------------------------------------------------------
    # STEP 2: Ingest Semantic Document into pgvector
    # -------------------------------------------------------------
    doc_text = b"The Carbon Footprint Tracker uses Python, FastAPI, and PostgreSQL for telemetry calculation and carbon emission metrics."
    files = {"file": ("carbon_footprint_architecture.txt", io.BytesIO(doc_text), "text/plain")}
    up_res = await client.post("/documents/upload", files=files)
    assert up_res.status_code == 202
    doc_id = up_res.json()["id"]

    for _ in range(20):
        stat_res = await client.get(f"/documents/{doc_id}")
        if stat_res.json()["status"] == "completed":
            break
        await asyncio.sleep(0.5)

    assert stat_res.json()["status"] == "completed"

    # -------------------------------------------------------------
    # STEP 3: Verify Context Summary Diagnostic Endpoint
    # -------------------------------------------------------------
    sum_res = await client.get("/rag/context-summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["profile_present"] is True
    assert summary["profile_name"] == "Karthik"
    assert summary["skills_count"] == 3
    assert summary["projects_count"] == 1
    assert summary["certifications_count"] == 1
    assert summary["companies_count"] == 1
    assert summary["placements_count"] == 1

    # -------------------------------------------------------------
    # STEP 4: Verify 9 Core Personal Context & Hybrid Questions
    # -------------------------------------------------------------
    # Q1: CGPA
    q1 = await client.post("/rag/query", json={"question": "What is my CGPA?"})
    assert q1.status_code == 200
    assert "8.5" in q1.json()["answer"]
    assert "profile" in q1.json().get("structured_sources", [])

    # Q2: University
    q2 = await client.post("/rag/query", json={"question": "What university do I study at?"})
    assert q2.status_code == 200
    assert "Amrita Vishwa Vidyapeetham" in q2.json()["answer"]
    assert "profile" in q2.json().get("structured_sources", [])

    # Q3: Role in ACM
    q3 = await client.post("/rag/query", json={"question": "What is my role in ACM?"})
    assert q3.status_code == 200
    assert "Media Co-Lead" in q3.json()["answer"] or "Lead" in q3.json()["answer"]
    assert "profile" in q3.json().get("structured_sources", [])

    # Q4: Technical Skills
    q4 = await client.post("/rag/query", json={"question": "What are my technical skills?"})
    assert q4.status_code == 200
    assert "Python" in q4.json()["answer"]
    assert "skills" in q4.json().get("structured_sources", [])

    # Q5: Completed Projects
    q5 = await client.post("/rag/query", json={"question": "What projects have I completed?"})
    assert q5.status_code == 200
    assert "Carbon Footprint Tracker" in q5.json()["answer"]
    assert "projects" in q5.json().get("structured_sources", [])

    # Q6: Certifications
    q6 = await client.post("/rag/query", json={"question": "What certifications do I have?"})
    assert q6.status_code == 200
    assert "AWS Certified Cloud Practitioner" in q6.json()["answer"]
    assert "certifications" in q6.json().get("structured_sources", [])

    # Q7: Placement Drives
    q7 = await client.post("/rag/query", json={"question": "What placement drives am I tracking?"})
    assert q7.status_code == 200
    assert "Google" in q7.json()["answer"]
    assert "placements" in q7.json().get("structured_sources", [])

    # Q8: Hybrid Structured + Semantic Query
    q8 = await client.post(
        "/rag/query",
        json={"question": "What technologies did I use in my carbon footprint project?", "similarity_threshold": 0.35},
    )
    assert q8.status_code == 200
    ans8 = q8.json()["answer"]
    assert "Python" in ans8 or "FastAPI" in ans8
    assert len(q8.json().get("sources", [])) >= 1
    assert len(q8.json().get("structured_sources", [])) >= 1

    # Q9: Placement Improvement Advice
    q9 = await client.post(
        "/rag/query",
        json={"question": "What should I improve for placements based on my resume and projects?"},
    )
    assert q9.status_code == 200
    ans9 = q9.json()["answer"]
    assert ("FACTS" in ans9 and "RECOMMENDATIONS" in ans9) or "improve" in ans9.lower() or "skills" in ans9.lower()

    # -------------------------------------------------------------
    # STEP 5: Verify Multi-Turn Conversational Chat Thread
    # -------------------------------------------------------------
    t1 = await client.post("/rag/chat", json={"message": "What is my current CGPA and degree?"})
    assert t1.status_code == 200
    conv_id = t1.json()["conversation_id"]
    assert "8.5" in t1.json()["message"]["content"]

    t2 = await client.post(
        "/rag/chat",
        json={"conversation_id": conv_id, "message": "And what university is that from?"},
    )
    assert t2.status_code == 200
    assert "Amrita Vishwa Vidyapeetham" in t2.json()["message"]["content"]

    # -------------------------------------------------------------
    # STEP 6: Verify Hallucination Guard for Unknown Fact
    # -------------------------------------------------------------
    unk = await client.post(
        "/rag/query",
        json={"question": "What is the topic of my PhD dissertation in Quantum Cryptography?"},
    )
    assert unk.status_code == 200
    unk_ans = unk.json()["answer"].lower()
    assert "not enough information" in unk_ans or "don't have any information" in unk_ans or "no information" in unk_ans
