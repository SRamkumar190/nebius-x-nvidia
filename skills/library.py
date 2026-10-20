"""Find skills on disk, in Hermes's skills directory."""
from __future__ import annotations

import os
from pathlib import Path

from .format import Skill, SkillFormatError, parse_skill


def skills_root() -> Path:
    if os.environ.get("KEEPER_SKILLS_DIR"):
        return Path(os.environ["KEEPER_SKILLS_DIR"])
    hermes_home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(hermes_home) / "skills"


def iter_skills(root: Path | None = None):
    """Yield (path, Skill or None). None means the file failed Keeper's format check."""
    root = root or skills_root()
    for path in sorted(root.rglob("SKILL.md")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue  # Hermes hub state, quarantine and so on
        try:
            yield path, parse_skill(path.read_text(encoding="utf-8"))
        except SkillFormatError:
            yield path, None


def find_skill(name: str, root: Path | None = None) -> tuple[Path, Skill] | None:
    for path, skill in iter_skills(root):
        if skill and skill.name == name:
            return path, skill
    return None
