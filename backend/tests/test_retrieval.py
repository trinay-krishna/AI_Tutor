import uuid

import pytest
from httpx import AsyncClient
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from src.models import Document as DocumentModel
from src.models import Resource, ResourceStatus, Technology, User, UserRole
from src.services.security import hash_password
from src.services.vector_store import METADATA_COLUMNS, get_pg_engine


async def _seed_chunks(db_session, monkeypatch, technology_id: int, resource_id: int, texts: list[str]):
    from langchain_postgres import PGVectorStore

    fake = DeterministicFakeEmbedding(size=1536)
    monkeypatch.setattr("src.services.vector_store.get_embeddings", lambda: fake)

    doc = DocumentModel(
        id=uuid.uuid4(),
        resource_id=resource_id,
        technology_id=technology_id,
        url="https://example.com/doc",
        title="Doc",
        content="\n\n".join(texts),
        outline=[],
        content_hash="hash",
    )
    db_session.add(doc)
    await db_session.commit()

    store = await PGVectorStore.create(
        engine=get_pg_engine(),
        embedding_service=fake,
        table_name="chunks",
        content_column="content",
        embedding_column="embedding",
        id_column="id",
        metadata_columns=METADATA_COLUMNS,
        metadata_json_column="langchain_metadata",
    )
    lc_docs = [
        Document(
            page_content=text,
            metadata={
                "technology_id": technology_id,
                "document_id": str(doc.id),
                "resource_id": resource_id,
                "heading_path": None,
                "chunk_index": i,
                "title": "Doc",
                "url": "https://example.com/doc",
            },
        )
        for i, text in enumerate(texts)
    ]
    await store.aadd_documents(lc_docs, ids=[str(uuid.uuid4()) for _ in lc_docs])


@pytest.mark.asyncio
async def test_search_returns_scored_chunks_scoped_to_technology(
    client: AsyncClient, db_session, monkeypatch
):
    admin = User(email="admin@example.com", password_hash=hash_password("password123"), role=UserRole.admin)
    db_session.add(admin)
    tech_a = Technology(name="React", slug="react")
    tech_b = Technology(name="Docker", slug="docker")
    db_session.add_all([tech_a, tech_b])
    await db_session.flush()

    resource_a = Resource(
        technology_id=tech_a.id, url="u1", normalized_url="u1", status=ResourceStatus.ready
    )
    resource_b = Resource(
        technology_id=tech_b.id, url="u2", normalized_url="u2", status=ResourceStatus.ready
    )
    db_session.add_all([resource_a, resource_b])
    await db_session.flush()

    await _seed_chunks(
        db_session, monkeypatch, tech_a.id, resource_a.id,
        ["useEffect lets you synchronize a component with an external system."],
    )
    await _seed_chunks(
        db_session, monkeypatch, tech_b.id, resource_b.id,
        ["Docker containers package an application with its dependencies."],
    )

    resp = await client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "password123"}
    )
    assert resp.status_code == 200

    # DeterministicFakeEmbedding is a hash-based stand-in with no real semantics,
    # so an exact-text query is the only reliable way to get a high similarity score.
    resp = await client.post(
        f"/api/technologies/{tech_a.id}/search",
        json={"query": "useEffect lets you synchronize a component with an external system.", "k": 5},
    )
    assert resp.status_code == 200
    hits = resp.json()
    assert len(hits) == 1
    assert "useEffect" in hits[0]["content"]
    assert hits[0]["score"] == pytest.approx(1.0)

    # Docker's chunk must never leak into a React-scoped search.
    resp = await client.post(
        f"/api/technologies/{tech_a.id}/search", json={"query": "Docker containers", "k": 5}
    )
    hits = resp.json()
    assert all("Docker" not in h["content"] for h in hits)


@pytest.mark.asyncio
async def test_search_forbidden_for_learner(client: AsyncClient, db_session):
    tech = Technology(name="React", slug="react")
    db_session.add(tech)
    await db_session.commit()

    await client.post("/api/auth/register", json={"email": "l@example.com", "password": "password123"})
    resp = await client.post(f"/api/technologies/{tech.id}/search", json={"query": "x"})
    assert resp.status_code == 403
