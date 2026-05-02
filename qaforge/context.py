"""
Context loader. Reads knowledge.md + the requested SKILL.md files from disk
and concatenates them into a system prompt that QAForge sends to the configured LLM.

Usage:
    from qaforge.context import build_system_prompt, list_skills
    system = build_system_prompt(["test-design"])
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

# Project root is two levels up from this file: qaforge/context.py -> qaforge/ -> root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_PATH = PROJECT_ROOT / "knowledge.md"
SKILLS_DIR = PROJECT_ROOT / "skills"


def list_skills() -> list[str]:
    """Return all skill names that have a SKILL.md file."""
    if not SKILLS_DIR.is_dir():
        return []
    names = [
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
    ]
    names.sort()
    return names


def _resolve_skill_paths(skill_names: Optional[Iterable[str]]) -> list[Path]:
    wanted = list(skill_names) if skill_names else list_skills()
    paths: list[Path] = []
    for name in wanted:
        p = SKILLS_DIR / name / "SKILL.md"
        if not p.is_file():
            raise FileNotFoundError(f'skill "{name}" not found at {p}')
        paths.append(p)
    return paths


def build_system_prompt(skill_names: Optional[Iterable[str]] = None) -> str:
    """
    Build the system prompt: knowledge.md first (authoritative), then each skill.
    Each section is wrapped in clear delimiters so the configured LLM can parse them.
    """
    if not KNOWLEDGE_PATH.is_file():
        raise FileNotFoundError(f"knowledge.md is missing at {KNOWLEDGE_PATH}")

    skill_paths = _resolve_skill_paths(skill_names)

    parts: list[str] = [
        "You are QAForge, an AI test automation engineer.",
        (
            "Follow the rules in <project_knowledge> exactly. "
            "If a skill conflicts with project_knowledge, project_knowledge wins."
        ),
        f"<project_knowledge>\n{KNOWLEDGE_PATH.read_text(encoding='utf-8').strip()}\n</project_knowledge>",
    ]
    for path in skill_paths:
        skill_name = path.parent.name
        body = path.read_text(encoding="utf-8").strip()
        parts.append(f'<skill name="{skill_name}">\n{body}\n</skill>')

    return "\n\n".join(parts)
