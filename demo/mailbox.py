"""Host-only demo seed/reset tooling. Never deployed with Keeper runtime code."""
import argparse
import base64
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCOPES = {"seed": ["https://www.googleapis.com/auth/gmail.insert"],
          "reset": ["https://www.googleapis.com/auth/gmail.modify"]}


def save(path, data):
    temp = path.with_suffix(path.suffix + ".new")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def mime(email, digest):
    message = EmailMessage()
    message["From"] = email["sender"]
    message["To"] = email["recipient"]
    message["Subject"] = email["subject"]
    message["Date"] = format_datetime(datetime.fromisoformat(email["received_at"].replace("Z", "+00:00")))
    message["Message-ID"] = f"<{email['id']}.{digest}@keeper-demo.example.test>"
    message.set_content(email["body_text"])
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def seed(service, fixture, manifest_path, account):
    digest = hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest()
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "version": 1, "account": account, "fixture_sha256": digest, "messages": {}}
    if manifest["account"] != account or manifest["fixture_sha256"] != digest:
        raise ValueError("manifest account or fixture differs")
    for email in fixture["emails"]:
        prior = manifest["messages"].get(email["id"])
        if prior:
            if prior["status"] != "stored":
                raise RuntimeError("uncertain insert: reconcile pending manifest entry before replay")
            continue
        entry = {"status": "pending", "message_id_header": f"<{email['id']}.{digest}@keeper-demo.example.test>"}
        manifest["messages"][email["id"]] = entry
        save(manifest_path, manifest)
        response = service.users().messages().insert(userId=account, internalDateSource="dateHeader",
            body={"raw": mime(email, digest), "labelIds": ["INBOX", "UNREAD"]}).execute()
        if not isinstance(response.get("id"), str):
            raise ValueError("insert returned no provider ID")
        entry.update(status="stored", provider_id=response["id"])
        save(manifest_path, manifest)
    return manifest


def reset(service, manifest, db_path=None):
    """Restore only seed IDs to the initial inbox labels; never delete messages."""
    account = manifest["account"]
    for entry in manifest["messages"].values():
        if entry["status"] != "stored":
            raise ValueError("reconcile pending seed first")
        message = service.users().messages().get(userId=account, id=entry["provider_id"], format="full").execute()
        headers = message.get("payload", {}).get("headers", [])
        if not any(h.get("name", "").lower() == "message-id" and h.get("value") == entry["message_id_header"] for h in headers):
            raise ValueError("manifest identity verification failed")
        # Seeded messages started with precisely these labels. Touch only manifest IDs.
        service.users().messages().modify(userId=account, id=entry["provider_id"],
            body={"addLabelIds": ["INBOX", "UNREAD"], "removeLabelIds": [
                label for label in message.get("labelIds", []) if label not in ("INBOX", "UNREAD")]}).execute()
    if db_path:
        with closing(sqlite3.connect(db_path)) as conn, conn:
            conn.execute("PRAGMA foreign_keys=ON")
            for entry in manifest["messages"].values():
                conn.execute("DELETE FROM ingestion_outcomes WHERE provider_id=?", (entry["provider_id"],))
                conn.execute("DELETE FROM email_records WHERE provider='gmail' AND provider_id=?", (entry["provider_id"],))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("authorize-seed", "authorize-reset", "seed", "reset", "ingest"))
    parser.add_argument("--token", type=Path, required=True)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--account", required=True, help="disposable demo account address")
    parser.add_argument("--manifest", type=Path, default=Path("data/demo-seed.json"))
    parser.add_argument("--fixture", type=Path, default=Path("demo/fixtures/inbox_75.json"))
    parser.add_argument("--db", type=Path, default=Path("data/demo-keeper.db"))
    args = parser.parse_args()
    if args.token.resolve().is_relative_to(REPO):
        parser.error("demo credentials must be outside the checkout")
    if args.command.startswith("authorize"):
        from google_auth_oauthlib.flow import InstalledAppFlow
        purpose = args.command.split("-")[1]
        if not args.client or args.client.resolve().is_relative_to(REPO):
            parser.error("separate demo Desktop OAuth client outside checkout required")
        credentials = InstalledAppFlow.from_client_secrets_file(str(args.client), SCOPES[purpose]).run_local_server(
            port=0, prompt="consent", access_type="offline", login_hint=args.account)
        if not credentials.refresh_token:
            raise ValueError("refresh token missing")
        args.token.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name != "posix" or args.token.parent.stat().st_mode & 0o077:
            raise ValueError("run on Unix/WSL with a private token directory")
        with os.fdopen(os.open(args.token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            stream.write(credentials.to_json())
        return
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    if args.token.is_symlink() or args.token.stat().st_mode & 0o077:
        raise ValueError("credential must be a private regular file")
    data = json.loads(args.token.read_text())
    required = SCOPES["seed" if args.command == "seed" else "reset"]
    if args.command != "ingest" and set(data.get("scopes", [])) != set(required):
        raise ValueError("use a separate credential with exactly the demo operation scope")
    service = build("gmail", "v1", credentials=Credentials.from_authorized_user_file(str(args.token)), cache_discovery=False)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    lock = args.manifest.with_suffix(".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if args.command == "seed":
            seed(service, json.loads(args.fixture.read_text()), args.manifest, args.account)
        elif args.command == "reset":
            manifest = json.loads(args.manifest.read_text())
            if manifest["account"] != args.account:
                raise ValueError("wrong demo account")
            reset(service, manifest, args.db if args.db.exists() else None)
        else:
            from integrations.gmail import LiveGmail
            from integrations.ingestion import ingest
            from keeper_core.db import migrate
            profile = service.users().getProfile(userId="me").execute()
            if profile.get("emailAddress", "").lower() != args.account.lower():
                raise ValueError("ingestion token belongs to a different account")
            migrate(args.db)
            print(ingest(LiveGmail(service, run_id="demo-ingest"), args.db, run_id="demo-ingest"))
    finally:
        os.close(fd)
        lock.unlink()


if __name__ == "__main__":
    main()
