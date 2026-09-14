"""Structured-output schemas for LLM calls inside the tutor graph."""

from typing import Literal

from pydantic import BaseModel, Field


class PlanRequestSchema(BaseModel):
    duration_weeks: int | None = Field(default=None, description="Requested plan length in weeks, if stated")
    start_level: str | None = Field(default=None, description='e.g. "beginner", "intermediate"')
    target_level: str | None = Field(default=None, description='e.g. "advanced", "job-ready"')
    focus: str | None = Field(default=None, description="Any topic focus the user asked for")


class ScopeDecision(BaseModel):
    """The tutor's routing decision for one user message."""

    scope: Literal["technology", "related", "unrelated"] = Field(
        description=(
            "'technology': about the selected technology or its ecosystem. "
            "'related': about other software/programming/CS/dev-tooling topics, or "
            "meta questions like greetings or 'what can you do'. "
            "'unrelated': anything else (sports, news, recipes, personal advice, etc.)."
        )
    )
    intent: Literal["question", "study_plan"] = Field(
        description="'study_plan' if the user is asking for a learning/study plan or curriculum."
    )
    standalone_query: str = Field(
        description=(
            "The user's message rewritten as a standalone question using the conversation "
            "history, so it makes sense without any prior context. If it's already "
            "standalone, repeat it as-is."
        )
    )
    plan_request: PlanRequestSchema | None = Field(
        default=None, description="Filled in only when intent is 'study_plan'."
    )
    reason: str = Field(description="One short phrase explaining the scope decision.")


# --- Study plan generation ---


class StudyTopic(BaseModel):
    name: str
    why: str = Field(description="One sentence on why this topic matters / where it fits")
    resource_refs: list[int] = Field(
        default_factory=list, description="Numbers of onboarded resources (from the outline) that cover this topic"
    )
    sections: list[str] = Field(
        default_factory=list, description="Specific section/heading names within those resources, if known"
    )


class StudyWeek(BaseModel):
    week: int
    theme: str
    goals: list[str]
    estimated_hours: int
    topics: list[StudyTopic]
    exercises: list[str] = Field(default_factory=list)
    mini_project: str | None = None


class StudyPlan(BaseModel):
    title: str
    duration_weeks: int
    start_level: str
    target_level: str
    prerequisites: list[str] = Field(default_factory=list)
    weeks: list[StudyWeek]
    coverage_gaps: list[str] = Field(
        default_factory=list,
        description="Topics the plan should ideally cover but the onboarded resources don't -- "
        "never invent a resource to fill this instead.",
    )
    notes: str | None = None
