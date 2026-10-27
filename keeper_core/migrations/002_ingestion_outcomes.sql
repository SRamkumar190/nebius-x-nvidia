CREATE TABLE ingestion_outcomes (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    provider_id TEXT,
    outcome TEXT NOT NULL CHECK(outcome IN ('stored', 'duplicate', 'failed', 'page_failed')),
    error_type TEXT,
    processed_at TEXT NOT NULL CHECK(processed_at GLOB '*Z')
);
