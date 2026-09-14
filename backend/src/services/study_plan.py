"""Study-plan outline building, grounding validation, and markdown rendering.

Coverage-based retrieval (not top-k): a single similarity query for "make me a
4-week plan" would surface a handful of unrelated chunks, so instead we build a
outline of every onboarded, ready resource for the technology and let the model
organize *that* into a progression.
"""

import logging

from pydantic import BaseModel
from sqlalchemy import select

from src.config import get_settings
from src.db import AsyncSessionLocal
from src.models import Document, Resource, ResourceStatus
from src.services.tutor_graph.schemas import StudyPlan

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_OUTLINE_RESOURCES = 60
EXCERPT_CHARS = 300
MAX_HEADINGS_PER_RESOURCE = 12


class OutlineEntry(BaseModel):
    n: int
    resource_id: int
    title: str
    url: str
    headings: list[str]
    excerpt: str


async def build_outline_entries(technology_id: int) -> list[OutlineEntry]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document)
            .join(Resource, Resource.id == Document.resource_id)
            .where(Resource.technology_id == technology_id, Resource.status == ResourceStatus.ready)
            .order_by(Document.created_at)
            .limit(MAX_OUTLINE_RESOURCES)
        )
        documents = result.scalars().all()

    entries = []
    for i, doc in enumerate(documents):
        headings = [h["text"] for h in (doc.outline or [])][:MAX_HEADINGS_PER_RESOURCE]
        entries.append(
            OutlineEntry(
                n=i + 1,
                resource_id=doc.resource_id,
                title=doc.title or doc.url,
                url=doc.url,
                headings=headings,
                excerpt=doc.content[:EXCERPT_CHARS].strip(),
            )
        )
    return entries


def render_outline_text(entries: list[OutlineEntry]) -> str:
    if not entries:
        return "(No resources have been onboarded for this technology yet.)"
    blocks = []
    for e in entries:
        headings = ", ".join(e.headings) if e.headings else "(no headings extracted)"
        blocks.append(f"[{e.n}] {e.title} ({e.url})\nHeadings: {headings}\nExcerpt: {e.excerpt}...")
    return "\n\n".join(blocks)


def validate_plan(plan: StudyPlan, entries: list[OutlineEntry]) -> StudyPlan:
    valid_ns = {e.n for e in entries}
    unreferenced = 0
    total_topics = 0

    for week in plan.weeks:
        for topic in week.topics:
            total_topics += 1
            topic.resource_refs = [n for n in topic.resource_refs if n in valid_ns]
            if not topic.resource_refs and "(general knowledge)" not in topic.name:
                topic.name = f"{topic.name} (general knowledge)"
                unreferenced += 1

    if total_topics and unreferenced / total_topics > 0.5:
        logger.warning(
            "Study plan for a technology has %d/%d topics with no onboarded resource reference",
            unreferenced,
            total_topics,
        )

    return plan


def render_markdown(plan: StudyPlan, entries: list[OutlineEntry]) -> str:
    by_n = {e.n: e for e in entries}
    lines = [f"## {plan.title}", f"*{plan.duration_weeks} weeks · {plan.start_level} → {plan.target_level}*"]

    if plan.prerequisites:
        lines.append("\n**Prerequisites:** " + ", ".join(plan.prerequisites))

    for week in plan.weeks:
        lines.append(f"\n### Week {week.week}: {week.theme}")
        lines.append(f"*~{week.estimated_hours}h*")
        if week.goals:
            lines.append("\n**Goals:**")
            lines.extend(f"- {g}" for g in week.goals)

        lines.append("\n**Topics:**")
        for topic in week.topics:
            refs = " ".join(f"[{n}]" for n in topic.resource_refs)
            lines.append(f"- **{topic.name}** {refs} — {topic.why}")
            for section in topic.sections:
                lines.append(f"  - {section}")

        if week.exercises:
            lines.append("\n**Exercises:**")
            lines.extend(f"- {ex}" for ex in week.exercises)
        if week.mini_project:
            lines.append(f"\n**Mini-project:** {week.mini_project}")

    if plan.coverage_gaps:
        lines.append("\n### Not covered by the onboarded resources")
        lines.extend(f"- {gap}" for gap in plan.coverage_gaps)

    if plan.notes:
        lines.append(f"\n{plan.notes}")

    if entries:
        lines.append("\n### Resources")
        for e in entries:
            if any(e.n in t.resource_refs for w in plan.weeks for t in w.topics):
                lines.append(f"[{e.n}] [{e.title}]({e.url})")

    return "\n".join(lines)
