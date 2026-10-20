"""Parse and check Keeper skill files.

A Keeper skill is a standard Hermes SKILL.md, so Hermes loads it with no
extra setup. The three parts Keeper requires map onto Hermes's own fields:

    name     ->  frontmatter `name`
    trigger  ->  frontmatter `description` plus the "## When to Use" section
    steps    ->  numbered list under "## Procedure"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_STEP_RE = re.compile(r"^\s*\d+\.\s+\S")


class SkillFormatError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class Skill:
    name: str
    description: str
    trigger: str
    steps: list[str]
    meta: dict = field(default_factory=dict)
    text: str = ""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillFormatError(["file must start with a '---' frontmatter block"])
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise SkillFormatError(["frontmatter block is never closed with '---'"]) from None
    meta = {}
    for line in lines[1:end]:
        # Top-level scalar keys only; nested blocks such as metadata: are kept out.
        if line and not line[0].isspace() and not line.startswith("#") and ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("'\"")
    return meta, "\n".join(lines[end + 1:])


def _section(body: str, heading: str) -> list[str]:
    out, inside = [], False
    for line in body.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == heading.lower()
            continue
        if inside:
            out.append(line)
    return out


def parse_skill(text: str) -> Skill:
    """Parse a SKILL.md and raise SkillFormatError listing everything wrong."""
    meta, body = _split_frontmatter(text)
    problems = []
    name = meta.get("name", "")
    description = meta.get("description", "")
    if not NAME_RE.match(name):
        problems.append("frontmatter 'name' must be 2-64 chars of lowercase letters, digits and hyphens")
    if not description:
        problems.append("frontmatter 'description' is missing; it should say when to use the skill")
    trigger = " ".join(l.strip() for l in _section(body, "When to Use") if l.strip())
    if not trigger:
        problems.append("'## When to Use' section (the trigger) is missing or empty")
    steps = [l.strip() for l in _section(body, "Procedure") if _STEP_RE.match(l)]
    if not steps:
        problems.append("'## Procedure' needs at least one numbered step like '1. ...'")
    if problems:
        raise SkillFormatError(problems)
    return Skill(name=name, description=description, trigger=trigger, steps=steps, meta=meta, text=text)


def clean_model_output(text: str) -> str:
    """Strip code fences or chatter a model puts around the file."""
    text = text.strip()
    fence = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("---")
    if start > 0:
        text = text[start:]
    return text.rstrip() + "\n"
