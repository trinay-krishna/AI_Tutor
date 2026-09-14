import uuid

import pytest
from httpx import AsyncClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.runnables import RunnableLambda

from src.deps import get_tutor_graph
from src.main import app
from src.models import Document as DocumentModel
from src.models import Resource, ResourceStatus, Technology
from src.services.tutor_graph.graph import build_tutor_graph
from src.services.tutor_graph.schemas import ScopeDecision, StudyPlan, StudyTopic, StudyWeek


class FakeMultiSchemaLLM:
    """Returns a different canned structured-output result depending on which
    schema `with_structured_output` was asked for -- lets one fake model stand in
    for both the classify (ScopeDecision) and generate_plan (StudyPlan) calls.
    """

    def __init__(self, results_by_schema: dict):
        self._results = results_by_schema

    def with_structured_output(self, schema):
        result = self._results[schema]

        async def _return(_input):
            return result

        return RunnableLambda(_return)


@pytest.mark.asyncio
async def test_study_plan_end_to_end(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(
        "src.services.vector_store.get_embeddings", lambda: DeterministicFakeEmbedding(size=1536)
    )

    tech = Technology(name="React", slug="react")
    db_session.add(tech)
    await db_session.flush()
    resource = Resource(technology_id=tech.id, url="https://react.dev/x", normalized_url="u", status=ResourceStatus.ready)
    db_session.add(resource)
    await db_session.flush()
    doc = DocumentModel(
        id=uuid.uuid4(), resource_id=resource.id, technology_id=tech.id, url="https://react.dev/x",
        title="useEffect Guide", content="Intro to effects.", outline=[{"level": 1, "text": "useEffect"}],
        content_hash="h",
    )
    db_session.add(doc)
    await db_session.commit()

    decision = ScopeDecision(
        scope="technology", intent="study_plan", standalone_query="4 week React plan", reason="plan request"
    )
    plan = StudyPlan(
        title="4-Week React Plan",
        duration_weeks=4,
        start_level="beginner",
        target_level="advanced",
        weeks=[
            StudyWeek(
                week=1, theme="Fundamentals", goals=["Learn JSX"], estimated_hours=6,
                topics=[StudyTopic(name="useEffect", why="core hook", resource_refs=[1])],
            )
        ],
        coverage_gaps=["Testing"],
    )
    fake_llm = FakeMultiSchemaLLM({ScopeDecision: decision, StudyPlan: plan})
    graph = build_tutor_graph(fake_llm, fake_llm)
    app.dependency_overrides[get_tutor_graph] = lambda: graph

    try:
        await client.post("/api/auth/register", json={"email": "planner@example.com", "password": "password123"})
        resp = await client.post("/api/conversations", json={"technology_id": tech.id})
        conversation_id = resp.json()["id"]

        resp = await client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "Create me a 4-week study plan for React"},
        )
        assert resp.status_code == 200
        assistant = resp.json()["assistant_message"]
        assert assistant["intent"] == "study_plan"
        assert assistant["mode"] == "grounded"
        assert "4-Week React Plan" in assistant["content"]
        assert "useEffect Guide" in assistant["content"]  # cited resource rendered
    finally:
        app.dependency_overrides.pop(get_tutor_graph, None)


@pytest.mark.asyncio
async def test_study_plan_falls_back_to_general_with_no_resources(client: AsyncClient, db_session, monkeypatch):
    monkeypatch.setattr(
        "src.services.vector_store.get_embeddings", lambda: DeterministicFakeEmbedding(size=1536)
    )
    tech = Technology(name="EmptyTech", slug="emptytech")
    db_session.add(tech)
    await db_session.commit()

    decision = ScopeDecision(
        scope="technology", intent="study_plan", standalone_query="plan please", reason="plan request"
    )
    plan = StudyPlan(
        title="General Plan", duration_weeks=2, start_level="beginner", target_level="intermediate",
        weeks=[
            StudyWeek(
                week=1, theme="Basics", goals=["g"], estimated_hours=4,
                topics=[StudyTopic(name="Basics", why="general", resource_refs=[])],
            )
        ],
    )
    fake_llm = FakeMultiSchemaLLM({ScopeDecision: decision, StudyPlan: plan})
    graph = build_tutor_graph(fake_llm, fake_llm)
    app.dependency_overrides[get_tutor_graph] = lambda: graph

    try:
        await client.post("/api/auth/register", json={"email": "planner2@example.com", "password": "password123"})
        resp = await client.post("/api/conversations", json={"technology_id": tech.id})
        conversation_id = resp.json()["id"]
        resp = await client.post(
            f"/api/conversations/{conversation_id}/messages", json={"content": "plan please"}
        )
        assistant = resp.json()["assistant_message"]
        assert assistant["mode"] == "general"
        assert "(general knowledge)" in assistant["content"]
    finally:
        app.dependency_overrides.pop(get_tutor_graph, None)
