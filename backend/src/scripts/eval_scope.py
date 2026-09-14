"""Reliability check for the scope/intent classifier (§7 of the plan).

Runs only the `classify` node (no DB, no retrieval, no generation) against a
labelled case set and prints accuracy plus a confusion matrix. Needs a real
OPENAI_API_KEY -- this exercises the actual fast model, unlike the pytest suite.

Usage:
    uv run python -m src.scripts.eval_scope [path/to/cases.yaml]
"""

import asyncio
import sys
from collections import Counter
from pathlib import Path

import yaml

from src.services.llm import get_fast_llm
from src.services.tutor_graph.nodes import make_classify_node

DEFAULT_CASES_PATH = Path(__file__).resolve().parents[2] / "evals" / "scope_cases.yaml"


async def run_eval(cases_path: Path) -> None:
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    classify = make_classify_node(get_fast_llm())

    scope_confusion: Counter[tuple[str, str]] = Counter()
    intent_confusion: Counter[tuple[str, str]] = Counter()
    failures = []

    for case in cases:
        state = {
            "technology_id": 0,
            "technology_name": case["technology"],
            "technology_description": None,
            "history": [],
            "user_message": case["message"],
        }
        result = await classify(state)
        scope_confusion[(case["expected_scope"], result["scope"])] += 1
        intent_confusion[(case["expected_intent"], result["intent"])] += 1

        if result["scope"] != case["expected_scope"] or result["intent"] != case["expected_intent"]:
            failures.append((case, result))

    total = len(cases)
    scope_correct = sum(1 for (exp, got) in scope_confusion.elements() if exp == got)
    intent_correct = sum(1 for (exp, got) in intent_confusion.elements() if exp == got)

    print(f"Cases: {total}")
    print(f"Scope accuracy:  {scope_correct}/{total} ({scope_correct / total:.1%})")
    print(f"Intent accuracy: {intent_correct}/{total} ({intent_correct / total:.1%})")

    print("\nScope confusion matrix (expected -> got: count):")
    for (exp, got), count in sorted(scope_confusion.items()):
        marker = "" if exp == got else "  <-- MISS"
        print(f"  {exp:12} -> {got:12}: {count}{marker}")

    print("\nIntent confusion matrix (expected -> got: count):")
    for (exp, got), count in sorted(intent_confusion.items()):
        marker = "" if exp == got else "  <-- MISS"
        print(f"  {exp:12} -> {got:12}: {count}{marker}")

    if failures:
        print(f"\n{len(failures)} failing case(s):")
        for case, result in failures:
            print(
                f"  [{case['technology']}] {case['message']!r}\n"
                f"    expected scope={case['expected_scope']} intent={case['expected_intent']}\n"
                f"    got      scope={result['scope']} intent={result['intent']}"
            )

    # The plan's bar: unrelated must never be confused with technology in either direction.
    dangerous = scope_confusion[("unrelated", "technology")] + scope_confusion[("technology", "unrelated")]
    if dangerous:
        print(f"\n WARNING: {dangerous} unrelated<->technology confusion(s) -- see failures above.")
        sys.exit(1)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CASES_PATH
    asyncio.run(run_eval(path))
