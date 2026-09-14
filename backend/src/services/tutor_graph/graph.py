"""Builds the compiled tutor LangGraph.

START -> classify -> retrieve -> generate_answer -> END

(Conditional routing to a `refuse` node for unrelated questions, and a
build_outline -> generate_plan -> validate_plan branch for study-plan requests,
are added in later phases without changing this shape.)
"""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.services.llm import get_fast_llm, get_main_llm
from src.services.tutor_graph.nodes import (
    make_build_outline_node,
    make_classify_node,
    make_generate_answer_node,
    make_generate_plan_node,
    make_refuse_node,
    make_retrieve_node,
    make_validate_plan_node,
    route_after_classify,
)
from src.services.tutor_graph.state import TutorState


def build_tutor_graph(main_llm: BaseChatModel, fast_llm: BaseChatModel) -> CompiledStateGraph:
    graph = StateGraph(TutorState)

    graph.add_node("classify", make_classify_node(fast_llm))
    graph.add_node("refuse", make_refuse_node())
    graph.add_node("retrieve", make_retrieve_node())
    graph.add_node("generate_answer", make_generate_answer_node(main_llm))
    graph.add_node("build_outline", make_build_outline_node())
    graph.add_node("generate_plan", make_generate_plan_node(main_llm))
    graph.add_node("validate_plan", make_validate_plan_node())

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"refuse": "refuse", "retrieve": "retrieve", "build_outline": "build_outline"},
    )
    graph.add_edge("refuse", END)
    graph.add_edge("retrieve", "generate_answer")
    graph.add_edge("generate_answer", END)
    graph.add_edge("build_outline", "generate_plan")
    graph.add_edge("generate_plan", "validate_plan")
    graph.add_edge("validate_plan", END)

    return graph.compile()


@lru_cache
def get_compiled_tutor_graph() -> CompiledStateGraph:
    """Built lazily on first use (not at import time or app startup) so importing
    this module never requires OPENAI_API_KEY to be set -- constructing ChatOpenAI
    validates credentials eagerly.
    """
    return build_tutor_graph(get_main_llm(), get_fast_llm())
