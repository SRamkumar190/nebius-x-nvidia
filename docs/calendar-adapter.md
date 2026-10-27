# Google Calendar adapter

`integrations.calendar.LiveCalendar` implements `CalendarAdapter` for one calendar. Install `requirements.txt`, then construct it with `LiveCalendar.from_token_file(Path("/sandbox/keeper/secrets/google-token.json"), Path("/sandbox/keeper/data/keeper.db"))`. The token needs `calendar.events`. A Keeper `deadline_events` row, linked to an opportunity, must exist before `create_deadline` or `upsert_deadline` is called.

`search_events(query, cursor=None, limit=50)` returns one page of event summaries and a next cursor. Repeat with that cursor until it is `None`. Timed event starts are converted to UTC; all-day events return `starts_at=None` rather than an invented instant.

`create_deadline(event_id, deadline_at, summary, idempotency_key=...)` creates a 30-minute event starting at the confirmed deadline. `upsert_deadline` uses the same event identity for extensions or other edits. Both return the Google provider event ID and write `provider='google-calendar'`, `provider_event_id`, the confirmed UTC deadline, and `updated_at` to the existing SQLite `deadline_events` row. The caller may also pass a known `provider_event_id` to `upsert_deadline`; it must agree with the stored mapping.

Every event carries a hashed Keeper deadline ID in Calendar private extended properties. Before creation, the adapter searches for that marker, including subsequent pages. It also supplies a deterministic Google event ID, so a repeated insert can recover from a 409 collision. After an uncertain insert failure, call again with the same event ID and idempotency key; the adapter searches before another attempt. It never blindly retries an insert. It patches an existing event only when the summary or deadline differs. Conflicting mappings or an event with the wrong Keeper marker stop with `IdempotencyConflict`.

Searches, reads, and idempotent patches use bounded backoff for 429, Calendar rate quota responses, and transient 5xx. Inserts surface uncertain errors. The offline tests use a fake Calendar API service with real SQLite storage; no live account has been tested.
