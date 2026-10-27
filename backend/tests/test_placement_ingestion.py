"""Regression tests for Automated Placement Drive Ingestion.

Ensures:
1. Complete database isolation: tests run exclusively against karthik_ai_test.
2. Deterministic text extraction from placement circulars & JDs (company, role, CGPA, branches, CTC, skills, rounds, deadline).
3. Document extraction directly from uploaded knowledge base documents.
4. Auto-creation of missing company records and placement drives via /api/placements/extract-and-create.
5. Immediate integration into Placement Intelligence (eligibility checks, priority ranking).
"""

from datetime import date
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.database import async_session
from app.models.company import Company
from app.models.document import Document, DocumentChunk
from app.models.placement import PlacementDrive
from app.schemas.placement import ExtractedDriveData
from app.services.placement_parser import placement_parser_service


SAMPLE_CIRCULAR_TEXT = """
CAMPUS RECRUITMENT NOTICE: HCLTech Campus Drive 2027
Job Role: Graduate Engineer Trainee (GET)
Employment Type: Full-Time
Work Location: Noida / Chennai / Bangalore

Academic Eligibility Criteria:
- Minimum CGPA: 7.0 and above throughout academics
- Eligible Branches: B.E. / B.Tech (Computer Science and Engineering, Information Technology, ECE)
- Eligible Batch: 2027 graduating batch
- Active Backlogs: No active backlogs allowed

Compensation & Package:
- Annual CTC: 5.5 LPA
- Tier: Dream

Important Dates:
- Last Date to Register: 2026-11-30

Selection Process:
1. Online Assessment (Aptitude + Technical MCQs)
2. Technical Interview 1 (DSA, OOP, SQL)
3. HR Interview

Skill Requirements:
- Required Skills: Python, Java, SQL, Data Structures
- Preferred Skills: Cloud Computing, Docker, Git
"""


@pytest.mark.asyncio
async def test_placement_ingestion_database_isolation():
    """Verify that tests execute strictly on karthik_ai_test and never the live DB."""
    async with async_session() as session:
        res = await session.execute(text("SELECT current_database();"))
        db_name = res.scalar()
        assert db_name == "karthik_ai_test"


