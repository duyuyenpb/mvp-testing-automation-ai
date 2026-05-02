"""
Test planner — Week 2.

Turns a free-form feature description into a Markdown test plan that follows
the format defined in skills/test-design/SKILL.md.

Public API:
    plan_feature(description) -> PlanResult        # ask configured LLM, return markdown
    save_plan(markdown, slug, root) -> Path        # write to test-plans/NNN-slug.md
    next_counter(test_plans_dir) -> int            # 3-digit auto-increment
    slugify(text) -> str                           # filesystem-safe slug
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from qaforge.context import PROJECT_ROOT, build_system_prompt
from qaforge.llm import ask_llm

TEST_PLANS_DIR = PROJECT_ROOT / "test-plans"

# Strip any opening/closing ``` fences if the LLM ignored the rule about raw markdown.
_FENCE_OPEN = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n")
_FENCE_CLOSE = re.compile(r"\n\s*```\s*$")
_REQUIRED_HEADERS = ("# Test Plan:", "## Feature Summary", "## Test Cases", "## Out of Scope")


@dataclass(frozen=True)
class PlanResult:
    markdown: str
    title: str
    slug: str
    input_tokens: int
    output_tokens: int
    model: str


def plan_feature(description: str, *, model: Optional[str] = None) -> PlanResult:
    """Ask the configured LLM (with the test-design skill loaded) for a test plan."""
    description = description.strip()
    if not description:
        raise ValueError("feature description is empty")

    system = build_system_prompt(["test-design"])
    user = (
        "Generate a Markdown test plan for the following feature. "
        "Output the Markdown only — no preamble, no closing remarks, "
        "no surrounding code fences.\n\n"
        f"FEATURE:\n{description}"
    )

    result = ask_llm(system=system, user=user, model=model)
    markdown = _normalise_markdown(result.text)
    _validate_markdown(markdown)

    title = _extract_title(markdown)
    return PlanResult(
        markdown=markdown,
        title=title,
        slug=slugify(title),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        model=result.model,
    )


def save_plan(markdown: str, slug: str, *, root: Path = PROJECT_ROOT) -> Path:
    """Write a plan to test-plans/NNN-slug.md (auto-numbered, 3-digit padded)."""
    plans_dir = root / "test-plans"
    plans_dir.mkdir(exist_ok=True)
    counter = next_counter(plans_dir)
    filename = f"{counter:03d}-{slug}.md"
    path = plans_dir / filename
    path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
    return path


def next_counter(plans_dir: Path) -> int:
    """Return the next 3-digit counter for plans_dir/NNN-*.md, starting at 1."""
    if not plans_dir.is_dir():
        return 1
    used: list[int] = []
    for entry in plans_dir.iterdir():
        match = re.match(r"^(\d{3})-", entry.name)
        if match and entry.is_file() and entry.suffix == ".md":
            used.append(int(match.group(1)))
    return (max(used) + 1) if used else 1


def slugify(text: str) -> str:
    """Make a filesystem-safe kebab-case slug. Strips diacritics conservatively."""
    text = text.strip().lower()
    # Replace anything that isn't alphanumeric with a dash.
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "plan"


# ----------------------- internal helpers -----------------------


def _normalise_markdown(text: str) -> str:
    text = text.strip()
    text = _FENCE_OPEN.sub("", text, count=1)
    text = _FENCE_CLOSE.sub("", text, count=1)
    return text.strip()


def _validate_markdown(markdown: str) -> None:
    """Surface obvious format violations early so the user can re-roll."""
    missing = [h for h in _REQUIRED_HEADERS if h not in markdown]
    if missing:
        raise ValueError(
            "Generated plan is missing required headers: "
            + ", ".join(repr(m) for m in missing)
        )
    if "TC-001" not in markdown:
        raise ValueError("Generated plan does not contain TC-001 — at least one test case is required.")


def _extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# Test Plan:"):
            return line[len("# Test Plan:") :].strip()
    return "untitled"
