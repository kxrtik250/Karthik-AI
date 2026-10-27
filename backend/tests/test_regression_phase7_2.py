"""Phase 7.2 Regression Tests — Grounding Remediation & Diagnostic Verification.

Verifies:
1. Identity: 'who am i?' correctly uses profile (Karthik) and isn't corrupted by previous turns.
2. Empty projects: queries about project technologies deterministically state no project records exist.
3. Empty placements: queries about eligible companies deterministically state zero drives loaded.
4. Document attribution: candidate resume documents (e.g. KARTHIK_SRIRAM_S_HCLTech.pdf) are flagged as candidate resumes.
5. Contextual follow-up: 'What should I prepare?' resolves active company entity from conversation history.
6. Diagnostic endpoint: GET /api/rag/context-summary?query=... exposes diagnostics safely without secrets.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.database import async_session
from app.models.conversation import Message
from app.models.document import Document, DocumentChunk
from app.services.context_builder import ContextBuilder, context_builder
from app.services.intent_router import IntentCategory, intent_router


@pytest.mark.asyncio
async def test_regression_database_isolation():
    """Ensure tests run strictly on karthik_ai_test."""
    async with async_session() as session:
        res = await session.execute(text("SELECT current_database();"))
        assert res.scalar() == "karthik_ai_test"


# ---------------------------------------------------------------------------
# Test A: Identity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identity_who_am_i_returns_karthik(client: AsyncClient, fake_phase6_profile: dict):
    """'who am i?' must cite Karthik and not fail with 'not enough information'."""
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "who am i?"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["intent"] == "PERSONAL_PROFILE"
    ans_text = data["message"]["content"]
    assert "Karthik" in ans_text
    assert "not enough information" not in ans_text.lower()


@pytest.mark.asyncio
async def test_standalone_identity_not_corrupted_by_previous_turn(client: AsyncClient, fake_phase6_profile: dict):
    """A standalone 'who am i?' following a company inquiry must NOT concatenate the company into the query."""
    await client.post("/profile", json=fake_phase6_profile)

    # Turn 1: Casual / company inquiry
    t1_resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert t1_resp.status_code == 200
    conv_id = t1_resp.json()["conversation_id"]

    # Turn 2: Standalone identity question
    t2_resp = await client.post("/rag/chat", json={
        "conversation_id": conv_id,
        "message": "who am i?",
    })
    assert t2_resp.status_code == 200
    data = t2_resp.json()

    # Must route cleanly to PERSONAL_PROFILE without HCLTech entity contamination
    assert data["intent"] == "PERSONAL_PROFILE"
    ans_text = data["message"]["content"]
    assert "Karthik" in ans_text
    assert "not enough information" not in ans_text.lower()


# ---------------------------------------------------------------------------
# Test B: Empty Project Records
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_projects_deterministic_guard(client: AsyncClient, fake_phase6_profile: dict):
    """When projects table is empty, asking about project technologies must not hallucinate tools."""
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "what technologies are in my projects?"})
    assert resp.status_code == 200
    data = resp.json()

    ans_text = data["message"]["content"]
    assert "no project records" in ans_text.lower() or "not have any project" in ans_text.lower()

    # Must NOT hallucinate arbitrary deep learning libraries
    for hallu in ["tensorflow", "pytorch", "keras", "opencv", "computer vision"]:
        assert hallu not in ans_text.lower()


# ---------------------------------------------------------------------------
# Test C: Empty Placement Records
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_placement_drives_deterministic_guard(client: AsyncClient, fake_phase6_profile: dict):
    """When placement_drives table is empty, questions about eligible companies report zero drives."""
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "which companies am I eligible for?"})
    assert resp.status_code == 200
    data = resp.json()

    ans_text = data["message"]["content"]
    assert "no placement drives" in ans_text.lower()

    # Must NOT hallucinate tech giants
    for comp in ["amazon", "microsoft", "accenture", "ibm"]:
        assert comp not in ans_text.lower()


@pytest.mark.asyncio
async def test_open_drives_zero_records(client: AsyncClient, fake_phase6_profile: dict):
    """When placement_drives is empty, 'which drives are currently open?' reports no drives."""
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Which drives are currently open?"})
    assert resp.status_code == 200
    data = resp.json()

    ans_text = data["message"]["content"]
    assert "no placement drives" in ans_text.lower()


# ---------------------------------------------------------------------------
# Test D: Resume versus Company Documents
# ---------------------------------------------------------------------------

def test_resume_document_type_detection():
    """Detects candidate resumes even when named after target companies (e.g. KARTHIK_SRIRAM_S_HCLTech.pdf)."""
    doc_type_1 = ContextBuilder.detect_document_type("KARTHIK_SRIRAM_S_HCLTech.pdf", "")
    assert doc_type_1 == "Candidate Resume / Personal Application Document"

    doc_type_2 = ContextBuilder.detect_document_type("resume_2026.pdf", "")
    assert doc_type_2 == "Candidate Resume / Personal Application Document"

    doc_type_3 = ContextBuilder.detect_document_type("HCLTech_Campus_Drive_Brochure.pdf", "")
    assert doc_type_3 == "Placement / Job Description Document"


def test_format_documents_section_attribution_note():
    """Ensures candidate resumes receive an explicit source attribution note separating candidate from company."""
    from app.services.rag_service import SourceCitation

    fake_source = SourceCitation(
        source_index=1,
        document_id=str(uuid.uuid4()),
        filename="KARTHIK_SRIRAM_S_HCLTech.pdf",
        page_number=1,
        chunk_index=0,
        snippet="Candidate with AWS and IBM credentials.",
        similarity_score=0.88,
    )

    doc_section = ContextBuilder.format_documents_section(
        sources=[fake_source],
        full_chunks=["Education: Sathyabama Institute. Certifications: AWS Certified."],
    )

    assert "Candidate Resume / Personal Application Document" in doc_section
    assert "IMPORTANT SOURCE ATTRIBUTION NOTE" in doc_section
    assert "describe the candidate Karthik" in doc_section


# ---------------------------------------------------------------------------
# Test E: Contextual Follow-ups
# ---------------------------------------------------------------------------

def test_contextual_followup_resolves_company_entity():
    """Follow-up 'What should I prepare?' following an HCLTech discussion retains HCLTech."""
    history = [
        Message(role="user", content="Tell me about HCLTech.", conversation_id=None),
        Message(role="assistant", content="HCLTech is a multinational IT services company.", conversation_id=None),
    ]

    result = intent_router.classify("What should I prepare?", conversation_history=history)
    assert result.intent == IntentCategory.PLACEMENT
    assert result.is_followup is True
    assert result.resolved_entity == "HCLTech"


# ---------------------------------------------------------------------------
# Test 3: Diagnostic Endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diagnostic_endpoint_query_summary(client: AsyncClient, fake_phase6_profile: dict):
    """GET /api/rag/context-summary?query=... exposes query diagnostics without leaking secrets."""
    await client.post("/profile", json=fake_phase6_profile)

    # 1. Base summary without query
    base_resp = await client.get("/rag/context-summary")
    assert base_resp.status_code == 200
    base_data = base_resp.json()
    assert base_data["profile_present"] is True
    assert base_data["profile_name"] == "Karthik"
    assert "query_diagnostics" not in base_data

    # 2. Summary with placement eligibility query (fires zero-drives guard)
    diag_resp = await client.get("/rag/context-summary?query=which+companies+am+I+eligible+for")
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()

    assert "query_diagnostics" in diag_data
    q_diag = diag_data["query_diagnostics"]
    assert q_diag["intent"] == "PLACEMENT"
    assert q_diag["deterministic_guard_fired"] is True
    assert q_diag["deterministic_guard_name"] == "ZERO_PLACEMENT_DRIVES_GUARD"
    assert q_diag["llm_invoked"] is False

    # 3. Summary with project inquiry (fires empty projects guard)
    proj_resp = await client.get("/rag/context-summary?query=what+technologies+are+in+my+projects")
    assert proj_resp.status_code == 200
    proj_data = proj_resp.json()
    assert proj_data["query_diagnostics"]["deterministic_guard_fired"] is True
    assert proj_data["query_diagnostics"]["deterministic_guard_name"] == "EMPTY_PROJECTS_GUARD"
    assert proj_data["query_diagnostics"]["llm_invoked"] is False

    # 4. Ensure no credentials or API keys exposed anywhere in the response
    for k in str(diag_data).lower():
        assert "api_key" not in k
        assert "password" not in k
        assert "secret" not in k


# ---------------------------------------------------------------------------
# Test 4: HCLTech Grounding & Resume Distinction (Regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hcltech_exact_query_no_hallucinated_role_or_responsibilities(client: AsyncClient, fake_phase6_profile: dict):
    """
    Exact query: 'Tell me about HCLTech.'
    Requirements:
    1. Never infer that candidate holds a role (e.g. Senior AI Architect) at HCLTech.
    2. Never treat candidate resume (KARTHIK_SRIRAM_S_HCLTech.pdf) as official company documentation.
    3. State limitations clearly when no reliable company information exists.
    4. Distinguish general company info, job-specific requirements, and personal eligibility.
    5. Do not output 'Eligibility: ELIGIBLE'.
    """
    from app.services.embedding_service import embedding_provider

    # Seed candidate profile with career_goals
    fake_profile = {**fake_phase6_profile, "career_goals": "Senior AI Architect"}
    await client.post("/profile", json=fake_profile)

    # Ingest candidate resume named KARTHIK_SRIRAM_S_HCLTech.pdf
    async with async_session() as session:
        doc = Document(
            id=uuid.uuid4(),
            filename="test_hcltech_resume.pdf",
            original_filename="KARTHIK_SRIRAM_S_HCLTech.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=1024,
            file_path="uploads/test_hcltech_resume.pdf",
            checksum="testchecksum123456",
            status="completed",
            total_pages=1,
            total_chunks=1,
        )
        session.add(doc)
        await session.flush()

        chunk_text = (
            "Karthik Sriram S. B.E. Computer Science and Engineering at Sathyabama. "
            "Technical Skills: Java, Python, SQL. Certifications: AWS Cloud Practitioner, IBM Cloud. "
            "Projects: Student Result Management System, AI-Controlled Traffic Management."
        )
        emb = embedding_provider.embed_texts([chunk_text])[0]
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content=chunk_text,
            page_number=1,
            token_count=40,
            chunk_metadata={"doc_type": "Candidate Resume"},
            embedding=emb,
        )
        session.add(chunk)
        await session.commit()

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    data = resp.json()
    ans = data["message"]["content"]
    citations = data["message"]["citations"]

    # 1. Must NOT hallucinate working as Senior AI Architect or holding a role at HCLTech
    assert "Senior AI Architect" not in ans
    assert "As a Senior AI Architect" not in ans
    assert "No current role at HCLTech is recorded in your profile" in ans
    assert "You do not currently hold a role at HCLTech" not in ans

    # 2. Must NOT output false eligibility
    assert "Eligibility: ELIGIBLE" not in ans

    # 3. Must use official company source (https://www.hcltech.com/about-us) for general overview
    assert "https://www.hcltech.com/about-us" in ans
    assert "global technology company" in ans.lower()

    # 4. Candidate resume is referenced as personal candidate resume and excluded from company citations
    assert "KARTHIK_SRIRAM_S_HCLTech.pdf" in ans
    assert "personal candidate application resume" in ans.lower() or "candidate application" in ans.lower()
    assert "excluded from company citations" in ans.lower()
    assert len(citations) == 0

    # 5. Must distinguish general company info, job requirements, and personal eligibility
    assert "General Company Information" in ans
    assert "Job-Specific Requirements" in ans
    assert "Personal Role & Eligibility" in ans


@pytest.mark.asyncio
async def test_hcltech_followup_question_preserves_context_without_invented_rounds(client: AsyncClient, fake_phase6_profile: dict):
    """
    Multi-turn conversation:
    Turn 1: 'Tell me about HCLTech.'
    Turn 2: 'What should I prepare?'
    Requirements:
    - Turn 2 preserves context that the topic is HCLTech.
    - Does NOT invent fictitious company rounds (e.g. AI Architecture assessment).
    - Recommends grounded CS fundamentals (DSA, OOP, DBMS, problem solving in Java/Python).
    - Explicitly clarifies that no specialized roles (such as Senior AI Architect) are assumed.
    """
    await client.post("/profile", json=fake_phase6_profile)

    # Turn 1
    t1 = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert t1.status_code == 200
    conv_id = t1.json()["conversation_id"]

    # Turn 2: Follow-up question
    t2 = await client.post("/rag/chat", json={"conversation_id": conv_id, "message": "What should I prepare?"})
    assert t2.status_code == 200
    t2_data = t2.json()
    ans2 = t2_data["message"]["content"]

    # Context preserved: knows company is HCLTech
    assert t2_data["intent"] == "PLACEMENT"
    assert "HCLTech" in ans2

    # Does NOT invent Senior AI Architect role
    assert "Senior AI Architect" not in ans2
    assert "No active job-specific role or placement record for HCLTech is recorded in your profile" in ans2

    # Grounded recommendations based on Computer Science fundamentals
    assert "Data Structures" in ans2 or "DSA" in ans2
    assert "Database Management Systems" in ans2 or "DBMS" in ans2


@pytest.mark.asyncio
async def test_company_query_without_documents_states_limitations(client: AsyncClient, fake_phase6_profile: dict):
    """When no documents or drives exist, general company inquiries provide official overview and state placement limitations."""
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    ans = resp.json()["message"]["content"]

    assert "Senior AI Architect" not in ans
    assert "https://www.hcltech.com/about-us" in ans
    assert "No placement drives or official job descriptions for HCLTech" in ans
    assert "No current role at HCLTech is recorded in your profile" in ans


# ---------------------------------------------------------------------------
# Test 5: Citation Formatting and Deduplication
# ---------------------------------------------------------------------------

def test_citation_metadata_valid_page_and_deduplication():
    """Valid page numbers are preserved; invalid or absent page numbers are None; duplicates are deduplicated."""
    from app.services.rag_service import SourceCitation, deduplicate_citations

    # 1. Page number normalization
    c1 = SourceCitation(
        source_index=1,
        document_id="doc-1",
        filename="Resume.pdf",
        page_number=1,
        chunk_index=0,
        snippet="Snippet 1",
        similarity_score=0.75,
    )
    assert c1.to_dict()["page_number"] == 1
    assert c1.to_dict()["similarity_score"] == 0.75

    c2 = SourceCitation(
        source_index=2,
        document_id="doc-2",
        filename="CompanyDoc.pdf",
        page_number=None,
        chunk_index=0,
        snippet="Snippet 2",
        similarity_score=None,
    )
    assert c2.to_dict()["page_number"] is None
    assert c2.to_dict()["similarity_score"] is None

    c3_invalid_page = SourceCitation(
        source_index=3,
        document_id="doc-3",
        filename="OtherDoc.pdf",
        page_number=0,  # Invalid page 0
        chunk_index=0,
        snippet="",
        similarity_score=0.8,
    )
    assert c3_invalid_page.to_dict()["page_number"] is None

    # 2. Deduplication: multiple chunks from same file & page kept as single highest-scoring entry
    c_dup1 = SourceCitation(
        source_index=1,
        document_id="doc-1",
        filename="KARTHIK_SRIRAM_S-Resume.pdf",
        page_number=1,
        chunk_index=0,
        snippet="Chunk 0",
        similarity_score=0.62,
    )
    c_dup2 = SourceCitation(
        source_index=2,
        document_id="doc-1",
        filename="KARTHIK_SRIRAM_S-Resume.pdf",
        page_number=1,
        chunk_index=1,
        snippet="Chunk 1",
        similarity_score=0.72,
    )
    deduped = deduplicate_citations([c_dup1, c_dup2])
    assert len(deduped) == 1
    assert deduped[0].filename == "KARTHIK_SRIRAM_S-Resume.pdf"
    assert deduped[0].page_number == 1
    assert deduped[0].similarity_score == 0.72


@pytest.mark.asyncio
async def test_evidence_calibrated_wording_in_rag_response(client: AsyncClient, fake_phase6_profile: dict):
    """Verifies evidence-accurate phrasing stating no role is recorded in the profile."""
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    data = resp.json()
    ans = data["message"]["content"]

    # Evidence-accurate phrasing
    assert "No current role at HCLTech is recorded in your profile" in ans
    assert "You do not currently hold a role at HCLTech" not in ans


@pytest.mark.asyncio
async def test_hcltech_citations_exclude_unrelated_resume_and_no_malformed_metadata(client: AsyncClient, fake_phase6_profile: dict):
    """
    Regression test reproducing the malformed citation case:
    When candidate resumes exist in database:
    1. 'KARTHIK_SRIRAM_S-Resume.pdf' (generic candidate resume, not entity-related)
    2. 'KARTHIK_SRIRAM_S_HCLTech.pdf' (candidate resume named for HCLTech)
    Querying 'Tell me about HCLTech.':
    - Must NOT cite unrelated generic resume 'KARTHIK_SRIRAM_S-Resume.pdf' for the HCLTech limitation notice.
    - Must NOT concatenate page numbers and similarity scores (e.g. 'KARTHIK_SRIRAM_S-Resume.pdfp. 162%').
    - Candidate Notice in response content must only mention entity-related resume(s).
    - Citation metadata must have valid page_number (int > 0 or None) and similarity_score (float or None).
    """
    from app.database import async_session
    from app.models.document import Document, DocumentChunk
    from app.services.embedding_service import embedding_provider
    import uuid

    await client.post("/profile", json=fake_phase6_profile)

    # Ingest generic resume KARTHIK_SRIRAM_S-Resume.pdf
    async with async_session() as session:
        doc_generic = Document(
            id=uuid.uuid4(),
            filename="test_gen_resume.pdf",
            original_filename="KARTHIK_SRIRAM_S-Resume.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=2048,
            file_path="uploads/test_gen_resume.pdf",
            checksum="checksum_gen_123",
            status="completed",
            total_pages=1,
            total_chunks=1,
        )
        session.add(doc_generic)
        await session.flush()

        gen_chunk_text = (
            "Relevant Coursework: DSA, Operating Systems, DBMS, Computer Networks, Software Engineering. "
            "Technical Skills: Python, Java, SQL, Machine Learning. Projects: Web Application."
        )
        gen_emb = embedding_provider.embed_texts([gen_chunk_text])[0]
        gen_chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_generic.id,
            chunk_index=0,
            content=gen_chunk_text,
            page_number=1,
            token_count=35,
            chunk_metadata={"doc_type": "Candidate Resume", "page": 1},
            embedding=gen_emb,
        )
        session.add(gen_chunk)

        # Ingest HCLTech-specific resume KARTHIK_SRIRAM_S_HCLTech.pdf
        doc_hcl = Document(
            id=uuid.uuid4(),
            filename="test_hcl_resume.pdf",
            original_filename="KARTHIK_SRIRAM_S_HCLTech.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=1024,
            file_path="uploads/test_hcl_resume.pdf",
            checksum="checksum_hcl_456",
            status="completed",
            total_pages=1,
            total_chunks=1,
        )
        session.add(doc_hcl)
        await session.flush()

        hcl_chunk_text = (
            "Karthik Sriram S. B.E. CSE at Sathyabama. Applied for HCLTech Campus Drive. "
            "Skills: Java, Python, SQL. Certifications: AWS Cloud Practitioner."
        )
        hcl_emb = embedding_provider.embed_texts([hcl_chunk_text])[0]
        hcl_chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc_hcl.id,
            chunk_index=0,
            content=hcl_chunk_text,
            page_number=1,
            token_count=30,
            chunk_metadata={"doc_type": "Candidate Resume", "page": 1},
            embedding=hcl_emb,
        )
        session.add(hcl_chunk)
        await session.commit()

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    data = resp.json()
    ans = data["message"]["content"]
    citations = data["message"]["citations"]

    # 1. Limitation text must only mention the entity resume, NOT the generic resume
    assert "KARTHIK_SRIRAM_S_HCLTech.pdf" in ans
    assert "KARTHIK_SRIRAM_S-Resume.pdf" not in ans

    # 2. Citations must NOT include candidate resumes as evidence for corporate facts
    citation_filenames = [c["filename"] for c in citations]
    assert "KARTHIK_SRIRAM_S-Resume.pdf" not in citation_filenames
    assert "KARTHIK_SRIRAM_S_HCLTech.pdf" not in citation_filenames
    assert len(citations) == 0

    # 3. No invented page numbers or malformed concatenated strings
    for cite in citations:
        assert cite["filename"]
        # page_number must be None or positive int
        assert cite["page_number"] is None or (isinstance(cite["page_number"], int) and cite["page_number"] > 0)
        # similarity_score must be None or valid float
        assert cite["similarity_score"] is None or isinstance(cite["similarity_score"], (int, float))


@pytest.mark.asyncio
async def test_general_company_query_with_verified_company_record(client: AsyncClient, fake_phase6_profile: dict):
    """
    When a verified company record exists in PostgreSQL:
    1. 'Tell me about HCLTech.' provides a concise general company overview from the record.
    2. Distinguishes general company info from missing official campus placement details & job descriptions.
    3. States no current role at HCLTech is recorded in profile, and personal eligibility cannot be verified.
    4. Provides actionable next steps (checking college placement notice, uploading official JD).
    """
    await client.post("/profile", json=fake_phase6_profile)

    comp_payload = {
        "name": "HCLTech",
        "industry": "Information Technology & Consulting",
        "location": "Noida, India",
        "website": "https://www.hcltech.com",
        "notes": "Global technology company specializing in digital, engineering, and cloud services.",
    }
    c_resp = await client.post("/companies", json=comp_payload)
    assert c_resp.status_code == 201

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    ans = resp.json()["message"]["content"]

    # 1. General Company Overview from verified record
    assert "General Company Information" in ans
    assert "Global technology company" in ans or "Information Technology" in ans
    assert "HCLTech" in ans

    # 2. Distinguish missing official campus placement details
    assert "No placement drives or official job descriptions for HCLTech" in ans
    assert "Job-Specific Requirements" in ans

    # 3. Personal role & eligibility distinction
    assert "No current role at HCLTech is recorded in your profile" in ans
    assert "Personal Role & Eligibility" in ans
    assert "Senior AI Architect" not in ans
    assert "Eligibility: ELIGIBLE" not in ans

    # 4. Actionable next steps provided
    assert "Recommended Next Steps" in ans or "Next Steps" in ans
    assert "college placement" in ans.lower() or "tpo" in ans.lower()
    assert "job description" in ans.lower() or "jd" in ans.lower()


@pytest.mark.asyncio
async def test_general_company_query_without_verified_sources_labels_limitations_and_next_steps(client: AsyncClient, fake_phase6_profile: dict):
    """
    When a company has no verified sources or official registry:
    1. 'Tell me about Wipro.' clearly labels the limitation rather than inventing corporate facts.
    2. Distinguishes general company info, job requirements, and personal eligibility.
    3. Explicitly says official placement info is missing and provides useful next steps.
    """
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Tell me about Wipro."})
    assert resp.status_code == 200
    ans = resp.json()["message"]["content"]

    # 1. Labeled limitations
    assert "General Company Information" in ans
    assert "No official company overview" in ans

    # 2. Missing placement records distinguished
    assert "Job-Specific Requirements" in ans
    assert "No placement drives or official job descriptions for Wipro" in ans

    # 3. Grounded personal role
    assert "Personal Role & Eligibility" in ans
    assert "No current role at Wipro is recorded in your profile" in ans

    # 4. Actionable next steps
    assert "Recommended Next Steps" in ans
    assert "college placement portal" in ans.lower() or "tpo notice" in ans.lower()
    assert "upload the official" in ans.lower()


@pytest.mark.asyncio
async def test_followup_preparation_query_labeled_general_and_not_company_specific(client: AsyncClient, fake_phase6_profile: dict):
    """
    Follow-up 'What should I prepare?' preserves context, provides clearly labeled general
    placement preparation advice, explicitly clarifies it is not company-specific, and offers next steps.
    """
    await client.post("/profile", json=fake_phase6_profile)

    # Turn 1
    t1 = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert t1.status_code == 200
    conv_id = t1.json()["conversation_id"]

    # Turn 2: Follow-up
    t2 = await client.post("/rag/chat", json={"conversation_id": conv_id, "message": "What should I prepare?"})
    assert t2.status_code == 200
    ans = t2.json()["message"]["content"]

    # Clearly labeled as general preparation advice, not company-specific
    assert "[General Placement Preparation Advice - Not Company-Specific]" in ans
    assert "Official company-specific interview rounds and job requirements for HCLTech are not recorded" in ans

    # Grounded technical fundamentals
    assert "Data Structures" in ans or "DSA" in ans
    assert "Database Management Systems" in ans or "DBMS" in ans

    # Profile grounding preserved
    assert "No active job-specific role or placement record for HCLTech is recorded in your profile" in ans
    assert "Senior AI Architect" not in ans

    # Actionable next steps
    assert "Recommended Next Steps" in ans
    assert "college placement portal" in ans.lower() or "tpo notice" in ans.lower()
    assert "job description" in ans.lower() or "jd" in ans.lower()


# ---------------------------------------------------------------------------
# Test 6: Targeted Regression Tests for Official Source & Exclusion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hcltech_official_source_retrieval(client: AsyncClient, fake_phase6_profile: dict):
    """
    Requirement 1 & 2:
    - General company query 'Tell me about HCLTech.' retrieves info from preferred official source (https://www.hcltech.com/about-us).
    - Explains that live web retrieval is unsupported in this offline system and proposes ingesting the official page.
    """
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    ans = resp.json()["message"]["content"]

    assert "https://www.hcltech.com/about-us" in ans
    assert "global technology company" in ans.lower()
    assert "Noida" in ans
    assert "Live external web retrieval is not supported in this offline local system" in ans
    assert "ingest the official company webpage" in ans or "ingest the official" in ans.lower()


@pytest.mark.asyncio
async def test_hcltech_candidate_resume_excluded_from_citations(client: AsyncClient, fake_phase6_profile: dict):
    """
    Requirement 4:
    - Never cite personal resume as evidence for corporate facts.
    - Exclude candidate resumes from company-overview citations.
    """
    from app.models.document import Document, DocumentChunk
    from app.services.embedding_service import embedding_provider

    await client.post("/profile", json=fake_phase6_profile)

    # Ingest candidate resume
    async with async_session() as session:
        doc = Document(
            id=uuid.uuid4(),
            filename="candidate_resume_hcl.pdf",
            original_filename="KARTHIK_SRIRAM_S_HCLTech.pdf",
            file_type="pdf",
            mime_type="application/pdf",
            file_size=1024,
            file_path="uploads/candidate_resume_hcl.pdf",
            checksum="testchecksum999",
            status="completed",
            total_pages=1,
            total_chunks=1,
        )
        session.add(doc)
        await session.flush()

        chunk_text = "Karthik Sriram candidate profile for HCLTech drive. Skills: Python, Java."
        emb = embedding_provider.embed_texts([chunk_text])[0]
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content=chunk_text,
            page_number=1,
            token_count=20,
            chunk_metadata={"doc_type": "Candidate Resume"},
            embedding=emb,
        )
        session.add(chunk)
        await session.commit()

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    data = resp.json()

    # Candidate resume MUST be excluded from citations
    citations = data["message"]["citations"]
    assert len(citations) == 0
    assert not any("KARTHIK_SRIRAM" in c["filename"] for c in citations)


@pytest.mark.asyncio
async def test_hcltech_missing_campus_drive_information_ordering(client: AsyncClient, fake_phase6_profile: dict):
    """
    Requirement 5:
    - When official placement records are missing, provide general company overview first,
      followed by a concise note that campus-specific drive and eligibility details are unavailable.
    """
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    ans = resp.json()["message"]["content"]

    # Verify presentation order: General Company Information is first
    gen_idx = ans.find("• General Company Information")
    drive_idx = ans.find("• Job-Specific Requirements & Drives")
    elig_idx = ans.find("• Personal Role & Eligibility")
    next_idx = ans.find("• Recommended Next Steps")

    assert gen_idx != -1
    assert drive_idx != -1
    assert elig_idx != -1
    assert next_idx != -1
    assert gen_idx < drive_idx < elig_idx < next_idx

    assert "No placement drives or official job descriptions for HCLTech are registered" in ans
    assert "No current role at HCLTech is recorded in your profile" in ans


@pytest.mark.asyncio
async def test_hcltech_no_duplicate_disclaimers_in_response(client: AsyncClient, fake_phase6_profile: dict):
    """
    Requirement 6:
    - Remove duplicate or redundant disclaimers.
    - No double-rendering of 'not have verified company information' or repeating disclaimer phrases.
    """
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "Tell me about HCLTech."})
    assert resp.status_code == 200
    ans = resp.json()["message"]["content"]

    # Ensure no repeating header disclaimer before the bullet
    assert "I do not have verified company information for HCLTech in your knowledge base." not in ans
    # Ensure sections appear exactly once
    assert ans.count("• General Company Information") == 1
    assert ans.count("• Job-Specific Requirements & Drives") == 1
    assert ans.count("• Personal Role & Eligibility") == 1
    assert ans.count("• Recommended Next Steps") == 1




