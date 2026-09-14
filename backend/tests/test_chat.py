import uuid

import pytest
from httpx import AsyncClient
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_postgres import PGVectorStore

from src.deps import get_tutor_graph
from src.main import app
from src.models import Document as DocumentModel
from src.models import Resource, ResourceStatus, Technology
from src.services.tutor_graph.graph import build_tutor_graph
from src.services.vector_store import METADATA_COLUMNS, get_pg_engine


async def _seed_react_chunk(db_session, monkeypatch, tech_id: int, resource_id: int, text: str):
    fake = DeterministicFakeEmbedding(size=1536)
    monkeypatch.setattr("src.services.vector_store.get_embeddings", lambda: fake)

    doc = DocumentModel(
        id=uuid.uuid4(), resource_id=resource_id, technology_id=tech_id,
        url="https://react.dev/x", title="useEffect", content=text, outline=[], content_hash="h",
    )
    db_session.add(doc)
    await db_session.commit()

    store = await PGVectorStore.create(
        engine=get_pg_engine(), embedding_service=fake, table_name="chunks",
        content_column="content", embedding_column="embedding", id_column="id",
        metadata_columns=METADATA_COLUMNS, metadata_json_column="langchain_metadata",
    )
    lc_doc = Document(
        page_content=text,
        metadata={
            "technology_id": tech_id, "document_id": str(doc.id), "resource_id": resource_id,
            "heading_path": "useEffect > Cleanup", "chunk_index": 0, "title": "useEffect", "url": "https://react.dev/x",
        },
    )
    await store.aadd_documents([lc_doc], ids=[str(uuid.uuid4())])


@pytest.fixture
def fake_tutor_graph(monkeypatch):
    # Retrieval always embeds the query, even when there's nothing indexed yet,
    # so every test using this fixture gets safe fake embeddings.
    monkeypatch.setattr(
        "src.services.vector_store.get_embeddings", lambda: DeterministicFakeEmbedding(size=1536)
    )
    fake_llm = FakeListChatModel(responses=["Effects clean up on unmount [1]."])
    graph = build_tutor_graph(fake_llm, fake_llm)
    app.dependency_overrides[get_tutor_graph] = lambda: graph
    yield graph
    app.dependency_overrides.pop(get_tutor_graph, None)


@pytest.mark.asyncio
async def test_chat_grounded_answer_with_citation(client: AsyncClient, db_session, monkeypatch, fake_tutor_graph):
    tech = Technology(name="React", slug="react")
    db_session.add(tech)
    await db_session.flush()
    resource = Resource(technology_id=tech.id, url="u", normalized_url="u", status=ResourceStatus.ready)
    db_session.add(resource)
    await db_session.flush()

    exact_text = "useEffect cleanup functions run before the component unmounts or re-runs."
    await _seed_react_chunk(db_session, monkeypatch, tech.id, resource.id, exact_text)

    await client.post("/api/auth/register", json={"email": "learner@example.com", "password": "password123"})

    resp = await client.post("/api/conversations", json={"technology_id": tech.id})
    assert resp.status_code == 201
    conversation_id = resp.json()["id"]

    resp = await client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": exact_text},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assistant_message"]["content"] == "Effects clean up on unmount [1]."
    assert body["assistant_message"]["mode"] == "grounded"
    assert body["assistant_message"]["sources"][0]["cited"] is True
    assert body["assistant_message"]["sources"][0]["title"] == "useEffect"


@pytest.mark.asyncio
async def test_chat_general_mode_when_no_chunks_match(client: AsyncClient, db_session, fake_tutor_graph):
    tech = Technology(name="React", slug="react")
    db_session.add(tech)
    await db_session.commit()

    await client.post("/api/auth/register", json={"email": "learner2@example.com", "password": "password123"})
    resp = await client.post("/api/conversations", json={"technology_id": tech.id})
    conversation_id = resp.json()["id"]

    resp = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "anything at all"}
    )
    assert resp.status_code == 200
    assert resp.json()["assistant_message"]["mode"] == "general"
    assert not resp.json()["assistant_message"]["sources"]  # stored as null, not []


@pytest.mark.asyncio
async def test_cannot_message_someone_elses_conversation(client: AsyncClient, db_session, fake_tutor_graph):
    tech = Technology(name="React", slug="react")
    db_session.add(tech)
    await db_session.commit()

    await client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    resp = await client.post("/api/conversations", json={"technology_id": tech.id})
    conversation_id = resp.json()["id"]
    await client.post("/api/auth/logout")

    await client.post("/api/auth/register", json={"email": "intruder@example.com", "password": "password123"})
    resp = await client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "hi"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_conversation_history_persisted_and_returned(client: AsyncClient, db_session, fake_tutor_graph):
    tech = Technology(name="React", slug="react")
    db_session.add(tech)
    await db_session.commit()

    await client.post("/api/auth/register", json={"email": "hist@example.com", "password": "password123"})
    resp = await client.post("/api/conversations", json={"technology_id": tech.id})
    conversation_id = resp.json()["id"]

    await client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "first question"})
    await client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "second question"})

    resp = await client.get(f"/api/conversations/{conversation_id}")
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 4  # 2 user + 2 assistant
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
