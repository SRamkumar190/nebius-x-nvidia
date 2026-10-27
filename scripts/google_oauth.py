"""Local desktop OAuth for Keeper's disposable demo Google account.

Run on the computer with a browser. This module never calls Gmail or Calendar.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
)
REPO_ROOT = Path(__file__).resolve().parents[1]


def validate_client_secrets(path: Path) -> None:
    if path.expanduser().resolve().is_relative_to(REPO_ROOT):
        raise ValueError("OAuth client JSON must be outside the repository")
    data = json.loads(path.read_text(encoding="utf-8"))
    installed = data.get("installed")
    if not isinstance(installed, dict) or not installed.get("client_id") or not installed.get("client_secret"):
        raise ValueError("expected a Google OAuth Desktop app client JSON (installed client)")


def validate_token_payload(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("token must be a JSON object")
    for key in ("token", "refresh_token", "client_id", "client_secret"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f"token is missing {key}")
    if data.get("token_uri") not in (
        "https://oauth2.googleapis.com/token",
        "https://accounts.google.com/o/oauth2/token",
    ):
        raise ValueError("unexpected Google token endpoint")
    scopes = data.get("scopes")
    if not isinstance(scopes, list) or set(scopes) != set(SCOPES) or len(scopes) != len(SCOPES):
        raise ValueError("token scopes do not match Keeper's runtime scopes")


def write_token(path: Path, serialized: str) -> None:
    """Create a private token file exactly once, outside this repository."""
    if path.expanduser().is_symlink():
        raise ValueError("token output must not be a symlink")
    destination = path.expanduser().resolve()
    if destination.is_relative_to(REPO_ROOT):
        raise ValueError("token output must be outside the repository")
    data = json.loads(serialized)
    validate_token_payload(data)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and stat.S_IMODE(destination.parent.stat().st_mode) & 0o077:
        raise ValueError("token directory must not be accessible to group or others")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(serialized)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        if os.name == "nt":
            import subprocess
            account = subprocess.run(["whoami"], check=True, capture_output=True, text=True).stdout.strip()
            subprocess.run(
                ["icacls", str(destination), "/inheritance:r", "/grant:r", f"{account}:(F)"],
                check=True, capture_output=True, text=True,
            )
        else:
            os.chmod(destination, 0o600)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def authorize(client_secrets: Path, output: Path) -> None:
    validate_client_secrets(client_secrets)
    if output.expanduser().exists():
        raise FileExistsError(f"token already exists: {output}; choose a new output path")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError("install google-auth-oauthlib before running authorization") from exc
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not credentials.refresh_token:
        raise ValueError("Google did not return a refresh token; authorization was not saved")
    write_token(output, credentials.to_json())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authorize Keeper's demo Google account on this computer")
    parser.add_argument("--client-secrets", required=True, type=Path, help="downloaded Desktop app OAuth JSON")
    parser.add_argument("--output", required=True, type=Path, help="token JSON path outside this repository")
    args = parser.parse_args(argv)
    print("This opens Google consent for the disposable demo account.")
    print("Scopes: gmail.modify (read/label/draft; also permits send), calendar.events.")
    print("Confirm the demo account in the browser before granting access.")
    try:
        authorize(args.client_secrets.expanduser(), args.output)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Authorization failed: {exc}", file=sys.stderr)
        return 1
    print(f"Token saved to {args.output.expanduser()} (contents hidden).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
