"""Versioned, repeatable bootstrap for Keeper's product SQLite database."""
from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path

MIGRATIONS = Path(__file__).with_name("migrations")


def default_db_path() -> Path:
    explicit = os.environ.get("KEEPER_DB_PATH")
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("KEEPER_DATA_DIR", "data")) / "keeper.db"


def migrate(db_path: Path, *, migrations_dir: Path = MIGRATIONS) -> int:
    """Apply pending numbered SQL files atomically; return the schema version."""
    files = sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))
    versions = [int(path.name[:3]) for path in files]
    if versions != list(range(1, len(files) + 1)):
        raise ValueError("migration numbers must be unique and contiguous from 001")
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path, timeout=10)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > len(files):
            raise ValueError(f"database version {version} is newer than this code ({len(files)})")
        if version >= 1:
            legacy = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE ? LIMIT 1",
                ("%LIKE '*Z'%",),
            ).fetchone()
            if legacy:
                raise ValueError(
                    f"database has the older version 1 timestamp checks in {legacy[0]}; "
                    "back up and rebuild this development database before continuing"
                )
        for number, path in enumerate(files, 1):
            if number <= version:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")
            except sqlite3.Error:
                conn.rollback()
                raise
        return conn.execute("PRAGMA user_version").fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap or migrate Keeper's SQLite database")
    parser.add_argument("--db", type=Path, default=default_db_path(), help="database path (default: data/keeper.db)")
    args = parser.parse_args(argv)
    version = migrate(args.db)
    print(f"Keeper database: {args.db} (schema version {version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
