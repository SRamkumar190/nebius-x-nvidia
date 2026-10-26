import unittest
from datetime import datetime, timedelta, timezone

from keeper_core import (
    Application, ApplicationStatus, ApplicationStatusChange, CorrectionRecord,
    DeadlineEvent, DraftRecord, EmailRecord, Eligibility, IngestionMetadata,
    ManualOverride, ModelMetadata, NotificationRecord, Opportunity, SecurityEvent,
    TriageBucket, TriageResult,
)


UTC_TIME = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


class ContractTest(unittest.TestCase):
    def test_records_connect_by_stable_ids(self):
        email = EmailRecord(
            id="gmail:msg-1", provider="gmail", provider_id="msg-1",
            thread_id="thread-1", sender="recruiter@example.test", subject="Interview",
            received_at=UTC_TIME, body_excerpt="Please pick a slot", labels=("INBOX",),
            raw_link_reference="gmail:msg-1",
            ingestion=IngestionMetadata(UTC_TIME, "run-1", "demo-fixture"),
        )
        triage = TriageResult(
            id="triage:gmail:msg-1", email_id=email.id, bucket=TriageBucket.ACTIONABLE,
            reason="Interview invitation", career=True, scam_signals=(),
            extracted_deadline=None, confidence=0.8,
            model=ModelMetadata("nano", "nano", "v1", "call-1"),
            classified_at=UTC_TIME,
        )
        opportunity = Opportunity(
            id="opportunity:1", dedupe_key="posting:1", canonical_url="https://example.test/apply",
            organization="Example", title="Intern", source="radar", discovered_at=UTC_TIME,
            score=8, explanation="Matches target role", eligibility=Eligibility.UNVERIFIED,
            eligibility_reason="Graduation year unknown", deadline=None,
        )
        change = ApplicationStatusChange("change:1", ApplicationStatus.INTERVIEW, UTC_TIME, email.id, "Invite")
        application = Application(
            id="application:1", opportunity_id=opportunity.id, status=ApplicationStatus.INTERVIEW,
            status_history=(change,), source_email_ids=(email.id,),
            created_at=UTC_TIME, updated_at=UTC_TIME,
            manual_override=ManualOverride("user:1", "Confirmed match", UTC_TIME),
        )
        deadline = DeadlineEvent("deadline:1", opportunity.id, application.id, email.id,
                                 UTC_TIME, "Explicit email date", None, None, UTC_TIME, UTC_TIME)
        draft = DraftRecord("draft:1", email.id, application.id, "gmail", None,
                            "Re: Interview", "Thank you", UTC_TIME, UTC_TIME)
        notice = NotificationRecord("notification:1", "telegram", "demo-chat", "triage-summary",
                                    "telegram:demo-chat:run-1", "pending", UTC_TIME)
        security = SecurityEvent("security:1", UTC_TIME, "injection_attempt", "ignored",
                                 "synthetic-fixture:1", email.id)
        correction = CorrectionRecord("correction:1", "triage", triage.id,
                                      "Keep this visible", UTC_TIME, "proposed")

        self.assertEqual(triage.email_id, email.id)
        self.assertEqual(application.opportunity_id, deadline.opportunity_id)
        self.assertEqual(draft.email_id, security.source_email_id)
        self.assertEqual(correction.target_id, triage.id)
        self.assertEqual(notice.idempotency_key, "telegram:demo-chat:run-1")

    def test_unknown_bucket_and_deadline_are_explicit(self):
        result = TriageResult("triage:2", "gmail:2", None, "Needs review", None, (),
                              None, None, None, UTC_TIME)
        self.assertIsNone(result.bucket)
        self.assertIsNone(result.extracted_deadline)

    def test_rejects_unbounded_scores_and_non_utc_timestamps(self):
        with self.assertRaises(ValueError):
            TriageResult("t", "e", TriageBucket.JUNK, "reason", False, (), None, 1.1, None, UTC_TIME)
        with self.assertRaises(ValueError):
            Opportunity("o", "key", "url", "org", "title", "source", UTC_TIME,
                        11, None, Eligibility.UNVERIFIED, None, None)
        with self.assertRaises(ValueError):
            IngestionMetadata(UTC_TIME.replace(tzinfo=None), "run", "source")
        with self.assertRaises(ValueError):
            IngestionMetadata(UTC_TIME.astimezone(timezone(timedelta(hours=-7))), "run", "source")

    def test_application_current_status_agrees_with_history(self):
        change = ApplicationStatusChange("change", ApplicationStatus.APPLIED, UTC_TIME, "gmail:1", "Confirmation")
        with self.assertRaises(ValueError):
            Application("app", "opp", ApplicationStatus.INTERVIEW, (change,),
                        ("gmail:1",), UTC_TIME, UTC_TIME)


if __name__ == "__main__":
    unittest.main()
