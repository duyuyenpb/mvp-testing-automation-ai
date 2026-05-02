"""
Week 1 end-to-end smoke test: combine context.py + llm.py and verify the configured LLM
answers questions with project-aware context (mentions QAForge folder layout
and Python locator strategy).
"""
from __future__ import annotations

import sys

from qaforge.context import build_system_prompt
from qaforge.llm import ask_llm

DEFAULT_QUESTION = (
    "In one short paragraph: where do generated test specs and Page Objects "
    "live in this project, and what locator strategies must I prefer?"
)


def run(question: str | None = None) -> int:
    user_question = (question or DEFAULT_QUESTION).strip() or DEFAULT_QUESTION

    print("[integration] loading project context (knowledge.md + skills)…", file=sys.stderr)
    system = build_system_prompt()
    print(f"[integration] system prompt: {len(system)} chars", file=sys.stderr)

    print("[integration] asking configured LLM…", file=sys.stderr)
    result = ask_llm(system=system, user=user_question)

    print("\n--- LLM says ---\n")
    print(result.text)
    print("\n-------------------\n")

    lower = result.text.lower()
    checks: list[tuple[str, bool]] = [
        ("mentions tests/specs path", "tests/specs" in lower),
        ("mentions tests/pages path", "tests/pages" in lower),
        (
            "mentions a preferred locator API",
            any(k in lower for k in ("get_by_role", "get_by_label", "get_by_test_id", "get_by_placeholder")),
        ),
    ]

    passed = 0
    for label, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {label}", file=sys.stderr)
        if ok:
            passed += 1

    print(
        f"\n[integration] {passed}/{len(checks)} checks passed. "
        f"tokens: in={result.input_tokens} out={result.output_tokens}",
        file=sys.stderr,
    )
    return 0 if passed >= 2 else 2


if __name__ == "__main__":
    sys.exit(run(" ".join(sys.argv[1:]).strip() or None))
