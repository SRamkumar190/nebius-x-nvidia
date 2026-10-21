"""`keeper skills prompt-check`: is Keeper's persona in the prompt Hermes uses?

Prints what each persona file holds, what Hermes's own scanner and SOUL.md
loader make of the one Hermes reads, and what the latest conversation's
stored system prompt contains. It ends with a one-line verdict.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .session import StoredPrompt, describe_schema, latest_stored_prompt
from .soul import END, INVISIBLE, KEEPER_END, START, soul_paths

PROBE = Path(__file__).with_name("hermes_probe.py")


def _when(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "unknown"


def invisible_chars(text: str) -> list[str]:
    """'U+200B on line 3' for each zero-width or bidi control character."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for ch in line:
            if ord(ch) in INVISIBLE:
                found.append(f"U+{ord(ch):04X} ({unicodedata.name(ch, 'unnamed')}) on line {number}")
    return found


def file_report(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path}: missing"]
    text = path.read_text(encoding="utf-8")
    st = path.stat()
    rules = text.split(START, 1)[1].split(END, 1)[0].count("\n- **") if START in text else 0
    keeper_end = text.find(KEEPER_END)
    rest = text[keeper_end:] if keeper_end >= 0 else text
    odd = invisible_chars(text)
    return [
        f"{path}: {len(text)} chars, changed {_when(st.st_mtime)}, owner uid {st.st_uid}, mode {st.st_mode & 0o777:o}",
        f"  starts with Keeper section: {'yes' if text.startswith('## Keeper') else 'NO'}; "
        f"learned rules: {rules}; HTML comments: {text.count('<!--')}; "
        f"'You are Hermes Agent' after Keeper section: {rest.count('You are Hermes Agent')}",
        "  invisible characters: " + ("; ".join(odd[:5]) if odd else "none"),
    ]


def hermes_view(path: Path) -> dict:
    """Run skills/hermes_probe.py with this Python in isolated mode."""
    src = os.environ.get("KEEPER_HERMES_SRC", "/opt/hermes")
    # Point Hermes's loader at the file being checked, so it can't go looking
    # for (or create) a ~/.hermes somewhere else.
    env = dict(os.environ)
    env.setdefault("HERMES_HOME", str(path.parent))
    try:
        done = subprocess.run([sys.executable, "-I", str(PROBE), str(path), src],
                              capture_output=True, text=True, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"scan": f"probe didn't run: {exc}"}
    for line in reversed(done.stdout.splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return {"scan": "probe printed no result: " + " ".join((done.stderr or done.stdout).split())[-300:]}


def run() -> int:
    paths = soul_paths()
    print("Persona files:")
    for path in paths:
        for line in file_report(path):
            print("  " + line)

    read_by_hermes = paths[-1]
    view = hermes_view(read_by_hermes) if read_by_hermes.exists() else {"scan": "file missing"}
    print(f"Hermes's own check of {read_by_hermes}" + (f" ({view['scanner']}):" if view.get("scanner") else ":"))
    print("  scanner: " + view.get("scan", "?"))
    if "load_soul_md" in view:
        print(f"  load_soul_md(): {view['load_soul_md']}")
    if "fallback_identity" in view:
        print(f"  built-in identity, used when SOUL.md isn't loaded: {view['fallback_identity']}")
    for err in view.get("import_errors", [])[:3]:
        print(f"  import error: {err}")

    try:
        stored = latest_stored_prompt()
        print(f"Latest conversation: session {stored.session_id or '?'} ({stored.source or 'source unknown'}), "
              f"started {_when(stored.started_at)}")
        if not stored.prompt:
            print("  (no stored system prompt found; state.db tables, for debugging:)")
            for line in describe_schema():
                print("   " + line)
    except sqlite3.Error as exc:  # no state.db yet, or Hermes is mid-write
        print(f"Latest conversation: couldn't read Hermes's session log ({exc})")
        stored = StoredPrompt("")
    prompt = stored.prompt
    print(f"  system prompt: {len(prompt)} chars")
    for needle in ("Your name is Keeper", "Learned rules", "/teach"):
        print(f"  contains {needle!r}: {'yes' if needle in prompt else 'NO'}")
    print("  starts with: " + " ".join(prompt[:200].split()))

    soul_changed = read_by_hermes.stat().st_mtime if read_by_hermes.exists() else None
    stale = bool(stored.started_at and soul_changed and stored.started_at < soul_changed)
    print("Verdict: " + verdict(view.get("scan", ""), "Your name is Keeper" in prompt, stale, bool(prompt)))
    return 0


def verdict(scan: str, keeper_in_prompt: bool, stale: bool, have_prompt: bool) -> str:
    if scan.startswith("BLOCKED"):
        return "Hermes refuses to load SOUL.md (see the scanner line). Send me this output."
    if keeper_in_prompt:
        return "Keeper's persona is in the prompt."
    if stale or not have_prompt:
        return ("no conversation since SOUL.md last changed, so the stored prompt is older than the persona. "
                "Start a new chat, send one message, type /exit, and run this again.")
    if scan.startswith("passes"):
        return "SOUL.md passes Hermes's scanner, but the latest prompt doesn't have it. Send me this output."
    return "the latest prompt doesn't have Keeper's persona, and Hermes's scanner couldn't be run. Send me this output."
