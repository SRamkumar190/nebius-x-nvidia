-- Product records. Timestamps are ISO 8601 UTC TEXT ending in Z.
-- NULL means unknown; never store an invented instant.

CREATE TABLE email_records (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    thread_id TEXT,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    received_at TEXT NOT NULL CHECK (received_at GLOB '*Z'),
    body_excerpt TEXT NOT NULL,
    labels_json TEXT NOT NULL DEFAULT '[]',
    raw_link_reference TEXT,
    ingested_at TEXT NOT NULL CHECK (ingested_at GLOB '*Z'),
    ingestion_run_id TEXT NOT NULL,
    ingestion_source TEXT NOT NULL
);
CREATE UNIQUE INDEX uq_email_provider_mapping ON email_records(provider, provider_id);
CREATE INDEX ix_email_received_at ON email_records(received_at);

CREATE TABLE triage_results (
    id TEXT PRIMARY KEY,
    email_id TEXT NOT NULL REFERENCES email_records(id),
    bucket TEXT CHECK (bucket IN ('junk', 'actionable', 'due', 'newsletter')),
    reason TEXT NOT NULL,
    career INTEGER CHECK (career IN (0, 1)),
    scam_signals_json TEXT NOT NULL DEFAULT '[]',
    extracted_deadline TEXT CHECK (extracted_deadline IS NULL OR extracted_deadline GLOB '*Z'),
    deadline_evidence TEXT,
    confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    requested_model TEXT,
    served_model TEXT,
    prompt_version TEXT,
    router_call_id TEXT,
    classified_at TEXT NOT NULL CHECK (classified_at GLOB '*Z')
);
CREATE UNIQUE INDEX uq_triage_email ON triage_results(email_id);

CREATE TABLE opportunities (
    id TEXT PRIMARY KEY,
    dedupe_key TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    organization TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    discovered_at TEXT NOT NULL CHECK (discovered_at GLOB '*Z'),
    score INTEGER CHECK (score IS NULL OR score BETWEEN 1 AND 10),
    explanation TEXT,
    eligibility TEXT NOT NULL CHECK (eligibility IN ('eligible', 'ineligible', 'unverified')),
    eligibility_reason TEXT,
    deadline TEXT CHECK (deadline IS NULL OR deadline GLOB '*Z'),
    deadline_evidence TEXT
);
CREATE UNIQUE INDEX uq_opportunity_canonical_url ON opportunities(canonical_url);
CREATE UNIQUE INDEX uq_opportunity_dedupe_key ON opportunities(dedupe_key);

CREATE TABLE applications (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
    status TEXT NOT NULL CHECK (status IN ('found', 'applied', 'interview', 'decision')),
    created_at TEXT NOT NULL CHECK (created_at GLOB '*Z'),
    updated_at TEXT NOT NULL CHECK (updated_at GLOB '*Z'),
    manual_override_actor_reference TEXT,
    manual_override_reason TEXT,
    manual_override_applied_at TEXT CHECK (manual_override_applied_at IS NULL OR manual_override_applied_at GLOB '*Z'),
    decision_outcome TEXT
);
CREATE UNIQUE INDEX uq_application_opportunity ON applications(opportunity_id);

CREATE TABLE application_status_changes (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES applications(id),
    status TEXT NOT NULL CHECK (status IN ('found', 'applied', 'interview', 'decision')),
    changed_at TEXT NOT NULL CHECK (changed_at GLOB '*Z'),
    source_email_id TEXT REFERENCES email_records(id),
    reason TEXT NOT NULL,
    manual INTEGER NOT NULL DEFAULT 0 CHECK (manual IN (0, 1))
);
CREATE INDEX ix_application_status_history ON application_status_changes(application_id, changed_at);

CREATE TABLE application_source_emails (
    application_id TEXT NOT NULL REFERENCES applications(id),
    email_id TEXT NOT NULL REFERENCES email_records(id),
    PRIMARY KEY (application_id, email_id)
);

CREATE TABLE deadline_events (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
    application_id TEXT REFERENCES applications(id),
    source_email_id TEXT REFERENCES email_records(id),
    deadline_at TEXT NOT NULL CHECK (deadline_at GLOB '*Z'),
    evidence TEXT NOT NULL,
    provider TEXT,
    provider_event_id TEXT,
    created_at TEXT NOT NULL CHECK (created_at GLOB '*Z'),
    updated_at TEXT NOT NULL CHECK (updated_at GLOB '*Z'),
    CHECK ((provider IS NULL AND provider_event_id IS NULL) OR provider IS NOT NULL)
);
CREATE UNIQUE INDEX uq_deadline_provider_event ON deadline_events(provider, provider_event_id)
    WHERE provider_event_id IS NOT NULL;

CREATE TABLE draft_records (
    id TEXT PRIMARY KEY,
    email_id TEXT NOT NULL REFERENCES email_records(id),
    application_id TEXT REFERENCES applications(id),
    provider TEXT NOT NULL,
    provider_draft_id TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL CHECK (created_at GLOB '*Z'),
    updated_at TEXT NOT NULL CHECK (updated_at GLOB '*Z'),
    requires_review INTEGER NOT NULL DEFAULT 1 CHECK (requires_review IN (0, 1))
);
CREATE UNIQUE INDEX uq_draft_email ON draft_records(email_id);
CREATE UNIQUE INDEX uq_draft_provider_mapping ON draft_records(provider, provider_draft_id)
    WHERE provider_draft_id IS NOT NULL;

CREATE TABLE notification_records (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    recipient_reference TEXT NOT NULL,
    purpose TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'delivered', 'failed')),
    created_at TEXT NOT NULL CHECK (created_at GLOB '*Z'),
    delivered_at TEXT CHECK (delivered_at IS NULL OR delivered_at GLOB '*Z'),
    provider_message_id TEXT,
    error TEXT
);
CREATE UNIQUE INDEX uq_notification_idempotency ON notification_records(idempotency_key);

CREATE TABLE security_events (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL CHECK (occurred_at GLOB '*Z'),
    category TEXT NOT NULL,
    outcome TEXT NOT NULL,
    evidence_reference TEXT NOT NULL,
    source_email_id TEXT REFERENCES email_records(id),
    attempted_destination TEXT
);

CREATE TABLE correction_records (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    correction TEXT NOT NULL,
    created_at TEXT NOT NULL CHECK (created_at GLOB '*Z'),
    approval_status TEXT NOT NULL CHECK (approval_status IN ('proposed', 'approved', 'rejected')),
    proposed_skill_name TEXT,
    approved_at TEXT CHECK (approved_at IS NULL OR approved_at GLOB '*Z'),
    actor_reference TEXT
);
