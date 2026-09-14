import pytest

from src.services.study_plan import OutlineEntry, render_markdown, validate_plan
from src.services.tutor_graph.schemas import StudyPlan, StudyTopic, StudyWeek


def _entries():
    return [
        OutlineEntry(n=1, resource_id=101, title="Quick Start", url="https://x/1", headings=["Install"], excerpt="a"),
        OutlineEntry(n=2, resource_id=102, title="Hooks Guide", url="https://x/2", headings=["useEffect"], excerpt="b"),
    ]


def _plan(refs_week1, refs_week2):
    return StudyPlan(
        title="Learn X",
        duration_weeks=2,
        start_level="beginner",
        target_level="advanced",
        weeks=[
            StudyWeek(
                week=1, theme="Basics", goals=["g1"], estimated_hours=5,
                topics=[StudyTopic(name="Installing", why="setup", resource_refs=refs_week1)],
            ),
            StudyWeek(
                week=2, theme="Advanced", goals=["g2"], estimated_hours=5,
                topics=[StudyTopic(name="Hooks", why="core", resource_refs=refs_week2)],
            ),
        ],
    )


def test_invalid_resource_refs_are_stripped():
    plan = _plan(refs_week1=[1, 99], refs_week2=[2])
    validated = validate_plan(plan, _entries())
    assert validated.weeks[0].topics[0].resource_refs == [1]  # 99 doesn't exist -> dropped
    assert validated.weeks[1].topics[0].resource_refs == [2]


def test_topic_with_no_valid_refs_is_labelled_general_knowledge():
    plan = _plan(refs_week1=[99], refs_week2=[2])
    validated = validate_plan(plan, _entries())
    assert validated.weeks[0].topics[0].resource_refs == []
    assert "(general knowledge)" in validated.weeks[0].topics[0].name


def test_topic_never_labelled_twice():
    plan = _plan(refs_week1=[], refs_week2=[2])
    plan.weeks[0].topics[0].name = "Installing (general knowledge)"
    validated = validate_plan(plan, _entries())
    assert validated.weeks[0].topics[0].name.count("(general knowledge)") == 1


def test_render_markdown_includes_only_cited_resources():
    plan = _plan(refs_week1=[1], refs_week2=[])
    md = render_markdown(plan, _entries())
    assert "[Quick Start]" in md
    assert "Hooks Guide" not in md  # never referenced after validation-time filtering
    assert "Week 1: Basics" in md
    assert "Week 2: Advanced" in md
