import pytest
from httpx import AsyncClient

from src.models import User, UserRole
from src.services.security import hash_password


@pytest.mark.asyncio
async def test_register_login_me_logout(client: AsyncClient):
    resp = await client.post("/api/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert body["role"] == "learner"
    assert "ai_tutor_session" in resp.cookies

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@example.com"

    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 204

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "password123"})
    resp = await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={"email": "b@example.com", "password": "password123"})
    resp = await client.post("/api/auth/login", json={"email": "b@example.com", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_without_session(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_learner_forbidden_from_admin_route(client: AsyncClient, db_session):
    from fastapi import APIRouter, Depends

    from src.deps import require_admin
    from src.main import app

    probe = APIRouter()

    @probe.get("/api/_test/admin-only")
    async def admin_only(_user=Depends(require_admin)):
        return {"ok": True}

    app.include_router(probe)

    await client.post("/api/auth/register", json={"email": "learner@example.com", "password": "password123"})
    resp = await client.get("/api/_test/admin-only")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_allowed_on_admin_route(client: AsyncClient, db_session):
    from fastapi import APIRouter, Depends

    from src.deps import require_admin
    from src.main import app

    probe = APIRouter()

    @probe.get("/api/_test/admin-only2")
    async def admin_only(_user=Depends(require_admin)):
        return {"ok": True}

    app.include_router(probe)

    admin = User(email="admin@example.com", password_hash=hash_password("password123"), role=UserRole.admin)
    db_session.add(admin)
    await db_session.commit()

    resp = await client.post("/api/auth/login", json={"email": "admin@example.com", "password": "password123"})
    assert resp.status_code == 200

    resp = await client.get("/api/_test/admin-only2")
    assert resp.status_code == 200
