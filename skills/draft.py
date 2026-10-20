"""Turn a user's correction into a skill draft, written by Nemotron 3 Ultra."""
from __future__ import annotations

from router import route

from .format import Skill, SkillFormatError, clean_model_output, parse_skill

SYSTEM_PROMPT = """You write skills for Keeper, a personal assistant that runs on Hermes Agent.
A skill is one SKILL.md file. Reply with ONLY the file, no code fences and no commentary, in exactly this shape:

---
name: lowercase-words-with-hyphens
description: Use when <the trigger>. <What the skill makes Keeper do, one sentence.>
version: 1.0.0
---

# <Short title>

## When to Use
<The trigger: the requests or situations that should load this skill. 1 to 3 sentences.>

## Procedure
1. <A concrete instruction Keeper can follow.>
2. <Another one. Use as many steps as needed, usually 2 to 6.>

## Pitfalls
- <A mistake to avoid, with a short reason. Optional.>

Rules:
- Turn the correction into a general rule Keeper can apply next time, not a story about this chat.
- No dates, names of chat participants, or quoted conversation.
- Keep it under 250 words.
"""


def _user_prompt(correction: str, context: str | None, existing: Skill | None) -> str:
    parts = [f"The user's correction:\n{correction.strip()}"]
    if context:
        parts.append(f"What Keeper did that the user corrected:\n{context.strip()}")
    if existing:
        parts.append(
            "Update this existing skill instead of writing a new one. Keep the same name, "
            "raise the minor version, and return the complete updated file:\n\n" + existing.text
        )
    return "\n\n".join(parts)


def draft_skill(correction: str, context: str | None = None, existing: Skill | None = None,
                *, route_fn=route) -> tuple[Skill, str | None]:
    """Return (skill, served_model). Retries once if the first draft breaks the format."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(correction, context, existing)},
    ]
    last_error = None
    for _ in range(2):
        resp = route_fn("skill_write", messages, max_tokens=4096)
        text = clean_model_output(resp.choices[0].message.content or "")
        try:
            skill = parse_skill(text)
        except SkillFormatError as exc:
            last_error = exc
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": "That file breaks the format: " + "; ".join(exc.problems)
                 + ". Reply with the corrected complete file only."},
            ]
            continue
        if existing and skill.name != existing.name:
            skill = parse_skill(text.replace(f"name: {skill.name}", f"name: {existing.name}", 1))
        return skill, getattr(resp, "model", None)
    raise last_error