@pytest.mark.asyncio
async def test_placement_parser_extract_from_text(client: AsyncClient):
    """Test extracting structured drive attributes from placement circular text."""
    resp = await client.post("/placements/extract-from-text", json={
        "text": SAMPLE_CIRCULAR_TEXT,
        "source_filename": "HCLTech_Campus_Notice_2027.pdf",
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["company_name"] == "HCLTech"
    assert "Graduate Engineer Trainee" in data["role"]
    assert data["min_cgpa"] == 7.0
    assert "CSE" in data["eligible_branches"]
    assert "IT" in data["eligible_branches"]
    assert "ECE" in data["eligible_branches"]
    assert data["graduation_year"] == 2027
    assert data["backlog_allowed"] is False
    assert "5.5 LPA" in data["compensation"]
    assert data["tier"] == "Dream"
    assert data["employment_type"] == "Full-Time"
    assert data["deadline"] == "2026-11-30"
    assert len(data["selection_process"]) >= 3
    assert any("Online Assessment" in r for r in data["selection_process"])
    assert any("Technical Interview" in r for r in data["selection_process"])

    # Required skills
    assert any("Python" in s for s in data["required_skills"])
    assert any("SQL" in s for s in data["required_skills"])


@pytest.mark.asyncio
async def test_placement_parser_extract_from_document(client: AsyncClient, seeded_profile: dict):
    """Test extracting placement criteria directly from an existing uploaded Document."""
    async with async_session() as session:
        # Create a test document record
        doc = Document(
            filename="Amazon_SDE_JD.pdf",
            original_filename="Amazon_SDE_JD.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=2048,
            file_path="uploads/documents/Amazon_SDE_JD.pdf",
            checksum="fakechecksum123456789",
            status="completed",
            total_pages=2,
            total_chunks=2,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        chunk1 = DocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content="Amazon Recruitment 2027. Role: Software Development Engineer (SDE-1). Location: Bangalore. CTC: 24 LPA. Super Dream tier.",
            page_number=1,
            token_count=40,
            embedding=[0.01] * 384,
        )
        chunk2 = DocumentChunk(
            document_id=doc.id,
            chunk_index=1,
            content="Eligibility: Minimum CGPA 7.5. Batch: 2027. Branches: CSE, IT. Deadline: 2026-12-15. Required: Data Structures, Algorithms, Java, AWS.",
            page_number=2,
            token_count=35,
            embedding=[0.02] * 384,
        )
        session.add_all([chunk1, chunk2])
        await session.commit()
        doc_id = doc.id

    # Call endpoint
    resp = await client.post(f"/placements/extract-from-document/{doc_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["company_name"] == "Amazon"
    assert "Software Development Engineer" in data["role"] or "SDE" in data["role"]
    assert data["min_cgpa"] == 7.5
    assert data["graduation_year"] == 2027
    assert data["deadline"] == "2026-12-15"
    assert data["tier"] == "Super Dream"
    assert "24 LPA" in data["compensation"]
    assert data["source_document_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_placement_extract_and_create_workflow(client: AsyncClient, seeded_profile: dict):
    """Test full workflow of extracting data and creating a PlacementDrive with auto-created company."""
    payload = {
        "drive_data": {
            "company_name": "Qualcomm",
            "role": "Hardware / Embedded Software Engineer",
            "status": "interested",
            "min_cgpa": 7.5,
            "eligible_branches": ["CSE", "ECE", "EEE"],
            "graduation_year": 2026,
            "compensation": "16 LPA",
            "employment_type": "Full-Time",
            "location": "Hyderabad / Bangalore",
            "deadline": "2026-11-25",
            "required_skills": ["C++", "Python", "Linux", "Data Structures"],
            "preferred_skills": ["Git", "Docker"],
            "backlog_allowed": False,
            "selection_process": ["Online Test", "Technical Interview", "HR Interview"],
            "tier": "Super Dream",
            "notes": "Parsed from college placement circular",
        },
        "create_company_if_missing": True,
    }

    # 1. Create drive from extracted data
    resp = await client.post("/placements/extract-and-create", json=payload)
    assert resp.status_code == 201
    created_drive = resp.json()

    assert created_drive["company"]["name"] == "Qualcomm"
    assert created_drive["role"] == "Hardware / Embedded Software Engineer"
    assert created_drive["min_cgpa"] == 7.5
    assert created_drive["tier"] == "Super Dream"
    assert created_drive["deadline"] == "2026-11-25"
    drive_id = created_drive["id"]

    # 2. Check drive appears in open placements list
    open_resp = await client.get("/placements/open")
    assert open_resp.status_code == 200
    assert any(d["id"] == drive_id for d in open_resp.json())

    # 3. Check Placement Intelligence eligibility for the candidate (CGPA 8.50 >= 7.5, CSE in branches, 2026 matches)
    elig_resp = await client.get(f"/placements/{drive_id}/eligibility")
    assert elig_resp.status_code == 200
    elig_data = elig_resp.json()
    # When backlog_allowed is False, status is UNKNOWN requiring student verification of 0 backlogs
    assert elig_data["status"] in ["ELIGIBLE", "UNKNOWN"]
    crit_map = {c["criterion"]: c["status"] for c in elig_data["criteria"]}
    assert crit_map["cgpa"] == "eligible"
    assert crit_map["branch"] == "eligible"
    assert crit_map["graduation_year"] == "eligible"

    # 4. Check priority ranking integration
    prio_resp = await client.get("/placements/priorities")
    assert prio_resp.status_code == 200
    prio_list = prio_resp.json()
    matched_prio = next((p for p in prio_list if p["drive_id"] == drive_id), None)
    assert matched_prio is not None
    assert matched_prio["company_name"] == "Qualcomm"
    assert matched_prio["priority_level"] in ["HIGH", "MEDIUM", "LOW"]
    assert matched_prio["composite_score"] >= 0
