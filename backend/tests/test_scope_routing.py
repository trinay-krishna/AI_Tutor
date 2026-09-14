import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda

from src.services.tutor_graph.nodes import make_classify_node, make_refuse_node, route_after_classify
from src.services.tutor_graph.schemas import PlanRequestSchema, ScopeDecision


class FakeStructuredLLM:
    """Mimics `chat_model.with_structured_output(Schema)`: composing it into a
    chain (`prompt | fake.with_structured_output(...)`) yields a canned schema
    instance instead of an AIMessage. `with_structured_output` returns a real
    `Runnable` (`RunnableLambda`) so it composes with `prompt |` like the genuine
    LangChain method does.
    """

    def __init__(self, result: ScopeDecision):
        self._result = result

    def with_structured_output(self, _schema):
        async def _return(_input):
            return self._result

        return RunnableLambda(_return)


@pytest.mark.asyncio
async def test_classify_routes_unrelated_to_refuse():
    fake = FakeStructuredLLM(
        ScopeDecision(scope="unrelated", intent="question", standalone_query="x", reason="off-topic")
    )
    classify = make_classify_node(fake)
    result = await classify({"technology_name": "React", "user_message": "who won the match?", "history": []})
    assert result["scope"] == "unrelated"
    assert route_after_classify(result) == "refuse"


@pytest.mark.asyncio
async def test_classify_routes_technology_question_to_retrieve():
    fake = FakeStructuredLLM(
        ScopeDecision(
            scope="technology", intent="question", standalone_query="How does useEffect work?", reason="on-topic"
        )
    )
    classify = make_classify_node(fake)
    result = await classify({"technology_name": "React", "user_message": "How does useEffect work?", "history": []})
    assert route_after_classify(result) == "retrieve"


@pytest.mark.asyncio
async def test_classify_captures_plan_request():
    fake = FakeStructuredLLM(
        ScopeDecision(
            scope="technology",
            intent="study_plan",
            standalone_query="4 week React study plan",
            plan_request=PlanRequestSchema(duration_weeks=4, start_level="beginner", target_level="advanced"),
            reason="study plan request",
        )
    )
    classify = make_classify_node(fake)
    result = await classify({"technology_name": "React", "user_message": "4 week plan please", "history": []})
    assert result["intent"] == "study_plan"
    assert result["plan_request"]["duration_weeks"] == 4


@pytest.mark.asyncio
async def test_classify_falls_back_when_structured_output_unsupported():
    # FakeListChatModel has no bind_tools support, so with_structured_output raises.
    classify = make_classify_node(FakeListChatModel(responses=["irrelevant"]))
    result = await classify({"technology_name": "React", "user_message": "anything", "history": []})
    assert result["scope"] == "technology"
    assert result["intent"] == "question"
    assert result["standalone_query"] == "anything"


def test_refuse_message_mentions_technology():
    refuse = make_refuse_node()
    result = asyncio.run(refuse({"technology_name": "React"}))
    assert result["mode"] == "refusal"
    assert "React" in result["answer"]
