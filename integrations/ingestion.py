"""Page Gmail identities first, then isolate failures per message."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from keeper_core.ingest import insert_email_once
from keeper_core.time import to_storage


def ingest(gmail, db_path: Path, *, run_id: str, page_size: int = 100):
    if not run_id or not 1 <= page_size <= 500:
        raise ValueError("run ID and bounded page size required")
    counts = dict(stored=0, duplicate=0, failed=0, page_failed=0)
    cursor = None
    seen_cursors = set()
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")

        def outcome(provider_id, status, error=None):
            conn.execute("""INSERT INTO ingestion_outcomes
                (run_id, provider_id, outcome, error_type, processed_at) VALUES (?, ?, ?, ?, ?)""",
                (run_id, provider_id, status, error, to_storage(datetime.now(timezone.utc))))
            counts[status] += 1

        while True:
            try:
                ids, next_cursor = gmail.list_message_ids(cursor=cursor, limit=page_size)
                if next_cursor is not None and next_cursor in seen_cursors:
                    raise ValueError("repeated page cursor")
            except Exception as exc:
                with conn:
                    outcome(None, "page_failed", type(exc).__name__)
                break
            for provider_id in ids:
                try:
                    with conn:
                        exists = conn.execute("SELECT 1 FROM email_records WHERE provider='gmail' AND provider_id=?",
                                              (provider_id,)).fetchone()
                        if exists:
                            outcome(provider_id, "duplicate")
                            continue
                        record = gmail.read_email(f"gmail:{provider_id}").record
                        if record.provider_id != provider_id:
                            raise ValueError("message identity changed")
                        insert_email_once(conn, record)
                        outcome(provider_id, "stored")
                except Exception as exc:
                    with conn:
                        outcome(provider_id, "failed", type(exc).__name__)
            if next_cursor is None:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
    return counts
