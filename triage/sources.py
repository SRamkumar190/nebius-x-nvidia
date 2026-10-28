"""Source allowlist for synthetic fixtures and verified Phase 3 seed manifests."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from keeper_core.adapters import InvalidProviderResponse
from .preview import MAX_FIXTURE_BYTES, load_emails


@dataclass(frozen=True)
class FixtureSource:
    emails: tuple
    account: str | None = None
    can_apply: bool = False

    @classmethod
    def from_path(cls, path):
        return cls(load_emails(path))

    def identities(self, limit):
        return tuple(email.id for email in self.emails[:limit])

    def read(self, identity):
        record = next(email for email in self.emails if email.id == identity)
        return record, record.body_excerpt, record.id

    def fixture_id(self, identity):
        return identity


@dataclass(frozen=True)
class GmailSource:
    gmail: object
    entries: tuple
    account: str
    can_apply: bool = True

    @classmethod
    def from_manifest(cls, gmail, path: Path, account: str):
        if not account or not account.strip() or path.stat().st_size > MAX_FIXTURE_BYTES:
            raise ValueError("Demo account and bounded seed manifest required")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("account") != account:
            raise ValueError("Manifest account does not match")
        digest = manifest.get("fixture_sha256")
        if not isinstance(digest, str) or re.fullmatch("[0-9a-f]{64}", digest) is None:
            raise ValueError("Invalid fixture digest")
        entries = _entries(manifest.get("messages"), digest)
        gmail.verify_account(account)
        return cls(gmail, entries, account.casefold())

    def identities(self, limit):
        return tuple("gmail:" + entry[1] for entry in self.entries[:limit])

    def read(self, identity):
        fixture_id, provider_id, header = next(entry for entry in self.entries if "gmail:" + entry[1] == identity)
        response = self.gmail.read_email(identity)
        if response.record.id != identity or response.record.provider_id != provider_id or response.message_id_header != header:
            raise InvalidProviderResponse("Seeded message identity verification failed")
        return response.record, response.body_text, fixture_id

    def fixture_id(self, identity):
        return next(entry[0] for entry in self.entries if "gmail:" + entry[1] == identity)

    def apply_labels(self, identity, labels, *, idempotency_key):
        self.read(identity)  # Reverify the synthetic identity immediately before mutations.
        self.gmail.add_labels(identity, labels, idempotency_key=idempotency_key)


def _entries(messages, digest):
    if not isinstance(messages, dict) or not 1 <= len(messages) <= 1000:
        raise ValueError("Expected a bounded, nonempty seed manifest")
    entries = []
    for identity, item in messages.items():
        if not isinstance(identity, str) or re.fullmatch("[A-Za-z0-9_-]+", identity) is None:
            raise ValueError("Invalid fixture ID")
        if not isinstance(item, dict) or item.get("status") != "stored":
            raise ValueError("Reconcile pending seed entries first")
        provider_id = item.get("provider_id")
        header = f"<{identity}.{digest}@keeper-demo.example.test>"
        if not isinstance(provider_id, str) or not provider_id or item.get("message_id_header") != header:
            raise ValueError("Invalid seeded message identity")
        entries.append((identity, provider_id, header))
    if len({entry[1] for entry in entries}) != len(entries):
        raise ValueError("Duplicate provider IDs")
    return tuple(entries)
