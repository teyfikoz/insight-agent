"""Utility to load SkillOpt-managed skill files as agent system prompts."""
from __future__ import annotations

from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def load_skill(name: str, fallback: str = "") -> str:
    """Load a skill markdown file from the skills/ directory.

    Checks for best_skill.md first (SkillOpt's trained artifact),
    then falls back to the seed skill, then to the hardcoded fallback string.

    Args:
        name: Skill name without extension, e.g. "seo_auditor"
        fallback: Hardcoded fallback if no skill file found
    """
    # SkillOpt saves trained artifacts as best_skill.md in skills/<name>/
    trained = _SKILLS_DIR / name / "best_skill.md"
    seed = _SKILLS_DIR / f"{name}.md"

    for path in (trained, seed):
        if path.exists():
            content = path.read_text(encoding="utf-8").strip()
            if content:
                return content

    return fallback
