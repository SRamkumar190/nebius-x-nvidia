"""Read-only adapter health checks and a gateway-user permission probe."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from .gateway_access import check_gateway_access

PROVIDERS = ("gmail", "calendar", "telegram", "tavily")
GOOGLE_SCOPES = {
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
}


def _private_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("credential file missing")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError("credential file must be mode 600 or stricter")
    with path.open("rb") as stream:
        if not stream.read(1):
            raise ValueError("credential file is empty")


def check_local(provider: str, secrets_dir: Path, db_path: Path) -> None:
    """Validate local readiness without making provider requests or printing secrets."""
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if secrets_dir.is_symlink() or not secrets_dir.is_dir() or stat.S_IMODE(secrets_dir.stat().st_mode) & 0o077:
        raise PermissionError("secrets directory must be mode 700 or stricter")
    filename = {
        "gmail": "google-token.json", "calendar": "google-token.json",
        "telegram": "telegram-bot.key", "tavily": "tavily.key",
    }[provider]
    path = secrets_dir / filename
    _private_file(path)
    if provider in ("gmail", "calendar"):
        data = json.loads(path.read_text(encoding="utf-8"))
        scopes = data.get("scopes") if isinstance(data, dict) else None
        if not isinstance(scopes, list) or any(not isinstance(scope, str) for scope in scopes) or \
                not GOOGLE_SCOPES <= set(scopes):
            raise ValueError("Google token lacks required scopes")
    if provider in ("calendar", "telegram"):
        if not db_path.is_file():
            raise FileNotFoundError("Keeper database missing")
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            table = "deadline_events" if provider == "calendar" else "notification_records"
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()


def check_live(provider: str, secrets_dir: Path, db_path: Path) -> None:
    """Make one safe API probe; Tavily's search consumes a request credit."""
    if provider == "gmail":
        from .gmail import LiveGmail
        adapter = LiveGmail.from_token_file(secrets_dir / "google-token.json", run_id="health")
    elif provider == "calendar":
        from .calendar import LiveCalendar
        adapter = LiveCalendar.from_token_file(secrets_dir / "google-token.json", db_path)
    elif provider == "telegram":
        from .telegram import LiveTelegram
        adapter = LiveTelegram.from_token_file(secrets_dir / "telegram-bot.key", db_path)
    elif provider == "tavily":
        from .tavily import LiveTavily
        adapter = LiveTavily.from_key_file(secrets_dir / "tavily.key")
    else:
        raise ValueError("unknown provider")
    adapter.check_health()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keeper health")
    sub = parser.add_subparsers(dest="command", required=True)
    adapters = sub.add_parser("adapters", help="check local config; add --live for provider calls")
    adapters.add_argument("--live", action="store_true")
    adapters.add_argument("--provider", choices=PROVIDERS, action="append")
    adapters.add_argument("--secrets-dir", type=Path,
                          default=Path("/sandbox/keeper/secrets"))
    adapters.add_argument("--db", type=Path,
                          default=Path(os.environ.get("KEEPER_DB_PATH", Path(os.environ.get(
                              "KEEPER_DATA_DIR", "/sandbox/keeper/data")) / "keeper.db")))
    permissions = sub.add_parser("permissions", help="run as the gateway UID; tests scoped writes")
    permissions.add_argument("--hermes-home", type=Path,
                             default=Path(os.environ.get("HERMES_HOME", "/sandbox/.hermes")))
    permissions.add_argument("--data-dir", type=Path,
                             default=Path(os.environ.get("KEEPER_DATA_DIR", "/sandbox/keeper/data")))
    permissions.add_argument("--secrets-dir", type=Path, default=Path("/sandbox/keeper/secrets"))
    permissions.add_argument("--soul-file", type=Path, action="append")
    permissions.add_argument("--expected-uid", type=int)
    args = parser.parse_args(argv)
    failed = False
    if args.command == "adapters":
        for provider in args.provider or PROVIDERS:
            try:
                check_local(provider, args.secrets_dir, args.db)
                if args.live:
                    check_live(provider, args.secrets_dir, args.db)
            except Exception as exc:
                print(f"{provider}: FAIL ({type(exc).__name__})")
                failed = True
            else:
                print(f"{provider}: PASS ({'live' if args.live else 'local'})")
    else:
        hermes = args.hermes_home
        configured = os.environ.get("KEEPER_SOUL_FILES", "")
        default_soul = [Path(part) for part in configured.split(os.pathsep) if part] if configured else [
            hermes.parent / "SOUL.md", hermes / "SOUL.md"] + (
            [hermes / "runtime" / "SOUL.md"] if (hermes / "runtime").is_dir() else [])
        soul = tuple(args.soul_file or default_soul)
        if args.expected_uid is not None and os.geteuid() != args.expected_uid:
            print(f"gateway UID: FAIL (running as {os.geteuid()}, expected {args.expected_uid})")
            failed = True
        else:
            print(f"gateway UID: {os.geteuid()}")
        results = check_gateway_access(hermes, args.data_dir, secrets_dir=args.secrets_dir, soul_files=soul)
        for name, result in results.items():
            print(f"{name}: {result}")
            failed |= result.startswith("FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
