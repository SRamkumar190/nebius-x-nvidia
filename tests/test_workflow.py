import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from keeper_core import (
    Application, ApplicationStatus, CorrectionRecord, EmailRecord, Eligibility,
    IngestionMetadata, Opportunity, TriageBucket,
)
from keeper_core.db import migrate
from keeper_core.ingest import IdentityConflict, insert_email_once, insert_opportunity_once
from keeper_core.workflow import (
    TransitionConflict, advance_application, canonical_url, opportunity_key,
    resolve_triage_bucket, stable_key,
)


WHEN = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.app = Application("app:1", "opp:1", ApplicationStatus.FOUND, (), (), WHEN, WHEN)

    def test_forward_transitions_replay_and_terminal_decision(self):
        applied = advance_application(self.app, ApplicationStatus.APPLIED,
                                      changed_at=WHEN + timedelta(hours=1), reason="Confirmed",
                                      source_email_id="gmail:confirmation")
        self.assertIs(advance_application(applied, ApplicationStatus.APPLIED,
                                          changed_at=WHEN + timedelta(hours=1), reason="Confirmed",
                                          source_email_id="gmail:confirmation"), applied)
        interview = advance_application(applied, ApplicationStatus.INTERVIEW,
                                        changed_at=WHEN + timedelta(hours=2), reason="Invite",
                                        source_email_id="gmail:invite")
        decision = advance_application(interview, ApplicationStatus.DECISION,
                                       changed_at=WHEN + timedelta(hours=3), reason="Rejection",
                                       source_email_id="gmail:decision", decision_outcome="rejected")
        self.assertEqual([entry.status for entry in decision.status_history],
                         [ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW, ApplicationStatus.DECISION])
        with self.assertRaises(TransitionConflict):
            advance_application(decision, ApplicationStatus.APPLIED,
                                changed_at=WHEN + timedelta(hours=4), reason="Late confirmation",
                                source_email_id="gmail:late")
        with self.assertRaises(TransitionConflict):
            advance_application(decision, ApplicationStatus.DECISION,
                                changed_at=WHEN + timedelta(hours=4), reason="Contradictory offer",
                                source_email_id="gmail:offer", decision_outcome="offered")

    def test_stale_and_manual_precedence(self):
        applied = advance_application(self.app, ApplicationStatus.APPLIED,
                                      changed_at=WHEN + timedelta(hours=2), reason="Confirmed",
                                      source_email_id="gmail:confirmation")
        self.assertIs(advance_application(applied, ApplicationStatus.INTERVIEW,
                                          changed_at=WHEN + timedelta(hours=1), reason="Old invite",
                                          source_email_id="gmail:old"), applied)
        correction = CorrectionRecord("correction:1", "application", applied.id,
                                      "Corrected status", WHEN + timedelta(hours=2),
                                      "approved", approved_at=WHEN + timedelta(hours=3),
                                      actor_reference="user:1")
        corrected = advance_application(applied, ApplicationStatus.FOUND,
                                        changed_at=WHEN + timedelta(hours=3), reason="User correction",
                                        correction=correction)
        self.assertEqual(corrected.status, ApplicationStatus.FOUND)
        self.assertIs(advance_application(corrected, ApplicationStatus.INTERVIEW,
                                          changed_at=WHEN + timedelta(hours=4), reason="New invite",
                                          source_email_id="gmail:new"), corrected)
        self.assertIs(advance_application(corrected, ApplicationStatus.FOUND,
                                          changed_at=WHEN + timedelta(hours=3), reason="User correction",
                                          correction=correction), corrected)
        with self.assertRaises(TransitionConflict):
            advance_application(corrected, ApplicationStatus.DECISION,
                                changed_at=WHEN + timedelta(hours=5), reason="Different correction",
                                correction=replace(correction, approved_at=WHEN + timedelta(hours=5)),
                                decision_outcome="rejected")
        with self.assertRaises(ValueError):
            advance_application(applied, ApplicationStatus.FOUND,
                                changed_at=WHEN + timedelta(hours=3), reason="Unapproved",
                                correction=replace(correction, approval_status="proposed"))

    def test_career_guard_and_identity_keys(self):
        self.assertEqual(resolve_triage_bucket(TriageBucket.JUNK, True), TriageBucket.ACTIONABLE)
        self.assertIsNone(resolve_triage_bucket(TriageBucket.JUNK, None))
        self.assertEqual(resolve_triage_bucket(TriageBucket.JUNK, False), TriageBucket.JUNK)
        self.assertEqual(canonical_url("HTTPS://CAREERS.EXAMPLE.TEST/apply/?utm_source=x&job=1#details"),
                         "https://careers.example.test/apply?job=1")
        self.assertEqual(opportunity_key("https://careers.example.test/apply?utm_source=x", " Example ", " Intern "),
                         opportunity_key("https://careers.example.test/apply", "example", "intern"))
        self.assertNotEqual(stable_key("test", "a", "bc"), stable_key("test", "ab", "c"))


class DuplicateProcessingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "keeper.db"
        migrate(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.email = EmailRecord("gmail:1", "gmail", "1", "thread:1", "sender@example.test",
                                 "Subject", WHEN, "Body", ("INBOX",), "gmail:1",
                                 IngestionMetadata(WHEN, "run:1", "fixture"))
        url = canonical_url("https://careers.example.test/apply?utm_source=a")
        self.opp = Opportunity("opp:1", opportunity_key(url, "Example", "Intern"), url,
                               "Example", "Intern", "fixture", WHEN, 8, "Matches",
                               Eligibility.UNVERIFIED, None, None)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_repeat_email_and_posting_preserve_identity(self):
        self.assertEqual(insert_email_once(self.conn, self.email), "gmail:1")
        replay = replace(self.email, ingestion=IngestionMetadata(WHEN, "run:2", "fixture"))
        self.assertEqual(insert_email_once(self.conn, replay), "gmail:1")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM email_records").fetchone()[0], 1)
        with self.assertRaises(IdentityConflict):
            insert_email_once(self.conn, replace(self.email, id="gmail:wrong"))
        self.assertEqual(insert_opportunity_once(self.conn, self.opp), "opp:1")
        self.assertEqual(insert_opportunity_once(self.conn, replace(self.opp, id="opp:duplicate")), "opp:1")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM opportunities").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
