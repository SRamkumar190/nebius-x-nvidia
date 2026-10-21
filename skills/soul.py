"""Keep learned rules in SOUL.md, which Hermes puts in every session's prompt.

Hermes only loads a skill's full text when the model asks for it, and
Nemotron 3 Super often doesn't. A one-line rule in SOUL.md is always seen.
The list sits between its own markers, so `agent/deploy.sh` (which only
replaces the keeper:start/end block) leaves it alone.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

START = "<!-- keeper:learned:start -->"
END = "<!-- keeper:learned:end -->"
HEADING = "### Learned rules\n\nThe user taught you these. Always follow them. The full skill has the details if you need them.\n"
_LINE_RE = re.compile(r"^- \*\*(?P<name>[a-z0-9-]+)\*\*: ")


def soul_paths() -> list[Path]:
    """Both persona files. NemoClaw keeps /sandbox/SOUL.md as the durable one and
    appears to copy it over ~/.hermes/SOUL.md (what Hermes reads) on start,
    so learned rules go into both."""
    if os.environ.get("KEEPER_SOUL_FILES"):
        return [Path(p) for p in os.environ["KEEPER_SOUL_FILES"].split(os.pathsep) if p]
    hermes_home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return [Path.home() / "SOUL.md", Path(hermes_home) / "SOUL.md"]


def soul_path() -> Path:
    return soul_paths()[-1]


def _rules(text: str) -> list[str]:
    if START not in text:
        return []
    block = text.split(START, 1)[1].split(END, 1)[0]
    return [l for l in block.splitlines() if _LINE_RE.match(l)]


def pin_rule(name: str, rule: str, path: Path | None = None) -> None:
    """Add or replace the learned rule for skill `name` (in every persona file)."""
    if path is None:
        for target in soul_paths():
            pin_rule(name, rule, target)
        return
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    rules = [l for l in _rules(text) if _LINE_RE.match(l)["name"] != name]
    rules.append(f"- **{name}**: {' '.join(rule.split())}")
    section = f"{START}\n{HEADING}\n" + "\n".join(rules) + f"\n{END}"
    if START in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), section, text, count=1, flags=re.S)
    elif "<!-- keeper:end -->" in text:
        text = text.replace("<!-- keeper:end -->", "<!-- keeper:end -->\n\n" + section, 1)
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + section + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
