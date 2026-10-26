import json
import unittest
from pathlib import Path

from keeper_core import (
    Application, ApplicationStatus, ApplicationStatusChange, CorrectionRecord,
    DeadlineEvent, DraftRecord, EmailRecord, Eligibility, IngestionMetadata,
    ManualOverride, ModelMetadata, NotificationRecord, Opportunity, SecurityEvent,
    TriageBucket, TriageResult,
)
from keeper_core.time import from_storage
from keeper_core.workflow import opportunity_key, stable_key


EXAMPLE = Path(__file__).resolve().parents[1] / "docs" / "examples" / "keeper_records.json"


class PublishedExampleTest(unittest.TestCase):
    def test_json_example_matches_all_record_fields_and_relationships(self):
        data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        email_data = data["email"]
        email = EmailRecord(**{
            **email_data,
            "received_at": from_storage(email_data["received_at"]),
            "labels": tuple(email_data["labels"]),
            "ingestion": IngestionMetadata(
                **{**email_data["ingestion"],
                   "ingested_at": from_storage(email_data["ingestion"]["ingested_at"])}
            ),
        })
        triage_data = data["triage"]
        triage = TriageResult(**{
            **triage_data,
            "bucket": TriageBucket(triage_data["bucket"]),
            "scam_signals": tuple(triage_data["scam_signals"]),
            "extracted_deadline": from_storage(triage_data["extracted_deadline"]),
            "classified_at": from_storage(triage_data["classified_at"]),
            "model": ModelMetadata(**triage_data["model"]),
        })
        opportunity_data = data["opportunity"]
        opportunity = Opportunity(**{
            **opportunity_data,
            "discovered_at": from_storage(opportunity_data["discovered_at"]),
            "deadline": from_storage(opportunity_data["deadline"]),
            "eligibility": Eligibility(opportunity_data["eligibility"]),
        })
        application_data = data["application"]
        history = tuple(ApplicationStatusChange(**{
            **entry, "status": ApplicationStatus(entry["status"]),
            "changed_at": from_storage(entry["changed_at"]),
        }) for entry in application_data["status_history"])
        application = Application(**{
            **application_data,
            "status": ApplicationStatus(application_data["status"]),
            "status_history": history,
            "source_email_ids": tuple(application_data["source_email_ids"]),
            "created_at": from_storage(application_data["created_at"]),
            "updated_at": from_storage(application_data["updated_at"]),
            "manual_override": None if application_data["manual_override"] is None
            else ManualOverride(**application_data["manual_override"]),
        })
        deadline_data = data["deadline_event"]
        deadline = DeadlineEvent(**{
            **deadline_data,
            **{key: from_storage(deadline_data[key]) for key in ("deadline_at", "created_at", "updated_at")},
        })
        draft_data = data["draft"]
        draft = DraftRecord(**{
            **draft_data,
            **{key: from_storage(draft_data[key]) for key in ("created_at", "updated_at")},
        })
        notification_data = data["notification"]
        notification = NotificationRecord(**{
            **notification_data,
            **{key: from_storage(notification_data[key]) for key in ("created_at", "delivered_at")},
        })
        security_data = data["security_event"]
        security = SecurityEvent(**{**security_data, "occurred_at": from_storage(security_data["occurred_at"])})
        correction_data = data["correction"]
        correction = CorrectionRecord(**{
            **correction_data,
            **{key: from_storage(correction_data[key]) for key in ("created_at", "approved_at")},
        })

        self.assertEqual(triage.email_id, email.id)
        self.assertEqual(application.opportunity_id, opportunity.id)
        self.assertEqual(opportunity.dedupe_key, opportunity_key(opportunity.canonical_url,
                                                                  opportunity.organization, opportunity.title))
        self.assertEqual(history[0].id, stable_key("application-change", application.id,
                                                    "email:gmail:demo-001"))
        self.assertEqual(deadline.application_id, application.id)
        self.assertEqual(draft.email_id, email.id)
        self.assertEqual(notification.status, "pending")
        self.assertEqual(security.source_email_id, email.id)
        self.assertEqual(correction.target_id, triage.id)


if __name__ == "__main__":
    unittest.main()
