"""Read the user's latest correction from Hermes's session log (state.db).

Opened read-only. The exact schema isn't documented, so we look for the
table that has `role` and `content` columns and read it newest first.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def state_db_path() -> Path:
    hermes_home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(os.environ.get("KEEPER_HERMES_STATE_DB", str(Path(hermes_home) / "state.db")))


def _text(content) -> str:
    """Message content may be plain text or a JSON list of parts."""
    if not isinstance(content, str):
        return ""
    stripped = content.strip()
    if stripped[:1] in "[{":
        try:
            data = json.loads(stripped)
        except ValueError:
            return stripped
        parts = data if isinstance(data, list) else [data]
        return " ".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    return stripped


def _messages_table(conn: sqlite3.Connection) -> tuple[str, str]:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for name in sorted(tables, key=lambda t: (t != "messages", t)):
        if "fts" in name.lower():
            continue
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info('{name}')")]
        if "role" in cols and "content" in cols:
            order = "id" if "id" in cols else "rowid"
            return name, order
    raise LookupError("no table with role and content columns in Hermes's state.db")


def last_correction(db_path: Path | None = None) -> tuple[str, str | None]:
    """Return (latest user message that isn't a slash command, Keeper's answer just before it)."""
    db_path = db_path or state_db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Hermes session log not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    try:
        table, order = _messages_table(conn)
        rows = conn.execute(f"SELECT role, content FROM '{table}' ORDER BY {order} DESC LIMIT 200").fetchall()
    finally:
        conn.close()
    correction = None
    for role, content in rows:
        text = _text(content)
        if correction is None:
            if role == "user" and text and not text.startswith("/"):
                correction = text
        elif role == "assistant" and text:
            return correction, text[:1500]
    if correction is None:
        raise LookupError("no recent message from you to learn from")
    return correction, None


def latest_system_prompt(db_path: Path | None = None) -> str:
    """The system prompt Hermes stored for its most recent session."""
    db_path = db_path or state_db_path()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for name in tables:
            if "fts" in name.lower():
                continue
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info('{name}')")]
            col = next((c for c in cols if "system" in c.lower() and "prompt" in c.lower()), None)
            if col:
                order = next((c for c in ("started_at", "created_at", "id") if c in cols), "rowid")
                row = conn.execute(
                    f"SELECT {col} FROM '{name}' WHERE {col} IS NOT NULL ORDER BY {order} DESC LIMIT 1"
                ).fetchone()
                if row:
                    return row[0] or ""
        # Fall back to the newest system message, if sessions keep it there.
        table, order = _messages_table(conn)
        row = conn.execute(
            f"SELECT content FROM '{table}' WHERE role = 'system' ORDER BY {order} DESC LIMIT 1"
        ).fetchone()
        return _text(row[0]) if row else ""
    finally:
        conn.close()


def describe_schema(db_path: Path | None = None) -> list[str]:
    """One line per table in state.db: name(columns). For debugging only."""
    db_path = db_path or state_db_path()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        out = []
        for name in tables:
            if "fts" in name.lower():
                continue
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info('{name}')")]
            out.append(f"{name}({', '.join(cols)})"[:220])
        return out
    finally:
        conn.close()
