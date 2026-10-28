# Phase 4 triage

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

The preview command prints proposed labels without changing Gmail or keeper.db.
The run command below adds persistence and explicit application. Neither
command creates drafts, sends mail, removes INBOX, archives, or deletes messages.

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

## Saved results and a complete run

The run command defaults to a dry run over all 75 synthetic fixture records:

    .venv/bin/python -m triage run --dry-run
    .venv/bin/python -m triage run --save --db data/phase4-offline.db

Offline saved results deliberately request review. They cannot be reused to
authorize a live run; use a separate database for live acceptance.

Saving uses the existing email_records and triage_results tables and retains
the original stable IDs and model metadata. Migration 003 adds a binding to one
verified Gmail account; existing version 2 data survives the upgrade.
Back up an existing database before migration. Dry runs never create or migrate
the product database, though live inference still writes the router usage log.

The run command uses Gmail's full body rather than its short snippet. Bodies
above 20,000 characters require review instead of being silently classified from
a truncated prefix.

## Verified demo Gmail

Gmail mode requires the Phase 3 seed manifest from demo/SEED_AND_RESET.md.
It reads only the manifest's completed synthetic message IDs. The manifest
account must match --account and the authenticated Gmail profile; every actual
Message-ID must match the manifest's synthetic identity, including immediately
before label changes. Pending seed entries must be reconciled before use.

Configure TOKENFACTORY_API_KEY privately, then set DEMO_ACCOUNT,
GOOGLE_TOKEN_FILE, and SEED_MANIFEST to the disposable account, private runtime
token path, and manifest path. The token must be outside the checkout in a
private directory (700) with file mode 600, using the exact runtime Gmail and
Calendar scopes. Do not use the insert-only seed token or reset token.

From the repository root:

    mkdir -p data
    .venv/bin/python -m triage run --gmail --live --dry-run \
      --account "$DEMO_ACCOUNT" --token "$GOOGLE_TOKEN_FILE" \
      --manifest "$SEED_MANIFEST" --db data/phase4-live.db --limit 75 \
      > data/phase4-dry-run.json

Inspect the proposed labels, reasons, warnings, errors, and review cases.
Explicitly apply the additive labels and save the selected decisions:

    .venv/bin/python -m triage run --gmail --live --apply \
      --account "$DEMO_ACCOUNT" --token "$GOOGLE_TOKEN_FILE" \
      --manifest "$SEED_MANIFEST" --db data/phase4-live.db --limit 75 \
      > data/phase4-applied.json

Application saves a decision before the first Gmail label change. Rerunning
reuses saved decisions without another model call. The Gmail adapter checks
provider state and adds only missing KEEPER_* labels, so restart and uncertain
label outcomes can be reconciled safely by rerunning. Saved decisions are
immutable; conflicting source content, a different bound account, or an approved
user correction requires operator reconciliation rather than an automatic
overwrite. An approved correction does not silently lose to a model result.

Transient inference failures remain unsaved so the next run can retry them.
Per-message read, save, or label failures are visible and produce exit status 1.
Fatal authentication/configuration errors stop further processing with status 2
and retain completed rows in the partial report. Invalid setup also returns 2.
Check exit status and report errors before treating a run as complete.

## Compare against the labeled fixture

After inference, compare the saved output to the fixture's gold answers:

    .venv/bin/python -m triage compare --report data/phase4-applied.json

The scorer maps Gmail provider IDs back through fixture_id, reports per-bucket
accuracy, career-to-junk errors, scam precision/recall, deadline mismatches,
review/failure counts, and missing coverage. Failures count as review cases in
the accuracy denominator. Gold fields are read only by the scorer, never the
classifier. Offline scores are labeled demonstration-only, not model evidence.

## Sandbox entry point

agent/deploy.sh now stages triage and the default synthetic fixture. The
existing deployment procedure remains controlled by the sandbox owner.
After deployment, replace the local Python prefix in the commands above with:

    keeper triage run ...
    keeper triage compare --report /sandbox/keeper/data/phase4-applied.json

Full live acceptance steps and evidence requirements are in
docs/phase4-triage-report.md. Live verification is still pending.
