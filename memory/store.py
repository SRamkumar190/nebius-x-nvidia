"""Markdown memory files under KEEPER_DATA_DIR/memory.

Each topic is one file, `<topic>.md`, with a heading and one dated bullet per
entry:

    # Deadlines

    - 2026-10-20 14:03 UTC | NVIDIA GTC student hackathon closes Nov 1

Plain markdown so you can read and fix the files by hand, and so Hermes can
read them with its normal file tools.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_ENTRY_RE = re.compile(r"^- (?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC) \| (?P<text>.*)$")


class BadTopic(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    topic: str
    when: str
    text: str


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


class MemoryStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, topic: str) -> Path:
        if not _TOPIC_RE.match(topic):
            raise BadTopic(
                f"topic {topic!r} must be lowercase letters, digits and hyphens, e.g. 'deadlines'"
            )
        return self.root / f"{topic}.md"

    def topics(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.md") if _TOPIC_RE.match(p.stem))

    def entries(self, topic: str) -> list[Entry]:
        path = self._path(topic)
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _ENTRY_RE.match(line)
            if m:
                out.append(Entry(topic, m["when"], m["text"]))
        return out

    def contains(self, topic: str, text: str) -> bool:
        """True if an entry with the same text (ignoring case and spacing) exists."""
        wanted = _normalize(text)
        return any(_normalize(e.text) == wanted for e in self.entries(topic))

    def add(self, topic: str, text: str, *, when: datetime | None = None, dedupe: bool = True) -> bool:
        """Append one entry. Returns False if dedupe found the same text already there."""
        text = " ".join(text.split())
        if not text:
            raise ValueError("memory entry is empty")
        if dedupe and self.contains(topic, text):
            return False
        path = self._path(topic)
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = (when or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        new_file = not path.exists()
        with path.open("a", encoding="utf-8") as f:
            if new_file:
                f.write(f"# {topic.replace('-', ' ').capitalize()}\n\n")
            f.write(f"- {stamp} | {text}\n")
        return True

    def search(self, query: str) -> list[Entry]:
        """Entries in any topic whose text contains every word of the query."""
        words = _normalize(query).split()
        return [
            e for topic in self.topics() for e in self.entries(topic)
            if all(w in _normalize(e.text) for w in words)
        ]


def default_store() -> MemoryStore:
    data_dir = Path(os.environ.get("KEEPER_DATA_DIR", "./data"))
    return MemoryStore(data_dir / "memory")
