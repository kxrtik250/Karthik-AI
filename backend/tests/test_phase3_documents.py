"""Tests for Phase 3 document processing, text extraction, chunking, and embeddings."""

import asyncio
import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_document_ingestion_and_chunking(client: AsyncClient):
    # Upload test document
    fake_doc_content = b"Karthik built a Carbon Footprint Tracker using Python, FastAPI, and PostgreSQL. Telemetry calculations monitor emission metrics."
    files = {"file": ("test_project_spec.txt", io.BytesIO(fake_doc_content), "text/plain")}

    upload_resp = await client.post("/documents/upload", files=files)
    assert upload_resp.status_code == 202
    doc_id = upload_resp.json()["id"]

    # Poll status
    for _ in range(20):
        resp = await client.get(f"/documents/{doc_id}")
        data = resp.json()
        if data["status"] == "completed":
            break
        await asyncio.sleep(0.5)

    assert data["status"] == "completed"
    assert data["total_chunks"] >= 1

    # Verify chunk details
    chunks_resp = await client.get(f"/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) >= 1
    assert "FastAPI" in chunks[0]["content"]

    # Delete document
    del_resp = await client.delete(f"/documents/{doc_id}")
    assert del_resp.status_code == 204
