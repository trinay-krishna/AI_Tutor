"""Tutor graph nodes. Each is a plain async function closing over the models and
vector store handed to it by `build_tutor_graph`, so tests can substitute fakes.
"""

import logging
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from src.config import get_settings
from src.services.prompts import (
    REFUSAL_MESSAGE,
    build_answer_prompt,
    build_classify_prompt,
    build_study_plan_prompt,
    render_sources_block,
)
from src.services.retrieval import RetrievedChunk, retrieve
from src.services.study_plan import (
    build_outline_entries,
    render_markdown,
    render_outline_text,
    validate_plan,
)
from src.services.tutor_graph.schemas import ScopeDecision, StudyPlan
from src.services.tutor_graph.state import RetrievedChunkView, SourceView, TutorState

logger = logging.getLogger(__name__)
settings = get_settings()


def make_classify_node(fast_llm: BaseChatModel) -> Callable:
    """Explicit scope/intent classification via structured output (see §7 of the
    plan) -- never relies on the answer prompt alone to enforce scope. Never sees
    scraped source content, so injected text in a page can't affect routing.
    """
    prompt = build_classify_prompt()

    async def classify(state: TutorState) -> dict:
        try:
            # Built lazily (not at graph-construction time) so a model that can't
            # do structured output fails over per-call instead of breaking the graph.
            chain = prompt | fast_llm.with_structured_output(ScopeDecision)
            decision: ScopeDecision = await chain.ainvoke(
                {
                    "technology_name": state["technology_name"],
                    "history": state.get("history") or [],
                    "message": state["user_message"],
                }
            )
            return {
                "scope": decision.scope,
                "intent": decision.intent,
                "standalone_query": decision.standalone_query or state["user_message"],
                "plan_request": decision.plan_request.model_dump() if decision.plan_request else None,
            }
        except Exception:
            logger.exception("classify failed; falling back to scope=technology")
            return {
                "scope": "technology",
                "intent": "question",
                "standalone_query": state["user_message"],
                "plan_request": None,
            }

    return classify


def make_refuse_node() -> Callable:
    async def refuse(state: TutorState) -> dict:
        return {
            "mode": "refusal",
            "answer": REFUSAL_MESSAGE.format(technology_name=state["technology_name"]),
            "sources": [],
        }

    return refuse


def route_after_classify(state: TutorState) -> str:
    if state.get("scope") == "unrelated":
        return "refuse"
    if state.get("intent") == "study_plan":
        return "build_outline"
    return "retrieve"


def make_build_outline_node() -> Callable:
    async def build_outline(state: TutorState) -> dict:
        entries = await build_outline_entries(state["technology_id"])
        return {"outline_entries": entries}

    return build_outline


def _format_plan_details(plan_request: dict | None) -> str:
    if not plan_request:
        return ""
    parts = []
    if plan_request.get("duration_weeks"):
        parts.append(f"Requested duration: {plan_request['duration_weeks']} weeks.")
    if plan_request.get("start_level"):
        parts.append(f"Starting level: {plan_request['start_level']}.")
    if plan_request.get("target_level"):
        parts.append(f"Target level: {plan_request['target_level']}.")
    if plan_request.get("focus"):
        parts.append(f"Focus: {plan_request['focus']}.")
    return " ".join(parts)


def make_generate_plan_node(main_llm: BaseChatModel) -> Callable:
    prompt = build_study_plan_prompt()

    async def generate_plan(state: TutorState) -> dict:
        entries = state.get("outline_entries") or []
        try:
            chain = prompt | main_llm.with_structured_output(StudyPlan)
            plan: StudyPlan = await chain.ainvoke(
                {
                    "technology_name": state["technology_name"],
                    "request": state.get("standalone_query") or state["user_message"],
                    "plan_details": _format_plan_details(state.get("plan_request")),
                    "outline": render_outline_text(entries),
                }
            )
            return {"study_plan_model": plan}
        except Exception:
            logger.exception("generate_plan failed")
            return {"study_plan_model": None}

    return generate_plan


def make_validate_plan_node() -> Callable:
    async def validate(state: TutorState) -> dict:
        plan: StudyPlan | None = state.get("study_plan_model")
        entries = state.get("outline_entries") or []

        if plan is None:
            return {
                "mode": "general",
                "answer": (
                    "Sorry, I couldn't build a study plan just now. Please try again in a moment."
                ),
                "sources": [],
                "study_plan": None,
            }

        plan = validate_plan(plan, entries)
        has_any_ref = any(t.resource_refs for w in plan.weeks for t in w.topics)

        return {
            "mode": "grounded" if has_any_ref else "general",
            "answer": render_markdown(plan, entries),
            "sources": [],
            "study_plan": plan.model_dump(),
        }

    return validate


def _to_view(chunk: RetrievedChunk) -> RetrievedChunkView:
    meta = chunk.document.metadata
    return RetrievedChunkView(
        content=chunk.document.page_content,
        score=chunk.score,
        resource_id=int(meta.get("resource_id")),
        chunk_id=str(getattr(chunk.document, "id", "") or ""),
        title=meta.get("title"),
        url=meta.get("url"),
        heading_path=meta.get("heading_path"),
    )


def make_retrieve_node() -> Callable:
    async def retrieve_node(state: TutorState) -> dict:
        query = state.get("standalone_query") or state["user_message"]
        chunks = await retrieve(query, state["technology_id"])
        return {"retrieved": [_to_view(c) for c in chunks]}

    return retrieve_node


def _build_sources(retrieved: list[RetrievedChunkView]) -> list[dict]:
    return [
        {
            "n": i + 1,
            "chunk_id": r["chunk_id"],
            "resource_id": r["resource_id"],
            "url": r["url"],
            "title": r["title"],
            "heading_path": r["heading_path"],
            "content": r["content"],
            "score": r["score"],
        }
        for i, r in enumerate(retrieved)
    ]


def _mark_cited(answer: str, sources: list[dict]) -> list[SourceView]:
    result = []
    for s in sources:
        cited = f"[{s['n']}]" in answer
        result.append(
            SourceView(
                n=s["n"],
                chunk_id=s["chunk_id"],
                resource_id=s["resource_id"],
                url=s["url"],
                title=s["title"],
                heading_path=s["heading_path"],
                score=s["score"],
                cited=cited,
            )
        )
    return result


def make_generate_answer_node(main_llm: BaseChatModel) -> Callable:
    async def generate_answer(state: TutorState) -> dict:
        retrieved = state.get("retrieved") or []
        usable = [r for r in retrieved if r["score"] >= settings.rag_min_similarity]
        mode = "grounded" if usable else "general"

        sources = _build_sources(usable)
        prompt = build_answer_prompt(mode)

        try:
            chain = prompt | main_llm
            response = await chain.ainvoke(
                {
                    "technology_name": state["technology_name"],
                    "technology_description": state.get("technology_description") or "",
                    "history": state.get("history") or [],
                    "sources_block": render_sources_block(sources),
                    "question": state["user_message"],
                }
            )
            answer = response.content
        except Exception:
            logger.exception("generate_answer failed")
            return {
                "mode": mode,
                "answer": (
                    "Sorry, I couldn't reach the language model just now. Please try again "
                    "in a moment."
                ),
                "sources": [],
            }

        return {
            "mode": mode,
            "answer": answer,
            "sources": _mark_cited(answer, sources) if mode == "grounded" else [],
        }

    return generate_answer
