# Keeper product record contracts (v1)

The Python definitions live in `keeper_core/contracts.py`. They are transport and storage independent: adapters normalize provider data into these records; persistence and workflow code consume them. These definitions do not create database tables or perform provider calls.

## Shared rules

- Every `id` is a stable, opaque string. Persist it and reuse it on retries; never generate a fresh ID just because an item was processed again. Namespace provider identities: an email can use `gmail:<message-id>`, and a provider event mapping can use `google-calendar:<event-id>`. Internal records use a deterministic key based on the source record and purpose. Do not put private message text in IDs.
- `Opportunity.dedupe_key` represents the same posting across radar runs. Build it from the normalized canonical URL plus normalized organization and title. Preserve the original record ID when a subsequent run matches this key. URL canonicalization and collision handling belong to the radar implementation; the string is opaque to consumers.
- `NotificationRecord.idempotency_key` names one intended delivery (channel, recipient, purpose, and run or source identity). Retrying delivery uses the same key.
- All `datetime` values are timezone aware UTC (`timezone.utc`) in Python. Convert at adapter boundaries; display in the user's timezone. Unknown or ambiguous dates are `None`, with source wording in an evidence field. A date with no known time must not be silently assigned one.
- References ending in `_id` point to the corresponding Keeper record, except explicitly named `provider_*_id`. Missing optional relationships are `None`. Collection fields are immutable tuples; an empty tuple means no known items.
- Provider links and evidence references are pointers, not copied raw inbox contents. Do not log or commit sensitive message bodies, credentials, or user profile data.

## Email and classification

| Record | Fields and meaning |
| --- | --- |
| `IngestionMetadata` | `ingested_at`, stable processing `run_id`, and source such as `gmail-inbox` or `demo-fixture`. |
| `EmailRecord` | Stable `id`; `provider` and its `provider_id`; optional `thread_id`; `sender`, `subject`, UTC `received_at`, bounded `body_excerpt`, `labels`, optional `raw_link_reference`, and `ingestion`. A raw link is a provider locator, not message content. |
| `ModelMetadata` | `requested_model`, optional `served_model`, `prompt_version`, and optional `router_call_id`; keep requested and served identities distinct. |
| `TriageResult` | Stable `id` and `email_id`; `bucket` (`junk`, `actionable`, `due`, `newsletter`, or `None` for manual review); short `reason`; `career` (`None` if unknown); zero or more `scam_signals`; optional `extracted_deadline` and `deadline_evidence`; optional `confidence` in `[0, 1]`; optional `model`; UTC `classified_at`. Confidence is a model report, not a calibrated probability. A scam signal is a warning, not proof. |

Career related email must remain reviewable even if a model proposes junk. The triage implementation applies that guard after classification. These records capture the final result and evidence; they do not themselves execute that policy.

## Opportunity and application

| Record | Fields and meaning |
| --- | --- |
| `Opportunity` | Stable `id`, `dedupe_key`, `canonical_url`, `organization`, `title`, `source`, UTC `discovered_at`; optional 1–10 `score` and `explanation`; `eligibility` (`eligible`, `ineligible`, `unverified`) and optional `eligibility_reason`; optional UTC `deadline` and `deadline_evidence`. Unknown eligibility stays `unverified`. A search snippet alone does not confirm a deadline. |
| `ApplicationStatusChange` | Stable history entry `id`, `status`, UTC `changed_at`, optional `source_email_id`, `reason`, and `manual` flag. Every change retains evidence or a manual reason. |
| `ManualOverride` | `actor_reference`, `reason`, and UTC `applied_at` for the latest manual intervention. The full series of changes remains in history. |
| `Application` | Stable `id`, `opportunity_id`, `status` (`found`, `applied`, `interview`, `decision`), ordered `status_history`, distinct `source_email_ids`, UTC `created_at` and `updated_at`, optional latest `manual_override`, and optional `decision_outcome` (for example offer or rejection). If history is present, the latest entry agrees with `status`. |

Status transitions, identity matching across emails, deduplication, and manual override precedence are workflow decisions for the tracker. Consumers should not infer an offer merely from `decision`.

## Side effects, security, and learning

| Record | Fields and meaning |
| --- | --- |
| `DeadlineEvent` | Stable Keeper `id`, `opportunity_id`, optional `application_id` and `source_email_id`, UTC `deadline_at`, source `evidence`, optional `provider` and `provider_event_id`, UTC `created_at` and `updated_at`. A changed deadline updates the existing mapping. |
| `DraftRecord` | Stable Keeper `id`, `email_id`, optional `application_id`, `provider`, optional `provider_draft_id`, `subject`, `body`, UTC `created_at` and `updated_at`, `requires_review`. This contract represents an unsent draft only; there is no send operation or sent status. |
| `NotificationRecord` | Stable Keeper `id`, `channel`, `recipient_reference`, `purpose`, `idempotency_key`, `status` (`pending`, `delivered`, `failed`), UTC `created_at`, optional `delivered_at`, `provider_message_id`, and `error`. |
| `SecurityEvent` | Stable `id`, UTC `occurred_at`, `category`, `outcome`, `evidence_reference`, optional `source_email_id` and `attempted_destination`. Behavioral injection handling and OpenShell network denials are separate event categories. A claim of blocked egress requires an actual audit reference. |
| `CorrectionRecord` | Stable `id`, `target_type` and `target_id`, user's `correction`, UTC `created_at`, `approval_status` (`proposed`, `approved`, `rejected`), optional `proposed_skill_name`, `approved_at`, and `actor_reference`. Only a user action can move a proposal to approved; email or model output cannot approve it. |

Provider event and draft IDs may be absent before creation. Keep the Keeper ID and retry using the same source identity; persist provider IDs as soon as a side effect succeeds. Database uniqueness and retry recovery are specified in the subsequent schema/workflow phase.
