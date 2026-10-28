# Triage preview

Run from the repository root:

    .venv/bin/python -m triage preview --limit 5

Default mode is offline. It runs the real classification pipeline with a fixed
response requesting manual review, and still applies deterministic career and
scam checks. Output identifies this as offline-demo: a plumbing demonstration,
not measured Nemotron classification or accuracy. It needs no credentials and
writes no provider or product state.

## Nebius preview

With your existing TOKENFACTORY_API_KEY environment variable configured:

    .venv/bin/python -m triage preview --live --limit 5

This sends synthetic source text to Nano through the existing router.route and
writes the router usage log (KEEPER_ROUTER_DB, or KEEPER_DATA_DIR/router.db).
Malformed completions get at most one repair attempt, so five emails can cost
up to ten model calls. Timeouts and rate-limit failures become explicit review
rows without immediate retries. Missing credentials, rejected access, and
permanent request errors stop the command with status 2.

Router environment variables and key-file fallback work as documented in
router/README.md; this command does not load .env automatically. Requested and
served model names are preserved separately. The shared router does not return
a log row ID, so router_call_id remains null.

## Input and output

--fixture defaults to demo/fixtures/inbox_75.json. Input must declare synthetic:
true and contain an emails list with unique nonempty IDs, sender, subject,
body_text, and a full UTC received_at ending in Z. Limits: 1,000 records,
2 MB per file, 20,000 characters per source field. --limit ranges from 1 to
1,000 and defaults to 5.

Only source fields enter prompts. Gold labels, notes, existing Gmail labels,
and expected outcomes are excluded. JSON includes stable result IDs, bucket
(null means review), reason, career status, scam indicators, model metadata,
and proposed additive KEEPER_* labels.

Labels are previews only. The command never imports Gmail adapters, changes
mail, creates drafts or calendar entries, or writes keeper.db. Apply mode and
shared keeper launcher wiring remain integration work.

Career keywords override model false/unknown career flags. Career junk becomes
actionable; unknown relevance plus junk becomes manual review. Upfront fees,
urgency, high stated pay, and free-mail career senders are warning indicators,
not proof of fraud.

Deadline extraction accepts only an explicit ISO-8601 timestamp with a timezone
whose instant matches a timestamp in the exact quoted source evidence.
Natural-language dates, missing zones, and unsupported evidence remain unknown
and require confirmation. This does not prove an email's deadline is truthful.

Email text is untrusted and the adapter exposes no tools. A prompt alone does
not establish resistance to every injection attack; the deployment owner still
needs to verify OpenShell policy and real deny evidence.

## Verification

    .venv/bin/python -m unittest tests.test_triage tests.test_triage_preview -v
    .venv/bin/python -m coverage run --branch --source=triage -m unittest tests.test_triage tests.test_triage_preview
    .venv/bin/python -m coverage report --show-missing --fail-under=80

Coverage is a development-only tool installed in the existing virtual
environment; it is not a runtime requirement. To reproduce in a fresh virtual
environment, install coverage first.

Router integration tests use the real router with an injected fake client and
temporary SQLite call log. Command tests run the offline preview in a subprocess
and verify no product state is created. Live Nebius behavior still needs a
credentialed smoke check.
