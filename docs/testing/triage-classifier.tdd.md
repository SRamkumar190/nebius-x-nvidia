# Triage classifier TDD evidence

Derived from Phase 4 in docs/KEEPER_MASTER_DEVELOPMENT_PLAN.md and the agreed
classifier plus preview contribution. See triage/README.md for usage and limits.
Shared contracts, migrations, providers, and agent/bin/keeper are unchanged.
Gmail apply mode and product persistence remain integration work for the shared
workflow owner.

## User journey

As a developer, I want to preview synthetic inbox decisions without changing
Gmail, and explicitly opt into Nebius inference when credentials are available.
As Keeper, I want validated decisions and safe review fallbacks so malformed
model output cannot discard an email or invent an actionable deadline.

## Evidence

| Guarantee | Test | Result |
| --- | --- | --- |
| Valid model JSON becomes an existing TriageResult with metadata | tests/test_triage.py:test_classifies_email_and_preserves_model_metadata | PASS |
| Career mail cannot be routed to junk | test_career_mail_cannot_be_automatically_put_in_junk | PASS |
| Unknown relevance plus proposed junk becomes manual review | test_unknown_noncareer_junk_requires_review | PASS |
| Scam indicators are deterministic and additive | test_deterministic_scam_signals_are_added_to_model_signals | PASS |
| Explicit deadlines are parsed to UTC | test_explicit_deadline_is_parsed_as_utc | PASS |
| Invalid output gets one repair attempt, then review | test_malformed_model_output_retries_once_then_becomes_review | PASS |
| Gold answers and preexisting labels never enter prompts | tests/test_triage_preview.py:test_fixture_projection_never_passes_gold_or_labels_to_model | PASS |
| Real router chooses Nano and records usage with a fake client | test_router_selects_nano_logs_usage_and_exposes_no_tools | PASS |
| Offline command needs no keys and creates no product state | test_cli_offline_subprocess_needs_no_keys_and_creates_no_product_state | PASS |
| Full UTC timestamps and unique fixture IDs are required | test_full_utc_timestamp_and_unique_ids_are_required | PASS |
| Permanent configuration errors stop the batch without exposing details | test_permanent_config_failure_stops_batch_and_redacts_error | PASS |

Validation:

    .venv/bin/python -m unittest tests.test_triage tests.test_triage_preview -q
    Ran 29 tests ... OK

RED evidence: the initial classifier test target failed on the missing triage package.
Continuing tests reproduced invalid bucket type crashes, missing review
fallback/repair, missing preview/router modules, unguarded date-only input,
and repeated permanent configuration errors before their fixes.
GREEN: the same focused targets pass after implementation.

Final verification:

    .venv/bin/python -m coverage run --branch --source=triage --data-file=/private/tmp/keeper-triage-01a180.coverage -m unittest tests.test_triage tests.test_triage_preview -q
    .venv/bin/python -m coverage report --data-file=/private/tmp/keeper-triage-01a180.coverage --show-missing --fail-under=80
    29 tests pass; TOTAL 95% with branch coverage enabled.

    .venv/bin/python -m unittest discover -s tests -q
    152 tests: 151 pass; one pre-existing Gmail draft-deduplication failure.

    .venv/bin/python -m triage preview --limit 75
    Offline-demo: 75 review rows, 12 rows with warning indicators.

Offline review rows are deliberate canned responses, not model predictions.
The command is also exercised in a subprocess by the tests. Coverage excludes
the subprocess's separate interpreter but exercises main() in-process.

The first checkpoint commit attempt failed because the Git index was protected.
Work now lives on local branch feature/zayd-triage; the branch was created after
permission was granted. RED/GREEN checkpoint commits were not made. This report
preserves the validation sequence rather than claiming commit evidence.

Known gaps: the real Nebius API has not been called. Injected-client tests
cannot establish live model quality, cost, or sandbox egress policy.
The existing Gmail draft-deduplication failure is outside this contribution.

