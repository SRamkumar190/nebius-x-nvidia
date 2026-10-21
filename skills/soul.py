"""Keeper's sections of SOUL.md, which Hermes puts at the top of every session's prompt.

Two sections, both plain markdown:

- The Keeper section (agent/SOUL.md), from "## Keeper" to "*End of Keeper section.*".
  `agent/deploy.sh` puts it first in the file with `merge_keeper_section`.
- Learned rules, from "### Learned rules" to "*End of learned rules.*", right
  after it. `/keep` adds one line per skill with `pin_rule`.

Hermes only loads a skill's full text when the model asks for it, and
Nemotron 3 Super often doesn't. A one-line rule in SOUL.md is always seen.

Older deploys marked both sections with HTML comments. Hermes scans SOUL.md
for prompt injection, and hidden HTML comments are one of the things it looks
for, so both functions here convert the old markers to the plain ones.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

START = "### Learned rules"
END = "*End of learned rules.*"
KEEPER_END = "*End of Keeper section.*"
OLD_START = "<!-- keeper:learned:start -->"
OLD_END = "<!-- keeper:learned:end -->"
INTRO = "The user taught you these. Always follow them. The full skill has the details if you need them.\n"
_LINE_RE = re.compile(r"^- \*\*(?P<name>[a-z0-9-]+)\*\*: ")
_OLD_KEEPER_RE = re.compile(r"\n*<!-- keeper:start -->.*?<!-- keeper:end -->\n*", re.S)
_KEEPER_RE = re.compile(r"(?m)^## Keeper\n.*?^" + re.escape(KEEPER_END) + r"\n*", re.S)
# The identity paragraph NemoClaw seeds SOUL.md with. Left in, it contradicts
# "Your name is Keeper" a few lines above it.
_STOCK_IDENTITY_RE = re.compile(r"(?m)^You are Hermes Agent\b.*?(?:\n[ \t]*\n|\Z)", re.S)
# Zero-width and bidirectional control characters. Hermes refuses to load a
# context file that contains any of them.
INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF,
     0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069])


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


def strip_invisible(text: str) -> str:
    return text.translate(INVISIBLE)


def _rules(text: str) -> list[str]:
    rules = []
    for start, end in ((START, END), (OLD_START, OLD_END)):
        if start in text:
            block = text.split(start, 1)[1].split(end, 1)[0]
            rules += [l for l in block.splitlines() if _LINE_RE.match(l)]
    return rules


def _strip_sections(text: str) -> str:
    for start, end in ((START, END), (OLD_START, OLD_END)):
        text = re.sub(r"\n*" + re.escape(start) + r".*?" + re.escape(end) + r"\n*", "\n\n", text, flags=re.S)
    return text.strip()


def pin_rule(name: str, rule: str, path: Path | None = None) -> None:
    """Add or replace the learned rule for skill `name` (in every persona file)."""
    if path is None:
        for target in soul_paths():
            pin_rule(name, rule, target)
        return
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    rules = [l for l in _rules(text) if _LINE_RE.match(l)["name"] != name]
    rules.append(f"- **{name}**: {' '.join(strip_invisible(rule).split())}")
    section = f"{START}\n\n{INTRO}\n" + "\n".join(rules) + f"\n\n{END}"
    text = _strip_sections(text)
    if KEEPER_END in text:
        text = text.replace(KEEPER_END, KEEPER_END + "\n\n" + section, 1)
    else:
        text = (text + "\n\n" if text else "") + section
    text = text.rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def merge_keeper_section(current: str, keeper: str) -> str:
    """Put the Keeper section at the top of a SOUL.md that may hold other text.

    The previous Keeper section (either marker style) and NemoClaw's stock
    "You are Hermes Agent" paragraph are dropped. Learned rules and anything
    else stay, after the Keeper section."""
    current = _OLD_KEEPER_RE.sub("\n", current)
    current = _KEEPER_RE.sub("", current)
    current = current.replace(OLD_START + "\n", "").replace(OLD_START, "")
    current = re.sub(r"\n*" + re.escape(OLD_END), "\n\n" + END, current)
    current = _STOCK_IDENTITY_RE.sub("", current)
    current = strip_invisible(current).strip()
    keeper = strip_invisible(keeper).rstrip() + "\n"
    return keeper + "\n" + current + "\n" if current else keeper


def main(argv: list[str]) -> int:
    """python3 -m skills.soul merge <SOUL.md to rewrite> <agent/SOUL.md>"""
    if len(argv) != 3 or argv[0] != "merge":
        print("usage: python3 -m skills.soul merge <SOUL.md to rewrite> <agent/SOUL.md>", file=sys.stderr)
        return 2
    target, keeper = Path(argv[1]), Path(argv[2])
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(merge_keeper_section(current, keeper.read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
