"""Idempotent inserts for the two identities shared by ingestion and radar."""
from __future__ import annotations

import json
import sqlite3

from .contracts import EmailRecord, Opportunity
from .time import to_storage


class IdentityConflict(ValueError):
    """Two natural identities point to different Keeper records."""


def insert_email_once(conn: sqlite3.Connection, email: EmailRecord) -> str:
    """Insert a new email or return its existing Keeper ID. Caller owns commit."""
    by_provider = conn.execute(
        "SELECT id FROM email_records WHERE provider = ? AND provider_id = ?",
        (email.provider, email.provider_id),
    ).fetchone()
    by_id = conn.execute("SELECT provider, provider_id FROM email_records WHERE id = ?", (email.id,)).fetchone()
    if by_provider or by_id:
        if by_provider == (email.id,) and by_id == (email.provider, email.provider_id):
            return email.id
        raise IdentityConflict("email ID conflicts with provider message identity")
    conn.execute(
        """INSERT INTO email_records
           (id, provider, provider_id, thread_id, sender, subject, received_at,
            body_excerpt, labels_json, raw_link_reference, ingested_at,
            ingestion_run_id, ingestion_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            email.id, email.provider, email.provider_id, email.thread_id,
            email.sender, email.subject, to_storage(email.received_at), email.body_excerpt,
            json.dumps(email.labels), email.raw_link_reference,
            to_storage(email.ingestion.ingested_at), email.ingestion.run_id,
            email.ingestion.source,
        ),
    )
    return email.id


def insert_opportunity_once(conn: sqlite3.Connection, opportunity: Opportunity) -> str:
    """Return an existing posting by canonical URL or dedupe key; caller commits."""
    by_url = conn.execute(
        "SELECT id FROM opportunities WHERE canonical_url = ?", (opportunity.canonical_url,)
    ).fetchone()
    by_key = conn.execute(
        "SELECT id FROM opportunities WHERE dedupe_key = ?", (opportunity.dedupe_key,)
    ).fetchone()
    if by_url and by_key and by_url[0] != by_key[0]:
        raise IdentityConflict("canonical URL and dedupe key identify different opportunities")
    existing = by_url or by_key
    if existing:
        return existing[0]
    conn.execute(
        """INSERT INTO opportunities
           (id, dedupe_key, canonical_url, organization, title, source,
            discovered_at, score, explanation, eligibility, eligibility_reason,
            deadline, deadline_evidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            opportunity.id, opportunity.dedupe_key, opportunity.canonical_url,
            opportunity.organization, opportunity.title, opportunity.source,
            to_storage(opportunity.discovered_at), opportunity.score, opportunity.explanation,
            opportunity.eligibility.value, opportunity.eligibility_reason,
            to_storage(opportunity.deadline), opportunity.deadline_evidence,
        ),
    )
    return opportunity.id