Pre-commit dependency audit: pip-audit reported no known vulnerabilities after
updating only the local virtual environment's packaging tools. This contribution
adds no application dependencies.

## Push verification follow-up

The configured ECC pre-push hook blocked the upload on the pre-existing Gmail
draft replay failure. Diagnosis showed MIME header folding preserved a leading
space on the 64-character Keeper marker and fingerprint headers, so exact
comparisons missed the existing draft. A separate fix normalizes surrounding
header whitespace before comparing; it does not change draft creation or sends.

RED: test_folded_draft_headers_survive_adapter_restart reproduced draft-2 instead
of draft-1 after constructing a new adapter. Checkpoint: ed96c55.
GREEN: the same test and the original draft test pass after normalization;
changed content with the same key still raises IdempotencyConflict.

    .venv/bin/python -m unittest tests.test_gmail_live -q
    7 tests pass.

    .venv/bin/python -m unittest discover -s tests -q
    All 153 tests pass. The earlier baseline failure is now resolved.

## Phase 4 completion work

Source requirements: master plan Phase 4; architecture and live acceptance
matrix are in docs/phase4-triage-report.md.

RED checkpoint c3ecf3e adds workflow tests that fail on missing triage.sources.
Evaluation tests independently failed on missing triage.evaluate before that
implementation. Later regressions reproduced a frozen transient model failure,
discarded partial authentication-error reports, and stale source reuse before
their fixes.

GREEN guarantees:

| Guarantee | Evidence |
| --- | --- |
| Dry run creates no product state or Gmail mutations | GmailRunTest.test_dry_run_has_no_product_writes_or_gmail_mutations |
| Email/result save is atomic and metadata round-trips | StateTest.test_save_roundtrip_replay_and_conflict_preserve_original and test_result_identity_and_transaction_rollback |
| Existing Phase 3 data upgrades without loss | StateTest.test_version_two_upgrade_preserves_ingested_email |
| Wrong accounts and synthetic message identities cannot apply labels | GmailRunTest account/manifest tests |
| Repeat apply reuses decisions and adds no duplicate provider effects | GmailRunTest.test_apply_replays_saved_decisions_after_restart_and_preserves_inbox |
| Failed label delivery recovers from the saved plan | GmailRunTest.test_label_failure_retains_plan_for_retry_without_model_recall |
| Temporary inference failures remain retryable | GmailRunTest.test_transient_inference_failure_is_not_saved_and_can_recover |
| Approved user corrections and changed source content are not overwritten | StateTest correction/content tests |
| Fatal errors retain partial progress | GmailRunTest.test_fatal_error_preserves_completed_work_and_stops_further_calls |
| Runtime token paths, permissions, scopes, and OAuth endpoints are checked | tests/test_triage_credentials.py |
| Full fixture saves/replays/scores and launcher dispatch works | RunCommandTest.test_all_75_fixture_records_save_replay_and_compare_offline and test_launcher_dispatches_triage_without_sandbox_dependencies |
| Evaluation counts failures and reviews and reports missing coverage | tests/test_triage_evaluate.py |

Validation:

    .venv/bin/python -m unittest discover -s tests -q
    All 200 tests pass.

    .venv/bin/python -m coverage run --branch --source=triage --data-file=/private/tmp/keeper-phase4-01a180.coverage -m unittest tests.test_triage tests.test_triage_preview tests.test_triage_run tests.test_triage_credentials tests.test_triage_evaluate -q
    .venv/bin/python -m coverage report --data-file=/private/tmp/keeper-phase4-01a180.coverage --show-missing --fail-under=80
    76 triage tests pass; total branch-aware coverage is 96%.

    bash -n agent/bin/keeper agent/deploy.sh
    Shell syntax checks pass.

No live provider call or sandbox deployment occurred. Live Nebius/Gmail quality,
real label application, and deployed acceptance remain pending the teammate's
credentials and environment.
