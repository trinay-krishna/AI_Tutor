import pytest
from httpx import AsyncClient

from src.models import User, UserRole
from src.services.security import hash_password


async def _register_admin(client: AsyncClient, db_session, email="admin@example.com"):
    admin = User(email=email, password_hash=hash_password("password123"), role=UserRole.admin)
    db_session.add(admin)
    await db_session.commit()
    resp = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert resp.status_code == 200
    return admin


async def _register_learner(client: AsyncClient, email="learner@example.com"):
    resp = await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_and_list_technology(client: AsyncClient, db_session):
    await _register_admin(client, db_session)

    resp = await client.post("/api/technologies", json={"name": "React", "description": "A UI library"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "react"
    assert body["ready_resource_count"] == 0

    resp = await client.get("/api/technologies")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_learner_cannot_create_technology(client: AsyncClient):
    await _register_learner(client)
    resp = await client.post("/api/technologies", json={"name": "React"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_technology_name_rejected(client: AsyncClient, db_session):
    await _register_admin(client, db_session)
    await client.post("/api/technologies", json={"name": "React"})
    resp = await client.post("/api/technologies", json={"name": "React"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_resources_and_dedupe(client: AsyncClient, db_session):
    await _register_admin(client, db_session)
    resp = await client.post("/api/technologies", json={"name": "React"})
    tech_id = resp.json()["id"]

    resp = await client.post(
        f"/api/technologies/{tech_id}/resources",
        json={
            "urls": [
                "https://react.dev/learn",
                "https://react.dev/learn/",  # normalizes to the same URL -> dup within batch
                "https://react.dev/learn/synchronizing-with-effects",
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["created"]) == 2
    assert len(body["skipped"]) == 1

    # Re-adding an already-onboarded URL is also a duplicate.
    resp = await client.post(
        f"/api/technologies/{tech_id}/resources", json={"urls": ["https://react.dev/learn"]}
    )
    assert resp.json()["skipped"][0]["reason"] == "duplicate"

    resp = await client.get(f"/api/technologies/{tech_id}/resources")
    assert len(resp.json()) == 2
    assert all(r["status"] == "pending" for r in resp.json())


@pytest.mark.asyncio
async def test_learner_cannot_list_resources(client: AsyncClient, db_session):
    await _register_admin(client, db_session)
    resp = await client.post("/api/technologies", json={"name": "React"})
    tech_id = resp.json()["id"]
    await client.post("/api/auth/logout")

    await _register_learner(client)
    resp = await client.get(f"/api/technologies/{tech_id}/resources")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_technology_cascades_resources(client: AsyncClient, db_session):
    await _register_admin(client, db_session)
    resp = await client.post("/api/technologies", json={"name": "React"})
    tech_id = resp.json()["id"]
    await client.post(f"/api/technologies/{tech_id}/resources", json={"urls": ["https://react.dev/learn"]})

    resp = await client.delete(f"/api/technologies/{tech_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/technologies/{tech_id}")
    assert resp.status_code == 404
