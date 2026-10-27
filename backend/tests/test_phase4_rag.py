"""Tests for Phase 4 RAG query retrieval and generation on isolated test DB."""

import asyncio
import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rag_query_with_uploaded_document(client: AsyncClient):
    # Ingest document
    content = b"The Carbon Footprint Tracker project was developed in 2024 using Python, FastAPI, React, and PostgreSQL for telemetry calculation."
    files = {"file": ("carbon_tracker.txt", io.BytesIO(content), "text/plain")}

    up_resp = await client.post("/documents/upload", files=files)
    assert up_resp.status_code == 202
    doc_id = up_resp.json()["id"]

    for _ in range(20):
        resp = await client.get(f"/documents/{doc_id}")
        if resp.json()["status"] == "completed":
            break
        await asyncio.sleep(0.5)

    # Query RAG
    query_resp = await client.post(
        "/rag/query",
        json={"question": "What technologies were used in the carbon footprint project?", "similarity_threshold": 0.30},
    )
    assert query_resp.status_code == 200
    res = query_resp.json()
    assert "answer" in res
    assert len(res["sources"]) >= 1
    assert "carbon_tracker.txt" in res["sources"][0]["filename"]


@pytest.mark.asyncio
async def test_rag_query_hallucination_safeguard(client: AsyncClient):
    # Query with no relevant context
    query_resp = await client.post(
        "/rag/query",
        json={"question": "What is the secret formula for dark matter propulsion in astrophysics?"},
    )
    assert query_resp.status_code == 200
    res = query_resp.json()
    assert "not enough information" in res["answer"].lower()
