"""LangGraph state for the tutor graph.

A TypedDict rather than a Pydantic model, per LangGraph convention -- nodes return
partial dict updates that LangGraph merges into the running state.
"""

from typing import Literal, TypedDict

from langchain_core.messages import BaseMessage


class RetrievedChunkView(TypedDict):
    content: str
    score: float
    resource_id: int
    chunk_id: str
    title: str | None
    url: str | None
    heading_path: str | None


class SourceView(TypedDict):
    n: int
    chunk_id: str
    resource_id: int
    url: str | None
    title: str | None
    heading_path: str | None
    score: float
    cited: bool


class PlanRequest(TypedDict, total=False):
    duration_weeks: int | None
    start_level: str | None
    target_level: str | None
    focus: str | None


class TutorState(TypedDict, total=False):
    # --- inputs ---
    technology_id: int
    technology_name: str
    technology_description: str | None
    history: list[BaseMessage]
    user_message: str

    # --- classifier outputs ---
    scope: Literal["technology", "related", "unrelated"]
    intent: Literal["question", "study_plan"]
    standalone_query: str
    plan_request: PlanRequest | None

    # --- retrieval ---
    retrieved: list[RetrievedChunkView]

    # --- study plan ---
    outline_entries: list  # list[services.study_plan.OutlineEntry]
    study_plan_model: object  # services.tutor_graph.schemas.StudyPlan, pre-validation

    # --- results ---
    mode: Literal["grounded", "general", "refusal"]
    answer: str
    sources: list[SourceView]
    study_plan: dict | None
