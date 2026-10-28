"""Validate the existing private runtime token before constructing a Gmail client."""
import json
import os
import stat
from pathlib import Path

from integrations.gmail import LiveGmail

ROOT = Path(__file__).resolve().parents[1]
SCOPES = frozenset({
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
})


def gmail_from_token(path: Path, *, run_id: str):
    path = path.expanduser()
    if path.is_symlink() or path.resolve().is_relative_to(ROOT):
        raise ValueError("Runtime credentials must be outside the checkout")
    if path.stat().st_size > 64_000:
        raise ValueError("Invalid runtime credential size")
    if os.name == "posix" and (
        stat.S_IMODE(path.stat().st_mode) & 0o077
        or stat.S_IMODE(path.parent.stat().st_mode) & 0o077
    ):
        raise ValueError("Runtime credentials require a private directory and file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(
        not isinstance(data.get(name), str) or not data[name]
        for name in ("refresh_token", "client_id", "client_secret")
    ):
        raise ValueError("Incomplete runtime credentials")
    if data.get("token_uri") not in (
        "https://oauth2.googleapis.com/token", "https://accounts.google.com/o/oauth2/token",
    ):
        raise ValueError("Unexpected OAuth endpoint")
    scopes = data.get("scopes")
    if not isinstance(scopes, list) or any(not isinstance(scope, str) for scope in scopes) or set(scopes) != SCOPES:
        raise ValueError("Use the runtime token, not a seeding or reset token")
    return LiveGmail.from_token_file(path, run_id=run_id)
