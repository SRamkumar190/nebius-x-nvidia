"""Preview synthetic source emails; gold annotations never enter model inputs."""
import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from keeper_core.adapters import ModelAnswer
from keeper_core.contracts import EmailRecord, IngestionMetadata, ModelMetadata
from keeper_core.time import from_storage, to_storage
from .classifier import classify_email

MAX_FIXTURE_BYTES = 2_000_000
MAX_BODY_CHARS = 20_000


def _text(item, name):
    value = item.get(name)
    if not isinstance(value, str) or len(value) > MAX_BODY_CHARS:
        raise ValueError("Invalid fixture field: " + name)
    return value


def load_emails(path: Path) -> tuple[EmailRecord, ...]:
    if path.stat().st_size > MAX_FIXTURE_BYTES:
        raise ValueError("Fixture exceeds size limit")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("synthetic") is not True or not isinstance(data.get("emails"), list):
        raise ValueError("Expected a synthetic inbox fixture")
    if len(data["emails"]) > 1000:
        raise ValueError("Too many fixture emails")
    emails = tuple(_email(item) for item in data["emails"])
    if len({email.id for email in emails}) != len(emails):
        raise ValueError("Duplicate fixture IDs")
    return emails


def _email(item):
    if not isinstance(item, dict):
        raise ValueError("Expected an email object")
    identity = _text(item, "id")
    if not identity.strip():
        raise ValueError("Email ID must not be empty")
    stamp = _text(item, "received_at")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", stamp):
        raise ValueError("received_at must be a complete UTC timestamp")
    received = from_storage(stamp)
    return EmailRecord(
        id=identity, provider="demo", provider_id=identity, thread_id=None,
        sender=_text(item, "sender"), subject=_text(item, "subject"), received_at=received,
        body_excerpt=_text(item, "body_text"), labels=(), raw_link_reference=None,
        ingestion=IngestionMetadata(received, "triage-preview", "synthetic-fixture"),
    )


class OfflineModel:
    """Fixed review reply exercises the pipeline without pretending to run inference."""
    def complete(self, task_type, prompt):
        return ModelAnswer(json.dumps({
            "bucket": None, "reason": "Offline demonstration; model classification was not run.",
            "career": None, "scam_signals": [], "deadline": None,
            "deadline_evidence": None, "confidence": None,
        }), ModelMetadata("offline-demo", None, "offline-demo-v1"))


def preview(emails, model, *, classified_at=None) -> dict:
    now = classified_at or datetime.now(timezone.utc)
    results = tuple(classify_email(email, model, classified_at=now) for email in emails)
    counts = Counter(result.bucket.value if result.bucket else "review" for result in results)
    return {
        "summary": {**{bucket: counts[bucket] for bucket in ("junk", "actionable", "due", "newsletter", "review")},
                    "total": len(results)},
        "results": [_serialize(result) for result in results],
    }


def _serialize(result):
    category = result.bucket.value.upper() if result.bucket else "REVIEW"
    labels = ["KEEPER_" + category] + (["KEEPER_SCAM_REVIEW"] if result.scam_signals else [])
    return {
        **asdict(result), "bucket": result.bucket.value if result.bucket else None,
        "proposed_labels": labels,
        "classified_at": to_storage(result.classified_at),
        "extracted_deadline": to_storage(result.extracted_deadline),
    }
