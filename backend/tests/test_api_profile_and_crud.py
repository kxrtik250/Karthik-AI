"""Tests for Profile, Skills, Projects, Certifications, Companies, and Placement endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_profile_crud(client: AsyncClient, fake_phase6_profile: dict):
    # Initial GET should be 404
    resp = await client.get("/profile")
    assert resp.status_code == 404

    # Create profile
    resp = await client.post("/profile", json=fake_phase6_profile)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == fake_phase6_profile["name"]
    assert data["university"] == fake_phase6_profile["university"]
    assert float(data["cgpa"]) == fake_phase6_profile["cgpa"]

    # Reject duplicate profile creation
    resp = await client.post("/profile", json=fake_phase6_profile)
    assert resp.status_code == 400

    # Update profile
    resp = await client.put("/profile", json={"career_goals": "AI Architect"})
    assert resp.status_code == 200
    assert resp.json()["career_goals"] == "AI Architect"


@pytest.mark.asyncio
async def test_skills_crud(client: AsyncClient, seeded_profile: dict, fake_phase6_skills: list):
    for skill_payload in fake_phase6_skills:
        resp = await client.post("/skills", json=skill_payload)
        assert resp.status_code == 201

    resp = await client.get("/skills")
    assert resp.status_code == 200
    skills = resp.json()
    assert len(skills) == 3
    names = [s["name"] for s in skills]
    assert "Python" in names
    assert "FastAPI" in names


@pytest.mark.asyncio
async def test_projects_crud(client: AsyncClient, seeded_profile: dict, fake_phase6_project: dict):
    resp = await client.post("/projects", json=fake_phase6_project)
    assert resp.status_code == 201
    proj_id = resp.json()["id"]

    resp = await client.get(f"/projects/{proj_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == fake_phase6_project["name"]


@pytest.mark.asyncio
async def test_certifications_crud(client: AsyncClient, seeded_profile: dict, fake_phase6_certification: dict):
    resp = await client.post("/certifications", json=fake_phase6_certification)
    assert resp.status_code == 201
    cert_id = resp.json()["id"]

    resp = await client.get("/certifications")
    assert resp.status_code == 200
    certs = resp.json()
    assert any(c["id"] == cert_id and c["name"] == fake_phase6_certification["name"] for c in certs)


@pytest.mark.asyncio
async def test_companies_and_placements_crud(
    client: AsyncClient, seeded_profile: dict, fake_phase6_company_and_placement: dict
):
    comp_data = fake_phase6_company_and_placement["company"]
    resp = await client.post("/companies", json=comp_data)
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    placement_data = {
        **fake_phase6_company_and_placement["placement"],
        "company_id": company_id,
    }
    resp = await client.post("/placements", json=placement_data)
    assert resp.status_code == 201
    assert resp.json()["company"]["name"] == comp_data["name"]
    assert resp.json()["role"] == placement_data["role"]
