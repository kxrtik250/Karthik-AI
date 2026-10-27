"""Tests for Intent Routing Layer before RAG on isolated test DB."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.database import async_session
from app.models.conversation import Message
from app.services.intent_router import IntentCategory, intent_router


def test_intent_classification_casual():
    """Verifies that greetings and conversational courtesies route to CASUAL."""
    casual_queries = [
        "hi",
        "hello",
        "hey there",
        "good morning",
        "how are you?",
        "thanks a lot",
        "bye",
        "who are you",
    ]
    for q in casual_queries:
        res = intent_router.classify(q)
        assert res.intent == IntentCategory.CASUAL, f"Expected CASUAL for '{q}', got {res.intent}"
        assert res.use_rag is False
        assert res.use_profile is False
        assert res.use_placement is False


def test_intent_classification_personal_profile():
    """Verifies that personal credentials and identity queries route to PERSONAL_PROFILE."""
    profile_queries = [
        "who am i?",
        "what is my name?",
        "what is my CGPA?",
        "where do I study?",
        "what is my university?",
        "what is my degree?",
        "what are my technical skills?",
        "what projects have I completed?",
        "what certifications do I have?",
        "what is my role in ACM?",
    ]
    for q in profile_queries:
        res = intent_router.classify(q)
        assert res.intent == IntentCategory.PERSONAL_PROFILE, f"Expected PERSONAL_PROFILE for '{q}', got {res.intent}"
        assert res.use_profile is True
        assert res.use_rag is False


def test_intent_classification_document_rag():
    """Verifies that explicit document and resume queries route to DOCUMENT_RAG."""
    doc_queries = [
        "summarize my resume",
        "what certifications are listed in my resume?",
        "what does my uploaded project report say?",
        "search my uploaded documents for telemetry",
    ]
    for q in doc_queries:
        res = intent_router.classify(q)
        assert res.intent == IntentCategory.DOCUMENT_RAG, f"Expected DOCUMENT_RAG for '{q}', got {res.intent}"
        assert res.use_rag is True


def test_intent_classification_placement():
    """Verifies that placement eligibility and drive queries route to PLACEMENT."""
    placement_queries = [
        "which companies am I eligible for?",
        "am I eligible for HCLTech?",
        "what should I prepare for HCLTech?",
        "which placement drives are currently open?",
        "compare my placement options",
        "show me my placement pipeline",
    ]
    for q in placement_queries:
        res = intent_router.classify(q)
        assert res.intent == IntentCategory.PLACEMENT, f"Expected PLACEMENT for '{q}', got {res.intent}"
        assert res.use_placement is True


def test_intent_classification_general_knowledge():
    """Verifies that general engineering concepts route to GENERAL_KNOWLEDGE without doc retrieval."""
    general_queries = [
        "what is Docker?",
        "explain REST API",
        "what is a GNN?",
        "how does JWT work?",
        "what is the difference between SQL and NoSQL?",
        "explain recursion in python",
    ]
    for q in general_queries:
        res = intent_router.classify(q)
        assert res.intent == IntentCategory.GENERAL_KNOWLEDGE, f"Expected GENERAL_KNOWLEDGE for '{q}', got {res.intent}"
        assert res.use_rag is False
        assert res.use_profile is False


def test_contextual_followup_routing():
    """Verifies multi-turn follow-up intent resolution based on conversational context."""
    # Placement follow-up
    hist_placement = [
        Message(role="user", content="Tell me about HCLTech placement drive", conversation_id=None),
        Message(role="assistant", content="HCLTech is offering 5 LPA for Graduate Trainee.", conversation_id=None),
    ]
    res_placement = intent_router.classify("What should I prepare?", conversation_history=hist_placement)
    assert res_placement.intent == IntentCategory.PLACEMENT

    # General Knowledge follow-up
    hist_tech = [
        Message(role="user", content="What is Docker?", conversation_id=None),
        Message(role="assistant", content="Docker is a containerization platform.", conversation_id=None),
    ]
    res_tech = intent_router.classify("How do I use it?", conversation_history=hist_tech)
    assert res_tech.intent == IntentCategory.GENERAL_KNOWLEDGE

    # Profile follow-up
    hist_profile = [
        Message(role="user", content="What is my CGPA and degree?", conversation_id=None),
        Message(role="assistant", content="Your CGPA is 8.5 in B.E. Computer Science.", conversation_id=None),
    ]
    res_profile = intent_router.classify("And what university is that from?", conversation_history=hist_profile)
    assert res_profile.intent == IntentCategory.PERSONAL_PROFILE


@pytest.mark.asyncio
async def test_e2e_casual_chat_greeting_no_rag_rejection(client: AsyncClient):
    """
    Verifies that 'hi' returns a friendly conversational greeting
    and does NOT return 'not enough information' or document ungrounded error.
    """
    # Verify DB isolation
    async with async_session() as session:
        db_res = await session.execute(text("SELECT current_database();"))
        assert db_res.scalar() == "karthik_ai_test"

    resp = await client.post("/rag/chat", json={"message": "hi"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["intent"] == "CASUAL"
    assert len(data["sources"]) == 0
    ans_text = data["message"]["content"].lower()

    # Must NOT fail with RAG ungrounded rejection
    assert "not enough information" not in ans_text
    assert "couldn't find relevant information" not in ans_text
    assert any(w in ans_text for w in ["hi", "hello", "hey", "how", "karthik", "help", "assist", "today"])


@pytest.mark.asyncio
async def test_e2e_general_knowledge_no_rag_rejection(client: AsyncClient):
    """
    Verifies that 'what is Docker?' returns a direct technical explanation
    and does NOT search documents or return 'not enough information'.
    """
    resp = await client.post("/rag/chat", json={"message": "what is Docker?"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["intent"] == "GENERAL_KNOWLEDGE"
    assert len(data["sources"]) == 0
    ans_text = data["message"]["content"].lower()

    # Must NOT fail with RAG ungrounded rejection
    assert "not enough information" not in ans_text
    assert "couldn't find relevant information" not in ans_text
    assert any(w in ans_text for w in ["container", "platform", "docker", "application", "environment"])


@pytest.mark.asyncio
async def test_e2e_profile_query_with_profile_intent(client: AsyncClient, fake_phase6_profile: dict):
    """
    Verifies that 'who am i?' correctly routes to PERSONAL_PROFILE and retrieves profile context.
    """
    # Seed test profile if not already present
    await client.post("/profile", json=fake_phase6_profile)

    resp = await client.post("/rag/chat", json={"message": "who am i?"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["intent"] == "PERSONAL_PROFILE"
    assert "profile" in data["structured_sources"]
    ans_text = data["message"]["content"]
    assert "Karthik" in ans_text
