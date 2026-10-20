"""SQLite log of every routed call. The phase 3 dashboard reads this file."""
from __future__ import annotations

import sqlite3
from dataclasses import astuple, dataclass, fields
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT    NOT NULL,  -- UTC, ISO 8601
    task_type         TEXT    NOT NULL,
    model             TEXT    NOT NULL,  -- model the router asked for
    served_model      TEXT,              -- model the API says answered
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    latency_ms        INTEGER NOT NULL,
    cost_usd          REAL,
    status            TEXT    NOT NULL,  -- ok | error
    error             TEXT
)
"""


@dataclass
class CallRecord:
    ts: str
    task_type: str
    model: str
    served_model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int
    cost_usd: float | None
    status: str
    error: str | None = None


_COLUMNS = [f.name for f in fields(CallRecord)]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(SCHEMA)
    return conn


def record(db_path: Path, entry: CallRecord) -> None:
    placeholders = ", ".join("?" for _ in _COLUMNS)
    with _connect(db_path) as conn:
        conn.execute(
            f"INSERT INTO calls ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
            astuple(entry),
        )
    conn.close()


def recent(db_path: Path, limit: int = 20) -> list[CallRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM calls ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [CallRecord(*row) for row in rows]


def summary(db_path: Path) -> list[tuple]:
    """Per model: calls, errors, prompt tokens, completion tokens, avg latency, cost."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT model,
                   COUNT(*),
                   SUM(status = 'error'),
                   COALESCE(SUM(prompt_tokens), 0),
                   COALESCE(SUM(completion_tokens), 0),
                   CAST(AVG(latency_ms) AS INTEGER),
                   COALESCE(SUM(cost_usd), 0.0)
            FROM calls GROUP BY model ORDER BY model
            """
        ).fetchall()
    conn.close()
    return rows
