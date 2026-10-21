"""The /teach, /keep and /drop flow.

/teach  draft a skill from your latest correction (written by Nemotron 3 Ultra)
/keep   save the pending draft into Hermes's skills, so it's used next time
/drop   throw the pending draft away

These run as Hermes quick commands: you type them, and Hermes runs them
without asking the model, so nothing is saved unless you say /keep.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .draft import draft_skill
from .format import parse_skill
from .library import find_skill, skills_root
from .session import last_correction


def _drafts_dir() -> Path:
    return Path(os.environ.get("KEEPER_DATA_DIR", "./data")) / "skill-drafts"


def pending_path() -> Path:
    return _drafts_dir() / "pending.md"


def teach(route_fn=None) -> str:
    correction, context = last_correction()
    kwargs = {"route_fn": route_fn} if route_fn else {}
    skill, served = draft_skill(correction, context, **kwargs)
    found = find_skill(skill.name)
    if found:
        # Same name as an existing skill: redraft as an update to it.
        skill, served = draft_skill(correction, context, existing=found[1], **kwargs)
    path = pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(skill.text, encoding="utf-8")
    verb = "Update" if found else "New"
    steps = "\n".join(f"  {s}" for s in skill.steps)
    return (
        f"{verb} skill proposed by {served or 'the router'}: {skill.name}\n"
        f"When: {skill.trigger}\n"
        f"Steps:\n{steps}\n\n"
        f"Type /keep to save it, or /drop to discard it."
    )


def keep() -> str:
    path = pending_path()
    if not path.exists():
        return "Nothing to keep. Correct me, then type /teach first."
    skill = parse_skill(path.read_text(encoding="utf-8"))
    target = skills_root() / "keeper" / skill.name / "SKILL.md"
    if target.exists():
        backup = _drafts_dir() / "replaced" / f"{skill.name}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(skill.text, encoding="utf-8")
    path.unlink()
    return f"Saved skill {skill.name}. I'll use it from the next conversation on."


def drop() -> str:
    path = pending_path()
    if not path.exists():
        return "No pending skill to drop."
    name = parse_skill(path.read_text(encoding="utf-8")).name
    path.unlink()
    return f"Dropped the draft for {name}."
