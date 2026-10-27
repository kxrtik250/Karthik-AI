"""Tests for Phase 4 multi-turn conversations and message persistence on isolated test DB."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_conversation_lifecycle(client: AsyncClient, fake_phase6_profile: dict):
    # Seed profile
    await client.post("/profile", json=fake_phase6_profile)

    # 1. Turn 1
    t1_resp = await client.post("/rag/chat", json={"message": "What is my current CGPA and degree?"})
    assert t1_resp.status_code == 200
    t1_data = t1_resp.json()
    conv_id = t1_data["conversation_id"]
    assert "8.5" in t1_data["message"]["content"]

    # 2. Turn 2 (Follow-up)
    t2_resp = await client.post(
        "/rag/chat",
        json={"conversation_id": conv_id, "message": "And what university is that from?"},
    )
    assert t2_resp.status_code == 200
    assert "Amrita Vishwa Vidyapeetham" in t2_resp.json()["message"]["content"]

    # 3. Retrieve conversation history
    get_resp = await client.get(f"/rag/conversations/{conv_id}")
    assert get_resp.status_code == 200
    conv = get_resp.json()
    assert len(conv["messages"]) == 4  # 2 user + 2 assistant messages

    # 4. List conversations
    list_resp = await client.get("/rag/conversations")
    assert list_resp.status_code == 200
    assert any(c["id"] == conv_id for c in list_resp.json())

    # 5. Delete conversation
    del_resp = await client.delete(f"/rag/conversations/{conv_id}")
    assert del_resp.status_code == 204

    # 6. Verify deleted
    get_after = await client.get(f"/rag/conversations/{conv_id}")
    assert get_after.status_code == 404
